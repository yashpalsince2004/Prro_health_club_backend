"""
SQLAlchemy diet plan and diet item models.
"""

from datetime import date
from enum import Enum
from typing import Optional, List, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import String, Integer, Text, Uuid, ForeignKey, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.trainer import Trainer


class MealType(str, Enum):
    """Meal type categorization for diet planning"""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    PRE_WORKOUT = "pre_workout"
    POST_WORKOUT = "post_workout"


class DietPlan(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    DietPlan model representing nutritional regimes assigned to members.
    """
    __tablename__ = "diet_plans"
    __table_args__ = (
        {"comment": "Stores overall diet plans prescribed to members by trainers"},
    )

    member_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing the member undergoing diet management"
    )
    trainer_id: Mapped[Optional[sqlalchemy.UUID]] = mapped_column(
        Uuid,
        ForeignKey("trainers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing the trainer prescribing the nutrition"
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Heading title of the diet program"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Explanatory description of diet targets"
    )
    daily_calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Target overall daily calories"
    )
    protein_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Target daily protein intake in grams"
    )
    carbs_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Target daily carbohydrates intake in grams"
    )
    fat_grams: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Target daily fat intake in grams"
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Beginning date of the diet plan"
    )
    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Ending date of the diet plan"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if this diet plan is active"
    )

    # Relationships
    member: Mapped["Member"] = relationship(back_populates="diet_plans")
    trainer: Mapped[Optional["Trainer"]] = relationship(back_populates="diet_plans")
    items: Mapped[List["DietItem"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class DietItem(Base, UUIDMixin):
    """
    DietItem model representing specific food details for a meal in a diet plan.
    """
    __tablename__ = "diet_items"
    __table_args__ = (
        {"comment": "Stores specific food items, caloric values, and portions linked to diet plans"},
    )

    plan_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("diet_plans.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing the associated diet plan"
    )
    meal_type: Mapped[MealType] = mapped_column(
        sqlalchemy.Enum(MealType, name="mealtype"),
        nullable=False,
        comment="Meal type categorization (breakfast, lunch, snack, etc.)"
    )
    food_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Name of the food item (e.g. Oats, Egg Whites, Chicken Breast)"
    )
    quantity: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Portion quantity (e.g. 100, 2, 1.5)"
    )
    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Portion measurement unit (e.g. grams, ml, pieces)"
    )
    calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Calculated calorie count of this food portion"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Preparation or eating instructions"
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sequence index order of the food item in the meal"
    )

    # Relationships
    plan: Mapped["DietPlan"] = relationship(back_populates="items")
