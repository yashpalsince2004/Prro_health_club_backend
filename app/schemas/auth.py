from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Schema for user login credentials request"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="Plain-text password")


class TokenResponse(BaseModel):
    """Schema returning OAuth2/JWT tokens upon successful login or refresh"""
    access_token: str = Field(..., description="Short-lived access token")
    refresh_token: str = Field(..., description="Long-lived refresh token")
    token_type: str = Field("bearer", description="Token protocol classification")
    expires_in: int = Field(..., description="Access token expiration window in seconds")


class TokenRefreshRequest(BaseModel):
    """Schema requesting new access tokens using a valid refresh token"""
    refresh_token: str = Field(..., description="Valid long-lived refresh token")


class ForgotPasswordRequest(BaseModel):
    """Schema requesting password reset instructions"""
    email: EmailStr = Field(..., description="Email address linked to the user account")


from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class ResetPasswordRequest(BaseModel):
    """Schema submitting a new password using a token payload"""
    token: str = Field(..., description="One-time validation reset token")
    new_password: str = Field(..., min_length=8, description="New user password (minimum 8 characters)")

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
