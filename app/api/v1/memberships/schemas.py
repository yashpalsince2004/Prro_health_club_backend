"""
Pydantic schemas for Membership subscription management.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.core.constants import SubscriptionStatus


class MembershipCreate(BaseModel):
    """Schema to subscribe a member to a plan."""
    member_id: UUID = Field(..., description="ID of the member")
    plan_id: UUID = Field(..., description="ID of the membership plan template")
    start_date: date = Field(default_factory=date.today, description="Activation start date")
    discount_percent: Decimal = Field(Decimal("0.00"), ge=0, le=100, description="Discount percent (0.00 to 100.00)")
    auto_renew: bool = Field(False, description="Flag to automatically renew upon expiration")
    notes: Optional[str] = Field(None, description="Subscription notes")


class MembershipRenew(BaseModel):
    """Schema to renew an existing membership subscription."""
    plan_id: UUID = Field(..., description="ID of the membership plan template (can switch plans)")
    start_from_expiry: bool = Field(True, description="If True, start date begins the day after current expiry")
    discount_percent: Decimal = Field(Decimal("0.00"), ge=0, le=100, description="Discount percent")
    auto_renew: bool = Field(False, description="Flag to automatically renew")
    notes: Optional[str] = Field(None, description="Renewal notes")


class PlanSummary(BaseModel):
    """Simplified plan template details for membership responses."""
    id: UUID
    name: str
    duration_days: int
    price: Decimal
    currency: str

    model_config = ConfigDict(from_attributes=True)


class MembershipResponse(BaseModel):
    """Schema exposing detailed membership subscription information."""
    id: UUID
    member_id: UUID
    plan: PlanSummary
    start_date: date
    end_date: date
    status: SubscriptionStatus
    auto_renew: bool
    discount_percent: Decimal
    notes: Optional[str] = None
    is_expired: bool
    days_remaining: int
    effective_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class MembershipStatusUpdate(BaseModel):
    """Request payload to manually alter a membership subscription status."""
    status: SubscriptionStatus = Field(..., description="Target status (active, cancelled, paused, etc.)")
    notes: Optional[str] = Field(None, description="Reason or comments for status alteration")


class MembershipListResponse(BaseModel):
    """Paginated collection of membership responses."""
    memberships: List[MembershipResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
