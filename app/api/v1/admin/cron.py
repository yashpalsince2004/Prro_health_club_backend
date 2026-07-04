"""Admin-triggered cron endpoints."""
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.dependencies.auth import RoleChecker, get_current_user_context
from app.core.constants import UserRole
from app.services.expiry_service import ExpiryService
from app.utils.response import success_response

router = APIRouter()

@router.post("/run-expiry-check")
async def trigger_expiry_check(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(RoleChecker([UserRole.ADMIN]))
):
    """Admin can manually trigger membership expiry check."""
    service = ExpiryService(db)
    result = service.run_expiry_check(background_tasks=background_tasks)
    return success_response(
        message="Expiry check triggered successfully",
        data=result
    )
