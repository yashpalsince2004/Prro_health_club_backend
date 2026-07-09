"""
SQLAlchemy model representing Locker plans.
"""

from typing import Optional
from sqlalchemy import String, DECIMAL, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin


class LockerPlan(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    LockerPlan model representing gym locker rental packages and deposits.
    """
    __tablename__ = "locker_plans"
    __table_args__ = (
        {"comment": "Stores gym locker rental configurations and deposits"},
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        default="Standard Locker",
        comment="Locker plan descriptor (e.g. Standard Locker)"
    )
    deposit: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Security deposit fee"
    )
    monthly_rent: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Locker rental fee per month"
    )
    quarterly_rent: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Locker rental fee per quarter (3 months)"
    )
    late_fee: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        default=0.00,
        comment="Late return penalty fee"
    )
    refundable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if the deposit is refundable"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if this locker configuration is active"
    )
