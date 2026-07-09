"""
SQLAlchemy payment model representing invoices and payments.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TYPE_CHECKING
import sqlalchemy
from sqlalchemy import String, DECIMAL, Text, Uuid, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from app.database.mixins import UUIDMixin, AuditMixin

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.membership import Membership
    from app.models.user import User


class PaymentStatusEnum(str, Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethodEnum(str, Enum):
    """Payment method enumeration"""
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class Payment(Base, UUIDMixin, AuditMixin):
    """
    Payment model capturing invoices, transactions, and payments collected.
    """
    __tablename__ = "payments"
    __table_args__ = (
        {"comment": "Stores individual payment transaction logs and methods"},
    )

    membership_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key referencing the associated membership purchase"
    )
    member_id: Mapped[sqlalchemy.UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        comment="Denormalized foreign key referencing the associated member for speed"
    )
    amount_paid: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="Total monetary value paid"
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default="INR",
        nullable=False,
        comment="Currency ISO code (default INR)"
    )
    receipt_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        index=True,
        comment="Sequential receipt number e.g. PRRO-2026-000001"
    )
    payment_method: Mapped[PaymentMethodEnum] = mapped_column(
        sqlalchemy.Enum(PaymentMethodEnum, name="paymentmethod"),
        nullable=False,
        comment="Method of payment (cash, upi, card, bank_transfer, other)"
    )
    payment_status: Mapped[PaymentStatusEnum] = mapped_column(
        sqlalchemy.Enum(PaymentStatusEnum, name="paymentstatus"),
        default=PaymentStatusEnum.COMPLETED,
        nullable=False,
        comment="Status of the transaction (pending, completed, failed, refunded)"
    )
    transaction_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True,
        comment="Bank or payment gateway reference ID (e.g. UPI Ref, Card Tx ID)"
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp when the payment occurred"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Receptionist comments about the invoice/payment"
    )
    billing_details: Mapped[Optional[dict]] = mapped_column(
        sqlalchemy.JSON,
        nullable=True,
        comment="JSON snapshot of detailed itemized invoice breakdown"
    )
    collected_by: Mapped[Optional[sqlalchemy.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Foreign key referencing the staff user who collected the payment"
    )

    # Relationships
    member: Mapped["Member"] = relationship(back_populates="payments")
    membership: Mapped["Membership"] = relationship(back_populates="payments")
    collector: Mapped[Optional["User"]] = relationship(foreign_keys=[collected_by])
