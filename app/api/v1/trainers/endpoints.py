"""
FastAPI route handlers for Trainer management.
"""

import math
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone, date
from decimal import Decimal
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import cast, String
from app.database.session import get_db
from app.core.exceptions import ConflictException, NotFoundException, AuthorizationException
from app.core.constants import UserRole
from app.core.security import get_password_hash
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.user import User
from app.models.profile import Profile
from app.models.trainer import Trainer
from app.models.member import Member
from app.models.association import trainer_members
from app.api.v1.trainers.schemas import (
    TrainerCreate,
    TrainerUpdate,
    TrainerResponse,
    AssignMemberRequest,
    UnassignMemberRequest,
    TrainerListResponse
)
from app.api.v1.members.schemas import ProfileResponse, MemberResponse

router = APIRouter()


def _map_trainer_to_response(trainer: Trainer, db: Session, hide_private_info: bool = False) -> TrainerResponse:
    """Helper to map a Trainer db model to TrainerResponse schema, hiding sensitive fields if needed."""
    profile_db = trainer.profile
    user_db = profile_db.user if profile_db else None
    
    profile_res = ProfileResponse(
        id=profile_db.id,
        full_name=profile_db.full_name,
        phone=None if hide_private_info else profile_db.phone,  # Privacy protection
        avatar_url=profile_db.avatar_url,
        date_of_birth=None if hide_private_info else profile_db.date_of_birth,
        gender=None if hide_private_info else profile_db.gender,
        address=None if hide_private_info else profile_db.address,
        emergency_contact_name=None if hide_private_info else profile_db.emergency_contact_name,
        emergency_contact_phone=None if hide_private_info else profile_db.emergency_contact_phone,
        biometric_device_id=None if hide_private_info else profile_db.biometric_device_id,
        email=user_db.email if (user_db and not hide_private_info) else None,
        emergency_relation=None if hide_private_info else profile_db.emergency_relation,
    )

    # Compute assigned member count dynamically
    assigned_count = len([m for m in trainer.assigned_members if not m.is_deleted])
    
    mapped_members = []
    if not hide_private_info:
        from app.api.v1.members.endpoints import _map_member_to_response
        mapped_members = [_map_member_to_response(m, db) for m in trainer.assigned_members if not m.is_deleted]

    return TrainerResponse(
        id=trainer.id,
        employee_id=trainer.employee_id,
        specialization=trainer.specialization,
        specializations=trainer.specializations,
        experience_years=trainer.experience_years,
        qualification=trainer.qualification,
        certifications=trainer.certifications,
        bio=trainer.bio,
        is_available=trainer.is_available,
        is_active=user_db.is_active if user_db else True,
        employment_type=trainer.employment_type,
        salary=profile_db.salary if profile_db else None,
        salary_type=trainer.salary_type,
        shift=profile_db.shift if profile_db else None,
        joining_staff_date=profile_db.joining_staff_date if profile_db else None,
        max_members=trainer.max_members,
        working_days=trainer.working_days,
        working_hours=trainer.working_hours,
        profile=profile_res,
        assigned_member_count=assigned_count,
        assigned_members=mapped_members if not hide_private_info else None
    )


