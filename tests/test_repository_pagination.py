from __future__ import annotations

from database.database import get_session
from database.repository import AttendanceRepo, EmployeeRepo, StudentRepo


def test_student_repo_search_paginates(reset_db):
    with get_session() as session:
        StudentRepo.create(session, student_id="STU001", name="Alice")
        StudentRepo.create(session, student_id="STU002", name="Albert")
        StudentRepo.create(session, student_id="STU003", name="Bob")

        page = StudentRepo.search(session, query="Al", limit=2)

        assert page.total == 2
        assert len(page.items) == 2
        assert [student.student_id for student in page.items] == ["STU001", "STU002"]
        assert page.has_more is False


def test_employee_repo_search_paginated(reset_db):
    with get_session() as session:
        EmployeeRepo.create(session, employee_id="EMP001", name="Alice", department="Admin")
        EmployeeRepo.create(session, employee_id="EMP002", name="Alicia", department="Admin")
        EmployeeRepo.create(session, employee_id="EMP003", name="Bob", department="Ops")

        page = EmployeeRepo.search_paginated(session, query="Ali", limit=1)

        assert page.total == 2
        assert len(page.items) == 1
        assert page.has_more is True


def test_attendance_repo_statistics_and_limits(reset_db):
    with get_session() as session:
        emp1 = EmployeeRepo.create(session, employee_id="EMP001", name="Alice")
        emp2 = EmployeeRepo.create(session, employee_id="EMP002", name="Bob")

        AttendanceRepo.create(session, employee_id=emp1.id, confidence=0.95)
        AttendanceRepo.create(session, employee_id=emp2.id, confidence=0.90)
        AttendanceRepo.create(session, employee_id=emp1.id, confidence=0.85)

        stats = AttendanceRepo.get_statistics(session)
        assert stats["today_count"] == 3
        assert stats["unique_today"] == 2
        assert stats["total_records"] == 3
        assert stats["unique_employees"] == 2

        limited = AttendanceRepo.get_today(session, limit=2)
        assert len(limited) == 2
