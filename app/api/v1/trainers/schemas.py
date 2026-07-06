from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional, List
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.api.v1.members.schemas import ProfileResponse, MemberResponse


class TrainerCreate(BaseModel):
    """Schema to create a new user, profile, and trainer record."""
    email: EmailStr = Field(..., description="Email address for trainer login")
    password: str = Field(..., min_length=8, description="Login password (min 8 characters)")
    full_name: str = Field(..., min_length=1, description="Legal full name")
    phone: Optional[str] = Field(None, description="Contact phone number")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[str] = Field(None, description="Gender (male/female/other)")
    address: Optional[str] = Field(None, description="Residential address")
    emergency_contact_name: Optional[str] = Field(None, description="Emergency contact name")
    emergency_contact_phone: Optional[str] = Field(None, description="Emergency contact phone number")
    emergency_relation: Optional[str] = Field(None, description="Emergency contact relation")
    
    employee_id: Optional[str] = Field(None, description="Unique Employee ID")
    specialization: Optional[str] = Field(None, description="Trainer's core fitness area")
    specializations: Optional[List[str]] = Field(None, description="Multi-select list of specialization areas")
    experience_years: Optional[int] = Field(None, ge=0, description="Years of professional experience")
    qualification: Optional[str] = Field(None, description="Qualifications")
    certifications: Optional[List[str]] = Field(None, description="List of professional credentials")
    bio: Optional[str] = Field(None, description="Short biography of the trainer")
    
    employment_type: Optional[str] = Field("Full Time", description="Full Time, Part Time, Contract")
    salary: Optional[Decimal] = Field(None, description="Monthly salary for the trainer")
    salary_type: Optional[str] = Field("Monthly", description="Monthly or Hourly")
    shift: Optional[str] = Field("Morning", description="Shift: Morning, Evening, Night, Flexible")
    joining_staff_date: date = Field(default_factory=date.today, description="Employment start date")
    
    max_members: Optional[int] = Field(15, ge=0, description="Max member capacity")
    working_days: Optional[List[str]] = Field(None, description="Working days")
    working_hours: Optional[str] = Field(None, description="Working hours shift details")


class TrainerUpdate(BaseModel):
    """Schema to modify a trainer's specifications and availability."""
    full_name: Optional[str] = Field(None, min_length=1, description="Legal full name")
    phone: Optional[str] = Field(None, description="Contact phone number")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[str] = Field(None, description="Gender")
    address: Optional[str] = Field(None, description="Residential address")
    emergency_contact_name: Optional[str] = Field(None, description="Emergency contact name")
    emergency_contact_phone: Optional[str] = Field(None, description="Emergency contact phone")
    emergency_relation: Optional[str] = Field(None, description="Emergency contact relation")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")

    employee_id: Optional[str] = Field(None, description="Unique Employee ID")
    specialization: Optional[str] = Field(None, description="Trainer's core fitness area")
    specializations: Optional[List[str]] = Field(None, description="Multi-select list of specialization areas")
    experience_years: Optional[int] = Field(None, ge=0, description="Years of professional experience")
    qualification: Optional[str] = Field(None, description="Qualifications")
    certifications: Optional[List[str]] = Field(None, description="List of professional credentials")
    bio: Optional[str] = Field(None, description="Short biography of the trainer")
    is_available: Optional[bool] = Field(None, description="Flag indicating if accepting new members")
    is_active: Optional[bool] = Field(None, description="User active status flag")
    
    employment_type: Optional[str] = Field(None, description="Full Time, Part Time, Contract")
    salary: Optional[Decimal] = Field(None, description="Monthly salary for the trainer")
    salary_type: Optional[str] = Field(None, description="Monthly or Hourly")
    shift: Optional[str] = Field(None, description="Shift: Morning, Evening, Night, Flexible")
    joining_staff_date: Optional[date] = Field(None, description="Employment start date")
    
    max_members: Optional[int] = Field(None, ge=0, description="Max member capacity")
    working_days: Optional[List[str]] = Field(None, description="Working days")
    working_hours: Optional[str] = Field(None, description="Working hours shift details")


class TrainerResponse(BaseModel):
    """Schema representing complete trainer records with nested profiles."""
    id: UUID
    employee_id: Optional[str] = None
    specialization: Optional[str] = None
    specializations: Optional[List[str]] = None
    experience_years: Optional[int] = None
    qualification: Optional[str] = None
    certifications: Optional[List[str]] = None
    bio: Optional[str] = None
    is_available: bool
    is_active: bool = True
    
    employment_type: Optional[str] = None
    salary: Optional[Decimal] = None
    salary_type: Optional[str] = None
    shift: Optional[str] = None
    joining_staff_date: Optional[date] = None
    
    max_members: Optional[int] = 15
    working_days: Optional[List[str]] = None
    working_hours: Optional[str] = None
    
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
