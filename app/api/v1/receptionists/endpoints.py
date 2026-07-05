from datetime import datetime, timezone
import math
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status, BackgroundTasks, Query
from sqlalchemy.orm import Session, joinedload
from app.database.session import get_db
from app.core.exceptions import ConflictException, NotFoundException
from app.core.constants import UserRole
from app.core.security import get_password_hash
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.user import User
from app.models.profile import Profile
from app.services.email_service import send_welcome_email
from app.api.v1.receptionists.schemas import (
    ReceptionistCreate,
    ReceptionistUpdate,
    ReceptionistResponse,
    ProfileResponse,
    StaffListResponse
)

router = APIRouter()

def _map_receptionist_to_response(user: User) -> ReceptionistResponse:
    profile_db = user.profile
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
        salary=profile_db.salary,
        shift=profile_db.shift,
        joining_staff_date=profile_db.joining_staff_date
    )
    return ReceptionistResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role.value if hasattr(user.role, "value") else user.role,
        profile=profile_res,
        created_at=user.created_at
    )

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_receptionist(
    payload: ReceptionistCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Create a new receptionist account (Admin only)."""
    # Check if email is already taken
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise ConflictException(message=f"Email '{payload.email}' is already registered")

    # Create user
    new_user = User(
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        role=UserRole.RECEPTIONIST,
        is_active=True
    )
    db.add(new_user)
    db.flush()

    # Create profile
    new_profile = Profile(
        user_id=new_user.id,
        full_name=payload.full_name,
        phone=payload.phone,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        address=payload.address,
        salary=payload.salary,
        shift=payload.shift,
        joining_staff_date=payload.joining_staff_date
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_user)

    # Send welcome email asynchronously
    background_tasks.add_task(
        send_welcome_email,
        to_email=new_user.email,
        member_name=payload.full_name,
        temp_password=payload.password
    )

    return success_response(
        message="Receptionist created successfully",
        data=_map_receptionist_to_response(new_user),
        status_code=status.HTTP_201_CREATED
    )

@router.get("/")
def list_receptionists(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """List all receptionist staff members (Admin only)."""
    query = db.query(User).options(joinedload(User.profile)).filter(
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    )

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.join(Profile).filter(
            (User.email.ilike(search_pattern)) |
            (Profile.full_name.ilike(search_pattern)) |
            (Profile.phone.ilike(search_pattern))
        )

    total = query.count()
    offset = (page - 1) * per_page
    receptionists = query.order_by(User.created_at.desc()).offset(offset).limit(per_page).all()

    mapped_list = [_map_receptionist_to_response(r) for r in receptionists]

    return paginated_response(
        message="Receptionists retrieved successfully",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )

@router.get("/{user_id}")
def get_receptionist(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Get details of a single receptionist (Admin only)."""
    user = db.query(User).options(joinedload(User.profile)).filter(
        User.id == user_id,
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).first()

    if not user:
        raise NotFoundException(message="Receptionist account not found")

    return success_response(
        message="Receptionist retrieved successfully",
        data=_map_receptionist_to_response(user)
    )

@router.patch("/{user_id}")
def update_receptionist(
    user_id: UUID,
    payload: ReceptionistUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update receptionist profile and status (Admin only)."""
    user = db.query(User).options(joinedload(User.profile)).filter(
        User.id == user_id,
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).first()

    if not user:
        raise NotFoundException(message="Receptionist account not found")

    # Update User model
    if payload.is_active is not None:
        user.is_active = payload.is_active

    # Update Profile model
    profile = user.profile
    if profile:
        if payload.full_name is not None:
            profile.full_name = payload.full_name
        if payload.phone is not None:
            profile.phone = payload.phone
        if payload.gender is not None:
            profile.gender = payload.gender
        if payload.address is not None:
            profile.address = payload.address
        if payload.salary is not None:
            profile.salary = payload.salary
        if payload.shift is not None:
            profile.shift = payload.shift

    db.commit()
    db.refresh(user)

    return success_response(
        message="Receptionist updated successfully",
        data=_map_receptionist_to_response(user)
    )

@router.delete("/{user_id}")
def delete_receptionist(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Soft delete receptionist account (Admin only)."""
    user = db.query(User).filter(
        User.id == user_id,
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).first()

    if not user:
        raise NotFoundException(message="Receptionist account not found")

    user.is_deleted = True
    user.is_active = False
    # Revoke sessions
    user.last_password_changed_at = datetime.now(timezone.utc)

    db.commit()

    return success_response(
        message="Receptionist account soft deleted successfully"
    )
