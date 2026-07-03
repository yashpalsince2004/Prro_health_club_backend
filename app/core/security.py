from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import bcrypt
import jwt
from jwt.exceptions import PyJWTError
from app.core.config import settings
from loguru import logger


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed database password"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Password verification failed: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash of a plain text password"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def create_access_token(
    subject: Union[str, Any],
    role: str,
    gym_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generate a short-lived JWT Access Token.
    Includes subject (user_id), role, and tenant context (gym_id, branch_id) in claims.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": str(subject),
        "role": role,
        "gym_id": str(gym_id) if gym_id else None,
        "branch_id": str(branch_id) if branch_id else None,
        "exp": expire,
        "type": "access"
    }
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Generate a long-lived JWT Refresh Token for credential renewal."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh"
    }
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token payload.
    Returns empty dict if the token is expired or signature is invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except PyJWTError as e:
        logger.warning(f"Failed to decode JWT token: {str(e)}")
        return {}
