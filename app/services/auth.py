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
    def process_forgot_password(email: str) -> None:
        """
        Process request for a forgotten password.
        Generates and dispatches a reset token to user's registered communication channels.
        """
        user = MOCK_USERS.get(email.lower())
        if not user:
            # Prevent user enumeration attacks by returning success even if email is not found
            return
        # Mock trigger for password reset email dispatch
        return

    @staticmethod
    def process_reset_password(token: str, new_password: str) -> None:
        """
        Reset user password using a verified reset token.
        """
        payload = decode_token(token)
        if not payload or payload.get("type") != "reset":
            raise AuthenticationException(message="Invalid or expired password reset token")
        # Mock successful password reset
        return
