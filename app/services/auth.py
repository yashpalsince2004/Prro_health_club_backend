import uuid
from datetime import timedelta
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password
)

# Hardcoded mocks for Phase 4 verification
# These will be replaced by UserRepository queries in Phase 5
MOCK_USERS = {
    "admin@prrohealthclub.com": {
        "id": "e9a039bd-6a84-486b-8874-885cc0a2569f",
        "password_hash": get_password_hash("Password123"),
        "role": "admin",
        "gym_id": "aa30e46b-0b5c-48c2-a4f6-7b2434d284a1",
        "branch_id": "bb30e46b-0b5c-48c2-a4f6-7b2434d284a2"
    },
    "trainer@prrohealthclub.com": {
        "id": "f5a039bd-6a84-486b-8874-885cc0a2569f",
        "password_hash": get_password_hash("Password123"),
        "role": "trainer",
        "gym_id": "aa30e46b-0b5c-48c2-a4f6-7b2434d284a1",
        "branch_id": "bb30e46b-0b5c-48c2-a4f6-7b2434d284a2"
    },
    "member@prrohealthclub.com": {
        "id": "c1a039bd-6a84-486b-8874-885cc0a2569f",
        "password_hash": get_password_hash("Password123"),
        "role": "member",
        "gym_id": "aa30e46b-0b5c-48c2-a4f6-7b2434d284a1",
        "branch_id": "bb30e46b-0b5c-48c2-a4f6-7b2434d284a2"
    }
}


class AuthService:
    """
    Service encapsulating Authentication and Session workflows.
    Bridges endpoints to the database repositories and token generation logic.
    """
    @staticmethod
    def authenticate_user(email: str, password: str) -> Dict[str, Any]:
        """
        Verify login credentials.
        Returns a dictionary representing access and refresh token metadata.
        """
        user = MOCK_USERS.get(email.lower())
        if not user:
            raise AuthenticationException(message="Incorrect email or password")
            
        if not verify_password(password, user["password_hash"]):
            raise AuthenticationException(message="Incorrect email or password")

        # Generate tokens
        access_token = create_access_token(
            subject=user["id"],
            role=user["role"],
            gym_id=user["gym_id"],
            branch_id=user["branch_id"]
        )
        refresh_token = create_refresh_token(
            subject=user["id"]
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    @staticmethod
    def refresh_session_token(refresh_token: str) -> Dict[str, Any]:
        """
        Exchange a valid refresh token for a new short-lived access token.
        """
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthenticationException(message="Invalid or expired session refresh token")

        user_id = payload.get("sub")
        # In a real environment, we verify the user still exists and is active in the database.
        # Find user by ID in mocks
        user = None
        for u in MOCK_USERS.values():
            if u["id"] == user_id:
                user = u
                break
                
        if not user:
            raise AuthenticationException(message="User account associated with session not found")

        new_access = create_access_token(
            subject=user["id"],
            role=user["role"],
            gym_id=user["gym_id"],
            branch_id=user["branch_id"]
        )
        new_refresh = create_refresh_token(
            subject=user["id"]
        )

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    @staticmethod
    def logout_session(refresh_token: str) -> None:
        """
        Log out and invalidate session refresh token (e.g. blacklist token).
        """
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthenticationException(message="Invalid or expired session token")
        # Mock successful token invalidation
        return

    @staticmethod
    def process_forgot_password(
        email: str,
        db: Session,
        background_tasks: Any,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Process request for a forgotten password.
        Generates and dispatches a reset token to user's registered communication channels.
        """
        from app.models.user import User
        from app.models.password_reset import PasswordResetToken
        from app.services.email_service import send_password_reset_email
        import secrets
        from datetime import datetime, timedelta

        user = db.query(User).filter(User.email == email.lower(), User.is_deleted == False).first()
        if not user:
            # Prevent user enumeration attacks by returning success even if email is not found
            logger.info(f"Password reset requested for non-existent email: {email}")
            return

        # Invalidate all previous unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False
        ).update({"is_used": True})
        db.flush()

        # Generate a random hex token
        token = secrets.token_hex(32)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_EXPIRY_MINUTES)

        reset_record = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(reset_record)
        db.commit()

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        member_name = user.profile.full_name if user.profile else user.email

        background_tasks.add_task(
            send_password_reset_email,
            user.email,
            member_name,
            reset_url
        )

    @staticmethod
    def process_reset_password(token: str, new_password: str, db: Session) -> None:
        """
        Reset user password using a verified reset token.
        """
        from app.models.user import User
        from app.models.password_reset import PasswordResetToken
        from datetime import datetime

        reset_record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        ).first()

        if not reset_record:
            raise AuthenticationException(message="Invalid or expired reset token")

        user = db.query(User).filter(User.id == reset_record.user_id, User.is_deleted == False).first()
        if not user:
            raise AuthenticationException(message="User account associated with this token not found")

        user.hashed_password = get_password_hash(new_password)
        user.last_password_changed_at = datetime.utcnow()
        
        reset_record.is_used = True
        reset_record.used_at = datetime.utcnow()
        
        db.add(user)
        db.add(reset_record)
        db.commit()
        logger.info(f"Password reset completed for user_id={reset_record.user_id}")
