"""
SQLAlchemy membership plan model representing gym membership plan templates.
"""

from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Text, JSON, DECIMAL, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.membership import Membership


class MembershipPlan(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    MembershipPlan model representing membership templates containing pricing,
    features, and durations (e.g. 1 Month Basic, Annual Premium).
    """
    __tablename__ = "membership_plans"
    __table_args__ = (
        {"comment": "Stores gym membership plan configurations and pricing metrics"},
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Unique identifier name of the membership plan (e.g. Basic Monthly)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of what the plan includes"
    )
    duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Duration of the membership plan in days"
    )
    price: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Cost of the membership plan in the specified currency"
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="INR",
        nullable=False,
        comment="Currency ISO code (default INR)"
    )
    features: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON list of feature strings describing what features this plan unlocks"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if the plan is available for new subscriptions"
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Order of appearance of the plan in listing pages"
    )

    # Relationships
    memberships: Mapped[List["Membership"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
