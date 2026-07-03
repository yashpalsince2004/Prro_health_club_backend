"""
FastAPI route handlers for Member management.
"""

import math
from typing import Optional
from uuid import UUID
from datetime import datetime, date, timezone
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
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
    MemberListResponse
)

router = APIRouter()


def _get_active_membership_summary(member: Member) -> Optional[ActiveMembershipSummary]:
    """Helper to find the active membership for a member and calculate remaining days."""
    today = date.today()
    for m in member.memberships:
        if m.status == SubscriptionStatus.ACTIVE and m.start_date <= today <= m.end_date:
            days_remaining = (m.end_date - today).days
            return ActiveMembershipSummary(
                id=m.id,
                plan_name=m.plan.name,
                start_date=m.start_date,
                end_date=m.end_date,
                status=m.status,
                days_remaining=max(0, days_remaining)
            )
    return None


def _map_member_to_response(member: Member) -> MemberResponse:
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
        biometric_device_id=profile_db.biometric_device_id
    )

    return MemberResponse(
        id=member.id,
        joining_date=member.joining_date,
        notes=member.notes,
        profile=profile_res,
        active_membership=_get_active_membership_summary(member)
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Create a User, Profile, and Member profile in a single transaction."""
    logger.info(f"[create_member] user={current_user.user_id} action=create email={payload.email}")

    # Check if email is already taken
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise ConflictException(message=f"Email '{payload.email}' is already registered")

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

        # Create profile
        new_profile = Profile(
            user_id=new_user.id,
            full_name=payload.full_name,
            phone=payload.phone,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            address=payload.address,
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_phone=payload.emergency_contact_phone
        )
        db.add(new_profile)
        db.flush()  # Generate profile ID

        # Create member
        new_member = Member(
            profile_id=new_profile.id,
            joining_date=payload.joining_date,
            notes=payload.notes
        )
        db.add(new_member)
        db.commit()

        # Eager load relationships for response
        member_with_relations = db.query(Member).options(
            joinedload(Member.profile),
            joinedload(Member.memberships).joinedload(Membership.plan)
        ).filter(Member.id == new_member.id).first()

        res_data = _map_member_to_response(member_with_relations)
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
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """List paginated gym members with search and status filters."""
    logger.info(f"[list_members] user={current_user.user_id} page={page} per_page={per_page}")

    query = db.query(Member).join(Member.profile).join(Profile.user).filter(
        Member.is_deleted == False,
        User.is_deleted == False
    )

    # 1. Apply search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Profile.full_name.ilike(search_filter)) |
            (User.email.ilike(search_filter)) |
            (Profile.phone.ilike(search_filter))
        )

    # 2. Apply status filter
    today = date.today()
    if status == "active":
        # Has at least one membership that is active and not expired
        query = query.filter(
            Member.memberships.any(
                (Membership.status == SubscriptionStatus.ACTIVE) &
                (Membership.start_date <= today) &
                (Membership.end_date >= today)
            )
        )
    elif status == "expired":
        # Has no active memberships (either none or all expired)
        query = query.filter(
            ~Member.memberships.any(
                (Membership.status == SubscriptionStatus.ACTIVE) &
                (Membership.start_date <= today) &
                (Membership.end_date >= today)
            )
        )

    # 3. Get paginated results
    total = query.count()
    members = query.options(
        joinedload(Member.profile),
        joinedload(Member.memberships).joinedload(Membership.plan)
    ).order_index = None  # Clear any default ordering
    
    members = query.offset((page - 1) * per_page).limit(per_page).all()

    mapped_members = [_map_member_to_response(m).model_dump() for m in members]
    return paginated_response(
        message="Members list retrieved successfully",
        data=mapped_members,
        page=page,
        limit=per_page,
        total=total
    )


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

    res_data = _map_member_to_response(member)
    return success_response(message="Member details retrieved", data=res_data.model_dump())


@router.patch("/{member_id}", response_model=None)
def update_member(
    member_id: UUID,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
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
        for field, value in payload.model_dump(exclude={"notes", "is_active"}, exclude_unset=True).items():
            setattr(profile, field, value)

        # Update member notes if provided
        if payload.notes is not None:
            member.notes = payload.notes

        db.commit()

        # Reload for response
        db.refresh(member)
        res_data = _map_member_to_response(member)
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
