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
from app.models.pt_plan import PTPlan
from app.api.v1.pt_plans.schemas import (
    PTPlanCreate,
    PTPlanUpdate,
    PTPlanResponse
)

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_pt_plan(
    payload: PTPlanCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Create a new PT Package (Admin only)."""
    logger.info(f"[create_pt_plan] user={current_user.user_id} package='{payload.package_name}'")

    existing = db.query(PTPlan).filter(
        PTPlan.package_name.ilike(payload.package_name),
        PTPlan.is_deleted == False
    ).first()

    if existing:
        raise ConflictException(message=f"PT package with name '{payload.package_name}' already exists")

    try:
        new_plan = PTPlan(
            package_name=payload.package_name,
            price=float(payload.price),
            session_count=payload.session_count,
            whatsapp_support=payload.whatsapp_support,
            locker_included=payload.locker_included,
            transformation_included=payload.transformation_included,
            diet_included=payload.diet_included,
            stretching_included=payload.stretching_included,
            supplement_guidance=payload.supplement_guidance,
            description=payload.description,
            is_active=payload.is_active
        )
        db.add(new_plan)
        db.commit()
        db.refresh(new_plan)

        res_data = PTPlanResponse.model_validate(new_plan)
        return success_response(message="PT Package created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_pt_plan] error: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_pt_plans(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """List PT packages (Any authenticated user)."""
    logger.info(f"[list_pt_plans] user={current_user.user_id} active_only={active_only}")

    query = db.query(PTPlan).filter(PTPlan.is_deleted == False)

    if active_only:
        query = query.filter(PTPlan.is_active == True)

    results = query.order_by(PTPlan.price.asc()).all()
    responses = [PTPlanResponse.model_validate(item).model_dump() for item in results]

    return success_response(message="PT Packages retrieved", data=responses)


@router.get("/{plan_id}", response_model=None)
def get_pt_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single PT package."""
    plan = db.query(PTPlan).filter(
        PTPlan.id == plan_id,
        PTPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="PT package not found")

    res_data = PTPlanResponse.model_validate(plan)
    return success_response(message="PT Package details retrieved", data=res_data.model_dump())


@router.patch("/{plan_id}", response_model=None)
def update_pt_plan(
    plan_id: UUID,
    payload: PTPlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update PT package details (Admin only)."""
    plan = db.query(PTPlan).filter(
        PTPlan.id == plan_id,
        PTPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="PT package not found")

    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "price":
                setattr(plan, field, float(value) if value is not None else 0.0)
            else:
                setattr(plan, field, value)

        db.commit()
        db.refresh(plan)

        res_data = PTPlanResponse.model_validate(plan)
        return success_response(message="PT Package updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_pt_plan] error: {str(e)}")
        raise e


@router.delete("/{plan_id}", response_model=None)
def delete_pt_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Soft delete a PT package (Admin only)."""
    plan = db.query(PTPlan).filter(
        PTPlan.id == plan_id,
        PTPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="PT package not found")

    try:
        plan.soft_delete(updater_id=current_user.user_id)
        db.commit()
        return success_response(message="PT Package deleted successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_pt_plan] error: {str(e)}")
        raise e
