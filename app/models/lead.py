from datetime import date
from enum import Enum
from typing import Optional
import uuid
import sqlalchemy
from sqlalchemy import String, Integer, Date, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin
from app.models.profile import Gender

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    TRIAL = "trial"
    CONVERTED = "converted"
    LOST = "lost"

class LeadSource(str, Enum):
    WALK_IN = "walk_in"
    REFERRAL = "referral"
    SOCIAL_MEDIA = "social_media"
    PHONE = "phone"
    OTHER = "other"

class Lead(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "leads"
    __table_args__ = ({"comment": "Walk-in and prospective member tracking"},)

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Full name of the prospective member"
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        index=True,
        nullable=False,
        comment="Contact phone number"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email address of the lead"
    )
    age: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Age of the lead"
    )
    gender: Mapped[Optional[Gender]] = mapped_column(
        sqlalchemy.Enum(Gender, name="lead_gender"),
        nullable=True,
        comment="Gender classification"
    )
    interest: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary fitness interest (e.g. Weight Loss, Muscle Gain)"
    )
    source: Mapped[LeadSource] = mapped_column(
        sqlalchemy.Enum(LeadSource, name="leadsource"),
        default=LeadSource.WALK_IN,
        nullable=False,
        comment="Lead acquisition source"
    )
    status: Mapped[LeadStatus] = mapped_column(
        sqlalchemy.Enum(LeadStatus, name="leadstatus"),
        default=LeadStatus.NEW,
        nullable=False,
        comment="Lead conversion status pipeline state"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Follow up and inquiry logs"
    )
    follow_up_date: Mapped[Optional[date]] = mapped_column(
        Date,
        index=True,
        nullable=True,
        comment="Scheduled follow up date"
    )
    trial_start: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Trial start date"
    )
    trial_end: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Trial end date"
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        sqlalchemy.Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member assigned to manage this lead"
    )
    converted_member_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sqlalchemy.Uuid,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to member ID if converted"
    )
