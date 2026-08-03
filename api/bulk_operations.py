"""
Bulk Operations Service
========================

Handles batch operations for college-scale deployment:
    - Batch student enrollment from CSV
    - Bulk attendance import/export
    - Batch employee enrollment
    - Bulk camera configuration

All operations are idempotent and provide detailed progress reporting.
"""

from __future__ import annotations

import csv
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


from database.database import get_session
from database.models import (
    Camera,
    Employee,
    Student,
    _utcnow,
)

logger = logging.getLogger(__name__)


@dataclass
class BulkResult:
    """Result of a bulk operation."""

    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)
    created_ids: List[int] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors[:20],  # Limit error list
            "created_ids": self.created_ids,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


class BulkOperations:
    """College-scale bulk operations service."""

    @staticmethod
    def import_students_from_csv(
        csv_content: str,
        default_department_id: Optional[int] = None,
        skip_duplicates: bool = True,
    ) -> BulkResult:
        """
        Import students from CSV content.

        Expected CSV columns:
            student_id, name, email (optional), phone (optional),
            department_id (optional), enrollment_year (optional),
            graduation_year (optional)

        Args:
            csv_content: Raw CSV string.
            default_department_id: Department ID to assign if not in CSV.
            skip_duplicates: If True, skip existing student_ids.

        Returns:
            BulkResult with counts and errors.
        """
        start = time.time()
        result = BulkResult()

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as exc:
            result.errors.append({"row": 0, "error": f"CSV parse error: {exc}"})
            result.failed = 1
            result.total = 1
            result.elapsed_ms = (time.time() - start) * 1000
            return result

        with get_session() as session:
            for row_num, row in enumerate(reader, start=1):
                result.total += 1
                try:
                    student_id = row.get("student_id", "").strip()
                    name = row.get("name", "").strip()

                    if not student_id or not name:
                        result.errors.append(
                            {"row": row_num, "error": "Missing required field: student_id or name"}
                        )
                        result.failed += 1
                        continue

                    # Check for duplicate
                    if skip_duplicates:
                        existing = session.query(Student).filter(Student.student_id == student_id).first()
                        if existing:
                            result.skipped += 1
                            continue

                    # Create student
                    student = Student(
                        student_id=student_id,
                        name=name,
                        email=row.get("email", "").strip() or None,
                        phone=row.get("phone", "").strip() or None,
                        department_id=(
                            int(row["department_id"]) if row.get("department_id") else default_department_id
                        ),
                        enrollment_year=(int(row["enrollment_year"]) if row.get("enrollment_year") else None),
                        graduation_year=(int(row["graduation_year"]) if row.get("graduation_year") else None),
                    )
                    session.add(student)
                    session.flush()
                    result.created_ids.append(student.id)
                    result.success += 1

                except Exception as exc:
                    result.errors.append(
                        {
                            "row": row_num,
                            "student_id": row.get("student_id", "?"),
                            "error": str(exc),
                        }
                    )
                    result.failed += 1

            session.commit()

        result.elapsed_ms = (time.time() - start) * 1000
        logger.info(
            "Student import: %d/%d success, %d failed, %d skipped",
            result.success,
            result.total,
            result.failed,
            result.skipped,
        )
        return result

    @staticmethod
    def import_employees_from_csv(
        csv_content: str,
        skip_duplicates: bool = True,
    ) -> BulkResult:
        """
        Import employees from CSV.

        Expected columns: employee_id, name, department (optional)
        """
        start = time.time()
        result = BulkResult()

        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as exc:
            result.errors.append({"row": 0, "error": f"CSV parse error: {exc}"})
            result.failed = 1
            result.total = 1
            result.elapsed_ms = (time.time() - start) * 1000
            return result

        with get_session() as session:
            for row_num, row in enumerate(reader, start=1):
                result.total += 1
                try:
                    employee_id = row.get("employee_id", "").strip()
                    name = row.get("name", "").strip()

                    if not employee_id or not name:
                        result.errors.append(
                            {"row": row_num, "error": "Missing required field: employee_id or name"}
                        )
                        result.failed += 1
                        continue

                    if skip_duplicates:
                        existing = session.query(Employee).filter(Employee.employee_id == employee_id).first()
                        if existing:
                            result.skipped += 1
                            continue

                    emp = Employee(
                        employee_id=employee_id,
                        name=name,
                        department=row.get("department", "").strip() or None,
                    )
                    session.add(emp)
                    session.flush()
                    result.created_ids.append(emp.id)
                    result.success += 1

                except Exception as exc:
                    result.errors.append(
                        {
                            "row": row_num,
                            "employee_id": row.get("employee_id", "?"),
                            "error": str(exc),
                        }
                    )
                    result.failed += 1

            session.commit()

        result.elapsed_ms = (time.time() - start) * 1000
        return result

    @staticmethod
    def bulk_update_camera_status(
        camera_ids: List[int],
        is_active: bool,
    ) -> BulkResult:
        """Bulk enable/disable cameras."""
        start = time.time()
        result = BulkResult()
        result.total = len(camera_ids)

        with get_session() as session:
            for cam_id in camera_ids:
                try:
                    camera = session.get(Camera, cam_id)
                    if not camera:
                        result.errors.append({"camera_id": cam_id, "error": "Camera not found"})
                        result.failed += 1
                        continue

                    camera.is_active = is_active
                    camera.status = "ONLINE" if is_active else "OFFLINE"
                    camera.last_seen = _utcnow()
                    result.success += 1

                except Exception as exc:
                    result.errors.append(
                        {
                            "camera_id": cam_id,
                            "error": str(exc),
                        }
                    )
                    result.failed += 1

            session.commit()

        result.elapsed_ms = (time.time() - start) * 1000
        return result

    @staticmethod
    def export_attendance_csv(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        section_id: Optional[int] = None,
    ) -> str:
        """Export attendance records as CSV string."""
        from database.models import Attendance

        with get_session() as session:
            query = session.query(Attendance)

            if date_from:
                query = query.filter(Attendance.timestamp >= date_from)
            if date_to:
                query = query.filter(Attendance.timestamp <= date_to)
            if section_id:
                query = query.filter(Attendance.section_id == section_id)

            records = query.order_by(Attendance.timestamp.desc()).all()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "id",
                    "student_id",
                    "employee_id",
                    "timestamp",
                    "confidence",
                    "method",
                    "status",
                    "section_id",
                    "course_id",
                    "classroom_id",
                ]
            )
            for r in records:
                writer.writerow(
                    [
                        r.id,
                        r.student_id,
                        r.employee_id,
                        r.timestamp,
                        r.confidence,
                        r.method,
                        r.status,
                        r.section_id,
                        r.course_id,
                        r.classroom_id,
                    ]
                )

            return output.getvalue()


# Global instance
bulk_operations = BulkOperations()
