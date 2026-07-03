"""
SQLAlchemy trainer model representing gym trainers.
"""

from typing import Optional, List, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import String, Integer, Text, JSON, Uuid, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin
from app.models.association import trainer_members

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.member import Member
    from app.models.workout import WorkoutPlan
    from app.models.diet import DietPlan


class Trainer(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    Trainer model representing fitness instructors. Tracks biography,
    experience years, certifications, availability, and assigned members.
    """
    __tablename__ = "trainers"
    __table_args__ = (
        {"comment": "Stores gym trainer details linked to user profiles"},
    )

    profile_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="Foreign key referencing the associated personal profile"
    )
    specialization: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Trainer's specialization area (e.g. Strength, Yoga, Cardio)"
    )
    experience_years: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of years of professional fitness training experience"
    )
    certifications: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON list of certification names/credentials held by the trainer"
    )
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Short biography or personal description of the trainer"
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if the trainer is currently accepting new members"
    )

    # Relationships
    profile: Mapped["Profile"] = relationship(back_populates="trainer")
    assigned_members: Mapped[List["Member"]] = relationship(
        secondary=trainer_members,
        back_populates="trainers"
    )
    workout_plans: Mapped[List["WorkoutPlan"]] = relationship(
        back_populates="trainer",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    diet_plans: Mapped[List["DietPlan"]] = relationship(
        back_populates="trainer",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