@router.get("/stats", response_model=None)
def get_trainer_stats(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve aggregate trainer KPIs for management dashboard."""
    logger.info(f"[get_trainer_stats] user={current_user.user_id}")

    trainers = db.query(Trainer).join(Trainer.profile).join(Profile.user).filter(
        Trainer.is_deleted == False,
        User.is_deleted == False
    ).all()
    
    total = len(trainers)
    active = sum(1 for t in trainers if t.profile.user.is_active)
    inactive = sum(1 for t in trainers if not t.profile.user.is_active)
    on_leave = sum(1 for t in trainers if not t.is_available)
    
    total_assigned = 0
    utilizations = []
    for t in trainers:
        assigned_count = len([m for m in t.assigned_members if not m.is_deleted])
        total_assigned += assigned_count
        max_cap = t.max_members or 15
        utilizations.append((assigned_count / max_cap) * 100)
        
    avg_utilization = round(sum(utilizations) / len(utilizations), 1) if utilizations else 0.0
    
    return success_response(message="Trainer KPI stats retrieved", data={
        "total_trainers": total,
        "active_trainers": active,
        "inactive_trainers": inactive,
        "on_leave_trainers": on_leave,
        "total_assigned_members": total_assigned,
        "average_rating": 4.8,
        "capacity_utilization": avg_utilization
    })


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_trainer(
    payload: TrainerCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Create a new Trainer user, profile, and trainer record (Admin only)."""
    logger.info(f"[create_trainer] user={current_user.user_id} action=create email={payload.email}")

    # Validation: Email unique
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise ConflictException(message=f"Email '{payload.email}' is already registered")

    # Validation: Phone unique
    if payload.phone:
        existing_phone = db.query(Profile).filter(Profile.phone == payload.phone).first()
        if existing_phone:
            raise ConflictException(message=f"Phone number '{payload.phone}' is already registered")

    # Validation: Employee ID unique
    if payload.employee_id:
        existing_emp = db.query(Trainer).filter(Trainer.employee_id == payload.employee_id).first()
        if existing_emp:
            raise ConflictException(message=f"Employee ID '{payload.employee_id}' is already registered")

    # Validation: Salary and Experience >= 0
    if payload.experience_years is not None and payload.experience_years < 0:
        raise ConflictException(message="Experience cannot be negative")
    if payload.salary is not None and payload.salary < 0:
        raise ConflictException(message="Salary cannot be negative")

    # Validation: DOB and Joining Date <= Today
    today = date.today()
    if payload.date_of_birth and payload.date_of_birth > today:
        raise ConflictException(message="Date of birth cannot be in the future")
    if payload.joining_staff_date and payload.joining_staff_date > today:
        raise ConflictException(message="Joining date cannot be in the future")

    try:
        # Create user credentials
        new_user = User(
            email=payload.email.lower(),
            hashed_password=get_password_hash(payload.password),
            role=UserRole.TRAINER,
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
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_phone=payload.emergency_contact_phone,
            emergency_relation=payload.emergency_relation,
            salary=payload.salary,
            shift=payload.shift,
            joining_staff_date=payload.joining_staff_date
        )
        db.add(new_profile)
        db.flush()

        # Create trainer details
        new_trainer = Trainer(
            profile_id=new_profile.id,
            employee_id=payload.employee_id,
            specialization=payload.specialization,
            specializations=payload.specializations,
            experience_years=payload.experience_years,
            qualification=payload.qualification,
            certifications=payload.certifications,
            bio=payload.bio,
            employment_type=payload.employment_type,
            salary_type=payload.salary_type,
            max_members=payload.max_members,
            working_days=payload.working_days,
            working_hours=payload.working_hours,
            is_available=True
        )
        db.add(new_trainer)
        db.commit()

        # Eager load relationships for response
        trainer_with_relations = db.query(Trainer).options(
            joinedload(Trainer.profile)
        ).filter(Trainer.id == new_trainer.id).first()

        res_data = _map_trainer_to_response(trainer_with_relations, db)
        return success_response(message="Trainer created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_trainer] error: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_trainers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query("all", description="all, active, suspended, archived"),
    shift: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    specialization: Optional[str] = Query(None),
    experience_min: Optional[int] = Query(None),
    experience_max: Optional[int] = Query(None),
    show_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """List and search paginated trainers with filtering options."""
    logger.info(f"[list_trainers] user={current_user.user_id} page={page} per_page={per_page}")

    query = db.query(Trainer).join(Trainer.profile).join(Profile.user)

    # Soft-delete visibility
    if show_archived or status == "archived":
        query = query.filter(Trainer.is_deleted == True)
    else:
        query = query.filter(Trainer.is_deleted == False, User.is_deleted == False)

    # Search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Profile.full_name.ilike(search_filter)) |
            (User.email.ilike(search_filter)) |
            (Profile.phone.ilike(search_filter)) |
            (Trainer.employee_id.ilike(search_filter)) |
            (Trainer.specialization.ilike(search_filter))
        )

    # Filter: Status (User active/suspended)
    if status == "active":
        query = query.filter(User.is_active == True)
    elif status == "suspended":
        query = query.filter(User.is_active == False)

    # Filter: Shift
    if shift:
        query = query.filter(Profile.shift == shift)

    # Filter: Employment Type
    if employment_type:
        query = query.filter(Trainer.employment_type == employment_type)

    # Filter: Specialization
    if specialization:
        query = query.filter(Trainer.specialization.ilike(f"%{specialization}%"))

    # Filter: Experience
    if experience_min is not None:
        query = query.filter(Trainer.experience_years >= experience_min)
    if experience_max is not None:
        query = query.filter(Trainer.experience_years <= experience_max)

    total = query.count()
    trainers = query.options(
        joinedload(Trainer.profile).joinedload(Profile.user),
        joinedload(Trainer.assigned_members)
    ).order_by(Profile.joining_staff_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    hide_private_info = current_user.role == UserRole.MEMBER
    mapped_trainers = [_map_trainer_to_response(t, db, hide_private_info).model_dump() for t in trainers]
    
    return paginated_response(
        message="Trainers list retrieved successfully",
        data=mapped_trainers,
        page=page,
        limit=per_page,
        total=total
    )


@router.get("/{trainer_id}", response_model=None)
def get_trainer(
    trainer_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single trainer."""
    logger.info(f"[get_trainer] user={current_user.user_id} target={trainer_id}")

    trainer = db.query(Trainer).options(
        joinedload(Trainer.profile).joinedload(Profile.user),
        joinedload(Trainer.assigned_members)
    ).filter(
        Trainer.id == trainer_id
    ).first()

    if not trainer or (trainer.is_deleted and current_user.role != UserRole.ADMIN):
        raise NotFoundException(message=f"Trainer not found")

    hide_private_info = True
    if current_user.role in [UserRole.ADMIN, UserRole.RECEPTIONIST]:
        hide_private_info = False
    elif current_user.role == UserRole.TRAINER:
        if trainer.profile.user_id == current_user.user_id:
            hide_private_info = False

    res_data = _map_trainer_to_response(trainer, db, hide_private_info)
    return success_response(message="Trainer details retrieved", data=res_data.model_dump())


@router.patch("/{trainer_id}", response_model=None)
def update_trainer(
    trainer_id: UUID,
    payload: TrainerUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update trainer attributes (Admin only)."""
    logger.info(f"[update_trainer] user={current_user.user_id} target={trainer_id}")

    trainer = db.query(Trainer).join(Trainer.profile).filter(
        Trainer.id == trainer_id,
        Trainer.is_deleted == False
    ).first()

    if not trainer:
        raise NotFoundException(message=f"Trainer not found")

    profile = trainer.profile
    user = db.query(User).filter(User.id == profile.user_id).first()

    # Validation: Phone unique
    if payload.phone is not None:
        existing_phone = db.query(Profile).filter(Profile.phone == payload.phone, Profile.id != profile.id).first()
        if existing_phone:
            raise ConflictException(message=f"Phone number '{payload.phone}' is already registered")

    # Validation: Employee ID unique
    if payload.employee_id is not None:
        existing_emp = db.query(Trainer).filter(Trainer.employee_id == payload.employee_id, Trainer.id != trainer.id).first()
        if existing_emp:
            raise ConflictException(message=f"Employee ID '{payload.employee_id}' is already registered")

    # Validation: Salary and Experience >= 0
    if payload.experience_years is not None and payload.experience_years < 0:
        raise ConflictException(message="Experience cannot be negative")
    if payload.salary is not None and payload.salary < 0:
        raise ConflictException(message="Salary cannot be negative")

    # Validation: DOB and Joining Date <= Today
    today = date.today()
    if payload.date_of_birth and payload.date_of_birth > today:
        raise ConflictException(message="Date of birth cannot be in the future")
    if payload.joining_staff_date and payload.joining_staff_date > today:
        raise ConflictException(message="Joining date cannot be in the future")

    # Validation: Max members capacity check
    if payload.max_members is not None:
        active_members_count = len([m for m in trainer.assigned_members if not m.is_deleted])
        if payload.max_members < active_members_count:
            raise ConflictException(
                message=f"Maximum capacity ({payload.max_members}) cannot be lower than current assigned members ({active_members_count})"
            )

    try:
        # Update user active status
        if payload.is_active is not None and user:
            user.is_active = payload.is_active

        # Update profile fields
        if payload.full_name is not None:
            profile.full_name = payload.full_name
        if payload.phone is not None:
            profile.phone = payload.phone
        if payload.avatar_url is not None:
            profile.avatar_url = payload.avatar_url
        if payload.date_of_birth is not None:
            profile.date_of_birth = payload.date_of_birth
        if payload.gender is not None:
            profile.gender = payload.gender
        if payload.address is not None:
            profile.address = payload.address
        if payload.emergency_contact_name is not None:
            profile.emergency_contact_name = payload.emergency_contact_name
        if payload.emergency_contact_phone is not None:
            profile.emergency_contact_phone = payload.emergency_contact_phone
        if payload.emergency_relation is not None:
            profile.emergency_relation = payload.emergency_relation
        if payload.salary is not None:
            profile.salary = payload.salary
        if payload.shift is not None:
            profile.shift = payload.shift
        if payload.joining_staff_date is not None:
            profile.joining_staff_date = payload.joining_staff_date

        # Update trainer-specific fields
        trainer_fields = {
            "employee_id", "specialization", "specializations", "experience_years", 
            "qualification", "certifications", "bio", "is_available", 
            "employment_type", "salary_type", "max_members", "working_days", "working_hours"
        }
        for field in trainer_fields:
            val = getattr(payload, field, None)
            if val is not None:
                setattr(trainer, field, val)

        db.commit()
        db.refresh(trainer)

        res_data = _map_trainer_to_response(trainer, db)
        return success_response(message="Trainer updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_trainer] error: {str(e)}")
        raise e


@router.post("/{trainer_id}/assign-member", response_model=None)
def assign_member(
    trainer_id: UUID,
    payload: AssignMemberRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Assign a member to a trainer's active coaching roster with capacity check."""
    logger.info(f"[assign_member] user={current_user.user_id} trainer={trainer_id} member={payload.member_id}")

    trainer = db.query(Trainer).filter(Trainer.id == trainer_id, Trainer.is_deleted == False).first()
    if not trainer:
        raise NotFoundException(message="Trainer not found")

    member = db.query(Member).filter(Member.id == payload.member_id, Member.is_deleted == False).first()
    if not member:
        raise NotFoundException(message="Member not found")

    # Capacity Check
    active_members_count = len([m for m in trainer.assigned_members if not m.is_deleted])
    max_cap = trainer.max_members or 15
    if active_members_count >= max_cap:
        raise ConflictException(message=f"Trainer has reached their maximum capacity of {max_cap} members")

    # Check if assignment already exists
    stmt = db.query(trainer_members).filter_by(
        trainer_id=trainer_id,
        member_id=payload.member_id
    ).first()

    if stmt:
        if stmt.is_active:
            raise ConflictException(message="Member is already assigned to this trainer")
        else:
            try:
                db.execute(
                    trainer_members.update().where(
                        (trainer_members.c.trainer_id == trainer_id) &
                        (trainer_members.c.member_id == payload.member_id)
                    ).values(is_active=True, assigned_at=datetime.now(timezone.utc))
                )
                db.commit()
                return success_response(message="Coaching link reactivated successfully", data={})
            except Exception as e:
                db.rollback()
                logger.error(f"[assign_member] error: {str(e)}")
                raise e

    try:
        db.execute(
            trainer_members.insert().values(
                trainer_id=trainer_id,
                member_id=payload.member_id,
                assigned_at=datetime.now(timezone.utc),
                is_active=True
            )
        )
        db.commit()
        return success_response(message="Member successfully assigned to trainer", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[assign_member] error: {str(e)}")
        raise e


@router.delete("/{trainer_id}/unassign-member", response_model=None)
def unassign_member(
    trainer_id: UUID,
    payload: UnassignMemberRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Deactivate (soft delete) member assignment coaching links."""
    logger.info(f"[unassign_member] user={current_user.user_id} trainer={trainer_id} member={payload.member_id}")

    stmt = db.query(trainer_members).filter_by(
        trainer_id=trainer_id,
        member_id=payload.member_id,
        is_active=True
    ).first()

    if not stmt:
        raise NotFoundException(message="Active coaching assignment not found")

    try:
        db.execute(
            trainer_members.update().where(
                (trainer_members.c.trainer_id == trainer_id) &
                (trainer_members.c.member_id == payload.member_id)
            ).values(is_active=False)
        )
        db.commit()
        return success_response(message="Member successfully unassigned from trainer", data={})

    except Exception as e:
        db.rollback()
        raise e


@router.delete("/{trainer_id}", response_model=None)
def delete_trainer(
    trainer_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Deactivate (soft delete) a trainer account (Admin only)."""
    logger.info(f"[delete_trainer] user={current_user.user_id} target={trainer_id}")

    trainer = db.query(Trainer).join(Trainer.profile).filter(
        Trainer.id == trainer_id,
        Trainer.is_deleted == False
    ).first()

    if not trainer:
        raise NotFoundException(message=f"Trainer not found")

    profile = trainer.profile
    user = db.query(User).filter(User.id == profile.user_id).first()

    try:
        trainer.soft_delete(updater_id=current_user.user_id)
        if user:
            user.soft_delete(updater_id=current_user.user_id)
            user.is_active = False

        db.commit()
        return success_response(message="Trainer deactivated successfully", data={})

    except Exception as e:
        db.rollback()
        raise e


@router.post("/{trainer_id}/restore", response_model=None)
def restore_trainer(
    trainer_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Restore an archived trainer account (Admin only)."""
    logger.info(f"[restore_trainer] user={current_user.user_id} target={trainer_id}")

    trainer = db.query(Trainer).join(Trainer.profile).filter(
        Trainer.id == trainer_id,
        Trainer.is_deleted == True
    ).first()
    if not trainer:
        raise NotFoundException(message="Trainer not found or not archived")
    
    profile = trainer.profile
    user = db.query(User).filter(User.id == profile.user_id).first()
    
    try:
        trainer.is_deleted = False
        trainer.deleted_at = None
        trainer.deleted_by = None
        
        if user:
            user.is_deleted = False
            user.deleted_at = None
            user.deleted_by = None
            user.is_active = True
            
        db.commit()
        return success_response(message="Trainer restored successfully")
    except Exception as e:
        db.rollback()
        raise e


@router.post("/bulk-archive", response_model=None)
def bulk_archive_trainers(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk archive trainers (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No trainers selected")
    
    trainers = db.query(Trainer).filter(Trainer.id.in_(ids), Trainer.is_deleted == False).all()
    try:
        for t in trainers:
            t.soft_delete(updater_id=current_user.user_id)
            user = db.query(User).filter(User.id == t.profile.user_id).first()
            if user:
                user.soft_delete(updater_id=current_user.user_id)
                user.is_active = False
        db.commit()
        return success_response(message=f"Successfully archived {len(trainers)} trainers")
    except Exception as e:
        db.rollback()
        raise e


@router.post("/bulk-restore", response_model=None)
def bulk_restore_trainers(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk restore trainers (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No trainers selected")
    
    trainers = db.query(Trainer).filter(Trainer.id.in_(ids), Trainer.is_deleted == True).all()
    try:
        for t in trainers:
            t.is_deleted = False
            t.deleted_at = None
            t.deleted_by = None
            user = db.query(User).filter(User.id == t.profile.user_id).first()
            if user:
                user.is_deleted = False
                user.deleted_at = None
                user.deleted_by = None
                user.is_active = True
        db.commit()
        return success_response(message=f"Successfully restored {len(trainers)} trainers")
    except Exception as e:
        db.rollback()
        raise e


@router.post("/bulk-change-shift", response_model=None)
def bulk_change_shift(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk update trainers' shifts (Admin only)."""
    ids = payload.get("ids", [])
    shift_val = payload.get("shift")
    if not ids or not shift_val:
        return success_response(message="No trainers or shift selected")
    
    trainers = db.query(Trainer).filter(Trainer.id.in_(ids), Trainer.is_deleted == False).all()
    try:
        for t in trainers:
            t.profile.shift = shift_val
        db.commit()
        return success_response(message=f"Successfully updated shift for {len(trainers)} trainers")
    except Exception as e:
        db.rollback()
        raise e


@router.post("/bulk-activate", response_model=None)
def bulk_activate_trainers(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk activate trainers' accounts (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No trainers selected")
    
    trainers = db.query(Trainer).filter(Trainer.id.in_(ids), Trainer.is_deleted == False).all()
    try:
        for t in trainers:
            user = db.query(User).filter(User.id == t.profile.user_id).first()
            if user:
                user.is_active = True
        db.commit()
        return success_response(message=f"Successfully activated {len(trainers)} trainers")
    except Exception as e:
        db.rollback()
        raise e


@router.post("/bulk-deactivate", response_model=None)
def bulk_deactivate_trainers(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Bulk deactivate trainers' accounts (Admin only)."""
    ids = payload.get("ids", [])
    if not ids:
        return success_response(message="No trainers selected")
    
    trainers = db.query(Trainer).filter(Trainer.id.in_(ids), Trainer.is_deleted == False).all()
    try:
        for t in trainers:
            user = db.query(User).filter(User.id == t.profile.user_id).first()
            if user:
                user.is_active = False
        db.commit()
        return success_response(message=f"Successfully suspended {len(trainers)} trainers")
    except Exception as e:
        db.rollback()
        raise e
