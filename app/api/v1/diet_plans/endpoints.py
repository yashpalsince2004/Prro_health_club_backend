"""
FastAPI route handlers for Trainer prescribing Diet Plans.
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
from app.models.diet import DietPlan, DietItem, MealType
from app.models.member import Member
from app.models.trainer import Trainer
from app.models.profile import Profile
from app.models.association import trainer_members
from app.api.v1.diet_plans.schemas import (
    DietPlanCreate,
    DietPlanUpdate,
    DietPlanResponse,
    DietItemCreate,
    DietItemUpdate,
    DietItemResponse
)

router = APIRouter()

meal_labels = {
    MealType.BREAKFAST: "Breakfast",
    MealType.LUNCH: "Lunch",
    MealType.DINNER: "Dinner",
    MealType.SNACK: "Snack",
    MealType.PRE_WORKOUT: "Pre Workout",
    MealType.POST_WORKOUT: "Post Workout"
}


def _map_diet_plan_to_response(plan: DietPlan) -> DietPlanResponse:
    """Helper to map a DietPlan db model to DietPlanResponse grouping items by meal type."""
    items_by_meal = {label: [] for label in meal_labels.values()}
    total_tracked_calories = 0

    sorted_items = sorted(plan.items, key=lambda x: (x.meal_type, x.order_index))
    for item in sorted_items:
        label = meal_labels.get(item.meal_type, "Snack")
        items_by_meal[label].append(
            DietItemResponse(
                id=item.id,
                meal_type=item.meal_type,
                meal_type_label=label,
                food_name=item.food_name,
                quantity=item.quantity,
                unit=item.unit,
                calories=item.calories,
                notes=item.notes,
                order_index=item.order_index
            )
        )
        if item.calories:
            total_tracked_calories += item.calories

    member_profile = plan.member.profile if plan.member else None
    member_name = member_profile.full_name if member_profile else "Unknown Member"
    
    trainer_profile = plan.trainer.profile if plan.trainer else None
    trainer_name = trainer_profile.full_name if trainer_profile else None

    return DietPlanResponse(
        id=plan.id,
        member_id=plan.member_id,
        member_name=member_name,
        trainer_id=plan.trainer_id,
        trainer_name=trainer_name,
        title=plan.title,
        description=plan.description,
        daily_calories=plan.daily_calories,
        protein_grams=plan.protein_grams,
        carbs_grams=plan.carbs_grams,
        fat_grams=plan.fat_grams,
        start_date=plan.start_date,
        end_date=plan.end_date,
        is_active=plan.is_active,
        items_by_meal=items_by_meal,
        total_tracked_calories=total_tracked_calories
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
def create_diet_plan(
    payload: DietPlanCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Create a new nutrition plan for a member."""
    logger.info(f"[create_diet_plan] user={current_user.user_id} member={payload.member_id} title='{payload.title}'")

    # Resolve trainer details if caller is trainer
    trainer_id = None
    if current_user.role == UserRole.TRAINER:
        trainer_id = _get_trainer_record_id(db, current_user.user_id)
        _verify_trainer_assignment(db, trainer_id, payload.member_id)

    # 1. Deactivate other active diet plans for this member (one active plan at a time)
    db.query(DietPlan).filter(
        DietPlan.member_id == payload.member_id,
        DietPlan.is_active == True
    ).update({DietPlan.is_active: False})

    try:
        # 2. Insert new diet plan
        new_plan = DietPlan(
            member_id=payload.member_id,
            trainer_id=trainer_id,
            title=payload.title,
            description=payload.description,
            daily_calories=payload.daily_calories,
            protein_grams=payload.protein_grams,
            carbs_grams=payload.carbs_grams,
            fat_grams=payload.fat_grams,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=True
        )
        db.add(new_plan)
        db.flush()  # Generate plan ID

        # 3. Add items in bulk
        for item in payload.items:
            new_item = DietItem(
                plan_id=new_plan.id,
                meal_type=item.meal_type,
                food_name=item.food_name,
                quantity=item.quantity,
                unit=item.unit,
                calories=item.calories,
                notes=item.notes,
                order_index=item.order_index
            )
            db.add(new_item)

        db.commit()

        # Eager load relationships for mapping
        plan_with_relations = db.query(DietPlan).options(
            joinedload(DietPlan.member).joinedload(Member.profile),
            joinedload(DietPlan.trainer).joinedload(Trainer.profile),
            joinedload(DietPlan.items)
        ).filter(DietPlan.id == new_plan.id).first()

        res_data = _map_diet_plan_to_response(plan_with_relations)

        # Fire notification side-effect
        try:
            from app.api.v1.notifications.service import notify_plan_assigned
            member_user_id = db.query(Profile.user_id).join(Member).filter(Member.id == payload.member_id).scalar()
            if member_user_id:
                notify_plan_assigned(db, member_user_id=member_user_id, plan_type="Diet Plan", plan_id=new_plan.id)
        except Exception as notify_err:
            logger.error(f"Failed to trigger plan notification (non-critical): {str(notify_err)}")

        return success_response(message="Diet plan created successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[create_diet_plan] error: {str(e)}")
        raise e


