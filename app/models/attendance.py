"""
SQLAlchemy attendance models tracking valid and unmatched device scans.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import String, Integer, Text, JSON, Uuid, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin
from app.core.constants import AttendanceSource

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.user import User


class AttendanceLog(Base, UUIDMixin, AuditMixin):
    """
    AttendanceLog model tracking validated check-ins/check-outs for members.
    """
    __tablename__ = "attendance_logs"
    __table_args__ = (
        {"comment": "Stores valid check-in and check-out entries for gym members"},
    )

    member_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Foreign key referencing the member who clocked in/out"
    )
    check_in: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        comment="Timestamp of check-in"
    )
    check_out: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of check-out"
    )
    source: Mapped[AttendanceSource] = mapped_column(
        sqlalchemy.Enum(AttendanceSource, name="attendancesource"),
        default=AttendanceSource.BIOMETRIC,
        nullable=False,
        comment="Source of attendance record (biometric, manual, qr, etc.)"
    )
    device_serial: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Serial number of the biometric terminal device"
    )
    raw_pin: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Numeric biometric enrolled user ID (pin) mapped from eSSL"
    )
    marked_by: Mapped[Optional[sqlalchemy.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing the staff user who recorded the entry manually"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes on check-in or manual corrections"
    )

    # Relationships
    member: Mapped["Member"] = relationship(back_populates="attendance_logs")
    marker: Mapped[Optional["User"]] = relationship(foreign_keys=[marked_by])


class UnmatchedScan(Base, UUIDMixin):
    """
    UnmatchedScan model holding raw biometric logs where the scanned PIN
    does not map to any active member profile's biometric_device_id.
    """
    __tablename__ = "unmatched_scans"
    __table_args__ = (
        {"comment": "Stores biometric scanner records that failed to map to a member profile PIN"},
    )

    device_serial: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="Serial number of the biometric terminal device"
    )
    raw_pin: Mapped[int] = mapped_column(
        Integer,
        index=True,
        nullable=False,
        comment="Biometric device enrolled user ID (pin) pushed from eSSL"
    )
    scan_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Date and time when the user finger scanned"
    )
    verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Device verification status flag (1 matched, 0 unmatched)"
    )
    raw_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Complete JSON structure of HTTP query parameters from the device"
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if the receptionist resolved this scan link"
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the scan was linked"
    )
    resolved_by: Mapped[Optional[sqlalchemy.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing the staff user who resolved the link"
    )
    resolved_member_id: Mapped[Optional[sqlalchemy.UUID]] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing the member linked during resolution"
    )

    # Relationships
    resolver: Mapped[Optional["User"]] = relationship(foreign_keys=[resolved_by])
    resolved_member: Mapped[Optional["Member"]] = relationship(foreign_keys=[resolved_member_id])
