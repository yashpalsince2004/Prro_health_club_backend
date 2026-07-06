"""
FastAPI route handlers for Member management.
"""

import math
from typing import Optional
from uuid import UUID
from datetime import datetime, date, timezone
# pyrefly: ignore [missing-import]
from loguru import logger
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session, joinedload
from app.database.session import get_db
from app.core.exceptions import ConflictException, NotFoundException, AuthorizationException
from app.core.constants import UserRole, SubscriptionStatus
from app.core.security import get_password_hash
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.user import User
from app.models.profile import Profile
from app.models.member import Member
from app.models.membership import Membership
from app.api.v1.members.schemas import (
    MemberCreate,
    MemberUpdate,
    MemberResponse,
    ProfileResponse,
    ActiveMembershipSummary,
    MemberListResponse,
    TrainerSummary,
    BulkArchiveRequest,
    BulkRestoreRequest,
    BulkAssignTrainerRequest,
    BulkChangePlanRequest,
    BulkActivateRequest,
    BulkDeactivateRequest
)
from app.models.attendance import AttendanceLog
from app.models.trainer import Trainer
from app.models.association import trainer_members

router = APIRouter()


def get_today_date() -> date:
    """Helper to get current local date in the gym's configured timezone."""
    try:
        from app.core.config import settings
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(settings.TIMEZONE)
        return datetime.now(tz).date()
    except Exception:
        return date.today()


def _get_active_membership_summary(member: Member) -> Optional[ActiveMembershipSummary]:
    """Helper to find the active or upcoming membership for a member and calculate remaining days."""
    today = get_today_date()
    # 1. Look for currently running active membership
    for m in member.memberships:
        if m.status == SubscriptionStatus.ACTIVE and m.start_date <= today <= m.end_date:
            days_remaining = (m.end_date - today).days
            return ActiveMembershipSummary(
                id=m.id,
                plan_name=m.plan.name,
                start_date=m.start_date,
                end_date=m.end_date,
                status=m.status,
                days_remaining=max(0, days_remaining),
                auto_renew=m.auto_renew
            )
    # 2. Fallback to upcoming active membership
    for m in member.memberships:
        if m.status == SubscriptionStatus.ACTIVE and today < m.start_date:
            days_remaining = (m.end_date - m.start_date).days
            return ActiveMembershipSummary(
                id=m.id,
                plan_name=m.plan.name,
                start_date=m.start_date,
                end_date=m.end_date,
                status=m.status,
                days_remaining=max(0, days_remaining),
                auto_renew=m.auto_renew
            )
    return None


def _map_member_to_response(member: Member, db: Session) -> MemberResponse:
    """Helper to map a Member db model to MemberResponse schema."""
    profile_db = member.profile
    profile_res = ProfileResponse(
        id=profile_db.id,
        full_name=profile_db.full_name,
        phone=profile_db.phone,
        avatar_url=profile_db.avatar_url,
        date_of_birth=profile_db.date_of_birth,
        gender=profile_db.gender,
        address=profile_db.address,
        emergency_contact_name=profile_db.emergency_contact_name,
        emergency_contact_phone=profile_db.emergency_contact_phone,
        biometric_device_id=profile_db.biometric_device_id,
        email=profile_db.user.email if profile_db.user else None,
        occupation=profile_db.occupation,
        height=profile_db.height,
        weight=profile_db.weight,
        medical_notes=profile_db.medical_notes,
        emergency_relation=profile_db.emergency_relation
    )

    # Fetch last visit
    last_visit_log = db.query(AttendanceLog).filter(
        AttendanceLog.member_id == member.id
    ).order_by(AttendanceLog.check_in.desc()).first()
    last_visit = last_visit_log.check_in.date() if last_visit_log else None

    # Fetch active trainer assignment
    active_trainer = db.query(Trainer).join(trainer_members).filter(
        trainer_members.c.member_id == member.id,
        trainer_members.c.is_active == True
    ).first()

    trainer_summary = None
    if active_trainer:
        trainer_summary = TrainerSummary(
            id=active_trainer.id,
            full_name=active_trainer.profile.full_name,
            specialization=active_trainer.specialization
        )

    return MemberResponse(
        id=member.id,
        joining_date=member.joining_date,
        notes=member.notes,
        profile=profile_res,
        active_membership=_get_active_membership_summary(member),
        is_active=profile_db.user.is_active if profile_db.user else True,
        last_visit=last_visit,
        assigned_trainer=trainer_summary
    )


# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query, status, BackgroundTasks

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_member(
    payload: MemberCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Create a User, Profile, and Member profile in a single transaction."""
    # ===== TEMPORARY INSTRUMENTATION START =====
    logger.info(f"[TRACE-1] payload.model_dump() = {payload.model_dump()}")
    logger.info(f"[TRACE-2] payload.plan_id repr={repr(payload.plan_id)} type={type(payload.plan_id).__name__}")
    logger.info(f"[TRACE-3] payload.trainer_id repr={repr(payload.trainer_id)} type={type(payload.trainer_id).__name__}")
    logger.info(f"[create_member] user={current_user.user_id} action=create email={payload.email}")

    # Check if email is already taken
    email_exists = db.query(User).filter(User.email == payload.email.lower()).first() is not None

    # Check if phone is already taken
    phone_exists = False
    if payload.phone:
        phone_exists = db.query(Profile).filter(Profile.phone == payload.phone).first() is not None

    if email_exists and phone_exists:
        raise ConflictException(message="An account with this email and phone number already exists.")
    elif email_exists:
        raise ConflictException(message="Email already registered.")
    elif phone_exists:
        raise ConflictException(message="Phone number already registered.")

    try:
        # Create user
        new_user = User(
            email=payload.email.lower(),
            hashed_password=get_password_hash(payload.password),
            role=UserRole.MEMBER,
            is_active=True
        )
        db.add(new_user)
        db.flush()  # Generate user ID
        logger.info(f"[TRACE-4] new_user.id={new_user.id}")

        # Create profile
        new_profile = Profile(
            user_id=new_user.id,
            full_name=payload.full_name,
            phone=payload.phone,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            address=payload.address,
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_phone=payload.emergency_contact_phone,
            emergency_relation=payload.emergency_relation,
            medical_notes=payload.medical_notes,
            occupation=payload.occupation,
            height=payload.height,
            weight=payload.weight
        )
        db.add(new_profile)
        db.flush()  # Generate profile ID
        logger.info(f"[TRACE-5] new_profile.id={new_profile.id}")

        # Create member
        new_member = Member(
            profile_id=new_profile.id,
            joining_date=payload.joining_date,
            notes=payload.notes
        )
        db.add(new_member)
        db.flush()
        logger.info(f"[TRACE-6] new_member.id={new_member.id}")

        # Handle Membership Assignment
        logger.info(f"[TRACE-7] entering plan branch: truthiness of payload.plan_id = {bool(payload.plan_id)}")
        if payload.plan_id:
            from app.models.plan import MembershipPlan
            from datetime import timedelta
            plan = db.query(MembershipPlan).filter(MembershipPlan.id == payload.plan_id, MembershipPlan.is_active == True).first()
            logger.info(f"[TRACE-8] plan lookup result = {plan!r} (id={payload.plan_id})")
            if plan:
                new_sub = Membership(
                    member_id=new_member.id,
                    plan_id=payload.plan_id,
                    start_date=payload.joining_date,
                    end_date=payload.joining_date + timedelta(days=plan.duration_days),
                    status=SubscriptionStatus.ACTIVE
                )
                logger.info(f"[TRACE-9] new_sub Membership object CREATED: id={new_sub.id} member_id={new_sub.member_id} plan_id={new_sub.plan_id} start={new_sub.start_date} end={new_sub.end_date} status={new_sub.status}")
                db.add(new_sub)
                logger.info(f"[TRACE-10] session.add(new_sub) EXECUTED; session.new contains membership? {new_sub in db.new}")
            else:
                logger.info(f"[TRACE-9] NO plan resolved — skipping Membership creation")
        else:
            logger.info(f"[TRACE-8] payload.plan_id falsy — skipping plan branch entirely")

        # Handle Trainer Assignment
        logger.info(f"[TRACE-11] entering trainer branch: truthiness of payload.trainer_id = {bool(payload.trainer_id)}")
        if payload.trainer_id:
            trainer = db.query(Trainer).filter(Trainer.id == payload.trainer_id, Trainer.is_deleted == False).first()
            logger.info(f"[TRACE-12] trainer lookup result = {trainer!r} (id={payload.trainer_id})")
            if trainer:
                db.execute(
                    trainer_members.insert().values(
                        trainer_id=payload.trainer_id,
                        member_id=new_member.id,
                        is_active=True
                    )
                )
                logger.info(f"[TRACE-13] trainer_members row INSERTED trainer_id={payload.trainer_id} member_id={new_member.id}")
            else:
                logger.info(f"[TRACE-13] NO trainer resolved — skipping trainer_members insert")
        else:
            logger.info(f"[TRACE-12] payload.trainer_id falsy — skipping trainer branch entirely")

        # Membership row existence check immediately before commit
        pre_commit_membership = db.query(Membership).filter(Membership.member_id == new_member.id).all()
        logger.info(f"[TRACE-14] BEFORE COMMIT — Membership rows for member_id={new_member.id}: count={len(pre_commit_membership)} rows={[(m.id, m.plan_id, m.status) for m in pre_commit_membership]}")

        db.commit()
        logger.info(f"[TRACE-15] db.commit() RETURNED OK")

        # Welcome email side-effect
        try:
            from app.services import email_service
            background_tasks.add_task(
                email_service.send_welcome_email,
                new_user.email,
                new_profile.full_name
            )
        except Exception as email_err:
            logger.error(f"Welcome email failed (non-critical): {str(email_err)}")

        # Eager load relationships for response
        member_with_relations = db.query(Member).options(
            joinedload(Member.profile),
            joinedload(Member.memberships).joinedload(Membership.plan)
        ).filter(Member.id == new_member.id).first()
        logger.info(f"[TRACE-16] member_with_relations.id={member_with_relations.id if member_with_relations else None}")
        logger.info(f"[TRACE-17] member_with_relations.memberships count={len(member_with_relations.memberships) if member_with_relations else 'N/A'}")
        if member_with_relations:
            for m in member_with_relations.memberships:
                logger.info(f"[TRACE-18]   membership: id={m.id} plan_id={m.plan_id} status={m.status} start={m.start_date} end={m.end_date} plan_name={m.plan.name if m.plan else None}")

        res_data = _map_member_to_response(member_with_relations, db)
        logger.info(f"[TRACE-19] _map_member_to_response active_membership = {res_data.active_membership!r}")
        if res_data.active_membership is None:
            # Diagnose WHY active_membership is None
            today = get_today_date()
            logger.info(f"[TRACE-20] active_membership=None diagnosis: today={today}, total_memberships_on_member={len(member_with_relations.memberships)}")
            for m in member_with_relations.memberships:
                in_window = m.start_date <= today <= m.end_date
                status_match = m.status == SubscriptionStatus.ACTIVE
                logger.info(f"[TRACE-21]   membership id={m.id}: status==ACTIVE? {status_match} (actual={m.status}); in_date_window? {in_window} (start={m.start_date} end={m.end_date})")
        return success_response(message="Member created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_member] error during database insertion: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_members(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query("all", description="Filter by active, expired, or all"),
    gender: Optional[str] = Query(None),
    plan_id: Optional[UUID] = Query(None),
    trainer_id: Optional[UUID] = Query(None),
    join_from: Optional[date] = Query(None),
    join_to: Optional[date] = Query(None),
    is_active: Optional[bool] = Query(None),
    show_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST, UserRole.TRAINER]))
):
    """List paginated gym members with search and status filters (Admins, Receptionists, and Trainers)."""
    logger.info(f"[list_members] user={current_user.user_id} page={page} per_page={per_page} show_archived={show_archived}")

    # Eagerly filter by role: trainers can only read their assigned members
    query = db.query(Member).join(Member.profile).join(Profile.user)

    if current_user.role == UserRole.TRAINER:
        query = query.filter(
            Member.trainers.any(Trainer.id == current_user.trainer_id)
        )

    # Apply soft-delete archive visibility
    if show_archived:
        query = query.filter(Member.is_deleted == True)
    else:
        query = query.filter(Member.is_deleted == False, User.is_deleted == False)

    # 1. Apply search filter (Full Name, Email, Phone, or Member ID)
    if search:
        search_filter = f"%{search}%"
        # pyrefly: ignore [missing-import]
        from sqlalchemy import cast, String
        query = query.filter(
            (Profile.full_name.ilike(search_filter)) |
            (User.email.ilike(search_filter)) |
            (Profile.phone.ilike(search_filter)) |
            (cast(Member.id, String).ilike(search_filter))
        )

    # 2. Apply membership status filter
    today = get_today_date()
    if status == "active":
        query = query.filter(
            Member.memberships.any(
                (Membership.status == SubscriptionStatus.ACTIVE) &
                (Membership.start_date <= today) &
                (Membership.end_date >= today)
            )
        )
    elif status == "expired":
        query = query.filter(
            ~Member.memberships.any(
                (Membership.status == SubscriptionStatus.ACTIVE) &
                (Membership.start_date <= today) &
                (Membership.end_date >= today)
            )
        )

    # 3. Apply gender filter
    if gender:
        query = query.filter(Profile.gender == gender)

    # 4. Apply plan filter
    if plan_id:
        query = query.filter(
            Member.memberships.any(Membership.plan_id == plan_id)
        )

    # 5. Apply trainer filter
    if trainer_id:
        query = query.filter(
            Member.trainers.any(Trainer.id == trainer_id)
        )

    # 6. Apply joining date range
    if join_from:
        query = query.filter(Member.joining_date >= join_from)
    if join_to:
        query = query.filter(Member.joining_date <= join_to)

    # 7. Apply user active status
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    # Get paginated results
    total = query.count()
    
    # Order by joining date descending
    query = query.order_by(Member.joining_date.desc())
    
    members = query.offset((page - 1) * per_page).limit(per_page).all()
    mapped_members = [_map_member_to_response(m, db).model_dump() for m in members]

    return paginated_response(
        message="Members list retrieved successfully",
        data=mapped_members,
        page=page,
        limit=per_page,
        total=total
    )


@router.get("/stats", response_model=None)
def get_member_stats(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST, UserRole.TRAINER]))
):
    """Retrieve aggregate member KPIs for management dashboard."""
    logger.info(f"[get_member_stats] user={current_user.user_id}")

    total = db.query(Member).filter(Member.is_deleted == False).count()
    
    today = get_today_date()
    active = db.query(Member).filter(
        Member.is_deleted == False,
        Member.memberships.any(
            (Membership.status == SubscriptionStatus.ACTIVE) &
            (Membership.start_date <= today) &
            (Membership.end_date >= today)
        )
    ).count()

    inactive = db.query(Member).join(Member.profile).join(Profile.user).filter(
        Member.is_deleted == False,
        User.is_deleted == False,
        User.is_active == False
    ).count()

    expired = db.query(Member).filter(
        Member.is_deleted == False,
        ~Member.memberships.any(
            (Membership.status == SubscriptionStatus.ACTIVE) &
            (Membership.start_date <= today) &
            (Membership.end_date >= today)
        )
    ).count()

    return success_response(message="Member KPI stats retrieved", data={
        "total_members": total,
        "active_members": active,
        "inactive_members": inactive,
        "expired_memberships": expired
    })


@router.get("/{member_id}", response_model=None)
def get_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single member."""
    logger.info(f"[get_member] user={current_user.user_id} action=get_member target={member_id}")

    member = db.query(Member).options(
        joinedload(Member.profile).joinedload(Profile.user),
        joinedload(Member.memberships).joinedload(Membership.plan)
    ).filter(
        Member.id == member_id,
        Member.is_deleted == False
    ).first()

    if not member:
        raise NotFoundException(message=f"Member not found")

    # Ownership checks: Member roles can only read their own profile
    if current_user.role == UserRole.MEMBER:
        if member.profile.user_id != current_user.user_id:
            raise AuthorizationException(message="You are not authorized to view this profile")

    res_data = _map_member_to_response(member, db)
    return success_response(message="Member details retrieved", data=res_data.model_dump())


@router.patch("/{member_id}", response_model=None)
def update_member(
    member_id: UUID,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Update profile and notes for a member."""
    logger.info(f"[update_member] user={current_user.user_id} action=update target={member_id}")

    member = db.query(Member).join(Member.profile).filter(
        Member.id == member_id,
        Member.is_deleted == False
    ).first()

    if not member:
        raise NotFoundException(message=f"Member not found")

    profile = member.profile
    user = db.query(User).filter(User.id == profile.user_id).first()

    # Enforce role ownership and restricted fields
    if current_user.role not in [UserRole.ADMIN, UserRole.RECEPTIONIST]:
        if current_user.user_id != profile.user_id:
            raise AuthorizationException(message="You do not have permission to update this member's details")
        if payload.is_active is not None or payload.notes is not None or payload.biometric_device_id is not None or payload.email is not None:
            raise AuthorizationException(message="Members cannot modify active status, administrative notes, biometric IDs, or email")

    # Verify email/phone uniqueness if updated
    email_exists = False
    if payload.email is not None and user:
        email_exists = db.query(User).filter(User.email == payload.email.lower(), User.id != user.id).first() is not None

    phone_exists = False
    if payload.phone is not None:
        phone_exists = db.query(Profile).filter(Profile.phone == payload.phone, Profile.id != profile.id).first() is not None

    if email_exists and phone_exists:
        raise ConflictException(message="An account with this email and phone number already exists.")
    elif email_exists:
        raise ConflictException(message="Email already registered.")
    elif phone_exists:
        raise ConflictException(message="Phone number already registered.")

    if payload.email is not None and user:
        user.email = payload.email.lower()

    # Verify biometric device PIN uniqueness
    if payload.biometric_device_id is not None:
        existing_pin = db.query(Profile).filter(
            Profile.biometric_device_id == payload.biometric_device_id,
            Profile.id != profile.id
        ).first()
        if existing_pin:
            raise ConflictException(message=f"Biometric ID '{payload.biometric_device_id}' is already assigned to another user")

    try:
        # Update user active status if requested
        if payload.is_active is not None and user:
            user.is_active = payload.is_active

        # Update profile details
        for field, value in payload.model_dump(exclude={"notes", "is_active", "plan_id", "trainer_id", "email"}, exclude_unset=True).items():
            setattr(profile, field, value)

        # Update member notes if provided
        if payload.notes is not None:
            member.notes = payload.notes

        # Handle Plan update
        if payload.plan_id is not None:
            from app.models.plan import MembershipPlan
            from datetime import timedelta
            plan = db.query(MembershipPlan).filter(MembershipPlan.id == payload.plan_id, MembershipPlan.is_active == True).first()
            if plan:
                # Expire previous subscriptions
                db.query(Membership).filter(
                    Membership.member_id == member.id,
                    Membership.status == SubscriptionStatus.ACTIVE
                ).update({Membership.status: SubscriptionStatus.EXPIRED})
                
                # Assign new active membership
                today = get_today_date()
                new_sub = Membership(
                    member_id=member.id,
                    plan_id=payload.plan_id,
                    start_date=today,
                    end_date=today + timedelta(days=plan.duration_days),
                    status=SubscriptionStatus.ACTIVE
                )
                db.add(new_sub)

        # Handle Trainer update
        if payload.trainer_id is not None:
            # Deactivate previous trainer assignments
            db.execute(
                trainer_members.update()
                .where(trainer_members.c.member_id == member.id)
                .values(is_active=False)
            )
            # Check if this assignment exists
            existing_link = db.execute(
                trainer_members.select()
                .where(trainer_members.c.member_id == member.id, trainer_members.c.trainer_id == payload.trainer_id)
            ).first()

            if existing_link:
                db.execute(
                    trainer_members.update()
                    .where(trainer_members.c.member_id == member.id, trainer_members.c.trainer_id == payload.trainer_id)
                    .values(is_active=True, assigned_at=datetime.now(timezone.utc))
                )
            else:
                db.execute(
                    trainer_members.insert().values(
                        trainer_id=payload.trainer_id,
                        member_id=member.id,
                        is_active=True
                    )
                )

        db.commit()

        # Reload for response
        db.refresh(member)
        res_data = _map_member_to_response(member, db)
        return success_response(message="Member updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_member] error during database modification: {str(e)}")
        raise e


@router.delete("/{member_id}", response_model=None)
def delete_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Deactivate (soft delete) a member account."""
    logger.info(f"[delete_member] user={current_user.user_id} action=delete target={member_id}")

    member = db.query(Member).join(Member.profile).filter(
        Member.id == member_id,
        Member.is_deleted == False
    ).first()

    if not member:
        raise NotFoundException(message=f"Member not found")

    profile = member.profile
    user = db.query(User).filter(User.id == profile.user_id).first()

    try:
        # Mark member as soft deleted
        member.soft_delete(updater_id=current_user.user_id)

        # Mark user credentials as deactivated/deleted
        if user:
            user.soft_delete(updater_id=current_user.user_id)
            user.is_active = False

        db.commit()
        return success_response(message="Member deactivated successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_member] error during soft deletion: {str(e)}")
        raise e


@router.post("/{member_id}/restore", response_model=None)
def restore_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Restore an archived (soft deleted) member account."""
    logger.info(f"[restore_member] user={current_user.user_id} action=restore target={member_id}")

    member = db.query(Member).join(Member.profile).filter(
        Member.id == member_id,
        Member.is_deleted == True
    ).first()

    if not member:
        raise NotFoundException(message="Archived member not found")

    profile = member.profile
    user = db.query(User).filter(User.id == profile.user_id).first()

    try:
        member.is_deleted = False
        member.deleted_at = None
        member.deleted_by = None

        if user:
            user.is_deleted = False
            user.deleted_at = None
            user.deleted_by = None
            user.is_active = True

        db.commit()
        return success_response(message="Member restored successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[restore_member] error during restoration: {str(e)}")
        raise e


@router.post("/bulk-archive", response_model=None)
def bulk_archive_members(
    payload: BulkArchiveRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Bulk soft delete multiple member accounts."""
    logger.info(f"[bulk_archive_members] user={current_user.user_id} count={len(payload.ids)}")

    try:
        for member_id in payload.ids:
            member = db.query(Member).filter(Member.id == member_id, Member.is_deleted == False).first()
            if member:
                member.soft_delete(updater_id=current_user.user_id)
                user = db.query(User).join(Profile).filter(Profile.id == member.profile_id).first()
                if user:
                    user.soft_delete(updater_id=current_user.user_id)
                    user.is_active = False
        db.commit()
        return success_response(message=f"Successfully archived {len(payload.ids)} members")
    except Exception as e:
        db.rollback()
        logger.error(f"[bulk_archive_members] error: {str(e)}")
        raise e


@router.post("/bulk-restore", response_model=None)
def bulk_restore_members(
    payload: BulkRestoreRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk restore multiple archived member accounts."""
    logger.info(f"[bulk_restore_members] user={current_user.user_id} count={len(payload.ids)}")

    try:
        for member_id in payload.ids:
            member = db.query(Member).filter(Member.id == member_id, Member.is_deleted == True).first()
            if member:
                member.is_deleted = False
                member.deleted_at = None
                member.deleted_by = None
                user = db.query(User).join(Profile).filter(Profile.id == member.profile_id).first()
                if user:
                    user.is_deleted = False
                    user.deleted_at = None
                    user.deleted_by = None
                    user.is_active = True
        db.commit()
        return success_response(message=f"Successfully restored {len(payload.ids)} members")
    except Exception as e:
        db.rollback()
        logger.error(f"[bulk_restore_members] error: {str(e)}")
        raise e


@router.post("/bulk-assign-trainer", response_model=None)
def bulk_assign_trainer(
    payload: BulkAssignTrainerRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Bulk assign/re-assign a trainer to multiple members."""
    logger.info(f"[bulk_assign_trainer] user={current_user.user_id} count={len(payload.member_ids)} trainer={payload.trainer_id}")

    # Check trainer exists
    trainer = db.query(Trainer).filter(Trainer.id == payload.trainer_id, Trainer.is_deleted == False).first()
    if not trainer:
        raise NotFoundException(message="Selected trainer not found")

    # Capacity Check
    active_members_count = len([m for m in trainer.assigned_members if not m.is_deleted])
    max_cap = trainer.max_members or 15
    new_assignments_count = len(payload.member_ids)
    
    # Calculate net new assignments by checking who is already active under this trainer
    already_assigned = db.query(trainer_members.c.member_id).filter(
        trainer_members.c.trainer_id == payload.trainer_id,
        trainer_members.c.member_id.in_(payload.member_ids),
        trainer_members.c.is_active == True
    ).all()
    already_assigned_count = len(already_assigned)
    net_new_assignments = new_assignments_count - already_assigned_count
    
    if active_members_count + net_new_assignments > max_cap:
        raise ConflictException(
            message=f"Cannot assign {new_assignments_count} members. Selected trainer has {active_members_count} active members and capacity limit is {max_cap}."
        )

    try:
        for m_id in payload.member_ids:
            # Deactivate current assignments
            db.execute(
                trainer_members.update()
                .where(trainer_members.c.member_id == m_id)
                .values(is_active=False)
            )

            # Insert new active assignment
            existing_link = db.execute(
                trainer_members.select()
                .where(trainer_members.c.member_id == m_id, trainer_members.c.trainer_id == payload.trainer_id)
            ).first()

            if existing_link:
                db.execute(
                    trainer_members.update()
                    .where(trainer_members.c.member_id == m_id, trainer_members.c.trainer_id == payload.trainer_id)
                    .values(is_active=True, assigned_at=datetime.now(timezone.utc))
                )
            else:
                db.execute(
                    trainer_members.insert().values(
                        trainer_id=payload.trainer_id,
                        member_id=m_id,
                        is_active=True
                    )
                )
        db.commit()
        return success_response(message=f"Successfully assigned trainer to {len(payload.member_ids)} members")
    except Exception as e:
        db.rollback()
        logger.error(f"[bulk_assign_trainer] error: {str(e)}")
        raise e


@router.post("/bulk-change-plan", response_model=None)
def bulk_change_plan(
    payload: BulkChangePlanRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Bulk subscribe multiple members to a new membership plan."""
    logger.info(f"[bulk_change_plan] user={current_user.user_id} count={len(payload.member_ids)} plan={payload.plan_id}")

    from app.models.plan import MembershipPlan
    from datetime import timedelta

    plan = db.query(MembershipPlan).filter(MembershipPlan.id == payload.plan_id, MembershipPlan.is_active == True).first()
    if not plan:
        raise NotFoundException(message="Selected pricing plan not found or inactive")

    try:
        today = get_today_date()
        for m_id in payload.member_ids:
            # Expire current active memberships
            db.query(Membership).filter(
                Membership.member_id == m_id,
                Membership.status == SubscriptionStatus.ACTIVE
            ).update({Membership.status: SubscriptionStatus.EXPIRED})

            # Create new active membership
            new_sub = Membership(
                member_id=m_id,
                plan_id=payload.plan_id,
                start_date=today,
                end_date=today + timedelta(days=plan.duration_days),
                status=SubscriptionStatus.ACTIVE
            )
            db.add(new_sub)
        db.commit()
        return success_response(message=f"Successfully switched plans for {len(payload.member_ids)} members")
    except Exception as e:
        db.rollback()
        logger.error(f"[bulk_change_plan] error: {str(e)}")
        raise e


@router.post("/bulk-activate", response_model=None)
def bulk_activate_members(
    payload: BulkActivateRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Bulk activate multiple member credentials."""
    logger.info(f"[bulk_activate_members] user={current_user.user_id} count={len(payload.ids)}")

    try:
        updated = 0
        for m_id in payload.ids:
            member = db.query(Member).filter(Member.id == m_id).first()
            if member:
                user = db.query(User).join(Profile).filter(Profile.id == member.profile_id).first()
                if user and not user.is_active:
                    user.is_active = True
                    updated += 1
        db.commit()
        return success_response(message=f"Successfully activated {updated} member accounts")
    except Exception as e:
        db.rollback()
        logger.error(f"[bulk_activate_members] error: {str(e)}")
        raise e


@router.post("/bulk-deactivate", response_model=None)
def bulk_deactivate_members(
    payload: BulkDeactivateRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Bulk deactivate multiple member credentials."""
    logger.info(f"[bulk_deactivate_members] user={current_user.user_id} count={len(payload.ids)}")

    try:
        updated = 0
        for m_id in payload.ids:
            member = db.query(Member).filter(Member.id == m_id).first()
            if member:
                user = db.query(User).join(Profile).filter(Profile.id == member.profile_id).first()
                if user and user.is_active:
                    user.is_active = False
                    updated += 1
        db.commit()
        return success_response(message=f"Successfully deactivated {updated} member accounts")
    except Exception as e:
        db.rollback()
        logger.error(f"[bulk_deactivate_members] error: {str(e)}")
        raise e
