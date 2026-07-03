"""
Pydantic schemas for Attendance tracking and biometric scan resolutions.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from app.core.constants import AttendanceSource


class ManualAttendanceCreate(BaseModel):
    """Schema for manually logging a member's check-in/check-out."""
    member_id: UUID = Field(..., description="ID of the member")
    check_in: datetime = Field(..., description="Check-in timestamp")
    check_out: Optional[datetime] = Field(None, description="Check-out timestamp")
    notes: Optional[str] = Field(None, description="Reason or context notes")


class AttendanceLogResponse(BaseModel):
    """Schema exposing validated check-in logs."""
    id: UUID
    member_id: UUID
    member_name: str
    check_in: datetime
    check_out: Optional[datetime] = None
    source: AttendanceSource
    device_serial: Optional[str] = None
    raw_pin: Optional[int] = None
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AttendanceSummary(BaseModel):
    """Schema compiling member visits and busiest times."""
    total_visits: int
    unique_members: int
    avg_duration_minutes: Optional[float] = None
    by_source: Dict[str, int]
    busiest_hour: Optional[int] = None
    period: str


class UnmatchedScanResponse(BaseModel):
    """Schema exposing unprocessed/unmatched biometric device punches."""
    id: UUID
    device_serial: str
    raw_pin: int
    scan_datetime: datetime
    verified: bool
    is_resolved: bool
    resolved_at: Optional[datetime] = None
    resolved_member_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class ResolveUnmatchedScanRequest(BaseModel):
    """Request payload to map an unmatched biometric PIN to a member."""
    member_id: UUID = Field(..., description="ID of the member to link the scan PIN to")
    create_attendance_record: bool = Field(True, description="Create an AttendanceLog for the resolved scan")
class AttendanceListResponse(BaseModel):
    """Paginated collection of attendance responses."""
    logs: List[AttendanceLogResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
