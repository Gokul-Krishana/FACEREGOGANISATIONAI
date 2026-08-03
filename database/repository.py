"""
Repository layer — CRUD operations for all database models.

Each function takes a SQLAlchemy ``Session`` as the first argument,
keeping the caller in control of transactions.

Usage::

    from database.database import get_session
    from database.repository import employees

    with get_session() as session:
        emp = employees.create(session, employee_id="EMP001", name="Alice")
        all_emps = employees.get_all(session)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import uuid
from typing import List, Optional

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, selectinload

from database.models import (
    Attendance,
    AuditLog,
    Camera,
    Employee,
    RecognitionLog,
    Student,
    UnknownFace,
)


@dataclass
class PageResult:
    """Lightweight pagination envelope used by the API and UI."""

    items: list
    total: int
    skip: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.skip + len(self.items) < self.total


def _bounded_search_pattern(value: str) -> str:
    """Prefer prefix search so the database can use indexes when possible."""
    cleaned = value.strip()
    return f"{cleaned}%"


def _paginate(query, skip: int, limit: int) -> PageResult:
    total = query.order_by(None).count()
    items = query.offset(skip).limit(limit).all()
    return PageResult(items=items, total=total, skip=skip, limit=limit)


# ── Employee Repository ───────────────────────────────────────


class StudentRepo:
    """CRUD and search operations for the ``students`` table."""

    @staticmethod
    def create(
        session: Session,
        student_id: str,
        name: str,
        email: Optional[str] = None,
        department_id: Optional[int] = None,
        is_active: bool = True,
    ) -> Student:
        student = Student(
            student_id=student_id,
            name=name,
            email=email,
            department_id=department_id,
            is_active=is_active,
        )
        session.add(student)
        session.commit()
        session.refresh(student)
        return student

    @staticmethod
    def get_by_id(session: Session, student_pk: int) -> Optional[Student]:
        return session.get(Student, student_pk)

    @staticmethod
    def get_by_student_id(session: Session, student_id: str) -> Optional[Student]:
        return session.query(Student).filter(Student.student_id == student_id).first()

    @staticmethod
    def get_all(session: Session, limit: int = 100, skip: int = 0) -> List[Student]:
        return session.query(Student).order_by(Student.student_id, Student.id).offset(skip).limit(limit).all()

    @staticmethod
    def search(
        session: Session,
        query: str,
        limit: int = 100,
        skip: int = 0,
        department_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> PageResult:
        term = query.strip()
        q = session.query(Student)

        if term:
            pattern = _bounded_search_pattern(term)
            q = q.filter(
                or_(
                    Student.name.ilike(pattern),
                    Student.student_id.ilike(pattern),
                )
            )
        if department_id is not None:
            q = q.filter(Student.department_id == department_id)
        if is_active is not None:
            q = q.filter(Student.is_active == is_active)

        q = q.order_by(Student.student_id, Student.id)
        return _paginate(q, skip=skip, limit=limit)

    @staticmethod
    def count(session: Session) -> int:
        return session.query(func.count(Student.id)).scalar() or 0


class EmployeeRepo:
    """CRUD operations for the ``employees`` table."""

    @staticmethod
    def create(
        session: Session,
        employee_id: str,
        name: str,
        department: Optional[str] = None,
        photo_path: Optional[str] = None,
        faiss_id: Optional[int] = None,
    ) -> Employee:
        emp = Employee(
            employee_id=employee_id,
            name=name,
            department=department,
            photo_path=photo_path,
            faiss_id=faiss_id,
        )
        session.add(emp)
        session.commit()
        session.refresh(emp)
        return emp

    @staticmethod
    def get_by_id(session: Session, emp_id: int) -> Optional[Employee]:
        return session.query(Employee).filter(Employee.id == emp_id).first()

    @staticmethod
    def get_by_employee_id(session: Session, employee_id: str) -> Optional[Employee]:
        return session.query(Employee).filter(Employee.employee_id == employee_id).first()

    @staticmethod
    def get_all(session: Session) -> List[Employee]:
        return session.query(Employee).order_by(Employee.name, Employee.id).limit(500).all()

    @staticmethod
    def get_by_name(session: Session, name: str) -> Optional[Employee]:
        """Look up an employee by their display name."""
        normalized = name.strip().lower()
        return session.query(Employee).filter(Employee.name.ilike(normalized)).first()

    @staticmethod
    def search(session: Session, query: str) -> List[Employee]:
        return EmployeeRepo.search_paginated(session, query=query, limit=100).items

    @staticmethod
    def search_paginated(
        session: Session,
        query: str,
        limit: int = 100,
        skip: int = 0,
    ) -> PageResult:
        q = session.query(Employee)
        if query.strip():
            pattern = _bounded_search_pattern(query)
            q = q.filter(
                or_(
                    Employee.name.ilike(pattern),
                    Employee.employee_id.ilike(pattern),
                    Employee.department.ilike(pattern),
                )
            )
        q = q.order_by(Employee.name, Employee.id)
        return _paginate(q, skip=skip, limit=limit)

    @staticmethod
    def delete(session: Session, employee_id: str) -> bool:
        emp = EmployeeRepo.get_by_employee_id(session, employee_id)
        if not emp:
            return False
        session.delete(emp)
        session.commit()
        return True

    @staticmethod
    def update(session: Session, emp_id: int, **fields) -> Optional[Employee]:
        """Update editable fields of an employee by database ID.

        Only keys present in ``fields`` are changed (partial update) and
        only whitelisted columns may be set — arbitrary attributes (e.g.
        ``id``, relationships) are ignored to protect invariants.

        Args:
            session: SQLAlchemy session.
            emp_id: Database primary key of the employee.
            **fields: Column names → new values (e.g. ``name=...``).

        Returns:
            The updated ``Employee``, or ``None`` if not found.
        """
        _EDITABLE = {"name", "department", "photo_path"}
        emp = EmployeeRepo.get_by_id(session, emp_id)
        if not emp:
            return None
        changed = False
        for key, value in fields.items():
            if key in _EDITABLE and hasattr(emp, key):
                setattr(emp, key, value)
                changed = True
        if not changed:
            return emp
        session.commit()
        session.refresh(emp)
        return emp

    @staticmethod
    def count(session: Session) -> int:
        return session.query(func.count(Employee.id)).scalar() or 0


# ── Attendance Repository ─────────────────────────────────────


class AttendanceRepo:
    """CRUD operations for the ``attendance`` table."""

    @staticmethod
    def create(
        session: Session,
        employee_id: int,
        confidence: float = 1.0,
        camera_id: Optional[int] = None,
    ) -> Attendance:
        record = Attendance(
            employee_id=employee_id,
            confidence=confidence,
            camera_id=camera_id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def get_by_date(
        session: Session,
        target_date: date,
        limit: Optional[int] = None,
        skip: int = 0,
    ) -> List[Attendance]:
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        query = (
            session.query(Attendance)
            .filter(Attendance.timestamp.between(start, end))
            .options(selectinload(Attendance.employee))
            .order_by(desc(Attendance.timestamp))
        )
        if skip:
            query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def get_today(session: Session, limit: Optional[int] = None, skip: int = 0) -> List[Attendance]:
        return AttendanceRepo.get_by_date(session, date.today(), limit=limit, skip=skip)

    @staticmethod
    def get_by_employee(
        session: Session,
        employee_id: int,
        limit: Optional[int] = None,
        skip: int = 0,
    ) -> List[Attendance]:
        query = (
            session.query(Attendance)
            .filter(Attendance.employee_id == employee_id)
            .options(selectinload(Attendance.employee))
            .order_by(desc(Attendance.timestamp))
        )
        if skip:
            query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def is_marked_today(session: Session, employee_id: int) -> bool:
        start = datetime.combine(date.today(), datetime.min.time())
        end = datetime.combine(date.today(), datetime.max.time())
        return (
            session.query(func.count(Attendance.id))
            .filter(
                Attendance.employee_id == employee_id,
                Attendance.timestamp.between(start, end),
            )
            .scalar()
            or 0
        ) > 0

    @staticmethod
    def get_statistics(session: Session) -> dict:
        start = datetime.combine(date.today(), datetime.min.time())
        end = datetime.combine(date.today(), datetime.max.time())
        today_count = (
            session.query(func.count(Attendance.id)).filter(Attendance.timestamp.between(start, end)).scalar()
            or 0
        )
        unique_today = (
            session.query(func.count(func.distinct(Attendance.employee_id)))
            .filter(Attendance.timestamp.between(start, end))
            .scalar()
            or 0
        )
        total = session.query(func.count(Attendance.id)).scalar() or 0
        unique_all = session.query(func.count(func.distinct(Attendance.employee_id))).scalar() or 0
        return {
            "today_count": today_count,
            "unique_today": unique_today,
            "total_records": total,
            "unique_employees": unique_all,
        }


# ── Recognition Log Repository ────────────────────────────────


class RecognitionLogRepo:
    """CRUD operations for the ``recognition_log`` table."""

    @staticmethod
    def create(
        session: Session,
        is_known: bool,
        confidence: Optional[float] = None,
        employee_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        face_snapshot_path: Optional[str] = None,
        liveness_confidence: Optional[float] = None,
        is_spoof: bool = False,
        track_id: Optional[str] = None,
    ) -> RecognitionLog:
        """Create a recognition log entry.

        ``liveness_confidence`` / ``is_spoof`` / ``track_id`` are stored on
        the model (used by the live pipeline via RecognitionService) — this
        previously caused a silent TypeError on every recognition event.
        """
        log = RecognitionLog(
            is_known=is_known,
            confidence=confidence,
            employee_id=employee_id,
            camera_id=camera_id,
            face_snapshot_path=face_snapshot_path,
            liveness_confidence=liveness_confidence,
            is_spoof=is_spoof,
            track_id=track_id,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return log

    @staticmethod
    def get_recent(session: Session, limit: int = 50) -> List[RecognitionLog]:
        return (
            session.query(RecognitionLog)
            .options(selectinload(RecognitionLog.employee))
            .order_by(desc(RecognitionLog.timestamp))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_by_date(session: Session, target_date: date) -> List[RecognitionLog]:
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())
        return (
            session.query(RecognitionLog)
            .filter(RecognitionLog.timestamp.between(start, end))
            .options(selectinload(RecognitionLog.employee))
            .order_by(desc(RecognitionLog.timestamp))
            .all()
        )


# ── Unknown Face Repository ───────────────────────────────────


class UnknownFaceRepo:
    """CRUD operations for the ``unknown_faces`` table."""

    @staticmethod
    def create(
        session: Session,
        image_path: str,
        camera_id: Optional[int] = None,
        confidence: Optional[float] = None,
    ) -> UnknownFace:
        uf = UnknownFace(
            image_path=image_path,
            camera_id=camera_id,
            confidence=confidence,
        )
        session.add(uf)
        session.commit()
        session.refresh(uf)
        return uf

    @staticmethod
    def get_by_id(session: Session, face_id: int) -> Optional[UnknownFace]:
        return session.query(UnknownFace).filter(UnknownFace.id == face_id).first()

    @staticmethod
    def get_unreviewed(
        session: Session,
        limit: Optional[int] = None,
        skip: int = 0,
    ) -> List[UnknownFace]:
        query = (
            session.query(UnknownFace)
            .filter(UnknownFace.reviewed.is_(False))
            .options(selectinload(UnknownFace.camera))
            .order_by(desc(UnknownFace.timestamp))
        )
        if skip:
            query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def get_all(session: Session, limit: Optional[int] = None, skip: int = 0) -> List[UnknownFace]:
        query = (
            session.query(UnknownFace)
            .options(selectinload(UnknownFace.camera))
            .order_by(desc(UnknownFace.timestamp))
        )
        if skip:
            query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def get_filtered(
        session: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        camera_id: Optional[int] = None,
        reviewed: Optional[bool] = None,
        min_confidence: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UnknownFace]:
        """Query unknown faces with optional filters."""
        q = session.query(UnknownFace)

        if start_date:
            q = q.filter(UnknownFace.timestamp >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            q = q.filter(UnknownFace.timestamp <= datetime.combine(end_date, datetime.max.time()))
        if camera_id is not None:
            q = q.filter(UnknownFace.camera_id == camera_id)
        if reviewed is not None:
            q = q.filter(UnknownFace.reviewed == reviewed)
        if min_confidence is not None:
            q = q.filter(UnknownFace.confidence >= min_confidence)

        return (
            q.options(selectinload(UnknownFace.camera))
            .order_by(desc(UnknownFace.timestamp))
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    def get_statistics(session: Session) -> dict:
        """Return aggregate statistics for unknown faces."""
        today_start = datetime.combine(date.today(), datetime.min.time())
        week_ago = datetime.combine(
            date.today() - timedelta(days=7),
            datetime.min.time(),
        )
        total = session.query(UnknownFace).count()
        today = session.query(UnknownFace).filter(UnknownFace.timestamp >= today_start).count()
        this_week = session.query(UnknownFace).filter(UnknownFace.timestamp >= week_ago).count()
        pending = session.query(UnknownFace).filter(UnknownFace.reviewed.is_(False)).count()
        converted = session.query(UnknownFace).filter(UnknownFace.converted_to_employee.is_(True)).count()
        return {
            "total": total,
            "today": today,
            "this_week": this_week,
            "pending_review": pending,
            "converted": converted,
        }

    @staticmethod
    def mark_reviewed(session: Session, face_id: int) -> bool:
        uf = session.query(UnknownFace).filter(UnknownFace.id == face_id).first()
        if not uf:
            return False
        uf.reviewed = True  # type: ignore[assignment]
        session.commit()
        return True

    @staticmethod
    def mark_converted(session: Session, face_id: int) -> bool:
        """Mark an unknown face as converted to an employee."""
        uf = session.query(UnknownFace).filter(UnknownFace.id == face_id).first()
        if not uf:
            return False
        uf.converted_to_employee = True  # type: ignore[assignment]
        uf.reviewed = True  # type: ignore[assignment]
        session.commit()
        return True

    @staticmethod
    def update_notes(session: Session, face_id: int, notes: str) -> bool:
        """Update the notes for an unknown face."""
        uf = session.query(UnknownFace).filter(UnknownFace.id == face_id).first()
        if not uf:
            return False
        uf.notes = notes  # type: ignore[assignment]
        session.commit()
        return True

    @staticmethod
    def delete(session: Session, face_id: int, delete_image: bool = True) -> bool:
        """Delete an unknown face record and optionally its image."""
        uf = session.query(UnknownFace).filter(UnknownFace.id == face_id).first()
        if not uf:
            return False

        image_path = uf.image_path
        session.delete(uf)
        session.commit()

        # Remove the image file from disk
        if delete_image and image_path:
            try:
                img_file = Path(image_path)
                if img_file.exists():
                    img_file.unlink()
            except OSError:
                pass  # File may be in use or already deleted

        return True

    @staticmethod
    def delete_all(session: Session, delete_images: bool = True) -> int:
        """Delete ALL unknown face records and optionally their images.

        Performs a single bulk delete and collects image paths before
        deleting records, so disk cleanup happens after the DB commit.
        Much faster than calling ``delete()`` in a loop when there are
        hundreds of records.

        Args:
            session: SQLAlchemy session.
            delete_images: Whether to delete the associated image files
                           from disk (default ``True``).

        Returns:
            Number of records deleted.
        """
        # Collect all image paths before deleting (so we can clean up files
        # after the DB operation, even if the session is closed)
        image_paths: List[str] = []
        if delete_images:
            image_paths = [row[0] for row in session.query(UnknownFace.image_path).all() if row[0]]

        # Bulk delete all records in one shot
        count = session.query(UnknownFace).delete()
        session.commit()

        # Clean up image files from disk
        if delete_images:
            from pathlib import Path as _Path

            for path in image_paths:
                try:
                    _Path(path).unlink(missing_ok=True)
                except OSError:
                    pass  # File may be in use or already deleted

        return count

    @staticmethod
    def delete_older_than(session: Session, days: int) -> int:
        """Delete unknown face records older than the specified number of days.

        Returns:
            Number of records deleted.
        """
        cutoff = datetime.combine(
            date.today() - timedelta(days=days),
            datetime.min.time(),
        )
        old_faces = session.query(UnknownFace).filter(UnknownFace.timestamp < cutoff).all()
        count = len(old_faces)
        for uf in old_faces:
            # Delete image file
            if uf.image_path:
                try:
                    Path(uf.image_path).unlink(missing_ok=True)
                except OSError:
                    pass
            session.delete(uf)
        session.commit()
        return count

    @staticmethod
    def count_unreviewed(session: Session) -> int:
        return session.query(UnknownFace).filter(UnknownFace.reviewed.is_(False)).count()

    @staticmethod
    def count_by_date_range(session: Session, start: date, end: date) -> int:
        return (
            session.query(UnknownFace)
            .filter(
                UnknownFace.timestamp.between(
                    datetime.combine(start, datetime.min.time()),
                    datetime.combine(end, datetime.max.time()),
                )
            )
            .count()
        )


# ── Camera Repository ─────────────────────────────────────────


class CameraRepo:
    """CRUD operations for the ``cameras`` table."""

    @staticmethod
    def create(
        session: Session,
        name: str,
        camera_index: int,
        location: Optional[str] = None,
    ) -> Camera:
        cam = Camera(
            name=name,
            camera_index=camera_index,
            camera_id=f"CAM-{uuid.uuid4().hex[:12]}",
            location=location,
        )
        session.add(cam)
        session.commit()
        session.refresh(cam)
        return cam

    @staticmethod
    def get_all(session: Session) -> List[Camera]:
        return session.query(Camera).order_by(Camera.camera_index).all()

    @staticmethod
    def get_active(session: Session) -> List[Camera]:
        return session.query(Camera).filter(Camera.is_active.is_(True)).order_by(Camera.camera_index).all()

    @staticmethod
    def get_by_id(session: Session, cam_id: int) -> Optional[Camera]:
        return session.query(Camera).filter(Camera.id == cam_id).first()

    @staticmethod
    def get_by_index(session: Session, camera_index: int) -> Optional[Camera]:
        return session.query(Camera).filter(Camera.camera_index == camera_index).first()


# ── Audit Log Repository ──────────────────────────────────────


class AuditLogRepo:
    """CRUD operations for the ``audit_log`` table."""

    @staticmethod
    def create(
        session: Session,
        action: str,
        description: Optional[str] = None,
        operator: str = "system",
        employee_id: Optional[int] = None,
    ) -> AuditLog:
        log = AuditLog(
            action=action,
            description=description,
            actor=operator,
            employee_id=employee_id,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return log

    @staticmethod
    def get_recent(session: Session, limit: int = 100) -> List[AuditLog]:
        return session.query(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit).all()

    @staticmethod
    def get_by_action(session: Session, action: str) -> List[AuditLog]:
        return (
            session.query(AuditLog).filter(AuditLog.action == action).order_by(desc(AuditLog.timestamp)).all()
        )

    @staticmethod
    def search_paginated(
        session: Session,
        query: str = "",
        action: Optional[str] = None,
        actor: Optional[str] = None,
        severity: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> PageResult:
        """Search audit logs with filters and server-side pagination.

        Supports free-text search across actor/action/description/resource,
        plus exact filters for action, actor, severity and a timestamp range.
        Results are ordered newest-first.
        """
        q = session.query(AuditLog)

        term = query.strip()
        if term:
            pattern = f"%{term}%"
            q = q.filter(
                or_(
                    AuditLog.actor.ilike(pattern),
                    AuditLog.action.ilike(pattern),
                    AuditLog.description.ilike(pattern),
                    AuditLog.resource_type.ilike(pattern),
                )
            )
        if action:
            q = q.filter(AuditLog.action == action)
        if actor:
            q = q.filter(AuditLog.actor == actor)
        if severity:
            q = q.filter(AuditLog.severity == severity)
        if date_from:
            q = q.filter(AuditLog.timestamp >= date_from)
        if date_to:
            q = q.filter(AuditLog.timestamp <= date_to)

        q = q.order_by(desc(AuditLog.timestamp))
        return _paginate(q, skip=skip, limit=limit)
