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
from app.models.additional_service import AdditionalService
from app.api.v1.additional_services.schemas import (
    AdditionalServiceCreate,
    AdditionalServiceUpdate,
    AdditionalServiceResponse
)

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_service(
    payload: AdditionalServiceCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Create a new Additional Service (Admin only)."""
    logger.info(f"[create_service] user={current_user.user_id} name='{payload.name}'")

    existing = db.query(AdditionalService).filter(
        AdditionalService.name.ilike(payload.name),
        AdditionalService.is_deleted == False
    ).first()

    if existing:
        raise ConflictException(message=f"Service with name '{payload.name}' already exists")

    try:
        new_service = AdditionalService(
            name=payload.name,
            price=float(payload.price),
            description=payload.description,
            is_active=payload.is_active
        )
        db.add(new_service)
        db.commit()
        db.refresh(new_service)

        res_data = AdditionalServiceResponse.model_validate(new_service)
        return success_response(message="Additional Service created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_service] error: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_services(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """List Additional Services (Any authenticated user)."""
    logger.info(f"[list_services] user={current_user.user_id} active_only={active_only}")

    query = db.query(AdditionalService).filter(AdditionalService.is_deleted == False)

    if active_only:
        query = query.filter(AdditionalService.is_active == True)

    results = query.order_by(AdditionalService.price.asc()).all()
    responses = [AdditionalServiceResponse.model_validate(item).model_dump() for item in results]

    return success_response(message="Additional Services retrieved", data=responses)


@router.get("/{service_id}", response_model=None)
def get_service(
    service_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single Additional Service."""
    service = db.query(AdditionalService).filter(
        AdditionalService.id == service_id,
        AdditionalService.is_deleted == False
    ).first()

    if not service:
        raise NotFoundException(message="Additional Service not found")

    res_data = AdditionalServiceResponse.model_validate(service)
    return success_response(message="Additional Service details retrieved", data=res_data.model_dump())


@router.patch("/{service_id}", response_model=None)
def update_service(
    service_id: UUID,
    payload: AdditionalServiceUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update Additional Service details (Admin only)."""
    service = db.query(AdditionalService).filter(
        AdditionalService.id == service_id,
        AdditionalService.is_deleted == False
    ).first()

    if not service:
        raise NotFoundException(message="Additional Service not found")

    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "price":
                setattr(service, field, float(value) if value is not None else 0.0)
            else:
                setattr(service, field, value)

        db.commit()
        db.refresh(service)

        res_data = AdditionalServiceResponse.model_validate(service)
        return success_response(message="Additional Service updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_service] error: {str(e)}")
        raise e


@router.delete("/{service_id}", response_model=None)
def delete_service(
    service_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Soft delete an Additional Service (Admin only)."""
    service = db.query(AdditionalService).filter(
        AdditionalService.id == service_id,
        AdditionalService.is_deleted == False
    ).first()

    if not service:
        raise NotFoundException(message="Additional Service not found")

    try:
        service.soft_delete(updater_id=current_user.user_id)
        db.commit()
        return success_response(message="Additional Service deleted successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_service] error: {str(e)}")
        raise e
