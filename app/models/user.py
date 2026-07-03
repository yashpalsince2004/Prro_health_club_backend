"""
SQLAlchemy user model representing authenticated system users.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin, SoftDeleteMixin
from app.core.constants import UserRole

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.notification import Notification


class User(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """
    User model representing individuals authenticated on the platform
    (Admins, Receptionists, Trainers, and Members).
    """
    __tablename__ = "users"
    __table_args__ = (
        {"comment": "Stores user credentials, activation status, and role definitions"},
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Primary login email address, unique across all users"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Securely hashed password string (Bcrypt)"
    )
    role: Mapped[UserRole] = mapped_column(
        sqlalchemy.Enum(UserRole, name="userrole"),
        nullable=False,
        comment="System role defining permission scopes (admin, receptionist, trainer, member)"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Flag indicating if the user account is active"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the user's last successful login"
    )

    # Relationships
    profile: Mapped[Optional["Profile"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="recipient",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
