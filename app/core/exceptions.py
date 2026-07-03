from typing import Any, Optional


class APIException(Exception):
    """Base API Exception for domain errors"""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Any] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class AuthenticationException(APIException):
    def __init__(self, message: str = "Authentication failed", details: Optional[Any] = None):
        super().__init__(
            code="UNAUTHENTICATED",
            message=message,
            status_code=401,
            details=details
        )


class AuthorizationException(APIException):
    def __init__(self, message: str = "Not authorized to perform this action", details: Optional[Any] = None):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=403,
            details=details
        )


class NotFoundException(APIException):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=404,
            details=details
        )


class ConflictException(APIException):
    def __init__(self, message: str = "Resource conflict occurred", details: Optional[Any] = None):
        super().__init__(
            code="CONFLICT",
            message=message,
            status_code=409,
            details=details
        )


class InternalServerException(APIException):
    def __init__(self, message: str = "Internal server error", details: Optional[Any] = None):
        super().__init__(
            code="INTERNAL_SERVER_ERROR",
            message=message,
            status_code=500,
            details=details
        )
