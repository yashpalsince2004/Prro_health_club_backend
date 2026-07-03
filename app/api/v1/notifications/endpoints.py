"""
FastAPI route handlers for in-app Notifications listing and status controls.
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.exceptions import NotFoundException, AuthorizationException
from app.dependencies.auth import get_current_user_context, UserContext
from app.utils.response import success_response
from app.models.notification import Notification
from app.api.v1.notifications.schemas import (
    NotificationResponse,
    NotificationListResponse
)

router = APIRouter()


@router.get("/", response_model=None)
def list_notifications(
    is_read: Optional[bool] = Query(None, description="Filter: True = read, False = unread, None = all"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve paginated notification alerts for the current authenticated user."""
    logger.info(f"[list_notifications] user={current_user.user_id} page={page}")

    query = db.query(Notification).filter(Notification.recipient_user_id == current_user.user_id)

    # Apply filter
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    total = query.count()
    
    # Calculate unread count globally for this user
    unread_count = db.query(func.count(Notification.id)).filter(
        Notification.recipient_user_id == current_user.user_id,
        Notification.is_read == False
    ).scalar() or 0

    notifications = query.order_by(Notification.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    mapped_list = [NotificationResponse.model_validate(n).model_dump() for n in notifications]
    
    res_data = NotificationListResponse(
        notifications=mapped_list,
        unread_count=unread_count,
        total=total
    )
    return success_response(message="Notifications list retrieved", data=res_data.model_dump())


@router.patch("/read-all", response_model=None)
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Mark all unread notifications of the logged-in user as read."""
    logger.info(f"[mark_all_as_read] user={current_user.user_id}")

    try:
        db.query(Notification).filter(
            Notification.recipient_user_id == current_user.user_id,
            Notification.is_read == False
        ).update({
            Notification.is_read: True,
            Notification.read_at: datetime.now(timezone.utc)
        })
        db.commit()
        return success_response(message="All notifications marked as read", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[mark_all_as_read] error: {str(e)}")
        raise e


@router.patch("/{notification_id}/read", response_model=None)
def mark_as_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Mark a single notification alert as read."""
    logger.info(f"[mark_as_read] user={current_user.user_id} target={notification_id}")

    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise NotFoundException(message="Notification not found")

    # Access rule: Can only mark own notification
    if notification.recipient_user_id != current_user.user_id:
        raise AuthorizationException(message="You are not authorized to modify this notification")

    try:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        
        res_data = NotificationResponse.model_validate(notification)
        return success_response(message="Notification marked as read", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[mark_as_read] error: {str(e)}")
        raise e


@router.delete("/{notification_id}", response_model=None)
def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Hard delete a notification (recipient user only)."""
    logger.info(f"[delete_notification] user={current_user.user_id} target={notification_id}")

    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise NotFoundException(message="Notification not found")

    # Access rule: Can only delete own notification
    if notification.recipient_user_id != current_user.user_id:
        raise AuthorizationException(message="You are not authorized to delete this notification")

    try:
        db.delete(notification)
        db.commit()
        return success_response(message="Notification deleted successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[delete_notification] error: {str(e)}")
        raise e
