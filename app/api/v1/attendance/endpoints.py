"""
FastAPI route handlers for front-desk Attendance log operations and unmatched scan resolutions.
"""

import math
from typing import Optional
from uuid import UUID
from datetime import datetime, time, date, timezone
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.database.session import get_db
from app.core.exceptions import NotFoundException, AuthorizationException, ConflictException
from app.core.constants import UserRole, AttendanceSource
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.member import Member
from app.models.profile import Profile
from app.models.user import User
from app.models.attendance import AttendanceLog, UnmatchedScan
from app.api.v1.attendance.schemas import (
    ManualAttendanceCreate,
    AttendanceLogResponse,
    AttendanceSummary,
    UnmatchedScanResponse,
    ResolveUnmatchedScanRequest,
    AttendanceListResponse
)

router = APIRouter()


def _map_attendance_to_response(log: AttendanceLog) -> AttendanceLogResponse:
    """Helper to map an AttendanceLog db model to AttendanceLogResponse schema."""
    member_profile = log.member.profile if log.member else None
    member_name = member_profile.full_name if member_profile else "Unknown Member"

    duration = None
    if log.check_out:
        duration = (log.check_out - log.check_in).seconds // 60

    return AttendanceLogResponse(
        id=log.id,
        member_id=log.member_id,
        member_name=member_name,
        check_in=log.check_in,
        check_out=log.check_out,
        source=log.source,
        device_serial=log.device_serial,
        raw_pin=log.raw_pin,
        notes=log.notes,
        duration_minutes=duration
    )


