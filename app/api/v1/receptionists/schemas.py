from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, List, Literal
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.profile import Gender

class ProfileResponse(BaseModel):
    id: UUID
    full_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    biometric_device_id: Optional[int] = None
    salary: Optional[Decimal] = None
    shift: Optional[str] = None
    joining_staff_date: Optional[date] = None
    medical_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ReceptionistCreate(BaseModel):
    # Account
    email: EmailStr
    password: str = Field(..., min_length=8)

    # Profile
    full_name: str
    phone: Optional[str] = None
    gender: Optional[Gender] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None

    # Staff-specific
    salary: Optional[Decimal] = None
    shift: Optional[Literal["morning", "evening", "full-day"]] = None
    joining_staff_date: date = Field(default_factory=date.today)
    medical_notes: Optional[str] = None

class ReceptionistUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[Gender] = None
    address: Optional[str] = None
    salary: Optional[Decimal] = None
    shift: Optional[str] = None
    is_active: Optional[bool] = None
    medical_notes: Optional[str] = None

class ReceptionistResponse(BaseModel):
    id: UUID              # User.id
    email: str
    is_active: bool
    role: str
    profile: ProfileResponse
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class StaffListResponse(BaseModel):
    staff: List[ReceptionistResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
