from decimal import Decimal
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class AdditionalServiceCreate(BaseModel):
    name: str = Field(..., description="Name of the service")
    price: Decimal = Field(..., ge=0, description="Price of the service")
    description: Optional[str] = Field(None, description="Detailed description")
    is_active: bool = Field(True, description="Service status flag")


class AdditionalServiceUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[Decimal] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AdditionalServiceResponse(BaseModel):
    id: UUID
    name: str
    price: Decimal
    description: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
