"""
Pydantic schemas for Member management.
"""

from datetime import date
from uuid import UUID
from typing import Optional, List
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

    # Member details
    joining_date: date = Field(default_factory=date.today, description="Gym joining date")
    notes: Optional[str] = Field(None, description="Gym notes or constraints")

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


class MemberUpdate(BaseModel):
    """Schema to update a member profile and status details."""
    full_name: Optional[str] = Field(None, min_length=1, description="Legal full name")
    phone: Optional[str] = Field(None, description="Contact phone number")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[Gender] = Field(None, description="Gender classification")
    address: Optional[str] = Field(None, description="Residential address")
    emergency_contact_name: Optional[str] = Field(None, description="Emergency contact name")
    emergency_contact_phone: Optional[str] = Field(None, description="Emergency contact phone number")
    notes: Optional[str] = Field(None, description="Gym notes or constraints")
    biometric_device_id: Optional[int] = Field(None, description="Biometric terminal device PIN")
    is_active: Optional[bool] = Field(None, description="User active status flag")


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


class MemberResponse(BaseModel):
    """Schema representing complete member records with nested profiles and active plans."""
    id: UUID
    joining_date: date
    notes: Optional[str] = None
    profile: ProfileResponse
    active_membership: Optional[ActiveMembershipSummary] = None

    model_config = ConfigDict(from_attributes=True)


class MemberListResponse(BaseModel):
    """Paginated collection of member responses."""
    members: List[MemberResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
