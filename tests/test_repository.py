"""
Tests for the database repository layer.

Covers CRUD operations for EmployeeRepo, CameraRepo, and AuditLogRepo.

Uses ``reset_db`` at the class level (drops/recreates all tables) and
``get_session()`` from the database module (which has been monkey-patched
by conftest.py to point to the test database).
"""

from __future__ import annotations

import pytest

from database.database import get_session
from database.repository import (
    EmployeeRepo,
    CameraRepo,
    AuditLogRepo,
    RecognitionLogRepo,
)


class TestEmployeeRepo:
    """Tests for EmployeeRepo CRUD operations."""

    @pytest.fixture(autouse=True)
    def _clean_slate(self, reset_db):
        """Reset all tables before each test class."""
        with get_session() as session:
            self.s = session

    def test_create_employee(self):
        emp = EmployeeRepo.create(
            self.s,
            employee_id="EMP001",
            name="Alice",
            department="Engineering",
        )
        assert emp.id is not None
        assert emp.employee_id == "EMP001"
        assert emp.name == "Alice"
        assert emp.department == "Engineering"

    def test_get_by_id(self):
        emp = EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        found = EmployeeRepo.get_by_id(self.s, emp.id)
        assert found is not None
        assert found.name == "Alice"

    def test_get_by_id_not_found(self):
        found = EmployeeRepo.get_by_id(self.s, 999)
        assert found is None

    def test_get_by_employee_id(self):
        EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        found = EmployeeRepo.get_by_employee_id(self.s, "EMP001")
        assert found is not None
        assert found.name == "Alice"

    def test_get_by_employee_id_not_found(self):
        found = EmployeeRepo.get_by_employee_id(self.s, "NONEXISTENT")
        assert found is None

    def test_get_all_empty(self):
        employees = EmployeeRepo.get_all(self.s)
        assert employees == []

    def test_get_all_multiple(self):
        EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        EmployeeRepo.create(self.s, employee_id="EMP002", name="Bob")
        EmployeeRepo.create(self.s, employee_id="EMP003", name="Charlie")
        employees = EmployeeRepo.get_all(self.s)
        assert len(employees) == 3

    def test_search_by_name(self):
        EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        EmployeeRepo.create(self.s, employee_id="EMP002", name="Bob")
        results = EmployeeRepo.search(self.s, "Ali")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_search_by_employee_id(self):
        EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        results = EmployeeRepo.search(self.s, "EMP001")
        assert len(results) == 1

    def test_search_by_department(self):
        EmployeeRepo.create(
            self.s, employee_id="EMP001", name="Alice", department="Engineering"
        )
        results = EmployeeRepo.search(self.s, "Engineer")
        assert len(results) == 1

    def test_search_no_results(self):
        EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        results = EmployeeRepo.search(self.s, "Nonexistent")
        assert results == []

    def test_search_case_insensitive(self):
        EmployeeRepo.create(self.s, employee_id="EMP001", name="alice")
        results = EmployeeRepo.search(self.s, "ALICE")
        assert len(results) == 1

    def test_delete_existing(self):
        EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        result = EmployeeRepo.delete(self.s, "EMP001")
        assert result is True
        assert EmployeeRepo.get_by_employee_id(self.s, "EMP001") is None

    def test_delete_not_found(self):
        result = EmployeeRepo.delete(self.s, "NONEXISTENT")
        assert result is False

    def test_count(self):
        assert EmployeeRepo.count(self.s) == 0
        EmployeeRepo.create(self.s, employee_id="EMP001", name="Alice")
        assert EmployeeRepo.count(self.s) == 1


