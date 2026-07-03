import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, declarative_mixin


@declarative_mixin
class UUIDMixin:
    """Mixin that adds a database-agnostic UUID primary key"""
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )


@declarative_mixin
class TimestampMixin:
    """Mixin that adds timezone-aware created_at and updated_at datetime tracking"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )


@declarative_mixin
class AuditMixin:
    """Mixin that tracks the user who created and last modified a record"""
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True
    )


@declarative_mixin
class SoftDeleteMixin:
    """Mixin that implements soft delete columns and logic"""
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    def soft_delete(self, updater_id: Optional[uuid.UUID] = None) -> None:
        """Mark record as deleted and set timestamps"""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        if updater_id:
            self.updated_by = updater_id


@declarative_mixin
class StatusMixin:
    """Mixin that adds a standard status indicator string field (e.g. active, suspended)"""
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
        index=True
    )


@declarative_mixin
class TenantMixin:
    """Mixin that supports multi-branch and multi-gym SaaS design"""
    # gym_id isolates gym tenants in a multi-tenant shared database setup
    gym_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
        index=True
    )
    # branch_id isolates branches within a single gym
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        index=True
    )
