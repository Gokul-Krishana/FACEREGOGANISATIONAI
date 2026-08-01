"""
Tests for EmployeeService.

Covers employee CRUD, duplicate detection, audit logging integration,
and error handling.
"""

from __future__ import annotations

import pytest

from services.employee_service import EmployeeService
from services.audit_service import AuditService
from database.models import Employee


class TestEmployeeService:
    """Tests for EmployeeService business logic."""

    @pytest.fixture(autouse=True)
    def _clean_db(self, reset_db):
        """Reset database before each test in this class."""
        pass

    def test_create_employee(self):
        emp = EmployeeService.create(
            employee_id="EMP001",
            name="Alice",
            department="Engineering",
            operator="test",
        )
        assert isinstance(emp, Employee)
        assert emp.employee_id == "EMP001"
        assert emp.name == "Alice"
        assert emp.department == "Engineering"

    def test_create_duplicate_raises_error(self):
        EmployeeService.create(employee_id="EMP001", name="Alice")
        with pytest.raises(ValueError, match="already exists"):
            EmployeeService.create(employee_id="EMP001", name="Alice 2")

    def test_get_by_employee_id(self):
        EmployeeService.create(employee_id="EMP001", name="Alice")
        emp = EmployeeService.get_by_employee_id("EMP001")
        assert emp is not None
        assert emp.name == "Alice"

    def test_get_by_employee_id_not_found(self):
        emp = EmployeeService.get_by_employee_id("NONEXISTENT")
        assert emp is None

    def test_get_by_id(self):
        created = EmployeeService.create(employee_id="EMP001", name="Alice")
        emp = EmployeeService.get_by_id(created.id)
        assert emp is not None
        assert emp.name == "Alice"

    def test_get_all(self):
        EmployeeService.create(employee_id="EMP001", name="Alice")
        EmployeeService.create(employee_id="EMP002", name="Bob")
        employees = EmployeeService.get_all()
        assert len(employees) == 2

    def test_get_all_empty(self):
        employees = EmployeeService.get_all()
        assert employees == []

    def test_search(self):
        EmployeeService.create(employee_id="EMP001", name="Alice")
        EmployeeService.create(employee_id="EMP002", name="Bob")
        results = EmployeeService.search("Ali")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_update_name_and_department(self):
        EmployeeService.create(employee_id="EMP001", name="Alice", department="Engineering")
        updated = EmployeeService.update(
            employee_id="EMP001",
            name="Alicia",
            department="Science",
            operator="test",
        )
        assert updated is not None
        assert updated.name == "Alicia"
        assert updated.department == "Science"
        # Persisted to DB
        emp = EmployeeService.get_by_employee_id("EMP001")
        assert emp.name == "Alicia"
        assert emp.department == "Science"

    def test_update_partial_only_changes_provided_fields(self):
        EmployeeService.create(employee_id="EMP001", name="Alice", department="Engineering")
        updated = EmployeeService.update(employee_id="EMP001", department="Science")
        assert updated is not None
        assert updated.name == "Alice"  # unchanged
        assert updated.department == "Science"

    def test_update_not_found_returns_none(self):
        updated = EmployeeService.update(employee_id="NONEXISTENT", name="X")
        assert updated is None

    def test_update_with_no_fields_returns_none(self):
        EmployeeService.create(employee_id="EMP001", name="Alice")
        updated = EmployeeService.update(employee_id="EMP001")
        assert updated is None

    def test_update_logs_audit(self):
        EmployeeService.create(employee_id="EMP001", name="Alice", operator="admin")
        EmployeeService.update(employee_id="EMP001", name="Alicia", operator="admin")
        logs = AuditService.get_by_action("UPDATE_EMPLOYEE")
        assert len(logs) >= 1
        assert any("Alicia" in (log.description or "") for log in logs)

    def test_delete_existing(self):
        EmployeeService.create(employee_id="EMP001", name="Alice", operator="test")
        result = EmployeeService.delete("EMP001", operator="test")
        assert result is True
        assert EmployeeService.get_by_employee_id("EMP001") is None

    def test_delete_not_found(self):
        result = EmployeeService.delete("NONEXISTENT")
        assert result is False

    def test_count(self):
        assert EmployeeService.count() == 0
        EmployeeService.create(employee_id="EMP001", name="Alice")
        assert EmployeeService.count() == 1

    def test_create_logs_audit(self):
        """Verify that creating an employee creates an audit log entry."""
        EmployeeService.create(employee_id="EMP001", name="Alice", operator="admin")
        logs = AuditService.get_by_action("ENROLL")
        assert len(logs) >= 1
        assert any("Alice" in (log.description or "") for log in logs)

    def test_delete_logs_audit(self):
        """Verify that deleting an employee creates an audit log entry."""
        EmployeeService.create(employee_id="EMP001", name="Alice", operator="admin")
        EmployeeService.delete("EMP001", operator="admin")
        logs = AuditService.get_by_action("DELETE_EMPLOYEE")
        assert len(logs) >= 1
        assert any("Alice" in (log.description or "") for log in logs)

    def test_to_dict(self):
        emp = EmployeeService.create(
            employee_id="EMP001",
            name="Alice",
            department="Engineering",
        )
        d = EmployeeService.to_dict(emp)
        assert d["employee_id"] == "EMP001"
        assert d["name"] == "Alice"
        assert d["department"] == "Engineering"
        assert "created_at" in d
        assert "updated_at" in d