class TestCameraRepo:
    """Tests for CameraRepo CRUD operations."""

    @pytest.fixture(autouse=True)
    def _clean_slate(self, reset_db):
        """Reset all tables before each test class."""
        with get_session() as session:
            self.s = session

    def test_create_camera(self):
        cam = CameraRepo.create(
            self.s,
            name="Main Entrance",
            camera_index=0,
            location="Lobby",
        )
        assert cam.id is not None
        assert cam.name == "Main Entrance"
        assert cam.camera_index == 0
        assert cam.location == "Lobby"
        assert cam.is_active is True

    def test_get_all(self):
        CameraRepo.create(self.s, name="Camera 1", camera_index=0)
        CameraRepo.create(self.s, name="Camera 2", camera_index=1)
        cameras = CameraRepo.get_all(self.s)
        assert len(cameras) == 2

    def test_get_active(self):
        from database.models import Camera
        cam1 = CameraRepo.create(self.s, name="Active Cam", camera_index=0)
        cam2 = CameraRepo.create(self.s, name="Inactive Cam", camera_index=1)
        cam2.is_active = False
        self.s.commit()

        active = CameraRepo.get_active(self.s)
        assert len(active) == 1
        assert active[0].name == "Active Cam"

    def test_get_by_index(self):
        CameraRepo.create(self.s, name="Main", camera_index=0)
        cam = CameraRepo.get_by_index(self.s, 0)
        assert cam is not None
        assert cam.name == "Main"

    def test_get_by_index_not_found(self):
        cam = CameraRepo.get_by_index(self.s, 99)
        assert cam is None


class TestAuditLogRepo:
    """Tests for AuditLogRepo CRUD operations."""

    @pytest.fixture(autouse=True)
    def _clean_slate(self, reset_db):
        """Reset all tables before each test class."""
        with get_session() as session:
            self.s = session

    def test_create_log(self):
        log = AuditLogRepo.create(
            self.s,
            action="TEST",
            description="Test audit entry",
            operator="test_suite",
        )
        assert log.id is not None
        assert log.action == "TEST"
        assert log.operator == "test_suite"

    def test_get_recent(self):
        AuditLogRepo.create(self.s, action="ACTION_A", description="First")
        AuditLogRepo.create(self.s, action="ACTION_B", description="Second")
        AuditLogRepo.create(self.s, action="ACTION_C", description="Third")
        recent = AuditLogRepo.get_recent(self.s, limit=2)
        assert len(recent) == 2

    def test_get_by_action(self):
        AuditLogRepo.create(self.s, action="ENROLL", description="Enrolled Alice")
        AuditLogRepo.create(self.s, action="ENROLL", description="Enrolled Bob")
        AuditLogRepo.create(self.s, action="DELETE", description="Deleted Charlie")
        enroll_logs = AuditLogRepo.get_by_action(self.s, "ENROLL")
        assert len(enroll_logs) == 2
        delete_logs = AuditLogRepo.get_by_action(self.s, "DELETE")
        assert len(delete_logs) == 1


class TestRecognitionLogRepo:
    """Tests for RecognitionLogRepo — verifies the AMFR fields forwarded by
    the live pipeline (liveness_confidence / is_spoof / track_id) persist.

    Regression guard for the real-camera validation finding: recognition
    events were silently failing to log because the repo rejected these
    kwargs (``unexpected keyword argument 'liveness_confidence'``).
    """

    @pytest.fixture(autouse=True)
    def _clean_slate(self, reset_db):
        """Reset all tables before each test class."""
        with get_session() as session:
            self.s = session

    def test_create_basic(self):
        log = RecognitionLogRepo.create(
            self.s,
            is_known=True,
            confidence=0.95,
        )
        assert log.id is not None
        assert log.is_known is True
        assert log.confidence == 0.95

    def test_create_persists_liveness_confidence(self):
        """liveness_confidence must be stored (the original TypeError fix)."""
        log = RecognitionLogRepo.create(
            self.s,
            is_known=True,
            confidence=0.9,
            liveness_confidence=0.8,
        )
        assert log.liveness_confidence == 0.8

    def test_create_persists_is_spoof(self):
        log = RecognitionLogRepo.create(
            self.s,
            is_known=False,
            confidence=0.0,
            is_spoof=True,
        )
        assert log.is_spoof is True

    def test_create_persists_track_id(self):
        log = RecognitionLogRepo.create(
            self.s,
            is_known=False,
            confidence=0.2,
            track_id="T000123-abc",
        )
        assert log.track_id == "T000123-abc"

    def test_create_all_amfr_fields_together(self):
        """Full AMFR result must persist all fields simultaneously."""
        log = RecognitionLogRepo.create(
            self.s,
            is_known=True,
            confidence=0.93,
            liveness_confidence=0.88,
            is_spoof=False,
            track_id="T000456-def",
        )
        assert log.liveness_confidence == 0.88
        assert log.is_spoof is False
        assert log.track_id == "T000456-def"
