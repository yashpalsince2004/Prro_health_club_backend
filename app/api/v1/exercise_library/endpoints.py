import math
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.exceptions import NotFoundException, ConflictException
from app.core.constants import UserRole
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.exercise_library import ExerciseLibrary, MuscleGroup
from app.api.v1.exercise_library.schemas import (
    ExerciseCreate,
    ExerciseUpdate,
    ExerciseResponse
)

router = APIRouter()

def _map_exercise_to_response(e: ExerciseLibrary) -> ExerciseResponse:
    return ExerciseResponse(
        id=e.id,
        name=e.name,
        muscle_group=e.muscle_group,
        equipment=e.equipment,
        description=e.description,
        default_sets=e.default_sets,
        default_reps=e.default_reps,
        default_rest_seconds=e.default_rest_seconds,
        is_active=e.is_active
    )

@router.get("/")
def search_exercises(
    search: Optional[str] = Query(None),
    muscle_group: Optional[MuscleGroup] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Search the exercise library catalog (Any Authenticated User)."""
    query = db.query(ExerciseLibrary).filter(ExerciseLibrary.is_active == True)

    if search:
        query = query.filter(ExerciseLibrary.name.ilike(f"%{search}%"))
    if muscle_group:
        query = query.filter(ExerciseLibrary.muscle_group == muscle_group)

    total = query.count()
    offset = (page - 1) * per_page
    exercises = query.order_by(ExerciseLibrary.name.asc()).offset(offset).limit(per_page).all()

    mapped_exercises = [_map_exercise_to_response(e) for e in exercises]

    return paginated_response(
        message="Exercises retrieved successfully",
        data=mapped_exercises,
        page=page,
        limit=per_page,
        total=total
    )

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_exercise(
    payload: ExerciseCreate,
    db: Session = Depends(get_db),
    current_admin: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Add a new exercise to the library (Admin only)."""
    existing = db.query(ExerciseLibrary).filter(
        ExerciseLibrary.name.ilike(payload.name)
    ).first()
    
    if existing:
        raise ConflictException(message=f"Exercise with name '{payload.name}' already exists in library")

    new_exercise = ExerciseLibrary(
        name=payload.name,
        muscle_group=payload.muscle_group,
        equipment=payload.equipment,
        description=payload.description,
        default_sets=payload.default_sets,
        default_reps=payload.default_reps,
        default_rest_seconds=payload.default_rest_seconds,
        is_active=True
    )
    db.add(new_exercise)
    db.commit()
    db.refresh(new_exercise)

    return success_response(
        message="Exercise added to library",
        data=_map_exercise_to_response(new_exercise),
        status_code=status.HTTP_201_CREATED
    )

@router.patch("/{exercise_id}")
def update_exercise(
    exercise_id: UUID,
    payload: ExerciseUpdate,
    db: Session = Depends(get_db),
    current_admin: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update exercise configuration or settings in the library (Admin only)."""
    exercise = db.query(ExerciseLibrary).filter(ExerciseLibrary.id == exercise_id).first()
    if not exercise:
        raise NotFoundException(message="Exercise not found in library")

    if payload.name is not None:
        existing = db.query(ExerciseLibrary).filter(
            ExerciseLibrary.name.ilike(payload.name),
            ExerciseLibrary.id != exercise_id
        ).first()
        if existing:
            raise ConflictException(message=f"Exercise with name '{payload.name}' already exists")
        exercise.name = payload.name

    if payload.muscle_group is not None:
        exercise.muscle_group = payload.muscle_group
    if payload.equipment is not None:
        exercise.equipment = payload.equipment
    if payload.description is not None:
        exercise.description = payload.description
    if payload.default_sets is not None:
        exercise.default_sets = payload.default_sets
    if payload.default_reps is not None:
        exercise.default_reps = payload.default_reps
    if payload.default_rest_seconds is not None:
        exercise.default_rest_seconds = payload.default_rest_seconds
    if payload.is_active is not None:
        exercise.is_active = payload.is_active

    db.commit()
    db.refresh(exercise)

    return success_response(
        message="Exercise updated successfully",
        data=_map_exercise_to_response(exercise)
    )

@router.delete("/{exercise_id}")
def delete_exercise(
    exercise_id: UUID,
    db: Session = Depends(get_db),
    current_admin: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Deactivate / soft-delete exercise from the active library catalog (Admin only)."""
    exercise = db.query(ExerciseLibrary).filter(ExerciseLibrary.id == exercise_id).first()
    if not exercise:
        raise NotFoundException(message="Exercise not found in library")

    exercise.is_active = False
    db.commit()

    return success_response(message="Exercise deactivated successfully")
