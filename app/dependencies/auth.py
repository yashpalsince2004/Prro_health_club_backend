import uuid
from dataclasses import dataclass
from typing import List, Optional
# pyrefly: ignore [missing-import]
from fastapi import Depends, Request
# pyrefly: ignore [missing-import]
from fastapi.security import OAuth2PasswordBearer
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import decode_token

# Define standard OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False
)


@dataclass
class UserContext:
    """Security principal representing the current authenticated session user"""
    user_id: uuid.UUID
    role: str
    gym_id: uuid.UUID
    branch_id: Optional[uuid.UUID] = None


def get_current_user_context(token: Optional[str] = Depends(oauth2_scheme)) -> UserContext:
    """
    FastAPI dependency that extracts and validates the JWT from headers,
    returning a strongly-typed security context.
    """
    if not token:
        raise AuthenticationException(message="Authentication credentials were not provided")

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise AuthenticationException(message="Invalid or expired authentication credentials")

    user_id_str = payload.get("sub")
    role = payload.get("role")
    gym_id_str = payload.get("gym_id")
    branch_id_str = payload.get("branch_id")

    if not user_id_str or not role or not gym_id_str:
        raise AuthenticationException(message="Token credentials are malformed")

    try:
        user_uuid = uuid.UUID(user_id_str)
        
        # Verify token has not been revoked by a password change
        from app.database.session import SessionLocal
        from app.models.user import User
        import calendar
        
        db = SessionLocal()
        try:
            db_user = db.query(User).filter(User.id == user_uuid, User.is_deleted == False).first()
            if db_user and db_user.last_password_changed_at and payload.get("iat"):
                token_iat = payload.get("iat")
                if isinstance(token_iat, (int, float)):
                    user_change_ts = calendar.timegm(db_user.last_password_changed_at.utctimetuple())
                    # Give 1 second grace period to avoid timing anomalies
                    if token_iat <= user_change_ts:
                        raise AuthenticationException(message="Session revoked. Please login again.")
        finally:
            db.close()

        return UserContext(
            user_id=user_uuid,
            role=role,
            gym_id=uuid.UUID(gym_id_str),
            branch_id=uuid.UUID(branch_id_str) if branch_id_str else None
        )
    except ValueError:
        raise AuthenticationException(message="Token identifiers are malformed UUIDs")


class RoleChecker:
    """Dependency factory that checks if current user role matches permitted roles"""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: UserContext = Depends(get_current_user_context)) -> UserContext:
        if current_user.role not in self.allowed_roles:
            raise AuthorizationException(
                message=f"Access denied: Role '{current_user.role}' is not authorized"
            )
        return current_user
