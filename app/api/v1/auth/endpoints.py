# pyrefly: ignore [missing-import]
from app.core.exceptions import NotFoundException
from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.services.auth import AuthService
from app.utils.response import success_response

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=None)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate credentials and establish session tokens"""
    tokens = AuthService.authenticate_user(
        email=payload.email,
        password=payload.password,
        db=db
    )
    return success_response(message="Login successful", data=tokens)


@router.post("/refresh", response_model=None)
def refresh_token(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    """Exchange refresh tokens for new session access tokens"""
    tokens = AuthService.refresh_session_token(refresh_token=payload.refresh_token, db=db)
    return success_response(message="Token refreshed successfully", data=tokens)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(payload: TokenRefreshRequest):
    """Revoke active session refresh tokens"""
    AuthService.logout_session(refresh_token=payload.refresh_token)
    return success_response(message="Logout successful")


# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, status, Request, BackgroundTasks
from app.core.limiter import limiter

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Initiate password recovery flow"""
    AuthService.process_forgot_password(
        email=payload.email,
        db=db,
        background_tasks=background_tasks,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    return success_response(message="If this email is registered, a reset link has been sent.")


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Apply a new password using a reset token"""
    AuthService.process_reset_password(token=payload.token, new_password=payload.new_password, db=db)
    return success_response(message="Password reset successful. Please log in with your new password.")


@router.get("/me", response_model=None)
def get_me(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Fetch current user session details derived from the active JWT"""
    from app.models.user import User
    from app.models.profile import Profile
    
    user = db.query(User).filter(User.id == current_user.user_id, User.is_deleted == False).first()
    if not user:
        raise NotFoundException(message="User not found")
        
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    
    profile_data = None
    if profile:
        profile_data = {
            "id": str(profile.id),
            "full_name": profile.full_name,
            "phone": profile.phone,
            "avatar_url": profile.avatar_url if hasattr(profile, 'avatar_url') else None,
            "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            "gender": profile.gender.value if hasattr(profile.gender, 'value') else profile.gender,
            "address": profile.address,
            "emergency_contact_name": profile.emergency_contact_name,
            "emergency_contact_phone": profile.emergency_contact_phone,
            "biometric_device_id": profile.biometric_device_id if hasattr(profile, 'biometric_device_id') else None
        }
        # Include member_id if present
        from app.models.member import Member
        member = db.query(Member).filter(Member.profile_id == profile.id).first()
        if member:
            profile_data["member_id"] = str(member.id)
        
    return success_response(
        message="Session user context retrieved",
        data={
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value if hasattr(user.role, 'value') else user.role,
            "is_active": user.is_active,
            "profile": profile_data
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
