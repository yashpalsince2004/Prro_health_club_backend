from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
from app.services.auth import AuthService
from app.utils.response import success_response

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=None)
def login(payload: LoginRequest):
    """Authenticate credentials and establish session tokens"""
    tokens = AuthService.authenticate_user(
        email=payload.email,
        password=payload.password
    )
    return success_response(message="Login successful", data=tokens)


@router.post("/refresh", response_model=None)
def refresh_token(payload: TokenRefreshRequest):
    """Exchange refresh tokens for new session access tokens"""
    tokens = AuthService.refresh_session_token(refresh_token=payload.refresh_token)
    return success_response(message="Token refreshed successfully", data=tokens)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(payload: TokenRefreshRequest):
    """Revoke active session refresh tokens"""
    AuthService.logout_session(refresh_token=payload.refresh_token)
    return success_response(message="Logout successful")


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(payload: ForgotPasswordRequest):
    """Initiate password recovery flow"""
    AuthService.process_forgot_password(email=payload.email)
    return success_response(message="If the email exists, a password reset link has been dispatched")


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest):
    """Apply a new password using a reset token"""
    AuthService.process_reset_password(token=payload.token, new_password=payload.new_password)
    return success_response(message="Password reset successfully")


# Test route to verify JWT decryption and UserContext parsing
@router.get("/me", response_model=None)
def get_me(current_user: UserContext = Depends(get_current_user_context)):
    """Fetch current user session details derived from the active JWT"""
    return success_response(
        message="Session user context retrieved",
        data={
            "user_id": str(current_user.user_id),
            "role": current_user.role,
            "gym_id": str(current_user.gym_id),
            "branch_id": str(current_user.branch_id) if current_user.branch_id else None
        }
    )


# Test route to verify Role-Based Access Control (RBAC) dependency
@router.get("/admin-only", response_model=None)
def get_admin_dashboard(
    current_admin: UserContext = Depends(RoleChecker(allowed_roles=["admin"]))
):
    """Endpoint restricted to Administrator roles only"""
    return success_response(
        message="Admin verification successful",
        data={"admin_user_id": str(current_admin.user_id)}
    )
