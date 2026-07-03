"""
FastAPI route handlers for consolidated Database Analytics & Reports (read-only dashboards).
"""

from typing import Optional, List, Literal
from uuid import UUID
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.exceptions import AuthorizationException
from app.core.constants import UserRole, SubscriptionStatus, AttendanceSource
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response
from app.models.member import Member
from app.models.trainer import Trainer
from app.models.profile import Profile
from app.models.user import User
from app.models.attendance import AttendanceLog, UnmatchedScan
from app.models.payment import Payment, PaymentStatusEnum, PaymentMethodEnum
from app.models.membership import Membership
from app.models.plan import MembershipPlan
from app.models.workout import WorkoutPlan
from app.models.diet import DietPlan
from app.models.association import trainer_members
from app.api.v1.analytics.schemas import (
    DashboardSummary,
    RevenueReport,
    RevenueDataPoint,
    AttendanceReport,
    AttendanceDataPoint,
    MembershipReport,
    MembershipTrendPoint,
    TrainerPerformanceReport,
    TrainerPerformanceRow
)

router = APIRouter()

day_of_week_names = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday"
}


@router.get("/dashboard-summary", response_model=None)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve consolidated KPI dashboard stats (Admin + Receptionist)."""
    logger.info(f"[get_dashboard_summary] user={current_user.user_id}")

    today = date.today()
    start_of_month = today.replace(day=1)
    
    # Dates for previous month
    end_of_prev_month = start_of_month - timedelta(days=1)
    start_of_prev_month = end_of_prev_month.replace(day=1)

    start_of_today_dt = datetime.combine(today, time.min).replace(tzinfo=timezone.utc)
    start_of_month_dt = datetime.combine(start_of_month, time.min).replace(tzinfo=timezone.utc)
    start_of_prev_month_dt = datetime.combine(start_of_prev_month, time.min).replace(tzinfo=timezone.utc)
    end_of_prev_month_dt = datetime.combine(end_of_prev_month, time.max).replace(tzinfo=timezone.utc)

    # 1. Member stats
    total_members = db.query(func.count(Member.id)).filter(Member.is_deleted == False).scalar() or 0
    active_members = db.query(func.count(Member.id)).filter(
        Member.is_deleted == False,
        Member.memberships.any(
            (Membership.status == SubscriptionStatus.ACTIVE) &
            (Membership.start_date <= today) &
            (Membership.end_date >= today)
        )
    ).scalar() or 0
    
    new_members_this_month = db.query(func.count(Member.id)).filter(
        Member.is_deleted == False,
        Member.joining_date >= start_of_month
    ).scalar() or 0

    # 2. Trainer stats
    total_trainers = db.query(func.count(Trainer.id)).filter(Trainer.is_deleted == False).scalar() or 0
    available_trainers = db.query(func.count(Trainer.id)).filter(
        Trainer.is_deleted == False,
        Trainer.is_available == True
    ).scalar() or 0

    # 3. Attendance
    today_attendance = db.query(func.count(AttendanceLog.id)).filter(
        AttendanceLog.check_in >= start_of_today_dt
    ).scalar() or 0

    # 4. Revenue
    this_month_revenue = db.query(func.sum(Payment.amount_paid)).filter(
        Payment.payment_status == PaymentStatusEnum.COMPLETED,
        Payment.payment_date >= start_of_month_dt
    ).scalar() or 0.0
    
    last_month_revenue = db.query(func.sum(Payment.amount_paid)).filter(
        Payment.payment_status == PaymentStatusEnum.COMPLETED,
        Payment.payment_date >= start_of_prev_month_dt,
        Payment.payment_date <= end_of_prev_month_dt
    ).scalar() or 0.0

    # Growth percent
    growth_percent = 0.0
    if last_month_revenue > 0:
        growth_percent = float(((this_month_revenue - last_month_revenue) / last_month_revenue) * 100)

    # 5. Alerts
    next_week = today + timedelta(days=7)
    expiring_memberships_7_days = db.query(func.count(Membership.id)).filter(
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.end_date >= today,
        Membership.end_date <= next_week,
        Membership.is_deleted == False
    ).scalar() or 0

    unresolved_biometric_scans = db.query(func.count(UnmatchedScan.id)).filter(
        UnmatchedScan.is_read == False if hasattr(UnmatchedScan, 'is_read') else UnmatchedScan.is_resolved == False
    ).scalar() or 0

    summary = DashboardSummary(
        total_members=total_members,
        active_members=active_members,
        new_members_this_month=new_members_this_month,
        total_trainers=total_trainers,
        available_trainers=available_trainers,
        today_attendance=today_attendance,
        this_month_revenue=Decimal(str(this_month_revenue)),
        last_month_revenue=Decimal(str(last_month_revenue)),
        revenue_growth_percent=growth_percent,
        expiring_memberships_7_days=expiring_memberships_7_days,
        unresolved_biometric_scans=unresolved_biometric_scans
    )
    return success_response(message="Dashboard KPI stats retrieved", data=summary.model_dump())


@router.get("/revenue", response_model=None)
def get_revenue_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    group_by: Literal["day", "week", "month"] = Query("month"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve consolidated revenue reports (Admin + Receptionist)."""
    logger.info(f"[get_revenue_report] user={current_user.user_id} group={group_by}")

    from_dt = datetime.combine(from_date, time.min).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, time.max).replace(tzinfo=timezone.utc)

    # 1. Total Metrics
    totals = db.query(
        func.sum(Payment.amount_paid).label("total_rev"),
        func.count(Payment.id).label("total_count")
    ).filter(
        Payment.payment_status == PaymentStatusEnum.COMPLETED,
        Payment.payment_date >= from_dt,
        Payment.payment_date <= to_dt
    ).one()

    total_revenue = Decimal(str(totals.total_rev or 0.0))
    total_payments = totals.total_count or 0
    avg_per_payment = total_revenue / total_payments if total_payments > 0 else Decimal("0.00")

    # 2. Method Breakdown
    methods = db.query(
        Payment.payment_method,
        func.sum(Payment.amount_paid).label("amt")
    ).filter(
        Payment.payment_status == PaymentStatusEnum.COMPLETED,
        Payment.payment_date >= from_dt,
        Payment.payment_date <= to_dt
    ).group_by(Payment.payment_method).all()

    by_method = {method.value: Decimal("0.00") for method in PaymentMethodEnum}
    for m, amt in methods:
        by_method[m.value] = Decimal(str(amt or 0.0))

    # 3. Status Breakdown
    statuses = db.query(
        Payment.payment_status,
        func.count(Payment.id).label("cnt")
    ).filter(
        Payment.payment_date >= from_dt,
        Payment.payment_date <= to_dt
    ).group_by(Payment.payment_status).all()

    by_status = {status_val.value: 0 for status_val in PaymentStatusEnum}
    for s, cnt in statuses:
        by_status[s.value] = cnt or 0

    # 4. Timeline (PostgreSQL date_trunc)
    timeline_results = db.query(
        func.date_trunc(group_by, Payment.payment_date).label("period"),
        func.sum(Payment.amount_paid).label("amt"),
        func.count(Payment.id).label("cnt")
    ).filter(
        Payment.payment_status == PaymentStatusEnum.COMPLETED,
        Payment.payment_date >= from_dt,
        Payment.payment_date <= to_dt
    ).group_by(
        func.date_trunc(group_by, Payment.payment_date)
    ).order_by(
        func.date_trunc(group_by, Payment.payment_date).asc()
    ).all()

    timeline = []
    for period, amt, cnt in timeline_results:
        if group_by == "month":
            label = period.strftime("%b %Y")
        elif group_by == "week":
            label = f"Week {period.strftime('%W, %Y')}"
        else:
            label = period.strftime("%Y-%m-%d")

        timeline.append(
            RevenueDataPoint(
                label=label,
                amount=Decimal(str(amt or 0.0)),
                payment_count=cnt or 0
            )
        )

    report = RevenueReport(
        total_revenue=total_revenue,
        total_payments=total_payments,
        avg_per_payment=avg_per_payment,
        by_method=by_method,
        by_status=by_status,
        timeline=timeline
    )
    return success_response(message="Revenue report compiled", data=report.model_dump())


