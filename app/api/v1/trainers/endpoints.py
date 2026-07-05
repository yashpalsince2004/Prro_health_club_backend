"""
FastAPI route handlers for Trainer management.
"""

import math
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session, joinedload
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
from app.api.v1.members.schemas import ProfileResponse

router = APIRouter()


def _map_trainer_to_response(trainer: Trainer, db: Session, hide_private_info: bool = False) -> TrainerResponse:
    """Helper to map a Trainer db model to TrainerResponse schema, hiding sensitive fields if needed."""
    profile_db = trainer.profile
    
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
        biometric_device_id=None if hide_private_info else profile_db.biometric_device_id
    )

    # Compute assigned member count dynamically
    assigned_count = len([m for m in trainer.assigned_members if not m.is_deleted])
    
    mapped_members = []
    if not hide_private_info:
        from app.api.v1.members.endpoints import _map_member_to_response
        mapped_members = [_map_member_to_response(m, db) for m in trainer.assigned_members if not m.is_deleted]

    return TrainerResponse(
        id=trainer.id,
        specialization=trainer.specialization,
        experience_years=trainer.experience_years,
        certifications=trainer.certifications,
        bio=trainer.bio,
        is_available=trainer.is_available,
        profile=profile_res,
        assigned_member_count=assigned_count,
        assigned_members=mapped_members if not hide_private_info else None
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_trainer(
    payload: TrainerCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Create a new Trainer user, profile, and trainer record (Admin only)."""
    logger.info(f"[create_trainer] user={current_user.user_id} action=create email={payload.email}")

    # Check if email is already taken
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise ConflictException(message=f"Email '{payload.email}' is already registered")

    try:
        # Create user credentials
        new_user = User(
            email=payload.email.lower(),
            hashed_password=get_password_hash(payload.password),
            role=UserRole.TRAINER,
            is_active=True
        )
        db.add(new_user)
        db.flush()  # Generate user ID

        # Create profile
        new_profile = Profile(
            user_id=new_user.id,
            full_name=payload.full_name,
            phone=payload.phone,
            date_of_birth=None,
            gender=None,
            salary=payload.salary,
            joining_staff_date=payload.joining_staff_date
        )
        db.add(new_profile)
        db.flush()  # Generate profile ID

        # Create trainer details
        new_trainer = Trainer(
            profile_id=new_profile.id,
            specialization=payload.specialization,
            experience_years=payload.experience_years,
            certifications=payload.certifications,
            bio=payload.bio,
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
        logger.error(f"[create_trainer] error during database insertion: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_trainers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    available_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """List and search paginated trainers."""
    logger.info(f"[list_trainers] user={current_user.user_id} page={page} per_page={per_page}")

    query = db.query(Trainer).join(Trainer.profile).join(Profile.user).filter(
        Trainer.is_deleted == False,
        User.is_deleted == False
    )

    # Apply search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Profile.full_name.ilike(search_filter)) |
            (Trainer.specialization.ilike(search_filter)) |
            (Profile.phone.ilike(search_filter))
        )

    # Apply availability filter
    if available_only:
        query = query.filter(Trainer.is_available == True)

    total = query.count()
    trainers = query.options(
        joinedload(Trainer.profile),
        joinedload(Trainer.assigned_members)
    ).offset((page - 1) * per_page).limit(per_page).all()

    # Determine privacy: Hide contact info if caller is a Member
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
    logger.info(f"[get_trainer] user={current_user.user_id} action=get_trainer target={trainer_id}")

    trainer = db.query(Trainer).options(
        joinedload(Trainer.profile).joinedload(Profile.user),
        joinedload(Trainer.assigned_members)
    ).filter(
        Trainer.id == trainer_id,
        Trainer.is_deleted == False
    ).first()

    if not trainer:
        raise NotFoundException(message=f"Trainer not found")

    # Access rule: Trainers can see their own full details; Members/other trainers see public info
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
    logger.info(f"[update_trainer] user={current_user.user_id} action=update target={trainer_id}")

    trainer = db.query(Trainer).join(Trainer.profile).filter(
        Trainer.id == trainer_id,
        Trainer.is_deleted == False
    ).first()

    if not trainer:
        raise NotFoundException(message=f"Trainer not found")

    profile = trainer.profile
    user = db.query(User).filter(User.id == profile.user_id).first()

    try:
        # Update user active status if requested
        if payload.is_active is not None and user:
            user.is_active = payload.is_active

        # Update profile full name and phone if provided
        if payload.full_name is not None:
            profile.full_name = payload.full_name
        if payload.phone is not None:
            profile.phone = payload.phone
        if payload.salary is not None:
            profile.salary = payload.salary
        if payload.joining_staff_date is not None:
            profile.joining_staff_date = payload.joining_staff_date

        # Update trainer details
        for field, value in payload.model_dump(exclude={"full_name", "phone", "is_active", "salary", "joining_staff_date"}, exclude_unset=True).items():
            setattr(trainer, field, value)

        db.commit()
        db.refresh(trainer)

        res_data = _map_trainer_to_response(trainer, db)
        return success_response(message="Trainer updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_trainer] error during database modification: {str(e)}")
        raise e


@router.post("/{trainer_id}/assign-member", response_model=None)
def assign_member(
    trainer_id: UUID,
    payload: AssignMemberRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Assign a member to a trainer's active coaching roster."""
    logger.info(f"[assign_member] user={current_user.user_id} trainer={trainer_id} member={payload.member_id}")

    trainer = db.query(Trainer).filter(Trainer.id == trainer_id, Trainer.is_deleted == False).first()
    if not trainer:
        raise NotFoundException(message="Trainer not found")

    member = db.query(Member).filter(Member.id == payload.member_id, Member.is_deleted == False).first()
    if not member:
        raise NotFoundException(message="Member not found")

    # Check if assignment already exists
    stmt = db.query(trainer_members).filter_by(
        trainer_id=trainer_id,
        member_id=payload.member_id
    ).first()

    if stmt:
        if stmt.is_active:
            raise ConflictException(message="Member is already assigned to this trainer")
        else:
            # Re-activate assignment
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
                logger.error(f"[assign_member] error re-activating assignment: {str(e)}")
                raise e

    try:
        # Insert new assignment link
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
        logger.error(f"[assign_member] error inserting assignment: {str(e)}")
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

    # Check if active assignment exists
    stmt = db.query(trainer_members).filter_by(
        trainer_id=trainer_id,
        member_id=payload.member_id,
        is_active=True
    ).first()

    if not stmt:
        raise NotFoundException(message="Active coaching assignment not found")

    try:
        # Mark assignment as inactive
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
        logger.error(f"[unassign_member] error updating assignment: {str(e)}")
        raise e


@router.delete("/{trainer_id}", response_model=None)
def delete_trainer(
    trainer_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Deactivate (soft delete) a trainer account (Admin only)."""
    logger.info(f"[delete_trainer] user={current_user.user_id} action=delete target={trainer_id}")

    trainer = db.query(Trainer).join(Trainer.profile).filter(
        Trainer.id == trainer_id,
        Trainer.is_deleted == False
    ).first()

    if not trainer:
        raise NotFoundException(message=f"Trainer not found")

    profile = trainer.profile
    user = db.query(User).filter(User.id == profile.user_id).first()

    try:
        # Soft delete trainer details
        trainer.soft_delete(updater_id=current_user.user_id)

        # Soft delete associated credentials
        if user:
            user.soft_delete(updater_id=current_user.user_id)
            user.is_active = False

        db.commit()
        return success_response(message="Trainer deactivated successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_trainer] error during soft deletion: {str(e)}")
        raise e
