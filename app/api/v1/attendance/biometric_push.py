"""
Webhook receiver for eSSL ADMS biometric device punch pushes.
"""

from datetime import datetime, timezone, time
from fastapi import APIRouter, Query, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, joinedload
from loguru import logger
from app.database.session import get_db
from app.core.constants import AttendanceSource
from app.models.profile import Profile
from app.models.attendance import AttendanceLog, UnmatchedScan

router = APIRouter()


@router.get("/biometric-push", response_class=PlainTextResponse)
async def biometric_push(
    SN: str = Query(..., description="Device serial number"),
    scan_date: str = Query(..., description="Scan datetime: YYYY-MM-DD HH:MM:SS"),
    pin: int = Query(..., description="Device enrolled user ID (pin)"),
    verified: int = Query(..., description="1 = matched, 0 = not matched"),
    status: int = Query(0, description="0 = check-in, 1 = check-out"),
    db: Session = Depends(get_db)
) -> str:
    """
    Receives attendance punch from eSSL biometric terminal.
    Always returns plain "OK" on any outcome to satisfy the device's retry loop.
    All errors are handled and logged server-side.
    """
    logger.info(f"[biometric_push] SN={SN} scan_date={scan_date} pin={pin} verified={verified} status={status}")

    try:
        # 1. Parse scan date string
        try:
            # eSSL sends YYYY-MM-DD HH:MM:SS or URL-encoded (e.g. YYYY-MM-DD+HH:MM:SS)
            # Python's datetime.fromisoformat or strptime can handle it
            cleaned_date_str = scan_date.replace("+", " ")
            scan_datetime = datetime.strptime(cleaned_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError as val_err:
            logger.error(f"[biometric_push] Invalid date format for scan_date='{scan_date}': {str(val_err)}")
            # Fall back to current time but log it
            scan_datetime = datetime.now(timezone.utc)

        # 2. Query profile matching the eSSL pin (biometric_device_id)
        profile = db.query(Profile).options(
            joinedload(Profile.member)
        ).filter(Profile.biometric_device_id == pin).first()

        # 3. Handle matched vs unmatched scan logic
        unmatched_created = False
        unmatched_scan_id = None

        if profile and profile.member and verified == 1:
            member = profile.member
            logger.info(f"[biometric_push] Matched member={member.id} name='{profile.full_name}'")

            # Check if there is an open check-in log today for this member
            today_start = datetime.combine(scan_datetime.date(), time.min).replace(tzinfo=timezone.utc)
            today_end = datetime.combine(scan_datetime.date(), time.max).replace(tzinfo=timezone.utc)

            open_log = db.query(AttendanceLog).filter(
                AttendanceLog.member_id == member.id,
                AttendanceLog.check_in >= today_start,
                AttendanceLog.check_in <= today_end,
                AttendanceLog.check_out == None
            ).first()

            if open_log and status == 1:
                # Update existing log check_out
                open_log.check_out = scan_datetime
                open_log.notes = f"{open_log.notes or ''}\nBiometric check-out recorded.".strip()
                logger.info(f"[biometric_push] Closed check-out for member={member.id} log={open_log.id}")
            else:
                # Create a new check-in record
                new_log = AttendanceLog(
                    member_id=member.id,
                    check_in=scan_datetime,
                    source=AttendanceSource.BIOMETRIC,
                    device_serial=SN,
                    raw_pin=pin,
                    notes="Biometric check-in recorded."
                )
                db.add(new_log)
                logger.info(f"[biometric_push] Created new biometric check-in log for member={member.id}")

        else:
            # Unmatched or verification failed scan -> record in unmatched scans
            logger.warning(f"[biometric_push] Unmatched pin={pin} verified={verified}. Recording unmatched scan.")
            
            raw_payload = {
                "SN": SN,
                "scan_date": scan_date,
                "pin": pin,
                "verified": verified,
                "status": status
            }

            new_unmatched = UnmatchedScan(
                device_serial=SN,
                raw_pin=pin,
                scan_datetime=scan_datetime,
                verified=bool(verified),
                raw_payload=raw_payload,
                is_resolved=False
            )
            db.add(new_unmatched)
            db.flush()
            unmatched_created = True
            unmatched_scan_id = new_unmatched.id

        db.commit()

        # Fire notification side-effect
        if unmatched_created and unmatched_scan_id:
            try:
                from app.api.v1.notifications.service import notify_unmatched_scan
                from app.models.user import User
                from app.core.constants import UserRole
                receptionist_ids = db.query(User.id).filter(User.role == UserRole.RECEPTIONIST, User.is_active == True).all()
                notify_unmatched_scan(db, [r.id for r in receptionist_ids], scan_id=unmatched_scan_id, raw_pin=pin)
            except Exception as notify_err:
                logger.error(f"Failed to trigger unmatched scan notification (non-critical): {str(notify_err)}")

    except Exception as e:
        db.rollback()
        logger.error(f"[biometric_push] System exception during processing: {str(e)}")

    # Always return plain OK to stop device retry loops
    return "OK"
