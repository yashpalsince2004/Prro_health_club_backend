import uuid
import calendar
from dataclasses import dataclass
from typing import List, Optional
# pyrefly: ignore [missing-import]
from fastapi import Depends, Request
# pyrefly: ignore [missing-import]
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# pyrefly: ignore [missing-import]
from loguru import logger
import traceback
from app.core.config import settings
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.security import decode_token

# Log JWT configuration at import time so it appears in Railway/Render startup logs
logger.info(
    f"[AUTH] JWT config loaded — ALGORITHM={settings.ALGORITHM} "
    f"SECRET_KEY_LENGTH={len(settings.SECRET_KEY)} "
    f"ACCESS_TOKEN_EXPIRE_MINUTES={settings.ACCESS_TOKEN_EXPIRE_MINUTES}"
)

# HTTP Bearer scheme — generates a correct OpenAPI 'http bearer' security scheme.
# Swagger will show a simple 'Bearer token' input box, not an OAuth2 password form.
# auto_error=False lets us produce a structured 401 instead of a raw FastAPI exception.
http_bearer = HTTPBearer(auto_error=False)



@dataclass
class UserContext:
    """Security principal representing the current authenticated session user"""
    user_id: uuid.UUID
    role: str
    gym_id: Optional[uuid.UUID] = None      # Optional — not all users have a gym association
    branch_id: Optional[uuid.UUID] = None


def get_current_user_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> UserContext:
    """
    FastAPI dependency that extracts and validates the JWT from the Authorization header,
    returning a strongly-typed security context.

    Reads: Authorization: Bearer <token>
    This is the SINGLE place that validates JWTs. All 401 decisions happen here.
    """
    # [AUTH-01] Log raw Authorization header received
    auth_header = request.headers.get("Authorization")
    logger.info(f"[AUTH-01] Authorization header received: {auth_header}")

    if not credentials or not credentials.credentials:
        logger.warning("[AUTH-01-FAIL] Authentication credentials were not provided in request headers")
        raise AuthenticationException(message="Authentication credentials were not provided")

    token = credentials.credentials
    # [AUTH-02] Token extracted successfully
    logger.info(f"[AUTH-02] Token extracted successfully (first 20 chars): {token[:20]}...")

    # [AUTH-03] JWT decode attempt
    try:
        payload = decode_token(token)
    except Exception as e:
        logger.error(f"[AUTH-03-FAIL] JWT decode exception of type {type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
        raise AuthenticationException(message="Invalid or expired authentication credentials")

    if not payload:
        logger.warning("[AUTH-03-FAIL] JWT decode returned empty payload (invalid signature, expired, or malformed)")
        raise AuthenticationException(message="Invalid or expired authentication credentials")

    logger.info(f"[AUTH-03] JWT decoded successfully. Payload: {payload}")

    token_type = payload.get("type")
    if token_type != "access":
        logger.warning(f"[AUTH-03-FAIL] Wrong token type presented: type={token_type!r}")
        raise AuthenticationException(message="Invalid or expired authentication credentials")

    user_id_str = payload.get("sub")
    role = payload.get("role")
    gym_id_str = payload.get("gym_id")        # Optional — may be None
    branch_id_str = payload.get("branch_id") # Optional — may be None

    # [AUTH-04] Required claims check
    if not user_id_str or not role:
        logger.warning(
            f"[AUTH-04-FAIL] Malformed token — missing required claims: "
            f"sub={user_id_str!r} role={role!r}"
        )
        raise AuthenticationException(message="Token credentials are malformed")
    
    logger.info(f"[AUTH-04] Required claims present. sub={user_id_str}, role={role}")

    # [AUTH-05] UUID parsing
    try:
        user_uuid = uuid.UUID(user_id_str)
        logger.info(f"[AUTH-05] UUID parsed successfully: {user_uuid}")
    except ValueError as e:
        logger.error(f"[AUTH-05-FAIL] Invalid UUID in sub claim: {user_id_str!r}. Exception: {e}")
        raise AuthenticationException(message="Token identifiers are malformed UUIDs")

    # [AUTH-06] Database lookup and verification
    logger.info(f"[AUTH-06] Looking up user in database: user_id={user_uuid}...")
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
                logger.warning(f"[AUTH-06-FAIL] User account not found in DB: user_id={user_uuid}")
                raise AuthenticationException(message="User account not found or deactivated")

            if not db_user.is_active:
                logger.warning(f"[AUTH-06-FAIL] Account is disabled: user_id={user_uuid}")
                raise AuthenticationException(message="Account is disabled. Please contact support.")

            logger.info(f"[AUTH-06] User found: id={db_user.id}, email={db_user.email}, active={db_user.is_active}")

            if db_user.last_password_changed_at and payload.get("iat"):
                token_iat = payload.get("iat")
                if isinstance(token_iat, (int, float)):
                    user_change_ts = calendar.timegm(
                        db_user.last_password_changed_at.utctimetuple()
                    )
                    if token_iat <= user_change_ts:
                        logger.warning(
                            f"[AUTH-06-FAIL] Token revoked by password change: "
                            f"user_id={user_uuid} token_iat={token_iat} changed_at={user_change_ts}"
                        )
                        raise AuthenticationException(message="Session revoked. Please login again.")
        finally:
            db.close()
    except AuthenticationException:
        raise  # re-raise auth exceptions unchanged
    except Exception as e:
        logger.error(f"[AUTH-06-FAIL] DB lookup exception of type {type(e).__name__}: {str(e)}\n{traceback.format_exc()}")
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

    # [AUTH-07] Returning UserContext
    logger.info(f"[AUTH-07] Returning UserContext for user_id={user_uuid}, role={role}")
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
