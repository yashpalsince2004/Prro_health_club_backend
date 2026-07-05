from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.constants import UserRole
from app.dependencies.auth import RoleChecker, UserContext
from app.services.report_service import ReportService

router = APIRouter()

@router.get("/members")
def get_members_excel_report(
    status: str = Query("all"),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Generate Excel report of all gym members and status (Admin + Receptionist)."""
    excel_bytes = ReportService.generate_members_report(db, status_filter=status)
    filename = f"members-report-{date.today().isoformat()}"
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'}
    )

@router.get("/attendance")
def get_attendance_excel_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Generate Excel report of attendance logs (Admin + Receptionist)."""
    excel_bytes = ReportService.generate_attendance_report(db, from_date=from_date, to_date=to_date)
    filename = f"attendance-report-{from_date.isoformat()}-to-{to_date.isoformat()}"
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'}
    )

@router.get("/payments")
def get_payments_excel_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Generate Excel report of transactions and payment methods (Admin + Receptionist)."""
    excel_bytes = ReportService.generate_payments_report(db, from_date=from_date, to_date=to_date)
    filename = f"payments-report-{from_date.isoformat()}-to-{to_date.isoformat()}"
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'}
    )

@router.get("/expiry")
def get_expiry_excel_report(
    days_ahead: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Generate Excel report of memberships expiring soon (Admin + Receptionist)."""
    excel_bytes = ReportService.generate_expiry_report(db, days_ahead=days_ahead)
    filename = f"expiry-report-{date.today().isoformat()}-days-{days_ahead}"
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'}
    )
