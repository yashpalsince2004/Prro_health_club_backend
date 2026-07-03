"""
Pydantic schemas for Payment transaction logging.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from app.models.payment import PaymentMethodEnum, PaymentStatusEnum


class PaymentCreate(BaseModel):
    """Schema to log a payment transaction."""
    membership_id: UUID = Field(..., description="ID of the membership subscription purchased")
    member_id: UUID = Field(..., description="ID of the member making the payment")
    amount_paid: Decimal = Field(..., ge=0, description="Amount collected")
    payment_method: PaymentMethodEnum = Field(..., description="Payment method used")
    transaction_reference: Optional[str] = Field(None, description="Transaction reference number")
    payment_date: Optional[datetime] = Field(None, description="Transaction timestamp (defaults to now)")
    notes: Optional[str] = Field(None, description="Any reception notes")


class PaymentResponse(BaseModel):
    """Schema exposing detailed payment transaction information."""
    id: UUID
    membership_id: UUID
    member_id: UUID
    member_name: str
    amount_paid: Decimal
    currency: str
    payment_method: PaymentMethodEnum
    payment_status: PaymentStatusEnum
    transaction_reference: Optional[str] = None
    payment_date: datetime
    notes: Optional[str] = None
    collected_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentSummary(BaseModel):
    """Schema detailing consolidated revenue figures over a period."""
    total_payments: int
    total_amount: Decimal
    by_method: Dict[str, Decimal]
    by_status: Dict[str, int]
    period: str
class PaymentListResponse(BaseModel):
    """Paginated collection of payment responses."""
    payments: List[PaymentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
