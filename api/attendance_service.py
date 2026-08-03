"""
Attendance service with timetable-aware processing.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Optional

from sqlalchemy.orm import Session

from database.models import (
    Attendance,
    Enrollment,
    Section,
    Timetable,
)


class AttendanceService:
    """Timetable-aware attendance management."""

    GRACE_PERIOD_MINUTES = 10  # Allow 10 min late

    @staticmethod
    def is_class_in_session(
        section_id: int,
        timestamp: datetime,
        session: Session,
    ) -> Optional[Timetable]:
        """Check if a given timestamp falls within a scheduled class for the section.

        Returns the matching Timetable entry if found, else None.
        """
        day_of_week = timestamp.weekday()  # 0=Monday, 6=Sunday
        current_time = timestamp.time()

        timetable = (
            session.query(Timetable)
            .filter(
                Timetable.section_id == section_id,
                Timetable.day_of_week == day_of_week,
            )
            .first()
        )

        if not timetable:
            return None

        start_h, start_m, start_s = map(int, timetable.start_time.split(":"))
        end_h, end_m, end_s = map(int, timetable.end_time.split(":"))

        start = dt_time(start_h, start_m, start_s)
        end = dt_time(end_h, end_m, end_s)
        grace = dt_time(0, AttendanceService.GRACE_PERIOD_MINUTES, 0)

        if start <= current_time <= end + grace:
            return timetable
        return None

    @staticmethod
    def is_within_time_window(
        timestamp: datetime,
        start_time: str,
        end_time: str,
        grace_minutes: int = 10,
    ) -> bool:
        """Check if timestamp falls within a time window with grace period."""

        def parse_t(s: str) -> dt_time:
            h, m, sec = map(int, s.split(":"))
            return dt_time(h, m, sec)

        start = parse_t(start_time)
        end = parse_t(end_time)
        grace = dt_time(0, grace_minutes, 0)
        current = timestamp.time()

        return start <= current <= end + grace

    @staticmethod
    def is_student_enrolled(
        student_id: int,
        section_id: int,
        session: Session,
    ) -> bool:
        """Check if a student is enrolled in a section."""
        enrollment = (
            session.query(Enrollment)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.section_id == section_id,
                Enrollment.status == "ACTIVE",
            )
            .first()
        )
        return enrollment is not None

    @staticmethod
    def get_today_attendance(
        student_id: int,
        section_id: Optional[int],
        session: Session,
    ) -> Optional[Attendance]:
        """Check if student already has attendance today for the section."""
        today_start = datetime.combine(datetime.today(), dt_time.min)
        today_end = datetime.combine(datetime.today(), dt_time.max)

        query = session.query(Attendance).filter(
            Attendance.student_id == student_id,
            Attendance.timestamp >= today_start,
            Attendance.timestamp <= today_end,
        )
        if section_id:
            query = query.filter(Attendance.section_id == section_id)

        return query.first()

    @staticmethod
    def create_attendance(
        session: Session,
        student_id: int,
        section_id: Optional[int] = None,
        course_id: Optional[int] = None,
        classroom_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        confidence: float = 1.0,
        method: str = "FACE_RECOGNITION",
        marked_manually: bool = False,
        marked_by_user_id: Optional[int] = None,
    ) -> Attendance:
        """Create a new attendance record with timetable validation."""
        # If no explicit section_id, try to derive from timetable
        if section_id and course_id is None:
            section = session.get(Section, section_id)
            if section:
                course_id = section.course_id

        # If no section_id, try to find it from timetable/camera/classroom
        if section_id is None and classroom_id:
            class_section = (
                session.query(Section)
                .join(Timetable)
                .filter(
                    Timetable.classroom_id == classroom_id,
                )
                .order_by(Timetable.start_time.desc())
                .first()
            )
            if class_section:
                section_id = class_section.id

        # Validate that the student is enrolled in this section
        if section_id and not AttendanceService.is_student_enrolled(student_id, section_id, session):
            raise ValueError(f"Student {student_id} is not enrolled in section {section_id}")

        # Mark attendance
        attendance = Attendance(
            student_id=student_id,
            section_id=section_id,
            course_id=course_id,
            classroom_id=classroom_id,
            camera_id=camera_id,
            confidence=confidence,
            method=method,
            status="PRESENT",
            marked_manually=marked_manually,
            marked_by_user_id=marked_by_user_id,
        )
        session.add(attendance)
        session.commit()
        session.refresh(attendance)
        return attendance

    @staticmethod
    def get_attendance_summary(
        session: Session,
        section_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict:
        """Get attendance summary statistics."""

        query = session.query(Attendance)

        if section_id:
            query = query.filter(Attendance.section_id == section_id)
        if date_from:
            query = query.filter(Attendance.timestamp >= date_from)
        if date_to:
            query = query.filter(Attendance.timestamp <= date_to)

        total = query.count()
        present = query.filter(Attendance.status == "PRESENT").count()
        late = query.filter(Attendance.status == "LATE").count()
        absent = query.filter(Attendance.status == "ABSENT").count()

        return {
            "total": total,
            "present": present,
            "late": late,
            "absent": absent,
            "attendance_rate": (present / total * 100) if total > 0 else 0,
        }
