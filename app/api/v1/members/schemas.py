"""
Pydantic schemas for Member management.
"""

from datetime import date
from uuid import UUID
from typing import Optional, List
from decimal import Decimal
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
# pyrefly: ignore [missing-import]
from pydantic_core import PydanticCustomError
from app.core.constants import UserRole, SubscriptionStatus
from app.models.profile import Gender


class MemberCreate(BaseModel):
    """Schema to create a new user, profile, and member record."""
    email: EmailStr = Field(..., description="Email address for user login")
    password: str = Field(..., min_length=8, description="Login password (min 8 characters)")
    role: UserRole = Field(UserRole.MEMBER, description="Default role is member")

    # Profile details
    full_name: str = Field(..., min_length=1, description="Legal full name")
    phone: Optional[str] = Field(None, description="Contact phone number")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[Gender] = Field(None, description="Gender classification")
    address: Optional[str] = Field(None, description="Residential address")
    emergency_contact_name: Optional[str] = Field(None, description="Emergency contact name")
    emergency_contact_phone: Optional[str] = Field(None, description="Emergency contact phone number")
    emergency_relation: Optional[str] = Field(None, description="Relationship of emergency contact")
    medical_notes: Optional[str] = Field(None, description="Injuries or health conditions")
    occupation: Optional[str] = Field(None, description="Profession or work")
    height: Optional[Decimal] = Field(None, description="Height in cm")
    weight: Optional[Decimal] = Field(None, description="Weight in kg")

    # Member details
    joining_date: date = Field(default_factory=date.today, description="Gym joining date")
    notes: Optional[str] = Field(None, description="Gym notes or constraints")
    plan_id: Optional[UUID] = Field(None, description="Optional subscription plan to assign")
    trainer_id: Optional[UUID] = Field(None, description="Optional trainer to assign")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate that password contains uppercase, lowercase, and numeric digits."""
        if not any(char.isupper() for char in v):
            raise PydanticCustomError("password_strength", "Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise PydanticCustomError("password_strength", "Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in v):
            raise PydanticCustomError("password_strength", "Password must contain at least one numeric digit")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        """Validate date of birth is in the past."""
        if v and v >= date.today():
            raise PydanticCustomError("invalid_dob", "Date of birth must be in the past")
        return v

    @field_validator("joining_date")
    @classmethod
    def validate_joining_date(cls, v: date) -> date:
        """Validate joining date is not in the future."""
        if v > date.today():
            raise PydanticCustomError("future_joining_date", "Joining date cannot be in the future")
        return v


class MemberUpdate(BaseModel):
    """Schema to update a member profile and status details."""
    full_name: Optional[str] = Field(None, min_length=1, description="Legal full name")
    email: Optional[EmailStr] = Field(None, description="Email address for user login")
    phone: Optional[str] = Field(None, description="Contact phone number")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[Gender] = Field(None, description="Gender classification")
    address: Optional[str] = Field(None, description="Residential address")
    emergency_contact_name: Optional[str] = Field(None, description="Emergency contact name")
    emergency_contact_phone: Optional[str] = Field(None, description="Emergency contact phone number")
    emergency_relation: Optional[str] = Field(None, description="Relationship of emergency contact")
    medical_notes: Optional[str] = Field(None, description="Injuries or health conditions")
    occupation: Optional[str] = Field(None, description="Profession or work")
    height: Optional[Decimal] = Field(None, description="Height in cm")
    weight: Optional[Decimal] = Field(None, description="Weight in kg")
    notes: Optional[str] = Field(None, description="Gym notes or constraints")
    biometric_device_id: Optional[int] = Field(None, description="Biometric terminal device PIN")
    is_active: Optional[bool] = Field(None, description="User active status flag")
    plan_id: Optional[UUID] = Field(None, description="Pricing plan template UUID")
    trainer_id: Optional[UUID] = Field(None, description="Assigned trainer UUID")

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        """Validate date of birth is in the past."""
        if v and v >= date.today():
            raise PydanticCustomError("invalid_dob", "Date of birth must be in the past")
        return v


class ProfileResponse(BaseModel):
    """Schema exposing user profile details."""
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
    email: Optional[str] = None
    occupation: Optional[str] = None
    height: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    medical_notes: Optional[str] = None
    emergency_relation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ActiveMembershipSummary(BaseModel):
    """Schema providing a summary of a member's active subscription."""
    id: UUID
    plan_name: str
    start_date: date
    end_date: date
    status: SubscriptionStatus
    days_remaining: int

    model_config = ConfigDict(from_attributes=True)


class TrainerSummary(BaseModel):
    """Minimal representation of an assigned trainer."""
    id: UUID
    full_name: str
    specialization: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MemberResponse(BaseModel):
    """Schema representing complete member records with nested profiles and active plans."""
    id: UUID
    joining_date: date
    notes: Optional[str] = None
    profile: ProfileResponse
    active_membership: Optional[ActiveMembershipSummary] = None
    is_active: bool = True
    last_visit: Optional[date] = None
    assigned_trainer: Optional[TrainerSummary] = None

    model_config = ConfigDict(from_attributes=True)


class MemberListResponse(BaseModel):
    """Paginated collection of member responses."""
    members: List[MemberResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class BulkArchiveRequest(BaseModel):
    ids: List[UUID]


class BulkRestoreRequest(BaseModel):
    ids: List[UUID]


class BulkAssignTrainerRequest(BaseModel):
    member_ids: List[UUID]
    trainer_id: UUID


class BulkChangePlanRequest(BaseModel):
    member_ids: List[UUID]
    plan_id: UUID


class BulkActivateRequest(BaseModel):
    ids: List[UUID]


class BulkDeactivateRequest(BaseModel):
    ids: List[UUID]
