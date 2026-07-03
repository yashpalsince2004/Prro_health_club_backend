"""
FastAPI route handlers for Trainer prescribing Workout Plans.
"""

import math
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date, timezone
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session, joinedload
from app.database.session import get_db
from app.core.exceptions import ConflictException, NotFoundException, AuthorizationException
from app.core.constants import UserRole
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.workout import WorkoutPlan, WorkoutExercise
from app.models.member import Member
from app.models.trainer import Trainer
from app.models.profile import Profile
from app.models.association import trainer_members
from app.api.v1.workout_plans.schemas import (
    WorkoutPlanCreate,
    WorkoutPlanUpdate,
    WorkoutPlanResponse,
    ExerciseCreate,
    ExerciseUpdate,
    ExerciseResponse
)

router = APIRouter()

day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}


def _map_workout_plan_to_response(plan: WorkoutPlan) -> WorkoutPlanResponse:
    """Helper to map a WorkoutPlan db model to WorkoutPlanResponse schema grouping exercises by day."""
    # Pre-populate empty lists for all days
    exercises_by_day = {day: [] for day in day_names.values()}
    
    # Sort and populate
    sorted_exercises = sorted(plan.exercises, key=lambda x: (x.day_of_week, x.order_index))
    for ex in sorted_exercises:
        d_name = day_names.get(ex.day_of_week, "Monday")
        exercises_by_day[d_name].append(
            ExerciseResponse(
                id=ex.id,
                day_of_week=ex.day_of_week,
                day_name=d_name,
                exercise_name=ex.exercise_name,
                sets=ex.sets,
                reps=ex.reps,
                duration_minutes=ex.duration_minutes,
                rest_seconds=ex.rest_seconds,
                notes=ex.notes,
                order_index=ex.order_index
            )
        )

    member_profile = plan.member.profile if plan.member else None
    member_name = member_profile.full_name if member_profile else "Unknown Member"
    
    trainer_profile = plan.trainer.profile if plan.trainer else None
    trainer_name = trainer_profile.full_name if trainer_profile else None

    return WorkoutPlanResponse(
        id=plan.id,
        member_id=plan.member_id,
        member_name=member_name,
        trainer_id=plan.trainer_id,
        trainer_name=trainer_name,
        title=plan.title,
        description=plan.description,
        start_date=plan.start_date,
        end_date=plan.end_date,
        is_active=plan.is_active,
        exercises_by_day=exercises_by_day,
        total_exercises=len(plan.exercises)
    )


def _get_trainer_record_id(db: Session, user_id: UUID) -> UUID:
    """Helper to resolve a User ID to a Trainer ID."""
    trainer = db.query(Trainer).join(Trainer.profile).filter(Profile.user_id == user_id).first()
    if not trainer:
        raise AuthorizationException(message="Coaching actions require a trainer profile")
    return trainer.id


