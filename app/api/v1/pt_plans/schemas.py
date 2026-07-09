from decimal import Decimal
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PTPlanCreate(BaseModel):
    package_name: str = Field(..., description="Name of the PT package (e.g. Silver)")
    price: Decimal = Field(..., ge=0, description="Monthly cost of the PT package")
    session_count: int = Field(0, ge=0, description="Sessions count included")
    whatsapp_support: bool = Field(False, description="WhatsApp support toggle")
    locker_included: bool = Field(False, description="Locker included toggle")
    transformation_included: bool = Field(False, description="Transformation toggle")
    diet_included: bool = Field(False, description="Diet plans toggle")
    stretching_included: bool = Field(False, description="Stretching sessions toggle")
    supplement_guidance: bool = Field(False, description="Supplement guidance toggle")
    description: Optional[str] = Field(None, description="Detailed package features or info")
    is_active: bool = Field(True, description="Package status flag")


class PTPlanUpdate(BaseModel):
    package_name: Optional[str] = None
    price: Optional[Decimal] = None
    session_count: Optional[int] = None
    whatsapp_support: Optional[bool] = None
    locker_included: Optional[bool] = None
    transformation_included: Optional[bool] = None
    diet_included: Optional[bool] = None
    stretching_included: Optional[bool] = None
    supplement_guidance: Optional[bool] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PTPlanResponse(BaseModel):
    id: UUID
    package_name: str
    price: Decimal
    session_count: int
    whatsapp_support: bool
    locker_included: bool
    transformation_included: bool
    diet_included: bool
    stretching_included: bool
    supplement_guidance: bool
    description: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
