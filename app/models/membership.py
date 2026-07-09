"""
SQLAlchemy membership model representing member subscriptions to plans.
"""

from datetime import date
from typing import Optional, List, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import Date, Boolean, DECIMAL, Text, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin
from app.core.constants import SubscriptionStatus

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.plan import MembershipPlan
    from app.models.payment import Payment


class Membership(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    Membership model capturing detailed subscriptions of members to membership plans,
    including durations, discount percentages, auto renewal settings, and status.
    """
    __tablename__ = "memberships"
    __table_args__ = (
        {"comment": "Stores active and historical member subscriptions to gym plans"},
    )

    member_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing the associated member"
    )
    plan_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("membership_plans.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Foreign key referencing the associated plan template"
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Official start date of the subscription"
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Official expiration date of the subscription"
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        sqlalchemy.Enum(SubscriptionStatus, name="subscriptionstatus"),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
        comment="Status of subscription (active, expired, paused, pending, cancelled)"
    )
    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if membership automatically renews upon expiration"
    )
    discount_percent: Mapped[float] = mapped_column(
        DECIMAL(5, 2),
        default=0,
        nullable=False,
        comment="Discount percentage applied to the membership"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional comments or context about the membership"
    )
    billing_details: Mapped[Optional[dict]] = mapped_column(
        sqlalchemy.JSON,
        nullable=True,
        comment="JSON snapshot of detailed itemized billing calculations"
    )

    # Relationships
    member: Mapped["Member"] = relationship(back_populates="memberships")
    plan: Mapped["MembershipPlan"] = relationship(back_populates="memberships")
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="membership",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    @property
    def is_expired(self) -> bool:
        """
        Check if the membership subscription has expired compared to the current date.
        Returns True if end_date < date.today() and status is active.
        """
        return self.end_date < date.today() and self.status == SubscriptionStatus.ACTIVE
