"""
Notification model for in-app alerts.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID
import sqlalchemy
from sqlalchemy import String, Text, Uuid, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin


class NotificationType(str, Enum):
    MEMBERSHIP_EXPIRING   = "membership_expiring"    # sent to member + receptionist
    MEMBERSHIP_EXPIRED    = "membership_expired"
    PAYMENT_RECEIVED      = "payment_received"       # sent to member
    UNMATCHED_SCAN        = "unmatched_scan"         # sent to receptionist
    PLAN_ASSIGNED         = "plan_assigned"          # workout/diet plan assigned to member
    GENERAL               = "general"


class Notification(Base, UUIDMixin):
    """
    In-app notifications stored in the DB and loaded by the frontend.
    """
    __tablename__ = "notifications"
    __table_args__ = (
        {"comment": "Stores inside-app notification alerts and delivery receipts"},
    )

    recipient_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key referencing the recipient User"
    )
    type: Mapped[NotificationType] = mapped_column(
        sqlalchemy.Enum(NotificationType, name="notificationtype"),
        nullable=False,
        comment="Type categorization of notification triggers"
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Short summary title of the alert"
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full notification detail description"
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Boolean read indicator flag"
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when user marked notification as read"
    )
    related_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Dynamic reference type (e.g. membership, payment, unmatched_scan)"
    )
    related_entity_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid,
        nullable=True,
        comment="Dynamic primary key reference value"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
        comment="Creation time of the notification"
    )

    # Relationships
    recipient: Mapped["User"] = relationship(back_populates="notifications")
