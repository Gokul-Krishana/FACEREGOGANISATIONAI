"""
Employee Service — manages employee records in the database.

Provides a clean API above the repository layer, with automatic
audit logging for every action.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import config.config as cfg
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
            employee_id=emp.id,
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

        .. note::
            This only removes the database record. The FAISS embedding
            is **not** removed (see ``FaceEnrollment.remove()``).

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
            AuditService.log(
                "DELETE_EMPLOYEE",
                f"Deleted employee '{emp_name}' ({employee_id})",
                operator=operator,
            )
        return success

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
