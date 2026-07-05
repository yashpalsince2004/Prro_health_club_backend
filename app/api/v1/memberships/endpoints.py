"""
FastAPI route handlers for Membership subscriptions.
"""

import math
from typing import Optional
from uuid import UUID
from datetime import date, timedelta
from decimal import Decimal
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session, joinedload
from app.database.session import get_db
from app.core.exceptions import ConflictException, NotFoundException, AuthorizationException
from app.core.constants import UserRole, SubscriptionStatus
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.member import Member
from app.models.plan import MembershipPlan
from app.models.membership import Membership
from app.api.v1.memberships.schemas import (
    MembershipCreate,
    MembershipRenew,
    MembershipResponse,
    PlanSummary,
    MembershipStatusUpdate,
    MembershipListResponse
)

router = APIRouter()


def _map_membership_to_response(m: Membership) -> MembershipResponse:
    """Helper to map a Membership db model to MembershipResponse schema."""
    plan_db = m.plan
    plan_summary = PlanSummary(
        id=plan_db.id,
        name=plan_db.name,
        duration_days=plan_db.duration_days,
        price=Decimal(str(plan_db.price)),
        currency=plan_db.currency
    )

    today = date.today()
    days_remaining = (m.end_date - today).days

    # Compute effective price
    base_price = Decimal(str(plan_db.price))
    discount = (base_price * Decimal(str(m.discount_percent))) / Decimal("100.00")
    effective_price = max(Decimal("0.00"), base_price - discount)

    return MembershipResponse(
        id=m.id,
        member_id=m.member_id,
        plan=plan_summary,
        start_date=m.start_date,
        end_date=m.end_date,
        status=m.status,
        auto_renew=m.auto_renew,
        discount_percent=Decimal(str(m.discount_percent)),
        notes=m.notes,
        is_expired=m.is_expired,
        days_remaining=max(0, days_remaining),
        effective_price=effective_price
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_membership(
    payload: MembershipCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Subscribe a member to a membership plan."""
    logger.info(f"[create_membership] user={current_user.user_id} member={payload.member_id} plan={payload.plan_id}")

    member = db.query(Member).filter(Member.id == payload.member_id, Member.is_deleted == False).first()
    if not member:
        raise NotFoundException(message="Member not found")

    plan = db.query(MembershipPlan).filter(MembershipPlan.id == payload.plan_id, MembershipPlan.is_active == True).first()
    if not plan:
        raise NotFoundException(message="Membership plan not found or inactive")

    # Check for active subscription overlap of the same plan
    today = date.today()
    overlapping = db.query(Membership).filter(
        Membership.member_id == payload.member_id,
        Membership.plan_id == payload.plan_id,
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.end_date >= today
    ).first()

    if overlapping:
        raise ConflictException(message="Member already has an active subscription for this plan")

    try:
        # Calculate expiration date
        end_date = payload.start_date + timedelta(days=plan.duration_days)

        new_membership = Membership(
            member_id=payload.member_id,
            plan_id=payload.plan_id,
            start_date=payload.start_date,
            end_date=end_date,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=payload.auto_renew,
            discount_percent=float(payload.discount_percent),
            notes=payload.notes
        )
        db.add(new_membership)
        db.commit()

        # Reload with relations for mapper
        m_with_relations = db.query(Membership).options(
            joinedload(Membership.plan)
        ).filter(Membership.id == new_membership.id).first()

        res_data = _map_membership_to_response(m_with_relations)
        return success_response(message="Membership created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_membership] error creating subscription: {str(e)}")
        raise e


@router.get("/active/me", response_model=None)
def get_my_active_membership(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve the currently active membership for the logged-in member."""
    from app.models.profile import Profile
    logger.info(f"[get_my_active_membership] user={current_user.user_id}")
    
    if current_user.role != UserRole.MEMBER:
        raise AuthorizationException(message="Only members can access this endpoint")
        
    profile = db.query(Profile).filter(Profile.user_id == current_user.user_id).first()
    if not profile:
        raise NotFoundException(message="Member profile not found")
        
    member = db.query(Member).filter(Member.profile_id == profile.id, Member.is_deleted == False).first()
    if not member:
        raise NotFoundException(message="Member record not found")
        
    today = date.today()
    membership = db.query(Membership).options(
        joinedload(Membership.plan)
    ).filter(
        Membership.member_id == member.id,
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.start_date <= today,
        Membership.end_date >= today,
        Membership.is_deleted == False
    ).order_by(Membership.end_date.desc()).first()
    
    if not membership:
        raise NotFoundException(message="No active membership subscription found")
        
    res_data = _map_membership_to_response(membership)
    return success_response(message="Active membership retrieved", data=res_data.model_dump())


@router.get("/expiring-soon", response_model=None)
def list_expiring_memberships(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve all active subscriptions expiring within the next 7 days (Receptionist alert widget)."""
    logger.info(f"[list_expiring_memberships] user={current_user.user_id}")

    today = date.today()
    next_week = today + timedelta(days=7)

    memberships = db.query(Membership).options(
        joinedload(Membership.plan)
    ).filter(
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.end_date >= today,
        Membership.end_date <= next_week,
        Membership.is_deleted == False
    ).order_by(Membership.end_date.asc()).all()

    mapped_list = [_map_membership_to_response(m).model_dump() for m in memberships]
    return success_response(message="Expiring memberships retrieved", data=mapped_list)


@router.get("/", response_model=None)
def list_memberships(
    member_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query("all"),
    expiring_in_days: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """List memberships with filters and pagination."""
    logger.info(f"[list_memberships] user={current_user.user_id} page={page} per_page={per_page}")

    query = db.query(Membership).options(
        joinedload(Membership.plan)
    ).filter(Membership.is_deleted == False)

    # Filter by member
    if member_id:
        query = query.filter(Membership.member_id == member_id)

    # Filter by status
    if status != "all":
        query = query.filter(Membership.status == status)

    # Filter by expiring days
    if expiring_in_days is not None:
        today = date.today()
        future_limit = today + timedelta(days=expiring_in_days)
        query = query.filter(
            Membership.status == SubscriptionStatus.ACTIVE,
            Membership.end_date >= today,
            Membership.end_date <= future_limit
        )

    total = query.count()
    memberships = query.order_by(Membership.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    mapped_list = [_map_membership_to_response(m).model_dump() for m in memberships]
    return paginated_response(
        message="Memberships list retrieved",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )


@router.get("/{membership_id}", response_model=None)
def get_membership(
    membership_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single membership subscription."""
    logger.info(f"[get_membership] user={current_user.user_id} target={membership_id}")

    membership = db.query(Membership).options(
        joinedload(Membership.plan),
        joinedload(Membership.member).joinedload(Member.profile)
    ).filter(
        Membership.id == membership_id,
        Membership.is_deleted == False
    ).first()

    if not membership:
        raise NotFoundException(message="Membership not found")

    # Ownership check: Member can only view their own membership
    if current_user.role == UserRole.MEMBER:
        if membership.member.profile.user_id != current_user.user_id:
            raise AuthorizationException(message="You are not authorized to view this subscription")

    res_data = _map_membership_to_response(membership)
    return success_response(message="Membership details retrieved", data=res_data.model_dump())


@router.post("/{membership_id}/renew", response_model=None)
def renew_membership(
    membership_id: UUID,
    payload: MembershipRenew,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Renew a membership, transitioning the previous status and spawning a new subscription period."""
    logger.info(f"[renew_membership] user={current_user.user_id} target={membership_id}")

    current_membership = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.is_deleted == False
    ).first()

    if not current_membership:
        raise NotFoundException(message="Membership not found")

    plan = db.query(MembershipPlan).filter(MembershipPlan.id == payload.plan_id, MembershipPlan.is_active == True).first()
    if not plan:
        raise NotFoundException(message="Target plan not found or inactive")

    try:
        # Determine new start date
        today = date.today()
        start_date = today
        if payload.start_from_expiry and current_membership.end_date >= today:
            start_date = current_membership.end_date + timedelta(days=1)

        # Transition status of old membership if it is active
        if current_membership.status == SubscriptionStatus.ACTIVE:
            current_membership.status = SubscriptionStatus.EXPIRED

        # Calculate new end date
        end_date = start_date + timedelta(days=plan.duration_days)

        new_membership = Membership(
            member_id=current_membership.member_id,
            plan_id=payload.plan_id,
            start_date=start_date,
            end_date=end_date,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=payload.auto_renew,
            discount_percent=float(payload.discount_percent),
            notes=payload.notes
        )
        db.add(new_membership)
        db.commit()

        # Reload for mapping
        m_with_relations = db.query(Membership).options(
            joinedload(Membership.plan)
        ).filter(Membership.id == new_membership.id).first()

        res_data = _map_membership_to_response(m_with_relations)
        return success_response(message="Membership renewed successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[renew_membership] error during renewal transaction: {str(e)}")
        raise e


@router.patch("/{membership_id}/status", response_model=None)
def update_membership_status(
    membership_id: UUID,
    payload: MembershipStatusUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Manually alter subscription status (e.g., cancel, freeze/pause)."""
    logger.info(f"[update_membership_status] user={current_user.user_id} target={membership_id} status={payload.status}")

    membership = db.query(Membership).options(
        joinedload(Membership.plan)
    ).filter(
        Membership.id == membership_id,
        Membership.is_deleted == False
    ).first()

    if not membership:
        raise NotFoundException(message="Membership not found")

    try:
        membership.status = payload.status
        if payload.notes:
            membership.notes = f"{membership.notes or ''}\nStatus update: {payload.notes}".strip()

        db.commit()
        res_data = _map_membership_to_response(membership)
        return success_response(message="Membership status updated", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_membership_status] error updating status: {str(e)}")
        raise e


class FreezeMembershipRequest(BaseModel):
    notes: Optional[str] = None


class UpgradeMembershipRequest(BaseModel):
    new_plan_id: UUID
    notes: Optional[str] = None


@router.post("/{membership_id}/freeze", response_model=None)
def freeze_membership(
    membership_id: UUID,
    payload: FreezeMembershipRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Pause/freeze a membership subscription (Admin + Receptionist)."""
    membership = db.query(Membership).options(joinedload(Membership.plan)).filter(
        Membership.id == membership_id,
        Membership.is_deleted == False
    ).first()

    if not membership:
        raise NotFoundException(message="Membership not found")

    try:
        membership.status = SubscriptionStatus.PAUSED
        if payload.notes:
            membership.notes = f"{membership.notes or ''}\nFrozen: {payload.notes}".strip()
        db.commit()
        db.refresh(membership)
        return success_response(
            message="Membership paused/frozen successfully",
            data=_map_membership_to_response(membership).model_dump()
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[freeze_membership] error pausing membership: {e}")
        raise e


@router.post("/{membership_id}/unfreeze", response_model=None)
def unfreeze_membership(
    membership_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Resume/unfreeze a paused membership subscription (Admin + Receptionist)."""
    membership = db.query(Membership).options(joinedload(Membership.plan)).filter(
        Membership.id == membership_id,
        Membership.is_deleted == False
    ).first()

    if not membership:
        raise NotFoundException(message="Membership not found")

    try:
        membership.status = SubscriptionStatus.ACTIVE
        membership.notes = f"{membership.notes or ''}\nUnfrozen at {date.today()}".strip()
        db.commit()
        db.refresh(membership)
        return success_response(
            message="Membership resumed/unfrozen successfully",
            data=_map_membership_to_response(membership).model_dump()
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[unfreeze_membership] error resuming membership: {e}")
        raise e


@router.post("/{membership_id}/upgrade", response_model=None)
def upgrade_membership(
    membership_id: UUID,
    payload: UpgradeMembershipRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Upgrade current membership to a new plan immediately (Admin + Receptionist)."""
    # 1. Fetch current membership
    current_membership = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.is_deleted == False
    ).first()

    if not current_membership:
        raise NotFoundException(message="Membership not found")

    # 2. Fetch new plan
    new_plan = db.query(MembershipPlan).filter(
        MembershipPlan.id == payload.new_plan_id,
        MembershipPlan.is_active == True
    ).first()

    if not new_plan:
        raise NotFoundException(message="New membership plan not found or inactive")

    try:
        # 3. Cancel old membership
        current_membership.status = SubscriptionStatus.CANCELLED
        cancel_notes = f"Upgraded to plan {new_plan.name} on {date.today()}"
        if payload.notes:
            cancel_notes += f" — {payload.notes}"
        current_membership.notes = f"{current_membership.notes or ''}\n{cancel_notes}".strip()

        # 4. Create new membership starting today
        today = date.today()
        end_date = today + timedelta(days=new_plan.duration_days)

        new_membership = Membership(
            member_id=current_membership.member_id,
            plan_id=new_plan.id,
            start_date=today,
            end_date=end_date,
            status=SubscriptionStatus.ACTIVE,
            discount_percent=0.0,
            notes=f"Upgraded from previous membership {current_membership.id}"
        )
        db.add(new_membership)
        db.commit()

        # Load relations for mapping
        m_with_relations = db.query(Membership).options(
            joinedload(Membership.plan)
        ).filter(Membership.id == new_membership.id).first()

        return success_response(
            message="Membership upgraded successfully",
            data=_map_membership_to_response(m_with_relations).model_dump()
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[upgrade_membership] error upgrading membership: {e}")
        raise e
