"""
Employee Service — manages employee records in the database.

Provides a clean API above the repository layer, with automatic
audit logging for every action.
"""

from __future__ import annotations

from typing import List, Optional

from database.database import get_session
from database.models import Employee
from database.repository import EmployeeRepo
from services.audit_service import AuditService


class EmployeeService:
    """Service for managing employee records.

    Usage::

        emp = EmployeeService.create("EMP001", "Alice", department="Engineering")
        all_emps = EmployeeService.get_all()
        found = EmployeeService.search("Ali")
    """

    @staticmethod
    def create(
        employee_id: str,
        name: str,
        department: Optional[str] = None,
        photo_path: Optional[str] = None,
        faiss_id: Optional[int] = None,
        operator: str = "system",
    ) -> Employee:
        """Register a new employee.

        Args:
            employee_id: Unique employee identifier (e.g. ``EMP001``).
            name: Display name.
            department: Department name (optional).
            photo_path: Path to the employee's photo (optional).
            faiss_id: FAISS index ID (optional, set after enrollment).
            operator: Who performed this action.

        Returns:
            The created ``Employee`` ORM object.

        Raises:
            ValueError: If ``employee_id`` already exists.
        """
        with get_session() as session:
            existing = EmployeeRepo.get_by_employee_id(session, employee_id)
            if existing:
                raise ValueError(f"Employee '{employee_id}' already exists")

            emp = EmployeeRepo.create(
                session,
                employee_id=employee_id,
                name=name,
                department=department,
                photo_path=photo_path,
                faiss_id=faiss_id,
            )

        AuditService.log(
            "ENROLL",
            f"Enrolled employee '{name}' ({employee_id})",
            operator=operator,
            employee_id=emp.id,  # type: ignore[arg-type]
        )
        return emp

    @staticmethod
    def get_by_employee_id(employee_id: str) -> Optional[Employee]:
        """Look up an employee by their ``employee_id``."""
        with get_session() as session:
            return EmployeeRepo.get_by_employee_id(session, employee_id)

    @staticmethod
    def get_by_id(emp_id: int) -> Optional[Employee]:
        """Look up an employee by database ID."""
        with get_session() as session:
            return EmployeeRepo.get_by_id(session, emp_id)

    @staticmethod
    def get_by_name(name: str) -> Optional[Employee]:
        """Look up an employee by display name."""
        with get_session() as session:
            return EmployeeRepo.get_by_name(session, name)

    @staticmethod
    def update(
        employee_id: str,
        name: Optional[str] = None,
        department: Optional[str] = None,
        operator: str = "system",
    ) -> Optional[Employee]:
        """Update an employee's editable fields.

        Only fields that are provided (not ``None``) are changed — a
        partial update. The employee is looked up by ``employee_id``.

        Args:
            employee_id: Unique employee identifier (e.g. ``EMP001``).
            name: New display name (optional).
            department: New department (optional).
            operator: Who performed this action.

        Returns:
            The updated ``Employee``, or ``None`` if not found.

        Note:
            When the display name changes, the FAISS metadata label is
            renamed to match so recognition keeps resolving the employee
            (a DB-only rename would silently break the match → attendance
            path). FAISS rename failures are logged, never fatal.
        """
        fields: dict = {}
        if name is not None:
            fields["name"] = name
        if department is not None:
            fields["department"] = department
        if not fields:
            return None

        with get_session() as session:
            emp = EmployeeRepo.get_by_employee_id(session, employee_id)
            if not emp:
                return None
            old_name = emp.name
            updated = EmployeeRepo.update(session, emp.id, **fields)  # type: ignore[arg-type]

        if updated is not None and name is not None and name != old_name:
            # Keep FAISS in sync so recognition keeps matching after a rename.
            # The pipeline resolves employees by the FAISS enrollment name, so
            # a DB-only rename would silently break recognition/attendance.
            try:
                from app.enrollment import FaceEnrollment

                enrollment = FaceEnrollment()
                enrollment.rename(old_name, name)  # type: ignore[arg-type]
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to rename '%s' → '%s' in FAISS: %s",
                    old_name,
                    name,
                    exc,
                )

        if updated is not None:
            AuditService.log(
                "UPDATE_EMPLOYEE",
                f"Updated employee '{updated.name}' ({employee_id})",
                operator=operator,
            )
        return updated

    @staticmethod
    def get_all() -> List[Employee]:
        """Get all employees, sorted by name."""
        with get_session() as session:
            return EmployeeRepo.get_all(session)

    @staticmethod
    def search(query: str) -> List[Employee]:
        """Search employees by name, ID, or department."""
        with get_session() as session:
            return EmployeeRepo.search(session, query)

    @staticmethod
    def delete(employee_id: str, operator: str = "system") -> bool:
        """Delete an employee by their ``employee_id``.

        Also removes the corresponding embedding from FAISS so the
        deleted employee's face will no longer be recognised.

        Returns:
            ``True`` if deleted, ``False`` if not found.
        """
        with get_session() as session:
            emp = EmployeeRepo.get_by_employee_id(session, employee_id)
            if not emp:
                return False
            emp_name = emp.name
            success = EmployeeRepo.delete(session, employee_id)

        if success:
            # Keep FAISS in sync so the deleted employee is no longer recognised.
            EmployeeService.remove_faiss_embedding(emp_name, fallback=employee_id)  # type: ignore[arg-type]

            AuditService.log(
                "DELETE_EMPLOYEE",
                f"Deleted employee '{emp_name}' ({employee_id})",
                operator=operator,
            )
        return success

    @staticmethod
    def remove_faiss_embedding(name: str, fallback: Optional[str] = None) -> bool:
        """Remove an employee's embedding(s) from the FAISS index.

        FAISS stores the display name, so ``name`` is tried first; if no
        entry matches, ``fallback`` (typically the ``employee_id``) is tried.
        Never raises — FAISS failures are logged and do not block the caller
        (the DB row is already gone by the time this is invoked).

        Args:
            name: Display name stored in the FAISS metadata.
            fallback: Alternate name to try if ``name`` is not found.

        Returns:
            ``True`` if any embeddings were removed, ``False`` otherwise.
        """
        try:
            from app.enrollment import FaceEnrollment

            enrollment = FaceEnrollment()
            removed = enrollment.remove_by_name(name)
            if not removed and fallback:
                removed = enrollment.remove_by_name(fallback)
            return removed
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to remove '%s' from FAISS: %s",
                name,
                exc,
            )
            return False

    @staticmethod
    def count() -> int:
        """Total number of registered employees."""
        with get_session() as session:
            return EmployeeRepo.count(session)

    @staticmethod
    def to_dict(emp: Employee) -> dict:
        """Convert an Employee ORM object to a dictionary."""
        return {
            "id": emp.id,
            "employee_id": emp.employee_id,
            "name": emp.name,
            "department": emp.department,
            "photo_path": emp.photo_path,
            "faiss_id": emp.faiss_id,
            "created_at": emp.created_at.isoformat() if emp.created_at else None,
            "updated_at": emp.updated_at.isoformat() if emp.updated_at else None,
        }
