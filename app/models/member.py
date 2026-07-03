"""
SQLAlchemy member model representing gym members.
"""

from datetime import date
from typing import Optional, List, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import Date, Text, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin
from app.models.association import trainer_members

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.membership import Membership
    from app.models.payment import Payment
    from app.models.attendance import AttendanceLog
    from app.models.workout import WorkoutPlan
    from app.models.diet import DietPlan
    from app.models.trainer import Trainer


class Member(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    Member model representing individual gym customers. Contains links
    to active memberships, workouts, diet plans, and attendance data.
    """
    __tablename__ = "members"
    __table_args__ = (
        {"comment": "Stores gym member records linked to user profiles"},
    )

    profile_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="Foreign key referencing the associated personal profile"
    )
    joining_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date when the member officially joined the gym"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="General admin or receptionist notes about the member"
    )

    # Relationships
    profile: Mapped["Profile"] = relationship(back_populates="member")
    memberships: Mapped[List["Membership"]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    workout_plans: Mapped[List["WorkoutPlan"]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    diet_plans: Mapped[List["DietPlan"]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    trainers: Mapped[List["Trainer"]] = relationship(
        secondary=trainer_members,
        back_populates="assigned_members"
    )
