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
        id=profile_db.id if profile_db else user.id,
        full_name=profile_db.full_name if profile_db else "Unknown",
        phone=profile_db.phone if profile_db else None,
        avatar_url=profile_db.avatar_url if profile_db else None,
        date_of_birth=profile_db.date_of_birth if profile_db else None,
        gender=profile_db.gender if profile_db else None,
        address=profile_db.address if profile_db else None,
        emergency_contact_name=profile_db.emergency_contact_name if profile_db else None,
        emergency_contact_phone=profile_db.emergency_contact_phone if profile_db else None,
        biometric_device_id=profile_db.biometric_device_id if profile_db else None,
        salary=profile_db.salary if profile_db else None,
        shift=profile_db.shift if profile_db else None,
        joining_staff_date=profile_db.joining_staff_date if profile_db else None,
        medical_notes=profile_db.medical_notes if profile_db else None
    )
    return ReceptionistResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role.value if hasattr(user.role, "value") else user.role,
        profile=profile_res,
        created_at=None
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
        joining_staff_date=payload.joining_staff_date,
        medical_notes=payload.medical_notes
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

@router.get("/stats", response_model=None)
def get_receptionist_stats(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Retrieve aggregate receptionist KPIs for management dashboard (Admin only)."""
    users = db.query(User).options(joinedload(User.profile)).filter(
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).all()
    
    total = len(users)
    active = sum(1 for u in users if u.is_active)
    inactive = total - active
    
    monthly_salary_cost = sum(float(u.profile.salary or 0) for u in users if u.profile and u.is_active)
    
    return success_response(message="Receptionist KPI stats retrieved", data={
        "total_receptionists": total,
        "active_receptionists": active,
        "inactive_receptionists": inactive,
        "on_leave_receptionists": 0,
        "today_attendance": 0,
        "pending_leave_requests": 0,
        "average_rating": 4.9,
        "monthly_salary_cost": monthly_salary_cost
    })

@router.post("/bulk-archive", response_model=None)
def bulk_archive_receptionists(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk archive receptionists (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No receptionists selected")
    
    users = db.query(User).filter(
        User.id.in_(ids),
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).all()
    
    try:
        for u in users:
            u.is_deleted = True
            u.is_active = False
            u.last_password_changed_at = datetime.now(timezone.utc)
        db.commit()
        return success_response(message=f"Successfully archived {len(users)} receptionists")
    except Exception as e:
        db.rollback()
        raise e

@router.post("/bulk-restore", response_model=None)
def bulk_restore_receptionists(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk restore receptionists (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No receptionists selected")
    
    users = db.query(User).filter(
        User.id.in_(ids),
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == True
    ).all()
    
    try:
        for u in users:
            u.is_deleted = False
            u.is_active = True
        db.commit()
        return success_response(message=f"Successfully restored {len(users)} receptionists")
    except Exception as e:
        db.rollback()
        raise e

@router.post("/bulk-activate", response_model=None)
def bulk_activate_receptionists(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk activate receptionists' logins (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No receptionists selected")
    
    users = db.query(User).filter(
        User.id.in_(ids),
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).all()
    
    try:
        for u in users:
            u.is_active = True
        db.commit()
        return success_response(message=f"Successfully activated {len(users)} receptionists")
    except Exception as e:
        db.rollback()
        raise e

@router.post("/bulk-deactivate", response_model=None)
def bulk_deactivate_receptionists(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk deactivate receptionists' logins (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No receptionists selected")
    
    users = db.query(User).filter(
        User.id.in_(ids),
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).all()
    
    try:
        for u in users:
            u.is_active = False
            u.last_password_changed_at = datetime.now(timezone.utc)
        db.commit()
        return success_response(message=f"Successfully suspended {len(users)} receptionists")
    except Exception as e:
        db.rollback()
        raise e

@router.post("/bulk-change-shift", response_model=None)
def bulk_change_shift(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk update receptionists' shifts (Admin only)."""
    ids = payload.get("ids", [])
    shift_val = payload.get("shift")
    if not ids or not shift_val:
        return success_response(message="No receptionists or shift selected")
    
    users = db.query(User).options(joinedload(User.profile)).filter(
        User.id.in_(ids),
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == False
    ).all()
    
    try:
        for u in users:
            if u.profile:
                u.profile.shift = shift_val
        db.commit()
        return success_response(message=f"Successfully updated shift for {len(users)} receptionists")
    except Exception as e:
        db.rollback()
        raise e

@router.get("/")
def list_receptionists(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    show_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """List all receptionist staff members (Admin only)."""
    query = db.query(User).options(joinedload(User.profile)).filter(
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == show_archived
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
    receptionists = query.order_by(User.id.desc()).offset(offset).limit(per_page).all()

    mapped_list = [_map_receptionist_to_response(r) for r in receptionists]

    return paginated_response(
        message="Receptionists retrieved successfully",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )

@router.post("/{user_id}/restore", response_model=None)
def restore_receptionist(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Restore soft deleted receptionist (Admin only)."""
    user = db.query(User).filter(
        User.id == user_id,
        User.role == UserRole.RECEPTIONIST,
        User.is_deleted == True
    ).first()

    if not user:
        raise NotFoundException(message="Archived receptionist account not found")

    user.is_deleted = False
    user.is_active = True
    db.commit()
    db.refresh(user)

    return success_response(
        message="Receptionist account restored successfully",
        data=_map_receptionist_to_response(user)
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
        if payload.medical_notes is not None:
            profile.medical_notes = payload.medical_notes

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