@router.get("/attendance", response_model=None)
def get_attendance_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    group_by: Literal["day", "week", "month"] = Query("day"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve consolidated attendance analysis (Admin + Receptionist)."""
    logger.info(f"[get_attendance_report] user={current_user.user_id} group={group_by}")

    from_dt = datetime.combine(from_date, time.min).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, time.max).replace(tzinfo=timezone.utc)

    # 1. Total Metrics
    totals = db.query(
        func.count(AttendanceLog.id).label("total_vis"),
        func.count(func.distinct(AttendanceLog.member_id)).label("uniq_m")
    ).filter(
        AttendanceLog.check_in >= from_dt,
        AttendanceLog.check_in <= to_dt
    ).one()

    total_visits = totals.total_vis or 0
    unique_members = totals.uniq_m or 0

    # Calculate average daily visits
    total_days = max(1, (to_date - from_date).days + 1)
    avg_daily_visits = float(total_visits / total_days)

    # 2. Peak Hours (Extract hour and group)
    peak_hour_result = db.query(
        extract("hour", AttendanceLog.check_in).label("hour"),
        func.count(AttendanceLog.id).label("cnt")
    ).filter(
        AttendanceLog.check_in >= from_dt,
        AttendanceLog.check_in <= to_dt
    ).group_by(
        extract("hour", AttendanceLog.check_in)
    ).order_by(
        func.count(AttendanceLog.id).desc()
    ).first()

    peak_hour = int(peak_hour_result.hour) if peak_hour_result else None

    # 3. Peak Day (DOW)
    peak_day_result = db.query(
        extract("dow", AttendanceLog.check_in).label("dow"),
        func.count(AttendanceLog.id).label("cnt")
    ).filter(
        AttendanceLog.check_in >= from_dt,
        AttendanceLog.check_in <= to_dt
    ).group_by(
        extract("dow", AttendanceLog.check_in)
    ).order_by(
        func.count(AttendanceLog.id).desc()
    ).first()

    peak_day = day_of_week_names.get(int(peak_day_result.dow)) if peak_day_result else None

    # 4. Source Breakdown
    sources = db.query(
        AttendanceLog.source,
        func.count(AttendanceLog.id).label("cnt")
    ).filter(
        AttendanceLog.check_in >= from_dt,
        AttendanceLog.check_in <= to_dt
    ).group_by(AttendanceLog.source).all()

    by_source = {src.value: 0 for src in AttendanceSource}
    for src, cnt in sources:
        by_source[src.value] = cnt or 0

    # 5. Timeline (PostgreSQL date_trunc)
    timeline_results = db.query(
        func.date_trunc(group_by, AttendanceLog.check_in).label("period"),
        func.count(AttendanceLog.id).label("total_vis"),
        func.count(func.distinct(AttendanceLog.member_id)).label("uniq_m"),
        func.count(AttendanceLog.id).filter(AttendanceLog.source == AttendanceSource.BIOMETRIC).label("biometric_vis"),
        func.count(AttendanceLog.id).filter(AttendanceLog.source == AttendanceSource.MANUAL).label("manual_vis")
    ).filter(
        AttendanceLog.check_in >= from_dt,
        AttendanceLog.check_in <= to_dt
    ).group_by(
        func.date_trunc(group_by, AttendanceLog.check_in)
    ).order_by(
        func.date_trunc(group_by, AttendanceLog.check_in).asc()
    ).all()

    timeline = []
    for period, vis, uniq, bio, man in timeline_results:
        if group_by == "month":
            label = period.strftime("%b %Y")
        elif group_by == "week":
            label = f"Week {period.strftime('%W, %Y')}"
        else:
            label = period.strftime("%Y-%m-%d")

        timeline.append(
            AttendanceDataPoint(
                label=label,
                total_visits=vis or 0,
                unique_members=uniq or 0,
                biometric_count=bio or 0,
                manual_count=man or 0
            )
        )

    report = AttendanceReport(
        total_visits=total_visits,
        unique_members=unique_members,
        avg_daily_visits=avg_daily_visits,
        peak_hour=peak_hour,
        peak_day=peak_day,
        by_source=by_source,
        timeline=timeline
    )
    return success_response(message="Attendance report compiled", data=report.model_dump())


@router.get("/memberships", response_model=None)
def get_membership_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    group_by: Literal["week", "month"] = Query("month"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve membership acquisition and subscription trends (Admin + Receptionist)."""
    logger.info(f"[get_membership_report] user={current_user.user_id} group={group_by}")

    today = date.today()
    from_dt = datetime.combine(from_date, time.min).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, time.max).replace(tzinfo=timezone.utc)

    # 1. Overall Status Counts
    total_active = db.query(func.count(Membership.id)).filter(
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.is_deleted == False
    ).scalar() or 0

    total_expired = db.query(func.count(Membership.id)).filter(
        Membership.status == SubscriptionStatus.EXPIRED,
        Membership.is_deleted == False
    ).scalar() or 0

    total_cancelled = db.query(func.count(Membership.id)).filter(
        Membership.status == SubscriptionStatus.CANCELLED,
        Membership.is_deleted == False
    ).scalar() or 0

    # 2. Expirations Alerts
    next_week = today + timedelta(days=7)
    expiring_this_week = db.query(func.count(Membership.id)).filter(
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.end_date >= today,
        Membership.end_date <= next_week,
        Membership.is_deleted == False
    ).scalar() or 0

    next_month = today + timedelta(days=30)
    expiring_this_month = db.query(func.count(Membership.id)).filter(
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.end_date >= today,
        Membership.end_date <= next_month,
        Membership.is_deleted == False
    ).scalar() or 0

    # 3. Plan Distribution Breakdown
    plans = db.query(
        MembershipPlan.name,
        func.count(Membership.id).label("cnt")
    ).join(
        Membership, MembershipPlan.id == Membership.plan_id
    ).filter(
        Membership.status == SubscriptionStatus.ACTIVE,
        Membership.is_deleted == False
    ).group_by(MembershipPlan.name).all()

    by_plan = {plan.name: cnt for plan, cnt in plans}

    # 4. Retention Rate: % of members who have 2+ memberships (renewed subscription)
    members_with_subscriptions = db.query(
        Membership.member_id,
        func.count(Membership.id).label("cnt")
    ).filter(
        Membership.is_deleted == False
    ).group_by(Membership.member_id).all()

    total_sub_members = len(members_with_subscriptions)
    retained_members = sum(1 for m in members_with_subscriptions if m.cnt >= 2)
    retention_rate = float((retained_members / total_sub_members) * 100) if total_sub_members > 0 else 0.0

    # 5. Timeline acquisition trend (PostgreSQL date_trunc)
    timeline_results = db.query(
        func.date_trunc(group_by, Membership.created_at).label("period"),
        func.count(Membership.id).label("total_new"),
        func.count(Membership.id).filter(Membership.status == SubscriptionStatus.EXPIRED).label("expired_cnt"),
        func.count(Membership.id).filter(Membership.status == SubscriptionStatus.CANCELLED).label("cancelled_cnt")
    ).filter(
        Membership.created_at >= from_dt,
        Membership.created_at <= to_dt,
        Membership.is_deleted == False
    ).group_by(
        func.date_trunc(group_by, Membership.created_at)
    ).order_by(
        func.date_trunc(group_by, Membership.created_at).asc()
    ).all()

    timeline = []
    active_cumulative = 0  # Running cumulative active count
    for period, total_new, expired, cancelled in timeline_results:
        label = period.strftime("%b %Y") if group_by == "month" else f"Week {period.strftime('%W, %Y')}"
        active_cumulative += (total_new - expired - cancelled)

        timeline.append(
            MembershipTrendPoint(
                label=label,
                new_memberships=total_new or 0,
                renewals=0,  # Renewals represented by new rows linked to existing member
                cancellations=cancelled or 0,
                active_total=max(0, active_cumulative)
            )
        )

    report = MembershipReport(
        total_active=total_active,
        total_expired=total_expired,
        total_cancelled=total_cancelled,
        expiring_this_week=expiring_this_week,
        expiring_this_month=expiring_this_month,
        by_plan=by_plan,
        timeline=timeline,
        retention_rate=retention_rate
    )
    return success_response(message="Membership subscription report compiled", data=report.model_dump())


