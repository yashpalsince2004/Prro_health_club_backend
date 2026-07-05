from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.api.v1.members.schemas import ProfileResponse, MemberResponse


class TrainerCreate(BaseModel):
    """Schema to create a new user, profile, and trainer record."""
    email: EmailStr = Field(..., description="Email address for trainer login")
    password: str = Field(..., min_length=8, description="Login password (min 8 characters)")
    full_name: str = Field(..., min_length=1, description="Legal full name")
    phone: Optional[str] = Field(None, description="Contact phone number")
    specialization: Optional[str] = Field(None, description="Trainer's core fitness area")
    experience_years: Optional[int] = Field(None, ge=0, description="Years of professional experience")
    certifications: Optional[List[str]] = Field(None, description="List of professional credentials")
    bio: Optional[str] = Field(None, description="Short biography of the trainer")
    salary: Optional[Decimal] = Field(None, description="Monthly salary for the trainer")
    joining_staff_date: date = Field(default_factory=date.today, description="Employment start date")


class TrainerUpdate(BaseModel):
    """Schema to modify a trainer's specifications and availability."""
    full_name: Optional[str] = Field(None, min_length=1, description="Legal full name")
    phone: Optional[str] = Field(None, description="Contact phone number")
    specialization: Optional[str] = Field(None, description="Trainer's core fitness area")
    experience_years: Optional[int] = Field(None, ge=0, description="Years of professional experience")
    certifications: Optional[List[str]] = Field(None, description="List of professional credentials")
    bio: Optional[str] = Field(None, description="Short biography of the trainer")
    is_available: Optional[bool] = Field(None, description="Flag indicating if accepting new members")
    is_active: Optional[bool] = Field(None, description="User active status flag")
    salary: Optional[Decimal] = Field(None, description="Monthly salary for the trainer")
    joining_staff_date: Optional[date] = Field(None, description="Employment start date")


class TrainerResponse(BaseModel):
    """Schema representing complete trainer records with nested profiles."""
    id: UUID
    specialization: Optional[str] = None
    experience_years: Optional[int] = None
    certifications: Optional[List[str]] = None
    bio: Optional[str] = None
    is_available: bool
    profile: ProfileResponse
    assigned_member_count: int
    assigned_members: Optional[List[MemberResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class AssignMemberRequest(BaseModel):
    """Request payload to link a member to a trainer."""
    member_id: UUID = Field(..., description="ID of the member to assign")


class UnassignMemberRequest(BaseModel):
    """Request payload to unlink a member from a trainer."""
    member_id: UUID = Field(..., description="ID of the member to unassign")
class TrainerListResponse(BaseModel):
    """Paginated collection of trainer responses."""
    trainers: List[TrainerResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