@router.get("/", response_model=None)
def list_diet_plans(
    member_id: Optional[UUID] = Query(None),
    trainer_id: Optional[UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """List and filter diet programs."""
    logger.info(f"[list_diet_plans] user={current_user.user_id}")

    query = db.query(DietPlan).filter(DietPlan.is_deleted == False)

    # Filter logic
    if member_id:
        query = query.filter(DietPlan.member_id == member_id)
    if trainer_id:
        query = query.filter(DietPlan.trainer_id == trainer_id)
    if is_active is not None:
        query = query.filter(DietPlan.is_active == is_active)

    # Trainer access enforcement: Trainers only see their assigned members' plans
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        # Filter where member is assigned to this trainer
        query = query.filter(
            DietPlan.member_id.in_(
                db.query(trainer_members.c.member_id).filter(
                    trainer_members.c.trainer_id == t_rec_id,
                    trainer_members.c.is_active == True
                )
            )
        )

    total = query.count()
    plans = query.options(
        joinedload(DietPlan.member).joinedload(Member.profile),
        joinedload(DietPlan.trainer).joinedload(Trainer.profile),
        joinedload(DietPlan.items)
    ).order_by(DietPlan.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    mapped_list = [_map_diet_plan_to_response(p).model_dump() for p in plans]
    return paginated_response(
        message="Diet plans retrieved",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )


@router.get("/my-plan", response_model=None)
def get_my_diet_plan(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.MEMBER]))
):
    """Retrieve the single active diet plan assigned to the logged-in member."""
    logger.info(f"[get_my_diet_plan] member={current_user.user_id}")

    plan = db.query(DietPlan).options(
        joinedload(DietPlan.member).joinedload(Member.profile),
        joinedload(DietPlan.trainer).joinedload(Trainer.profile),
        joinedload(DietPlan.items)
    ).join(Member).join(Profile).filter(
        Profile.user_id == current_user.user_id,
        DietPlan.is_active == True,
        DietPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="No active diet plan has been prescribed for you yet")

    res_data = _map_diet_plan_to_response(plan)
    return success_response(message="Active diet plan retrieved", data=res_data.model_dump())


