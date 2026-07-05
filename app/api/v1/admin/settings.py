from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from app.database.session import get_db
from app.core.exceptions import NotFoundException
from app.core.constants import UserRole
from app.dependencies.auth import RoleChecker, UserContext
from app.utils.response import success_response
from app.models.gym_settings import GymSettings

class SettingUpdateItem(BaseModel):
    key: str
    value: Optional[str] = None

class SettingsUpdatePayload(BaseModel):
    settings: List[SettingUpdateItem]

router = APIRouter()

@router.get("/")
def get_all_settings(
    db: Session = Depends(get_db),
    current_admin: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Retrieve all gym system operating configuration settings grouped by category (Admin only)."""
    settings = db.query(GymSettings).order_by(GymSettings.category.asc(), GymSettings.key.asc()).all()
    
    # Group settings by category
    grouped: Dict[str, List[dict]] = {}
    for s in settings:
        category = s.category
        if category not in grouped:
            grouped[category] = []
        grouped[category].append({
            "key": s.key,
            "value": s.value,
            "category": s.category,
            "label": s.label,
            "description": s.description
        })
        
    return success_response(
        message="Grouped gym settings retrieved successfully",
        data=grouped
    )

@router.get("/{key}")
def get_single_setting(
    key: str,
    db: Session = Depends(get_db),
    current_admin: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Retrieve details for a single gym configuration setting key (Admin only)."""
    setting = db.query(GymSettings).filter(GymSettings.key == key).first()
    if not setting:
        raise NotFoundException(message=f"Setting key '{key}' not found")
        
    return success_response(
        message="Setting parameter retrieved",
        data={
            "key": setting.key,
            "value": setting.value,
            "category": setting.category,
            "label": setting.label,
            "description": setting.description
        }
    )

@router.patch("/")
def update_multiple_settings(
    payload: SettingsUpdatePayload,
    db: Session = Depends(get_db),
    current_admin: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Update multiple settings keys at once (Admin only)."""
    updated_count = 0
    for item in payload.settings:
        setting = db.query(GymSettings).filter(GymSettings.key == item.key).first()
        if setting:
            setting.value = item.value
            updated_count += 1
            
    db.commit()
    
    return success_response(
        message=f"Successfully updated {updated_count} gym settings keys"
    )
