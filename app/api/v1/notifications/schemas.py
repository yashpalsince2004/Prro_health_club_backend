"""
Pydantic schemas for Notification alerts.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    """Schema exposing details of an in-app notification alert."""
    id: UUID
    type: NotificationType
    title: str
    message: str
    is_read: bool
    read_at: Optional[datetime] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Paginated response containing matching alerts and unread statistics."""
    notifications: List[NotificationResponse]
    unread_count: int
    total: int