@router.get("/{plan_id}", response_model=None)
def get_diet_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details of a single diet plan."""
    logger.info(f"[get_diet_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(DietPlan).options(
        joinedload(DietPlan.member).joinedload(Member.profile),
        joinedload(DietPlan.trainer).joinedload(Trainer.profile),
        joinedload(DietPlan.items)
    ).filter(
        DietPlan.id == plan_id,
        DietPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Diet plan not found")

    # Member ownership check
    if current_user.role == UserRole.MEMBER:
        if plan.member.profile.user_id != current_user.user_id:
            raise AuthorizationException(message="You are not authorized to view this diet plan")
            
    # Trainer access enforcement
    elif current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        _verify_trainer_assignment(db, t_rec_id, plan.member_id)

    res_data = _map_diet_plan_to_response(plan)
    return success_response(message="Diet plan retrieved", data=res_data.model_dump())


@router.patch("/{plan_id}", response_model=None)
def update_diet_plan(
    plan_id: UUID,
    payload: DietPlanUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Update metadata fields of a diet plan (Trainer who owns it or Admin)."""
    logger.info(f"[update_diet_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(DietPlan).options(
        joinedload(DietPlan.member).joinedload(Member.profile),
        joinedload(DietPlan.trainer).joinedload(Trainer.profile),
        joinedload(DietPlan.items)
    ).filter(
        DietPlan.id == plan_id,
        DietPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Diet plan not found")

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

        res_data = _map_diet_plan_to_response(plan)
        return success_response(message="Diet plan updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_diet_plan] error: {str(e)}")
        raise e


@router.post("/{plan_id}/items", response_model=None)
def add_diet_items(
    plan_id: UUID,
    items: List[DietItemCreate],
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Add a list of food items to an existing diet plan (Bulk insert)."""
    logger.info(f"[add_diet_items] user={current_user.user_id} target={plan_id}")

    plan = db.query(DietPlan).filter(DietPlan.id == plan_id, DietPlan.is_deleted == False).first()
    if not plan:
        raise NotFoundException(message="Diet plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only add items to plans created by yourself")

    try:
        for item in items:
            new_item = DietItem(
                plan_id=plan_id,
                meal_type=item.meal_type,
                food_name=item.food_name,
                quantity=item.quantity,
                unit=item.unit,
                calories=item.calories,
                notes=item.notes,
                order_index=item.order_index
            )
            db.add(new_item)
        db.commit()

        # Reload with relations
        updated_plan = db.query(DietPlan).options(
            joinedload(DietPlan.member).joinedload(Member.profile),
            joinedload(DietPlan.trainer).joinedload(Trainer.profile),
            joinedload(DietPlan.items)
        ).filter(DietPlan.id == plan_id).first()

        res_data = _map_diet_plan_to_response(updated_plan)
        return success_response(message="Diet items added to plan successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[add_diet_items] error: {str(e)}")
        raise e


@router.patch("/{plan_id}/items/{item_id}", response_model=None)
def update_diet_item(
    plan_id: UUID,
    item_id: UUID,
    payload: DietItemUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Update detail attributes of a single food item in a diet plan."""
    logger.info(f"[update_diet_item] user={current_user.user_id} plan={plan_id} item={item_id}")

    plan = db.query(DietPlan).filter(DietPlan.id == plan_id, DietPlan.is_deleted == False).first()
    if not plan:
        raise NotFoundException(message="Diet plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only edit items on plans created by yourself")

    item = db.query(DietItem).filter(
        DietItem.id == item_id,
        DietItem.plan_id == plan_id
    ).first()

    if not item:
        raise NotFoundException(message="Diet item not found in this diet plan")

    try:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        db.commit()

        # Reload and return updated plan
        updated_plan = db.query(DietPlan).options(
            joinedload(DietPlan.member).joinedload(Member.profile),
            joinedload(DietPlan.trainer).joinedload(Trainer.profile),
            joinedload(DietPlan.items)
        ).filter(DietPlan.id == plan_id).first()

        res_data = _map_diet_plan_to_response(updated_plan)
        return success_response(message="Diet item updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_diet_item] error: {str(e)}")
        raise e


@router.delete("/{plan_id}/items/{item_id}", response_model=None)
def remove_diet_item(
    plan_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Remove a specific food item from a diet plan."""
    logger.info(f"[remove_diet_item] user={current_user.user_id} plan={plan_id} item={item_id}")

    plan = db.query(DietPlan).filter(DietPlan.id == plan_id, DietPlan.is_deleted == False).first()
    if not plan:
        raise NotFoundException(message="Diet plan not found")

    # Authorizations
    if current_user.role == UserRole.TRAINER:
        t_rec_id = _get_trainer_record_id(db, current_user.user_id)
        if plan.trainer_id != t_rec_id:
            raise AuthorizationException(message="You can only modify items on plans created by yourself")

    item = db.query(DietItem).filter(
        DietItem.id == item_id,
        DietItem.plan_id == plan_id
    ).first()

    if not item:
        raise NotFoundException(message="Diet item not found in this diet plan")

    try:
        db.delete(item)
        db.commit()

        # Reload and return updated plan
        updated_plan = db.query(DietPlan).options(
            joinedload(DietPlan.member).joinedload(Member.profile),
            joinedload(DietPlan.trainer).joinedload(Trainer.profile),
            joinedload(DietPlan.items)
        ).filter(DietPlan.id == plan_id).first()

        res_data = _map_diet_plan_to_response(updated_plan)
        return success_response(message="Diet item removed from plan", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[remove_diet_item] error: {str(e)}")
        raise e


@router.delete("/{plan_id}", response_model=None)
def delete_diet_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.TRAINER]))
):
    """Soft delete a diet plan (Trainer who owns it or Admin)."""
    logger.info(f"[delete_diet_plan] user={current_user.user_id} target={plan_id}")

    plan = db.query(DietPlan).filter(
        DietPlan.id == plan_id,
        DietPlan.is_deleted == False
    ).first()

    if not plan:
        raise NotFoundException(message="Diet plan not found")

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
        return success_response(message="Diet plan deleted successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_diet_plan] error: {str(e)}")
        raise e
