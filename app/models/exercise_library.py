from enum import Enum
from typing import Optional
import sqlalchemy
from sqlalchemy import String, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin

class MuscleGroup(str, Enum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    LEGS = "legs"
    GLUTES = "glutes"
    CORE = "core"
    CARDIO = "cardio"
    FULL_BODY = "full_body"

class ExerciseLibrary(Base, UUIDMixin, AuditMixin):
    __tablename__ = "exercise_library"
    __table_args__ = (
        {"comment": "Stores standard workout exercises catalog for trainers to pick from"},
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique name of the exercise"
    )
    muscle_group: Mapped[MuscleGroup] = mapped_column(
        sqlalchemy.Enum(MuscleGroup, name="musclegroup"),
        nullable=False,
        comment="Primary target muscle group"
    )
    equipment: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Required training equipment (e.g. Barbell, Dumbbell)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Short explanation or video URL instructions"
    )
    default_sets: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Default recommended sets count"
    )
    default_reps: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Default recommended repetitions count"
    )
    default_rest_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Default recommended rest period in seconds"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active status flag"
    )
