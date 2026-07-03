"""
Pydantic schemas for Membership Plan Catalog Management.
"""

from decimal import Decimal
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class PlanCreate(BaseModel):
    """Schema to create a new membership plan template."""
    name: str = Field(..., description="Unique plan name (case-insensitive)")
    description: Optional[str] = Field(None, description="Detailed plan description")
    duration_days: int = Field(..., ge=1, description="Duration in days (e.g. 30, 90, 365)")
    price: Decimal = Field(..., ge=0, description="Plan price in local currency (INR)")
    features: Optional[List[str]] = Field(None, description="Plan features list")
    is_active: bool = Field(True, description="Flag indicating if plan is purchasable")
    display_order: int = Field(0, description="Order of sorting listing layouts")


class PlanUpdate(BaseModel):
    """Schema to update an existing membership plan template."""
    name: Optional[str] = Field(None, description="Unique plan name")
    description: Optional[str] = Field(None, description="Detailed plan description")
    duration_days: Optional[int] = Field(None, ge=1, description="Duration in days")
    price: Optional[Decimal] = Field(None, ge=0, description="Plan price")
    features: Optional[List[str]] = Field(None, description="Plan features list")
    is_active: Optional[bool] = Field(None, description="Flag indicating if plan is active")
    display_order: Optional[int] = Field(None, description="Order of sorting layout")


class PlanResponse(BaseModel):
    """Schema exposing complete membership plan details including subscriber stats."""
    id: UUID
    name: str
    description: Optional[str] = None
    duration_days: int
    price: Decimal
    currency: str
    features: Optional[List[str]] = None
    is_active: bool
    display_order: int
    active_subscriber_count: int

    model_config = ConfigDict(from_attributes=True)
