from decimal import Decimal
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class LockerPlanCreate(BaseModel):
    name: str = Field("Standard Locker", description="Locker plan descriptor")
    deposit: Decimal = Field(..., ge=0, description="Locker security deposit fee")
    monthly_rent: Decimal = Field(..., ge=0, description="Locker monthly rent fee")
    quarterly_rent: Decimal = Field(..., ge=0, description="Locker quarterly rent fee")
    late_fee: Decimal = Field(Decimal("0.00"), ge=0, description="Penalty fee for late returns")
    refundable: bool = Field(True, description="Deposit refundable toggle")
    is_active: bool = Field(True, description="Plan status flag")


class LockerPlanUpdate(BaseModel):
    name: Optional[str] = None
    deposit: Optional[Decimal] = None
    monthly_rent: Optional[Decimal] = None
    quarterly_rent: Optional[Decimal] = None
    late_fee: Optional[Decimal] = None
    refundable: Optional[bool] = None
    is_active: Optional[bool] = None


class LockerPlanResponse(BaseModel):
    id: UUID
    name: str
    deposit: Decimal
    monthly_rent: Decimal
    quarterly_rent: Decimal
    late_fee: Decimal
    refundable: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
