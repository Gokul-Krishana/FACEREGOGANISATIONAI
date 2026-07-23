"""
Attendance Service — records and queries attendance data.

Writes to **both** the SQLite database and CSV files for backward
compatibility. The CSV logger can be deprecated once the dashboard
fully replaces the terminal app.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

import config.config as cfg
from app.attendance import AttendanceTracker
from database.database import get_session
from database.models import Attendance
from database.repository import AttendanceRepo
from services.audit_service import AuditService


class AttendanceService:
    """Service for attendance marking and queries.

    Usage::

        AttendanceService.mark(employee_id=1, confidence=0.95)
        today = AttendanceService.get_today()
        stats = AttendanceService.get_statistics()
    """

    # Shared CSV tracker (backward compat)
    _csv_tracker = AttendanceTracker()

    @classmethod
    def mark(
        cls,
        employee_id: int,
        confidence: float = 1.0,
        camera_id: Optional[int] = None,
        operator: str = "system",
        employee_name: Optional[str] = None,
    ) -> bool:
        """Record attendance for an employee.

        Writes to both the SQLite database and the CSV log.

        Args:
            employee_id: Database ID of the employee.
            confidence: Recognition confidence score.
            camera_id: Camera that captured the recognition (optional).
            operator: Who performed this action.
            employee_name: Name for CSV logging (optional).

        Returns:
            ``True`` if attendance was newly recorded, ``False`` if
            already marked today (no duplicate per day).
        """
        with get_session() as session:
            if AttendanceRepo.is_marked_today(session, employee_id):
                return False

            AttendanceRepo.create(
                session,
                employee_id=employee_id,
                confidence=confidence,
                camera_id=camera_id,
            )

        # Also write to CSV for backward compatibility
        name = employee_name or f"ID:{employee_id}"
        cls._csv_tracker.mark(name, confidence)

        AuditService.log(
            "MARK_ATTENDANCE",
            f"Attendance marked for employee #{employee_id} ({name})",
            operator=operator,
            employee_id=employee_id,
        )
        return True

    @classmethod
    def get_today(cls) -> List[Attendance]:
        """Return today's attendance records."""
        with get_session() as session:
            records = AttendanceRepo.get_today(session)
            # Eager-load employee relationship to avoid DetachedInstanceError
            for r in records:
                _ = r.employee  # Force lazy load while session is open
            return records

    @classmethod
    def get_by_date(cls, target_date: date) -> List[Attendance]:
        """Return attendance records for a specific date."""
        with get_session() as session:
            records = AttendanceRepo.get_by_date(session, target_date)
            for r in records:
                _ = r.employee
            return records

    @classmethod
    def get_by_employee(cls, employee_id: int) -> List[Attendance]:
        """Return attendance history for a specific employee."""
        with get_session() as session:
            records = AttendanceRepo.get_by_employee(session, employee_id)
            for r in records:
                _ = r.employee
            return records

    @classmethod
    def get_statistics(cls) -> Dict:
        """Return aggregate attendance statistics."""
        with get_session() as session:
            return AttendanceRepo.get_statistics(session)

    @classmethod
    def to_dict(cls, record: Attendance) -> dict:
        """Convert an Attendance ORM object to a dictionary."""
        return {
            "id": record.id,
            "employee_id": record.employee_id,
            "employee_name": record.employee.name if record.employee else None,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "confidence": record.confidence,
            "camera_id": record.camera_id,
        }
