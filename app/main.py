from contextlib import asynccontextmanager
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import APIException
from app.core.logging import setup_logging
from app.middleware.request_context import RequestContextMiddleware
from app.utils.response import error_response

# Initialize logging before creating the FastAPI instance
setup_logging(debug=settings.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown lifecycle events."""
    logger.info("Initializing Prro Health Club ERP Backend Services...")
    # Place any startup operations here (e.g., establishing DB connections, priming caches)
    yield
    logger.info("Stopping Prro Health Club ERP Backend Services...")
    # Place clean up actions here (e.g., closing open connections)


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Production-ready backend API for Prro Health Club ERP system.\n\n"
        "Designed under Clean Architecture principles to support members, trainers, "
        "receptionists, biometric sync, automated payments, and multi-tenant expansion."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" or settings.DEBUG else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" or settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" or settings.DEBUG else None,
    contact={
        "name": "Prro Health Club Support Team",
        "email": "support@prrohealthclub.com",
    },
    license_info={
        "name": "Proprietary & Confidential",
    }
)

# --------------------------------------------------------------------------
# Middleware Registration (Processed bottom-to-top)
# --------------------------------------------------------------------------

# 4. Gzip response compression for packages exceeding 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Cross-Origin Resource Sharing (CORS) rules
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Prevent Host Header Injection Attacks (enforce specified hosts)
# In local development or debug mode, allow all hosts (*)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.DEBUG else ["prrohealthclub.com", "*.prrohealthclub.com"]
)

# 1. Request ID injector (Executes first to attach context variable tracing)
app.add_middleware(RequestContextMiddleware)


# --------------------------------------------------------------------------
# Exception Handlers (Standardizing JSON responses)
# --------------------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """Catch standard HTTPExceptions and format them to match JSON standards"""
    return error_response(
        code=f"HTTP_{exc.status_code}",
        message=exc.detail,
        status_code=exc.status_code
    )


@app.exception_handler(APIException)
async def api_exception_handler(request, exc: APIException):
    """Catch application custom exceptions and return uniform error structures"""
    return error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Intercept Pydantic validation errors and format them to match JSON standards"""
    raw_errors = exc.errors()
    formatted_details = []
    
    for err in raw_errors:
        # Simplify validation error context for API clients
        loc = " -> ".join([str(item) for item in err.get("loc", [])])
        formatted_details.append({
            "field": loc,
            "message": err.get("msg", "Validation failed"),
            "error_type": err.get("type", "value_error")
        })
        
    return error_response(
        code="VALIDATION_ERROR",
        message="Request payload validation failed",
        details=formatted_details,
        status_code=422
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """Catch any unhandled systemic failures, log tracing, and mask raw stack traces"""
    logger.exception("An unhandled exception occurred during request execution")
    return error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected system error occurred. Please contact support.",
        status_code=500
    )


# --------------------------------------------------------------------------
# Router Registration
# --------------------------------------------------------------------------

# Register versioned API router under the version prefix
app.include_router(api_router, prefix="/api/v1")