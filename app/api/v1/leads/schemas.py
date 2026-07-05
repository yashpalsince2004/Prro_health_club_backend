from datetime import date, datetime
from uuid import UUID
from typing import Optional, List
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.profile import Gender
from app.models.lead import LeadStatus, LeadSource

class LeadCreate(BaseModel):
    full_name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    age: Optional[int] = Field(None, ge=0)
    gender: Optional[Gender] = None
    interest: Optional[str] = None
    source: LeadSource = LeadSource.WALK_IN
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    assigned_to: Optional[UUID] = None

class LeadUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None
    interest: Optional[str] = None
    source: Optional[LeadSource] = None
    status: Optional[LeadStatus] = None
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    trial_start: Optional[date] = None
    trial_end: Optional[date] = None
    assigned_to: Optional[UUID] = None

class ConvertLeadRequest(BaseModel):
    password: str = Field(..., min_length=8)
    plan_id: Optional[UUID] = None
    joining_date: date = Field(default_factory=date.today)

class LeadResponse(BaseModel):
    id: UUID
    full_name: str
    phone: str
    email: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None
    interest: Optional[str] = None
    source: str
    status: str
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None
    trial_start: Optional[date] = None
    trial_end: Optional[date] = None
    assigned_to: Optional[UUID] = None
    converted_member_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LeadListResponse(BaseModel):
    leads: List[LeadResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