@router.post("/manual", response_model=None)
def record_manual_attendance(
    payload: ManualAttendanceCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Record manual check-in/check-out at the front desk."""
    logger.info(f"[record_manual_attendance] user={current_user.user_id} member={payload.member_id}")

    member = db.query(Member).filter(Member.id == payload.member_id, Member.is_deleted == False).first()
    if not member:
        raise NotFoundException(message="Member not found")

    # If member already has an open check-in today (check_out is None), update it instead
    today_start = datetime.combine(payload.check_in.date(), time.min).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(payload.check_in.date(), time.max).replace(tzinfo=timezone.utc)

    open_log = db.query(AttendanceLog).filter(
        AttendanceLog.member_id == payload.member_id,
        AttendanceLog.check_in >= today_start,
        AttendanceLog.check_in <= today_end,
        AttendanceLog.check_out == None
    ).first()

    try:
        if open_log:
            logger.info(f"[record_manual_attendance] Updating open check-in for member={payload.member_id}")
            open_log.check_out = payload.check_out or datetime.now(timezone.utc)
            if payload.notes:
                open_log.notes = f"{open_log.notes or ''}\n{payload.notes}".strip()
            db.commit()
            db.refresh(open_log)
            # Reload with profile
            log_with_relations = db.query(AttendanceLog).options(
                joinedload(AttendanceLog.member).joinedload(Member.profile)
            ).filter(AttendanceLog.id == open_log.id).first()
            return success_response(message="Manual check-out recorded successfully", data=_map_attendance_to_response(log_with_relations).model_dump())

        # Otherwise create a new check-in
        new_log = AttendanceLog(
            member_id=payload.member_id,
            check_in=payload.check_in,
            check_out=payload.check_out,
            source=AttendanceSource.MANUAL,
            marked_by=current_user.user_id,
            notes=payload.notes
        )
        db.add(new_log)
        db.commit()

        # Reload for mapping
        log_with_relations = db.query(AttendanceLog).options(
            joinedload(AttendanceLog.member).joinedload(Member.profile)
        ).filter(AttendanceLog.id == new_log.id).first()

        res_data = _map_attendance_to_response(log_with_relations)
        return success_response(message="Manual check-in recorded successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[record_manual_attendance] error during database transaction: {str(e)}")
        raise e


@router.get("/today", response_model=None)
def get_today_attendance(
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve all check-ins for the current calendar date (Front desk dashboard monitor)."""
    logger.info(f"[get_today_attendance] user={current_user.user_id}")

    today_start = datetime.combine(date.today(), time.min).replace(tzinfo=timezone.utc)

    logs = db.query(AttendanceLog).options(
        joinedload(AttendanceLog.member).joinedload(Member.profile)
    ).filter(
        AttendanceLog.check_in >= today_start
    ).order_by(AttendanceLog.check_in.desc()).all()

    mapped_list = [_map_attendance_to_response(l).model_dump() for l in logs]
    return success_response(message="Today's attendance logs retrieved", data=mapped_list)


@router.get("/unmatched", response_model=None)
def list_unmatched_scans(
    is_resolved: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve unprocessed biometric punches (receptionist resolution view)."""
    logger.info(f"[list_unmatched_scans] user={current_user.user_id} is_resolved={is_resolved}")

    scans = db.query(UnmatchedScan).filter(
        UnmatchedScan.is_resolved == is_resolved
    ).order_by(UnmatchedScan.scan_datetime.desc()).all()

    mapped_list = [UnmatchedScanResponse.model_validate(s).model_dump() for s in scans]
    return success_response(message="Unmatched scans retrieved", data=mapped_list)


@router.post("/unmatched/{scan_id}/resolve", response_model=None)
def resolve_unmatched_scan(
    scan_id: UUID,
    payload: ResolveUnmatchedScanRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Resolve an unrecognized biometric punch, mapping its PIN to a member."""
    logger.info(f"[resolve_unmatched_scan] user={current_user.user_id} scan={scan_id} member={payload.member_id}")

    scan = db.query(UnmatchedScan).filter(
        UnmatchedScan.id == scan_id,
        UnmatchedScan.is_resolved == False
    ).first()

    if not scan:
        raise NotFoundException(message="Unresolved scan not found")

    member = db.query(Member).options(joinedload(Member.profile)).filter(
        Member.id == payload.member_id,
        Member.is_deleted == False
    ).first()

    if not member:
        raise NotFoundException(message="Member not found")

    profile = member.profile

    # Check PIN uniqueness
    existing_pin = db.query(Profile).filter(
        Profile.biometric_device_id == scan.raw_pin,
        Profile.id != profile.id
    ).first()
    if existing_pin:
        raise ConflictException(message=f"Biometric ID '{scan.raw_pin}' is already assigned to another user profile")

    try:
        # 1. Update member profile with biometric device ID
        profile.biometric_device_id = scan.raw_pin

        # 2. Mark the unmatched scan record as resolved
        scan.is_resolved = True
        scan.resolved_at = datetime.now(timezone.utc)
        scan.resolved_by = current_user.user_id
        scan.resolved_member_id = payload.member_id

        # 3. Create active AttendanceLog if requested
        if payload.create_attendance_record:
            new_log = AttendanceLog(
                member_id=payload.member_id,
                check_in=scan.scan_datetime,
                source=AttendanceSource.BIOMETRIC,
                device_serial=scan.device_serial,
                raw_pin=scan.raw_pin,
                notes=f"Linked during unmatched scan resolution on {datetime.now().strftime('%Y-%m-%d')}"
            )
            db.add(new_log)

        db.commit()
        return success_response(message="Biometric device punch resolved and member linked successfully", data={})

    except Exception as e:
        db.rollback()
        logger.error(f"[resolve_unmatched_scan] error during resolution: {str(e)}")
        raise e


@router.get("/summary", response_model=None)
def get_attendance_summary(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve compiled attendance reports and metrics."""
    logger.info(f"[get_attendance_summary] user={current_user.user_id}")

    query = db.query(AttendanceLog)
    if from_date:
        query = query.filter(AttendanceLog.check_in >= from_date)
    if to_date:
        query = query.filter(AttendanceLog.check_in <= to_date)

    logs = query.all()

    total_visits = len(logs)
    unique_members = len(set(log.member_id for log in logs))

    # Calculate average duration
    durations = []
    for log in logs:
        if log.check_out:
            durations.append((log.check_out - log.check_in).seconds // 60)
    avg_duration = sum(durations) / len(durations) if durations else None

    # Source breakdown
    by_source = {}
    for src in AttendanceSource:
        by_source[src.value] = 0
    for log in logs:
        by_source[log.source.value] += 1

    # Busiest hour (0-23)
    hours = [log.check_in.hour for log in logs]
    busiest_hour = max(set(hours), key=hours.count) if hours else None

    summary = AttendanceSummary(
        total_visits=total_visits,
        unique_members=unique_members,
        avg_duration_minutes=avg_duration,
        by_source=by_source,
        busiest_hour=busiest_hour,
        period=f"From {from_date or 'beginning'} to {to_date or 'now'}"
    )
    return success_response(message="Attendance stats compiled", data=summary.model_dump())


@router.get("/member/{member_id}", response_model=None)
def get_member_attendance(
    member_id: UUID,
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve visit check-in records for a specific member."""
    logger.info(f"[get_member_attendance] user={current_user.user_id} target_member={member_id}")

    member = db.query(Member).options(joinedload(Member.profile)).filter(
        Member.id == member_id,
        Member.is_deleted == False
    ).first()

    if not member:
        raise NotFoundException(message="Member not found")

    # Ownership check: Member can only view their own attendance log history
    if current_user.role == UserRole.MEMBER:
        if member.profile.user_id != current_user.user_id:
            raise AuthorizationException(message="You are not authorized to view this log history")

    query = db.query(AttendanceLog).filter(AttendanceLog.member_id == member_id)

    if from_date:
        query = query.filter(AttendanceLog.check_in >= from_date)
    if to_date:
        query = query.filter(AttendanceLog.check_in <= to_date)

    total = query.count()
    logs = query.options(
        joinedload(AttendanceLog.member).joinedload(Member.profile)
    ).order_by(AttendanceLog.check_in.desc()).offset((page - 1) * per_page).limit(per_page).all()

    mapped_list = [_map_attendance_to_response(l).model_dump() for l in logs]
    return paginated_response(
        message="Member logs retrieved",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )


@router.get("/", response_model=None)
def list_attendance_logs(
    member_id: Optional[UUID] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    source: Optional[AttendanceSource] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """List and search paginated attendance logs."""
    logger.info(f"[list_attendance_logs] user={current_user.user_id} page={page} per_page={per_page}")

    query = db.query(AttendanceLog)

    if member_id:
        query = query.filter(AttendanceLog.member_id == member_id)
    if from_date:
        query = query.filter(AttendanceLog.check_in >= from_date)
    if to_date:
        query = query.filter(AttendanceLog.check_in <= to_date)
    if source:
        query = query.filter(AttendanceLog.source == source)

    total = query.count()
    logs = query.options(
        joinedload(AttendanceLog.member).joinedload(Member.profile)
    ).order_by(AttendanceLog.check_in.desc()).offset((page - 1) * per_page).limit(per_page).all()

    mapped_list = [_map_attendance_to_response(l).model_dump() for l in logs]
    return paginated_response(
        message="Logs retrieved successfully",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )
