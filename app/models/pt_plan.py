"""
SQLAlchemy model representing Personal Trainer packages.
"""

from typing import Optional
from sqlalchemy import String, Integer, Text, DECIMAL, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin


class PTPlan(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    PTPlan model representing Personal Trainer packages (e.g. Silver, Gold, Platinum)
    with base pricing, session count, features and flags.
    """
    __tablename__ = "pt_plans"
    __table_args__ = (
        {"comment": "Stores personal trainer subscription packages and features"},
    )

    package_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Name of the package (e.g. Silver, Gold, Platinum)"
    )
    price: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Monthly price of the PT package in INR"
    )
    session_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of coaching sessions included in this package"
    )
    whatsapp_support: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if WhatsApp support is included"
    )
    locker_included: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if locker facility is included"
    )
    transformation_included: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if transformation guidance is included"
    )
    diet_included: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if diet plans are included"
    )
    stretching_included: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if stretching sessions are included"
    )
    supplement_guidance: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if supplement guidance is included"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the package"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if package is active and purchaseable"
    )