@router.get("/trainer-performance", response_model=None)
def get_trainer_performance(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Retrieve detailed trainer roster performance metrics (Admin only)."""
    logger.info(f"[get_trainer_performance] user={current_user.user_id}")

    from_dt = datetime.combine(from_date, time.min).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, time.max).replace(tzinfo=timezone.utc)

    # 1. Fetch all trainers
    trainers = db.query(Trainer).options(
        joinedload(Trainer.profile)
    ).filter(Trainer.is_deleted == False).all()

    today = date.today()
    trainer_performance_rows = []

    for trainer in trainers:
        t_name = trainer.profile.full_name if trainer.profile else "Unknown Trainer"

        # Count total members assigned to this trainer
        assigned_members = db.query(func.count(trainer_members.c.member_id)).filter(
            trainer_members.c.trainer_id == trainer.id,
            trainer_members.c.is_active == True
        ).scalar() or 0

        # Count active members assigned to this trainer (assigned member has an active membership)
        active_members = db.query(func.count(Member.id)).filter(
            Member.is_deleted == False,
            Member.id.in_(
                db.query(trainer_members.c.member_id).filter(
                    trainer_members.c.trainer_id == trainer.id,
                    trainer_members.c.is_active == True
                )
            ),
            Member.memberships.any(
                (Membership.status == SubscriptionStatus.ACTIVE) &
                (Membership.start_date <= today) &
                (Membership.end_date >= today)
            )
        ).scalar() or 0

        # Plans created this month by this trainer
        workout_plans_created = db.query(func.count(WorkoutPlan.id)).filter(
            WorkoutPlan.trainer_id == trainer.id,
            WorkoutPlan.created_at >= from_dt,
            WorkoutPlan.created_at <= to_dt,
            WorkoutPlan.is_deleted == False
        ).scalar() or 0
        
        diet_plans_created = db.query(func.count(DietPlan.id)).filter(
            DietPlan.trainer_id == trainer.id,
            DietPlan.created_at >= from_dt,
            DietPlan.created_at <= to_dt,
            DietPlan.is_deleted == False
        ).scalar() or 0

        plans_created = workout_plans_created + diet_plans_created

        # Avg attendance visits/week for assigned members
        assigned_member_ids = db.query(trainer_members.c.member_id).filter(
            trainer_members.c.trainer_id == trainer.id,
            trainer_members.c.is_active == True
        ).all()
        
        assigned_member_uuids = [row.member_id for row in assigned_member_ids]

        avg_attendance = 0.0
        if assigned_member_uuids:
            total_visits_assigned = db.query(func.count(AttendanceLog.id)).filter(
                AttendanceLog.member_id.in_(assigned_member_uuids),
                AttendanceLog.check_in >= from_dt,
                AttendanceLog.check_in <= to_dt
            ).scalar() or 0
            
            weeks = max(1.0, float((to_date - from_date).days / 7.0))
            avg_attendance = float((total_visits_assigned / len(assigned_member_uuids)) / weeks)

        trainer_performance_rows.append(
            TrainerPerformanceRow(
                trainer_id=trainer.id,
                trainer_name=t_name,
                assigned_members=assigned_members,
                active_members=active_members,
                plans_created=plans_created,
                avg_member_attendance=avg_attendance
            )
        )

    report = TrainerPerformanceReport(
        period=f"From {from_date} to {to_date}",
        trainers=trainer_performance_rows
    )
    return success_response(message="Trainer performance report compiled", data=report.model_dump())
