import uuid
import calendar
from dataclasses import dataclass
from typing import List, Optional
# pyrefly: ignore [missing-import]
from fastapi import Depends
# pyrefly: ignore [missing-import]
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidSignatureError,
    DecodeError,
    PyJWTError,
)
from loguru import logger
from app.core.config import settings
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import decode_token

# Log JWT configuration at import time so it appears in Railway/Render startup logs
logger.info(
    f"[AUTH] JWT config loaded — ALGORITHM={settings.ALGORITHM} "
    f"SECRET_KEY_LENGTH={len(settings.SECRET_KEY)} "
    f"ACCESS_TOKEN_EXPIRE_MINUTES={settings.ACCESS_TOKEN_EXPIRE_MINUTES}"
)

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
    gym_id: Optional[uuid.UUID] = None      # Optional — not all users have a gym association
    branch_id: Optional[uuid.UUID] = None


def get_current_user_context(token: Optional[str] = Depends(oauth2_scheme)) -> UserContext:
    """
    FastAPI dependency that extracts and validates the JWT from the Authorization header,
    returning a strongly-typed security context.

    This is the SINGLE place that validates JWTs. All 401 decisions happen here.
    """
    if not token:
        raise AuthenticationException(message="Authentication credentials were not provided")

    logger.debug(f"[AUTH] Validating token (first 20 chars): {token[:20]}...")

    payload = decode_token(token)

    if not payload:
        # decode_token already logged the exact PyJWT exception
        raise AuthenticationException(message="Invalid or expired authentication credentials")

    token_type = payload.get("type")
    if token_type != "access":
        logger.warning(f"[AUTH] Wrong token type presented: type={token_type!r}")
        raise AuthenticationException(message="Invalid or expired authentication credentials")

    user_id_str = payload.get("sub")
    role = payload.get("role")
    gym_id_str = payload.get("gym_id")        # Optional — may be None
    branch_id_str = payload.get("branch_id") # Optional — may be None

    logger.debug(
        f"[AUTH] Token claims — sub={user_id_str!r} role={role!r} "
        f"gym_id={gym_id_str!r} branch_id={branch_id_str!r}"
    )

    # Only sub and role are mandatory
    if not user_id_str or not role:
        logger.warning(
            f"[AUTH] Malformed token — missing required claims: "
            f"sub={user_id_str!r} role={role!r}"
        )
        raise AuthenticationException(message="Token credentials are malformed")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        logger.warning(f"[AUTH] Invalid UUID in sub claim: {user_id_str!r}")
        raise AuthenticationException(message="Token identifiers are malformed UUIDs")

    # Verify token has not been revoked by a password change
    try:
        from app.database.session import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        try:
            db_user = db.query(User).filter(
                User.id == user_uuid,
                User.is_deleted == False
            ).first()

            if db_user is None:
                logger.warning(f"[AUTH] User not found in DB: user_id={user_uuid}")
                raise AuthenticationException(message="User account not found or deactivated")

            if not db_user.is_active:
                logger.warning(f"[AUTH] Inactive account attempted access: user_id={user_uuid}")
                raise AuthenticationException(message="Account is disabled. Please contact support.")

            if db_user.last_password_changed_at and payload.get("iat"):
                token_iat = payload.get("iat")
                if isinstance(token_iat, (int, float)):
                    user_change_ts = calendar.timegm(
                        db_user.last_password_changed_at.utctimetuple()
                    )
                    if token_iat <= user_change_ts:
                        logger.warning(
                            f"[AUTH] Token revoked by password change: "
                            f"user_id={user_uuid} token_iat={token_iat} changed_at={user_change_ts}"
                        )
                        raise AuthenticationException(message="Session revoked. Please login again.")
        finally:
            db.close()
    except AuthenticationException:
        raise  # re-raise auth exceptions unchanged
    except Exception as e:
        logger.error(f"[AUTH] DB verification error: {e}")
        raise AuthenticationException(message="Authentication verification failed")

    # Parse optional UUID fields
    gym_uuid: Optional[uuid.UUID] = None
    branch_uuid: Optional[uuid.UUID] = None

    if gym_id_str:
        try:
            gym_uuid = uuid.UUID(gym_id_str)
        except ValueError:
            logger.warning(f"[AUTH] Invalid gym_id UUID: {gym_id_str!r}")

    if branch_id_str:
        try:
            branch_uuid = uuid.UUID(branch_id_str)
        except ValueError:
            logger.warning(f"[AUTH] Invalid branch_id UUID: {branch_id_str!r}")

    return UserContext(
        user_id=user_uuid,
        role=role,
        gym_id=gym_uuid,
        branch_id=branch_uuid,
    )



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
