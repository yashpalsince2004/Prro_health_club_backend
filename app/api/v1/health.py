from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import httpx
from app.database.session import get_db
from app.core.config import settings
from app.utils.response import success_response, error_response
from loguru import logger

router = APIRouter(tags=["System Health"])


@router.get("/health")
def health_check():
    """Verify that the API is running and accessible"""
    return success_response(message="API is healthy", data={"status": "healthy"})


@router.get("/version")
def version_check():
    """Expose application metadata details"""
    return success_response(
        message="Application version details",
        data={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT
        }
    )


@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Check connections to dependent services (PostgreSQL, Supabase)"""
    db_status = "unconfigured"
    supabase_status = "unconfigured"
    is_ready = True
    
    # 1. Test Database Connectivity
    if settings.DATABASE_URL:
        try:
            db.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception as e:
            logger.error(f"Readiness check failed for Database: {str(e)}")
            db_status = f"unhealthy ({type(e).__name__})"
            is_ready = False
            
    # 2. Test Supabase Connectivity
    if settings.SUPABASE_URL:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # Ping the base REST endpoint to ensure domain/service is reachable
                res = await client.get(f"{settings.SUPABASE_URL}/rest/v1/")
                # 200 (OK) or 401 (Unauthorized) both indicate the server is reachable and active
                if res.status_code in (200, 401):
                    supabase_status = "healthy"
                else:
                    supabase_status = f"unhealthy (status {res.status_code})"
                    is_ready = False
        except Exception as e:
            logger.error(f"Readiness check failed for Supabase: {str(e)}")
            supabase_status = f"unhealthy ({type(e).__name__})"
            is_ready = False

    status_data = {
        "status": "ready" if is_ready else "not_ready",
        "services": {
            "database": db_status,
            "supabase": supabase_status
        }
    }
    
    if is_ready:
        return success_response(message="All systems operational", data=status_data)
    else:
        return error_response(
            code="SERVICE_UNAVAILABLE",
            message="One or more backend services are not ready",
            details=status_data,
            status_code=503
        )
