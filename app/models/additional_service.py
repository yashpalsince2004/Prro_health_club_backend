"""
SQLAlchemy model representing Additional Services.
"""

from typing import Optional
from sqlalchemy import String, DECIMAL, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin


class AdditionalService(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    AdditionalService model representing gym services (e.g. Massages, Consultation, BMI).
    """
    __tablename__ = "additional_services"
    __table_args__ = (
        {"comment": "Stores optional additional services configurations and pricing"},
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Name of the service (e.g. Body Massage, Premium Massage)"
    )
    price: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Price of the service in INR"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the service"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if the service is active and purchaseable"
    )
