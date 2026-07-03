"""
Pydantic schemas for Database Analytics Reports and Dashboard KPIs.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class RevenueDataPoint(BaseModel):
    """Timeline data point for revenue charts."""
    label: str
    amount: Decimal
    payment_count: int


class RevenueReport(BaseModel):
    """Revenue metrics report containing totals, method breakdowns, and timelines."""
    total_revenue: Decimal
    total_payments: int
    avg_per_payment: Decimal
    by_method: Dict[str, Decimal]
    by_status: Dict[str, int]
    timeline: List[RevenueDataPoint]
    currency: str = "INR"


class AttendanceDataPoint(BaseModel):
    """Timeline data point for daily/weekly attendance logs."""
    label: str
    total_visits: int
    unique_members: int
    biometric_count: int
    manual_count: int


class AttendanceReport(BaseModel):
    """Attendance statistics report."""
    total_visits: int
    unique_members: int
    avg_daily_visits: float
    peak_hour: Optional[int] = None
    peak_day: Optional[str] = None
    by_source: Dict[str, int]
    timeline: List[AttendanceDataPoint]


class MembershipTrendPoint(BaseModel):
    """Timeline trend data point for membership subscription status."""
    label: str
    new_memberships: int
    renewals: int
    cancellations: int
    active_total: int


class MembershipReport(BaseModel):
    """Comprehensive subscription analytics report."""
    total_active: int
    total_expired: int
    total_cancelled: int
    expiring_this_week: int
    expiring_this_month: int
    by_plan: Dict[str, int]
    timeline: List[MembershipTrendPoint]
    retention_rate: float


class DashboardSummary(BaseModel):
    """Top-level KPI summary cards for admin and receptionist dashboards."""
    total_members: int
    active_members: int
    new_members_this_month: int
    total_trainers: int
    available_trainers: int
    today_attendance: int
    this_month_revenue: Decimal
    last_month_revenue: Decimal
    revenue_growth_percent: float
    expiring_memberships_7_days: int
    unresolved_biometric_scans: int
    currency: str = "INR"


class TrainerPerformanceRow(BaseModel):
    """Overview statistics for a single trainer's roster."""
    trainer_id: UUID
    trainer_name: str
    assigned_members: int
    active_members: int
    plans_created: int
    avg_member_attendance: float


class TrainerPerformanceReport(BaseModel):
    """Consolidated performance details for all trainers."""
    period: str
    trainers: List[TrainerPerformanceRow]
