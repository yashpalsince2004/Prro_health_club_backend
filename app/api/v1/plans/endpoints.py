"""
FastAPI route handlers for Membership Plan Catalog management.
"""

from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.exceptions import ConflictException, NotFoundException
from app.core.constants import UserRole, SubscriptionStatus
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response
from app.models.plan import MembershipPlan
from app.models.membership import Membership
from app.api.v1.plans.schemas import (
    PlanCreate,
    PlanUpdate,
    PlanResponse
)

router = APIRouter()


def _get_active_subscriber_count(db: Session, plan_id: UUID) -> int:
    """Helper to count active subscribers for a single plan."""
    return db.query(func.count(Membership.id)).filter(
        Membership.plan_id == plan_id,
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.is_deleted == False
    ).scalar() or 0


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_plan(
    payload: PlanCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Create a new membership plan template (Admin only)."""
    logger.info(f"[create_plan] user={current_user.user_id} name='{payload.name}'")

    # Check case-insensitive duplicate plan name
    existing_plan = db.query(MembershipPlan).filter(
        func.lower(MembershipPlan.name) == payload.name.lower(),
        MembershipPlan.is_deleted == False
    ).first()

    if existing_plan:
        raise ConflictException(message=f"Membership plan with name '{payload.name}' already exists")

    try:
        new_plan = MembershipPlan(
            name=payload.name,
            description=payload.description,
            duration_days=payload.duration_days,
            price=float(payload.price),
            features=payload.features,
            is_active=payload.is_active,
            display_order=payload.display_order
        )
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)

        res_data = PlanResponse(
            id=new_plan.id,
            name=new_plan.name,
            description=new_plan.description,
            duration_days=new_plan.duration_days,
            price=Decimal(str(new_plan.price)),
            currency=new_plan.currency,
            features=new_plan.features,
            is_active=new_plan.is_active,
            display_order=new_plan.display_order,
            active_subscriber_count=0
        )
        return success_response(message="Membership plan created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_plan] error: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_plans(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """List plans sorted by display_order (Any authenticated user)."""
    logger.info(f"[list_plans] user={current_user.user_id} active_only={active_only}")

    # SQL aggregation subquery to get active subscribers count efficiently
    subq = db.query(
        Membership.plan_id,
        func.count(Membership.id).label("active_count")
    ).filter(
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.is_deleted == False
    ).group_by(Membership.plan_id).subquery()

    query = db.query(MembershipPlan, subq.c.active_count).outerjoin(
        subq, MembershipPlan.id == subq.c.plan_id
    ).filter(MembershipPlan.is_deleted == False)

    if active_only:
        query = query.filter(MembershipPlan.is_active == True)

    plans_results = query.order_by(MembershipPlan.display_order.asc()).all()

    plan_responses = []
    for plan, active_count in plans_results:
        plan_responses.append(
            PlanResponse(
                id=plan.id,
                name=plan.name,
                description=plan.description,
                duration_days=plan.duration_days,
                price=Decimal(str(plan.price)),
                currency=plan.currency,
                features=plan.features,
                is_active=plan.is_active,
                display_order=plan.display_order,
                active_subscriber_count=active_count or 0
            ).model_dump()
        )

    return success_response(message="Membership plans list retrieved", data=plan_responses)


@router.get("/{plan_id}", response_model=None)
def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single membership plan (Any authenticated user)."""
    logger.info(f"[get_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(MembershipPlan).filter(
        MembershipPlan.id == plan_id,
        MembershipPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Membership plan not found")

    active_count = _get_active_subscriber_count(db, plan_id)

    res_data = PlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        duration_days=plan.duration_days,
        price=Decimal(str(plan.price)),
        currency=plan.currency,
        features=plan.features,
        is_active=plan.is_active,
        display_order=plan.display_order,
        active_subscriber_count=active_count
    )
    return success_response(message="Membership plan details retrieved", data=res_data.model_dump())


@router.patch("/{plan_id}", response_model=None)
def update_plan(
    plan_id: UUID,
    payload: PlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update plan details (Admin only). Warns if modifying critical fields."""
    logger.info(f"[update_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(MembershipPlan).filter(
        MembershipPlan.id == plan_id,
        MembershipPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Membership plan not found")

    # Add warning logs if price or duration is being altered
    if payload.price is not None and float(payload.price) != plan.price:
        logger.warning(f"[update_plan] Admin user={current_user.user_id} is changing price of plan '{plan.name}' from {plan.price} to {payload.price}")
    if payload.duration_days is not None and payload.duration_days != plan.duration_days:
        logger.warning(f"[update_plan] Admin user={current_user.user_id} is changing duration of plan '{plan.name}' from {plan.duration_days} days to {payload.duration_days} days")

    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "price":
                setattr(plan, field, float(value))
            else:
                setattr(plan, field, value)

        db.commit()
        db.refresh(plan)

        active_count = _get_active_subscriber_count(db, plan_id)
        res_data = PlanResponse(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            duration_days=plan.duration_days,
            price=Decimal(str(plan.price)),
            currency=plan.currency,
            features=plan.features,
            is_active=plan.is_active,
            display_order=plan.display_order,
            active_subscriber_count=active_count
        )
        return success_response(message="Membership plan updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_plan] error: {str(e)}")
        raise e


@router.delete("/{plan_id}", response_model=None)
def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Soft delete a membership plan template. Blocks deletion if active subscribers exist."""
    logger.info(f"[delete_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(MembershipPlan).filter(
        MembershipPlan.id == plan_id,
        MembershipPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Membership plan not found")

    active_count = _get_active_subscriber_count(db, plan_id)
    if active_count > 0:
        raise ConflictException(
            message=f"Cannot delete plan with {active_count} active subscribers. Deactivate it instead."
        )

    try:
        plan.soft_delete(updater_id=current_user.user_id)
        db.commit()
        return success_response(message="Membership plan deleted successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_plan] error: {str(e)}")
        raise e