def _verify_trainer_assignment(db: Session, trainer_id: UUID, member_id: UUID) -> None:
    """Helper to assert that a trainer is assigned to a member."""
    assignment = db.query(trainer_members).filter_by(
        trainer_id=trainer_id,
        member_id=member_id,
        is_active=True
    ).first()
    if not assignment:
        raise AuthorizationException(message="You are only authorized to manage plans for your assigned members")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def create_workout_plan(
    payload: WorkoutPlanCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Create a new workout program prescription for a member."""
    logger.info(f"[create_workout_plan] user={current_user.user_id} member={payload.member_id} title='{payload.title}'")

    # Resolve trainer details if caller is trainer
    trainer_id = None
    if current_user.role == UserRole.TRAINER:
        trainer_id = _get_trainer_record_id(db, current_user.user_id)
        _verify_trainer_assignment(db, trainer_id, payload.member_id)
    
    # 1. Deactivate other active workout plans for this member (one active plan at a time)
    db.query(WorkoutPlan).filter(
        WorkoutPlan.member_id == payload.member_id,
        WorkoutPlan.is_active == True
    ).update({WorkoutPlan.is_active: False})

    try:
        # 2. Insert new workout plan
        new_plan = WorkoutPlan(
            member_id=payload.member_id,
            trainer_id=trainer_id,
            title=payload.title,
            description=payload.description,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=True
        )
        db.add(new_plan)
        db.flush()  # Generate plan ID

        # 3. Add exercises in bulk
        for ex in payload.exercises:
            new_exercise = WorkoutExercise(
                plan_id=new_plan.id,
                day_of_week=ex.day_of_week,
                exercise_name=ex.exercise_name,
                sets=ex.sets,
                reps=ex.reps,
                duration_minutes=ex.duration_minutes,
                rest_seconds=ex.rest_seconds,
                notes=ex.notes,
                order_index=ex.order_index
            )
            db.add(new_exercise)

        db.commit()

        # Eager load relationships for mapping
        plan_with_relations = db.query(WorkoutPlan).options(
            joinedload(WorkoutPlan.member).joinedload(Member.profile),
            joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
            joinedload(WorkoutPlan.exercises)
        ).filter(WorkoutPlan.id == new_plan.id).first()

        res_data = _map_workout_plan_to_response(plan_with_relations)
        
        # Fire notification side-effect
        try:
            from app.api.v1.notifications.service import notify_plan_assigned
            member_user_id = db.query(Profile.user_id).join(Member).filter(Member.id == payload.member_id).scalar()
            if member_user_id:
                notify_plan_assigned(db, member_user_id=member_user_id, plan_type="Workout Plan", plan_id=new_plan.id)
        except Exception as notify_err:
            logger.error(f"Failed to trigger plan notification (non-critical): {str(notify_err)}")

        return success_response(message="Workout plan created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_workout_plan] error: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_workout_plans(
    member_id: Optional[UUID] = Query(None),
    trainer_id: Optional[UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """List and filter workout programs."""
    logger.info(f"[list_workout_plans] user={current_user.user_id}")

    query = db.query(WorkoutPlan).filter(WorkoutPlan.is_deleted == False)

    # Filter logic
    if member_id:
        query = query.filter(WorkoutPlan.member_id == member_id)
    if trainer_id:
        query = query.filter(WorkoutPlan.trainer_id == trainer_id)
    if is_active is not None:
        query = query.filter(WorkoutPlan.is_active == is_active)

    # Trainer access enforcement: Trainers only see their assigned members' plans
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        # Filter where member is assigned to this trainer
        query = query.filter(
            WorkoutPlan.member_id.in_(
                db.query(trainer_members.c.member_id).filter(
                    trainer_members.c.trainer_id == t_rec_id,
                    trainer_members.c.is_active == True
                )
            )
        )

    total = query.count()
    plans = query.options(
        joinedload(WorkoutPlan.member).joinedload(Member.profile),
        joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
        joinedload(WorkoutPlan.exercises)
    ).order_by(WorkoutPlan.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    mapped_list = [_map_workout_plan_to_response(p).model_dump() for p in plans]
    return paginated_response(
        message="Workout plans retrieved",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )


@router.get("/my-plan", response_model=None)
def get_my_workout_plan(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.MEMBER]))
):
    """Retrieve the single active workout plan assigned to the logged-in member."""
    logger.info(f"[get_my_workout_plan] member={current_user.user_id}")

    plan = db.query(WorkoutPlan).options(
        joinedload(WorkoutPlan.member).joinedload(Member.profile),
        joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
        joinedload(WorkoutPlan.exercises)
    ).join(Member).join(Profile).filter(
        Profile.user_id == current_user.user_id,
        WorkoutPlan.is_active == True,
        WorkoutPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="No active workout plan has been prescribed for you yet")

    res_data = _map_workout_plan_to_response(plan)
    return success_response(message="Active workout plan retrieved", data=res_data.model_dump())


@router.get("/{plan_id}", response_model=None)
def get_workout_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details of a single workout plan."""
    logger.info(f"[get_workout_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(WorkoutPlan).options(
        joinedload(WorkoutPlan.member).joinedload(Member.profile),
        joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
        joinedload(WorkoutPlan.exercises)
    ).filter(
        WorkoutPlan.id == plan_id,
        WorkoutPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Workout plan not found")

    # Member ownership check
    if current_user.role == UserRole.MEMBER:
        if plan.member.profile.user_id != current_user.user_id:
            raise AuthorizationException(message="You are not authorized to view this workout plan")
            
    # Trainer access enforcement
    elif current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        _verify_trainer_assignment(db, t_rec_id, plan.member_id)

    res_data = _map_workout_plan_to_response(plan)
    return success_response(message="Workout plan retrieved", data=res_data.model_dump())


@router.patch("/{plan_id}", response_model=None)
def update_workout_plan(
    plan_id: UUID,
    payload: WorkoutPlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Update metadata fields of a workout plan (Trainer who owns it or Admin)."""
    logger.info(f"[update_workout_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(WorkoutPlan).options(
        joinedload(WorkoutPlan.member).joinedload(Member.profile),
        joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
        joinedload(WorkoutPlan.exercises)
    ).filter(
        WorkoutPlan.id == plan_id,
        WorkoutPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Workout plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only edit plans created by yourself")

    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(plan, field, value)
        db.commit()
        db.refresh(plan)

        res_data = _map_workout_plan_to_response(plan)
        return success_response(message="Workout plan updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_workout_plan] error: {str(e)}")
        raise e


@router.post("/{plan_id}/exercises", response_model=None)
def add_workout_exercises(
    plan_id: UUID,
    exercises: List[ExerciseCreate],
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Add a list of exercises to an existing workout plan (Bulk insert)."""
    logger.info(f"[add_workout_exercises] user={current_user.user_id} target={plan_id}")

    plan = db.query(WorkoutPlan).filter(WorkoutPlan.id == plan_id, WorkoutPlan.is_deleted == False).first()
    if not plan:
        raise NotFoundException(message="Workout plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only add exercises to plans created by yourself")

    try:
        for ex in exercises:
            new_exercise = WorkoutExercise(
                plan_id=plan_id,
                day_of_week=ex.day_of_week,
                exercise_name=ex.exercise_name,
                sets=ex.sets,
                reps=ex.reps,
                duration_minutes=ex.duration_minutes,
                rest_seconds=ex.rest_seconds,
                notes=ex.notes,
                order_index=ex.order_index
            )
            db.add(new_exercise)
        db.commit()

        # Reload with relations
        updated_plan = db.query(WorkoutPlan).options(
            joinedload(WorkoutPlan.member).joinedload(Member.profile),
            joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
            joinedload(WorkoutPlan.exercises)
        ).filter(WorkoutPlan.id == plan_id).first()

        res_data = _map_workout_plan_to_response(updated_plan)
        return success_response(message="Exercises added to plan successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[add_workout_exercises] error: {str(e)}")
        raise e


@router.patch("/{plan_id}/exercises/{exercise_id}", response_model=None)
def update_workout_exercise(
    plan_id: UUID,
    exercise_id: UUID,
    payload: ExerciseUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Update detail attributes of a single exercise in a workout plan."""
    logger.info(f"[update_workout_exercise] user={current_user.user_id} plan={plan_id} exercise={exercise_id}")

    plan = db.query(WorkoutPlan).filter(WorkoutPlan.id == plan_id, WorkoutPlan.is_deleted == False).first()
    if not plan:
        raise NotFoundException(message="Workout plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only edit exercises on plans created by yourself")

    exercise = db.query(WorkoutExercise).filter(
        WorkoutExercise.id == exercise_id,
        WorkoutExercise.plan_id == plan_id
    ).first()

    if not exercise:
        raise NotFoundException(message="Exercise item not found in this workout plan")

    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(exercise, field, value)
        db.commit()

        # Reload and return updated plan
        updated_plan = db.query(WorkoutPlan).options(
            joinedload(WorkoutPlan.member).joinedload(Member.profile),
            joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
            joinedload(WorkoutPlan.exercises)
        ).filter(WorkoutPlan.id == plan_id).first()

        res_data = _map_workout_plan_to_response(updated_plan)
        return success_response(message="Workout exercise updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_workout_exercise] error: {str(e)}")
        raise e


@router.delete("/{plan_id}/exercises/{exercise_id}", response_model=None)
def remove_workout_exercise(
    plan_id: UUID,
    exercise_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Remove a specific exercise from a workout plan."""
    logger.info(f"[remove_workout_exercise] user={current_user.user_id} plan={plan_id} exercise={exercise_id}")

    plan = db.query(WorkoutPlan).filter(WorkoutPlan.id == plan_id, WorkoutPlan.is_deleted == False).first()
    if not plan:
        raise NotFoundException(message="Workout plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only modify exercises on plans created by yourself")

    exercise = db.query(WorkoutExercise).filter(
        WorkoutExercise.id == exercise_id,
        WorkoutExercise.plan_id == plan_id
    ).first()

    if not exercise:
        raise NotFoundException(message="Exercise item not found in this workout plan")

    try:
        db.delete(exercise)
        db.commit()

        # Reload and return updated plan
        updated_plan = db.query(WorkoutPlan).options(
            joinedload(WorkoutPlan.member).joinedload(Member.profile),
            joinedload(WorkoutPlan.trainer).joinedload(Trainer.profile),
            joinedload(WorkoutPlan.exercises)
        ).filter(WorkoutPlan.id == plan_id).first()

        res_data = _map_workout_plan_to_response(updated_plan)
        return success_response(message="Exercise item removed from plan", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[remove_workout_exercise] error: {str(e)}")
        raise e


@router.delete("/{plan_id}", response_model=None)
def delete_workout_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Soft delete a workout plan (Trainer who owns it or Admin)."""
    logger.info(f"[delete_workout_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(WorkoutPlan).filter(
        WorkoutPlan.id == plan_id,
        WorkoutPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Workout plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only delete plans created by yourself")

    try:
        plan.soft_delete(updater_id=current_user.user_id)
        # Deactivate if deleting active plan
        plan.is_active = False
        db.commit()
        return success_response(message="Workout plan deleted successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_workout_plan] error: {str(e)}")
        raise e
