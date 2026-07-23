"""
Tests for AttendanceService.

Covers attendance marking, duplicate prevention, statistics, and CSV
dual-write integration.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

from config.config import ATTENDANCE_DIR
from services.attendance_service import AttendanceService
from services.employee_service import EmployeeService


class TestAttendanceService:
    """Tests for AttendanceService business logic."""

    @pytest.fixture(autouse=True)
    def _clean_db(self, reset_db):
        """Reset database before each test."""
        pass

    @pytest.fixture()
    def alice(self):
        return EmployeeService.create(
            employee_id="EMP001", name="Alice", department="Engineering"
        )

    @pytest.fixture()
    def bob(self):
        return EmployeeService.create(
            employee_id="EMP002", name="Bob", department="Marketing"
        )

    def test_mark_attendance(self, alice):
        result = AttendanceService.mark(
            employee_id=alice.id,
            confidence=0.95,
            employee_name=alice.name,
        )
        assert result is True

    def test_mark_attendance_double_prevention(self, alice):
        """Same person should not be marked twice on the same day."""
        first = AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        )
        assert first is True

        second = AttendanceService.mark(
            employee_id=alice.id, confidence=0.90, employee_name=alice.name
        )
        assert second is False  # Already marked today

    def test_mark_multiple_employees(self, alice, bob):
        """Different employees can both be marked on the same day."""
        assert AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        ) is True
        assert AttendanceService.mark(
            employee_id=bob.id, confidence=0.88, employee_name=bob.name
        ) is True

    def test_get_today(self, alice):
        AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        )
        today = AttendanceService.get_today()
        assert len(today) == 1
        assert today[0].employee_id == alice.id

    def test_get_today_empty(self):
        records = AttendanceService.get_today()
        assert records == []

    def test_get_by_date(self, alice):
        AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        )
        records = AttendanceService.get_by_date(date.today())
        assert len(records) == 1

    def test_get_by_date_no_records(self):
        records = AttendanceService.get_by_date(date.today() - timedelta(days=7))
        assert records == []

    def test_get_by_employee(self, alice):
        AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        )
        records = AttendanceService.get_by_employee(alice.id)
        assert len(records) == 1

    def test_get_statistics_empty(self):
        stats = AttendanceService.get_statistics()
        assert stats["today_count"] == 0
        assert stats["total_records"] == 0

    def test_get_statistics(self, alice, bob):
        AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        )
        AttendanceService.mark(
            employee_id=bob.id, confidence=0.88, employee_name=bob.name
        )
        stats = AttendanceService.get_statistics()
        assert stats["today_count"] == 2
        assert stats["unique_today"] == 2
        assert stats["total_records"] == 2
        assert stats["unique_employees"] == 2

    def test_csv_dual_write(self, alice):
        """Attendance should also be written to CSV."""
        AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        )
        # Check that a CSV file was created for today
        today_str = date.today().isoformat()
        csv_path = Path(ATTENDANCE_DIR) / f"{today_str}.csv"
        assert csv_path.exists()

        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) >= 1
        assert any(alice.name in row["name"] for row in rows)

    def test_to_dict(self, alice):
        AttendanceService.mark(
            employee_id=alice.id, confidence=0.95, employee_name=alice.name
        )
        records = AttendanceService.get_today()
        if records:
            d = AttendanceService.to_dict(records[0])
            assert "employee_id" in d
            assert "employee_name" in d
            assert "timestamp" in d
            assert "confidence" in d
