"""
SQLAlchemy profile model capturing personal details of users.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING
# pyrefly: ignore [missing-import]
import sqlalchemy
# pyrefly: ignore [missing-import]
from sqlalchemy import String, Date, Text, Uuid, ForeignKey, Integer, DECIMAL
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.member import Member
    from app.models.trainer import Trainer


class Gender(str, Enum):
    """Gender enumeration for user profiles"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Profile(Base, UUIDMixin, AuditMixin):
    """
    Profile model housing contact information and demographic metadata
    for users (members, trainers, or staff).
    """
    __tablename__ = "profiles"
    __table_args__ = (
        {"comment": "Stores personal profile and demographic details linked to user credentials"},
    )

    user_id: Mapped[Optional[sqlalchemy.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="Foreign key referencing the associated user account"
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Legal full name of the user"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        index=True,
        nullable=True,
        comment="Primary contact phone number"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="URL pointing to profile image file in storage"
    )
    date_of_birth: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Date of birth of the user"
    )
    gender: Mapped[Optional[Gender]] = mapped_column(
        sqlalchemy.Enum(Gender, name="gender"),
        nullable=True,
        comment="Gender classification (male, female, other)"
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Residential address of the user"
    )
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Full name of emergency contact person"
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Phone number of emergency contact person"
    )
    biometric_device_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        index=True,
        nullable=True,
        comment="eSSL Biometric PIN mapping users to attendance device scans"
    )
    salary: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(10, 2),
        nullable=True,
        comment="Monthly salary for staff members (null for regular members)"
    )
    shift: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Work shift for receptionists: morning/evening/full-day"
    )
    joining_staff_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Staff employment start date (separate from member joining_date)"
    )
    occupation: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Occupation or profession of the member"
    )
    height: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(5, 2),
        nullable=True,
        comment="Height of the member in cm"
    )
    weight: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(5, 2),
        nullable=True,
        comment="Weight of the member in kg"
    )
    medical_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Medical conditions or health notes"
    )
    emergency_relation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Relationship of the emergency contact to the member"
    )


    # Relationships
    user: Mapped["User"] = relationship(back_populates="profile")
    member: Mapped[Optional["Member"]] = relationship(
        back_populates="profile",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    trainer: Mapped[Optional["Trainer"]] = relationship(
        back_populates="profile",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True
    )
