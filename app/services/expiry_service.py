"""
Membership expiry business logic.
Called by both the cron script and the admin endpoint.
All email side effects use BackgroundTasks where available,
or direct calls when running as a standalone script.
"""
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from fastapi import BackgroundTasks
from loguru import logger
from app.models.membership import Membership
from app.core.constants import SubscriptionStatus
from app.api.v1.notifications.service import notify_membership_expiring, notify_membership_expired
from app.services import email_service

class ExpiryService:
    def __init__(self, db: Session):
        self.db = db
        
    def run_expiry_check(self, background_tasks: Optional[BackgroundTasks] = None) -> dict:
        """
        Main entry point. Call this from both cron and admin endpoint.
        Returns summary: { "expiring_notified": int, "expired_updated": int }
        """
        today = date.today()
        expiring_date = today + timedelta(days=7)
        
        # 1. Expiring soon: end_date == today + 7 days AND status == ACTIVE
        expiring_memberships = self.db.query(Membership).options(
            joinedload(Membership.member).joinedload(lambda m: m.profile).joinedload(lambda p: p.user),
            joinedload(Membership.plan)
        ).filter(
            Membership.end_date == expiring_date,
            Membership.status == SubscriptionStatus.ACTIVE,
            Membership.is_deleted == False
        ).all()
        
        expiring_notified = 0
        for m in expiring_memberships:
            if m.member and m.member.profile and m.member.profile.user:
                user = m.member.profile.user
                profile = m.member.profile
                
                # In-app notification
                notify_membership_expiring(self.db, user.id, m.id, 7)
                
                # Email notification
                if background_tasks:
                    background_tasks.add_task(
                        email_service.send_membership_expiry_reminder,
                        user.email,
                        profile.full_name,
                        m.plan.name,
                        m.end_date,
                        7
                    )
                else:
                    email_service.send_membership_expiry_reminder(
                        user.email,
                        profile.full_name,
                        m.plan.name,
                        m.end_date,
                        7
                    )
                expiring_notified += 1
                
        # 2. Expired: end_date < today AND status == ACTIVE
        expired_memberships = self.db.query(Membership).options(
            joinedload(Membership.member).joinedload(lambda m: m.profile).joinedload(lambda p: p.user),
            joinedload(Membership.plan)
        ).filter(
            Membership.end_date < today,
            Membership.status == SubscriptionStatus.ACTIVE,
            Membership.is_deleted == False
        ).all()
        
        expired_updated = 0
        for m in expired_memberships:
            if m.member and m.member.profile and m.member.profile.user:
                user = m.member.profile.user
                profile = m.member.profile
                
                # Update status
                m.status = SubscriptionStatus.EXPIRED
                self.db.add(m)
                
                # In-app notification
                notify_membership_expired(self.db, user.id, m.id)
                
                # Email notification
                if background_tasks:
                    background_tasks.add_task(
                        email_service.send_membership_expired_email,
                        user.email,
                        profile.full_name,
                        m.plan.name,
                        m.end_date
                    )
                else:
                    email_service.send_membership_expired_email(
                        user.email,
                        profile.full_name,
                        m.plan.name,
                        m.end_date
                    )
                expired_updated += 1
                
        self.db.commit()
        return {
            "expiring_notified": expiring_notified,
            "expired_updated": expired_updated
        }
