"""
SQLAlchemy workout plan and exercise models.
"""

from datetime import date
from typing import Optional, List, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import String, Integer, Text, Uuid, ForeignKey, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.trainer import Trainer


class WorkoutPlan(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    WorkoutPlan model representing training programs assigned to members.
    """
    __tablename__ = "workout_plans"
    __table_args__ = (
        {"comment": "Stores overall workout plans prescribed to members by trainers"},
    )

    member_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing the member undergoing training"
    )
    trainer_id: Mapped[Optional[sqlalchemy.UUID]] = mapped_column(
        Uuid,
        ForeignKey("trainers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing the trainer prescribing the plan"
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Heading title of the workout program"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Explanatory description of plan focus or remarks"
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Beginning date of the workout plan"
    )
    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Ending date of the workout plan"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if this workout program is active"
    )

    # Relationships
    member: Mapped["Member"] = relationship(back_populates="workout_plans")
    trainer: Mapped[Optional["Trainer"]] = relationship(back_populates="workout_plans")
    exercises: Mapped[List["WorkoutExercise"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class WorkoutExercise(Base, UUIDMixin):
    """
    WorkoutExercise model representing specific exercise steps on days of the week.
    """
    __tablename__ = "workout_exercises"
    __table_args__ = (
        {"comment": "Stores exercise items, sets, reps, and pacing linked to workout plans"},
    )

    plan_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("workout_plans.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing the associated workout plan"
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="ISO day index (1 = Monday, 7 = Sunday) when this exercise occurs"
    )
    exercise_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Name of the exercise (e.g. Squat, Bench Press)"
    )
    sets: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Prescribed sets quantity"
    )
    reps: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Prescribed reps per set"
    )
    duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration in minutes (for cardio/endurance)"
    )
    rest_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Rest time in seconds between sets"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Pacing or equipment instructions"
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Sequence index order of the exercise in the plan"
    )

    # Relationships
    plan: Mapped["WorkoutPlan"] = relationship(back_populates="exercises")
