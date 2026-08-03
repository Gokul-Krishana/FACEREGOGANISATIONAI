"""
Tests for AuditService.

Covers logging, retrieving recent logs, filtering by action, and
edge cases like empty logs.
"""

from __future__ import annotations

import pytest

from services.audit_service import AuditService


class TestAuditService:
    """Tests for AuditService business logic."""

    @pytest.fixture(autouse=True)
    def _clean_db(self, reset_db):
        """Reset database before each test."""
        pass

    def test_log_basic(self):
        AuditService.log(
            action="TEST",
            description="Basic test log entry",
            operator="test_suite",
        )
        logs = AuditService.get_recent(limit=10)
        assert len(logs) >= 1
        assert logs[0].action == "TEST"

    def test_log_with_employee_id(self):
        AuditService.log(
            action="ENROLL",
            description="Enrolled employee Alice",
            operator="admin",
            employee_id=42,
        )
        logs = AuditService.get_by_action("ENROLL")
        assert len(logs) >= 1
        assert logs[0].employee_id == 42

    def test_log_default_operator(self):
        AuditService.log(
            action="SYSTEM_ACTION",
            description="Automatic system action",
        )
        logs = AuditService.get_recent(limit=1)
        assert logs[0].operator == "system"

    def test_get_recent_returns_newest_first(self):
        AuditService.log(action="FIRST", description="First entry")
        AuditService.log(action="SECOND", description="Second entry")
        AuditService.log(action="THIRD", description="Third entry")
        logs = AuditService.get_recent(limit=3)
        assert logs[0].action == "THIRD"
        assert logs[-1].action == "FIRST"

    def test_get_recent_respects_limit(self):
        for i in range(10):
            AuditService.log(action=f"ACTION_{i}", description=f"Entry {i}")
        logs = AuditService.get_recent(limit=3)
        assert len(logs) == 3

    def test_get_by_action_empty(self):
        logs = AuditService.get_by_action("NONEXISTENT")
        assert logs == []

    def test_log_multiple_actions(self):
        AuditService.log(action="ENROLL", description="Enrolled Alice")
        AuditService.log(action="MARK_ATTENDANCE", description="Marked Alice")
        AuditService.log(action="DELETE", description="Deleted Bob")

        enroll_logs = AuditService.get_by_action("ENROLL")
        assert len(enroll_logs) >= 1
        assert any("Alice" in (log.description or "") for log in enroll_logs)

        delete_logs = AuditService.get_by_action("DELETE")
        assert len(delete_logs) >= 1
        assert any("Bob" in (log.description or "") for log in delete_logs)
