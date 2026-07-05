from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin

class GymSettings(Base, UUIDMixin, AuditMixin):
    __tablename__ = "gym_settings"
    __table_args__ = (
        {"comment": "Stores gym operating configuration parameters (e.g. Opening times, GST %, currencies)"},
    )
    
    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="Settings parameter key lookup identifier"
    )
    value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Configured string value payload"
    )
    category: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False,
        comment="Settings categorization grouping (general, finance, notifications, hours)"
    )
    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human readable descriptive title"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Help text explanation of setting parameter use"
    )
