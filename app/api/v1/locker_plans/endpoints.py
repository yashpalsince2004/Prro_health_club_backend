from typing import List
from uuid import UUID
from decimal import Decimal
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.exceptions import ConflictException, NotFoundException
from app.core.constants import UserRole
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response
from app.models.locker_plan import LockerPlan
from app.api.v1.locker_plans.schemas import (
    LockerPlanCreate,
    LockerPlanUpdate,
    LockerPlanResponse
)

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_locker_plan(
    payload: LockerPlanCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Create a new Locker Plan (Admin only)."""
    logger.info(f"[create_locker_plan] user={current_user.user_id} name='{payload.name}'")

    existing = db.query(LockerPlan).filter(
        LockerPlan.name.ilike(payload.name),
        LockerPlan.is_deleted == False
    ).first()

    if existing:
        raise ConflictException(message=f"Locker plan with name '{payload.name}' already exists")

    try:
        new_plan = LockerPlan(
            name=payload.name,
            deposit=float(payload.deposit),
            monthly_rent=float(payload.monthly_rent),
            quarterly_rent=float(payload.quarterly_rent),
            late_fee=float(payload.late_fee),
            refundable=payload.refundable,
            is_active=payload.is_active
        )
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)

        res_data = LockerPlanResponse.model_validate(new_plan)
        return success_response(message="Locker Plan created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_locker_plan] error: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_locker_plans(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """List Locker plans (Any authenticated user)."""
    logger.info(f"[list_locker_plans] user={current_user.user_id} active_only={active_only}")

    query = db.query(LockerPlan).filter(LockerPlan.is_deleted == False)

    if active_only:
        query = query.filter(LockerPlan.is_active == True)

    results = query.order_by(LockerPlan.monthly_rent.asc()).all()
    responses = [LockerPlanResponse.model_validate(item).model_dump() for item in results]

    return success_response(message="Locker Plans retrieved", data=responses)


@router.get("/{plan_id}", response_model=None)
def get_locker_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single Locker plan."""
    plan = db.query(LockerPlan).filter(
        LockerPlan.id == plan_id,
        LockerPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Locker plan not found")

    res_data = LockerPlanResponse.model_validate(plan)
    return success_response(message="Locker Plan details retrieved", data=res_data.model_dump())


@router.patch("/{plan_id}", response_model=None)
def update_locker_plan(
    plan_id: UUID,
    payload: LockerPlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update Locker plan details (Admin only)."""
    plan = db.query(LockerPlan).filter(
        LockerPlan.id == plan_id,
        LockerPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Locker plan not found")

    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field in ["deposit", "monthly_rent", "quarterly_rent", "late_fee"]:
                setattr(plan, field, float(value) if value is not None else 0.0)
            else:
                setattr(plan, field, value)

        db.commit()
        db.refresh(plan)

        res_data = LockerPlanResponse.model_validate(plan)
        return success_response(message="Locker Plan updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_locker_plan] error: {str(e)}")
        raise e


@router.delete("/{plan_id}", response_model=None)
def delete_locker_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Soft delete a Locker plan (Admin only)."""
    plan = db.query(LockerPlan).filter(
        LockerPlan.id == plan_id,
        LockerPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Locker plan not found")

    try:
        plan.soft_delete(updater_id=current_user.user_id)
        db.commit()
        return success_response(message="Locker Plan deleted successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_locker_plan] error: {str(e)}")
        raise e
