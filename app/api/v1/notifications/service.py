"""
Notification service — helper functions for creating in-app alerts from other modules.
All side effects are wrapped in exception handlers so parent transactions are not interrupted.
"""

from decimal import Decimal
from uuid import UUID
from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from app.models.notification import Notification, NotificationType


def create_notification(
    db: Session,
    recipient_user_id: UUID,
    type: NotificationType,
    title: str,
    message: str,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[UUID] = None
) -> Notification:
    """Low-level database helper to insert an in-app notification record."""
    try:
        new_notification = Notification(
            recipient_user_id=recipient_user_id,
            type=type,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            is_read=False
        )
        db.add(new_notification)
        db.flush()  # Generate ID and validate columns
        return new_notification
    except Exception as e:
        logger.error(f"[create_notification] Database write failed: {str(e)}")
        raise e


def notify_membership_expiring(db: Session, member_user_id: UUID, membership_id: UUID, days_remaining: int) -> None:
    """Triggered when a member's active subscription is close to expiration."""
    try:
        create_notification(
            db=db,
            recipient_user_id=member_user_id,
            type=NotificationType.MEMBERSHIP_EXPIRING,
            title="Membership Expiring Soon",
            message=f"Your membership subscription will expire in {days_remaining} days. Renew soon to avoid interruption.",
            related_entity_type="membership",
            related_entity_id=membership_id
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[notify_membership_expiring] failed to send notification: {str(e)}")


def notify_membership_expired(db: Session, member_user_id: UUID, membership_id: UUID) -> None:
    """Triggered when a member's subscription expires."""
    try:
        create_notification(
            db=db,
            recipient_user_id=member_user_id,
            type=NotificationType.MEMBERSHIP_EXPIRED,
            title="Membership Subscription Expired",
            message="Your membership subscription has expired. Please visit the front desk to purchase a renewal.",
            related_entity_type="membership",
            related_entity_id=membership_id
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[notify_membership_expired] failed to send notification: {str(e)}")


def notify_payment_received(db: Session, member_user_id: UUID, payment_id: UUID, amount: Decimal) -> None:
    """Triggered when a member's payment invoice is logged."""
    try:
        create_notification(
            db=db,
            recipient_user_id=member_user_id,
            type=NotificationType.PAYMENT_RECEIVED,
            title="Payment Invoice Recorded",
            message=f"A payment of INR {amount:.2f} has been received and credited to your account.",
            related_entity_type="payment",
            related_entity_id=payment_id
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[notify_payment_received] failed to send notification: {str(e)}")


def notify_unmatched_scan(db: Session, receptionist_user_ids: List[UUID], scan_id: UUID, raw_pin: int) -> None:
    """Triggered when a biometric push fails to match any member profile."""
    try:
        for rec_id in receptionist_user_ids:
            create_notification(
                db=db,
                recipient_user_id=rec_id,
                type=NotificationType.UNMATCHED_SCAN,
                title="Unrecognized Fingerprint Punch",
                message=f"An unrecognized biometric ID PIN '{raw_pin}' was registered at the device terminal. Please map it to a member.",
                related_entity_type="unmatched_scan",
                related_entity_id=scan_id
            )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[notify_unmatched_scan] failed to send notification to receptionists: {str(e)}")


def notify_plan_assigned(db: Session, member_user_id: UUID, plan_type: str, plan_id: UUID) -> None:
    """Triggered when a trainer prescribes a workout or nutrition plan to a member."""
    try:
        create_notification(
            db=db,
            recipient_user_id=member_user_id,
            type=NotificationType.PLAN_ASSIGNED,
            title=f"New {plan_type} Prescribed",
            message=f"Your trainer has prescribed a new {plan_type.lower()} program for you. Open your dashboard to view the routine.",
            related_entity_type="workout_plan" if "Workout" in plan_type else "diet_plan",
            related_entity_id=plan_id
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[notify_plan_assigned] failed to send notification: {str(e)}")
