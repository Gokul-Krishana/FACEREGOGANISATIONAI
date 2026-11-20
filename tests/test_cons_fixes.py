"""
Regression tests for all 6 security, reliability, and correctness fixes:
1. Cross-platform camera backend discovery (Windows / Linux / macOS)
2. Anti-spoofing & mobile-photo rejection (MiniFASNetV2 BGR/class-1, bezel/glare, blink, AMFR gate)
3. Dashboard authentication & RBAC login gate
4. Overnight camera midnight date rollover
5. Idempotent concurrent attendance marking across multiple cameras
6. Same-name employee disambiguation & rename invariance
"""

from __future__ import annotations

import csv
import sys
import threading
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

import config.config as cfg
from app.amfr_engine import AMFRDecision, AMFREngine
from app.deep_liveness import DeepLivenessDetector
from app.enrollment import FaceEnrollment
from app.liveness_detector import LivenessDetector
from camera.webcam import WebcamSource, get_preferred_backends, list_webcams
from database.database import get_session
from database.models import Attendance, Role, RoleName, User
from services.attendance_service import AttendanceService
from services.employee_service import EmployeeService
from services.recognition_service import RecognitionService


# ═════════════════════════════════════════════════════════════════════
#  1. Cross-Platform Camera Support
# ═════════════════════════════════════════════════════════════════════


class TestCrossPlatformCameras:
    def test_preferred_backends_linux(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(cv2, "CAP_V4L2", 200, raising=False)
        backends = get_preferred_backends()
        codes = [b for b, _ in backends]
        assert 200 in codes
        assert codes[-1] is None
        assert getattr(cv2, "CAP_DSHOW", 700) not in codes

    def test_preferred_backends_macos(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(cv2, "CAP_AVFOUNDATION", 1200, raising=False)
        backends = get_preferred_backends()
        codes = [b for b, _ in backends]
        assert 1200 in codes
        assert codes[-1] is None
        assert getattr(cv2, "CAP_DSHOW", 700) not in codes

    def test_list_webcams_uses_platform_backends_on_linux(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(cv2, "CAP_V4L2", 200, raising=False)

        calls = []

        def fake_vc(idx, backend=None):
            calls.append((idx, backend))
            cap = MagicMock()
            cap.isOpened.return_value = idx == 0 and backend == 200
            return cap

        monkeypatch.setattr(cv2, "VideoCapture", fake_vc)
        found = list_webcams(max_devices=2)
        assert found == [0]
        assert all(b != getattr(cv2, "CAP_DSHOW", 700) for _, b in calls)

    def test_webcam_source_open_fallback_to_default(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(cv2, "CAP_V4L2", 200, raising=False)

        def fake_vc(idx, backend=None):
            cap = MagicMock()
            cap.isOpened.return_value = backend is None
            return cap

        monkeypatch.setattr(cv2, "VideoCapture", fake_vc)
        cam = WebcamSource(device_id=0)
        assert cam.open() is True
        cam.release()


# ═════════════════════════════════════════════════════════════════════
#  2. Anti-Spoofing / Mobile Photo Rejection
# ═════════════════════════════════════════════════════════════════════


class TestAntiSpoofingFixes:
    def test_amfr_never_accepts_when_is_live_false(self):
        engine = AMFREngine()
        # Even with perfect ArcFace match (dist=0.0) and high quality,
        # a failed liveness check MUST reject as spoof, even if liveness_score >= 0.15.
        decision, risk, details = engine._decide(
            arcface_distance=0.0,
            liveness_score=0.45,
            quality_score=1.0,
            is_live=False,
            faiss_confidence=1.0,
        )
        assert decision == AMFRDecision.REJECT_SPOOF
        assert risk == 0.0
        assert details["liveness_gate"] == "FAILED"

    def test_amfr_fails_closed_without_face_crop(self):
        engine = AMFREngine()
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        det = {"bbox": (50, 50, 200, 220), "confidence": 0.9}
        faiss_res = [{"name": "Alice", "employee_id": "EMP001", "confidence": 0.99, "distance": 0.05}]
        results = engine.process_frame(
            frame=frame,
            detections=[det],
            embeddings=[np.ones(512, dtype=np.float32)],
            faiss_results=[faiss_res],
            face_data=[None],
        )
        assert len(results) == 1
        assert results[0]["amfr_decision"] == AMFRDecision.REJECT_SPOOF.value
        assert results[0]["is_live"] is False

    def test_liveness_rejects_bezel_in_context_crop(self):
        det = LivenessDetector(use_deep_liveness=False)
        face = np.random.randint(80, 180, (120, 120, 3), dtype=np.uint8)
        # Context image has a bright rectangular phone bezel around the border
        ctx = np.zeros((240, 240, 3), dtype=np.uint8)
        cv2.rectangle(ctx, (6, 6), (234, 234), (255, 255, 255), 3)
        cv2.rectangle(ctx, (10, 10), (230, 230), (255, 255, 255), 2)
        landmarks = np.array([[35, 45], [85, 45], [60, 70], [42, 95], [78, 95]], dtype=np.float32)
        result = det.analyze_frame(face, landmarks=landmarks, context_img=ctx)
        assert result.screen_score > 0.6
        assert "screen_detected" in result.reasons
        assert result.is_live is False

    def test_liveness_rejects_static_open_eyes_no_blink(self):
        det = LivenessDetector(use_deep_liveness=False)
        face = np.random.randint(60, 200, (120, 120, 3), dtype=np.uint8)
        landmarks = np.array([[35, 45], [85, 45], [60, 75], [42, 95], [78, 95]], dtype=np.float32)
        result = None
        for _ in range(16):
            result = det.analyze_frame(face, landmarks=landmarks)
        assert result is not None
        assert "no_blink_detected" in result.reasons
        assert result.is_live is False

    def test_liveness_rejects_when_dl_below_threshold(self, monkeypatch):
        det = LivenessDetector(use_deep_liveness=True)
        monkeypatch.setattr(
            det._deep_liveness,
            "predict",
            lambda face_img, landmarks=None: SimpleNamespace(
                is_live=False, dl_score=0.35, inference_time_ms=1.0
            ),
        )
        face = np.random.randint(60, 200, (120, 120, 3), dtype=np.uint8)
        landmarks = np.array([[35, 45], [85, 45], [60, 75], [42, 95], [78, 95]], dtype=np.float32)
        result = det.analyze_frame(face, landmarks=landmarks)
        assert "deep_learning_spoof" in result.reasons
        assert result.is_live is False

    def test_minifasnet_onnx_separates_screen_from_real_photo(self):
        model_path = Path(cfg.ROOT_DIR) / "models" / "liveness" / "MiniFASNetV2.onnx"
        if not model_path.exists():
            pytest.skip("MiniFASNetV2.onnx not present")
        dl = DeepLivenessDetector()
        assert not dl.using_fallback

        # Synthetic screen pixel-grid spoof
        screen_grid = np.tile(np.array([[[255, 0, 0], [0, 255, 0]]], dtype=np.uint8), (80, 40, 1))
        spoof_res = dl.predict(screen_grid)
        assert spoof_res.is_live is False
        assert spoof_res.dl_score < 0.2

        # Real face sample if present
        sample = Path(cfg.ROOT_DIR) / "dataset" / "demo_enroll.jpg"
        if sample.exists():
            real_img = cv2.imread(str(sample))
            real_res = dl.predict(real_img)
            assert real_res.is_live is True
            assert real_res.dl_score > 0.8

    def test_align_face_does_not_throw_tuple_error(self):
        dl = DeepLivenessDetector()
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        lm = np.array([[30, 32], [70, 32], [50, 48], [36, 65], [64, 65]], dtype=np.float32)
        aligned = dl._align_face(img, lm)
        assert aligned.shape == img.shape


# ═════════════════════════════════════════════════════════════════════
#  3. Dashboard Login Gate & RBAC
# ═════════════════════════════════════════════════════════════════════


class TestDashboardAuthGate:
    def test_create_initial_admin_and_authenticate(self, reset_db):
        from dashboard import auth

        assert auth.has_any_users() is False
        ok, msg = auth.create_initial_admin("admin", "admin@college.edu", "Str0ngPass!9")
        assert ok is True, msg
        assert auth.has_any_users() is True

        # Wrong password fails
        ok_bad, user_bad, _ = auth.authenticate_user("admin", "wrongpass")
        assert ok_bad is False
        assert user_bad is None

        # Correct password succeeds
        ok_good, user_good, _ = auth.authenticate_user("admin", "Str0ngPass!9")
        assert ok_good is True
        assert user_good is not None
        assert user_good["username"] == "admin"
        assert RoleName.SUPER_ADMIN.value in user_good["roles"]

    def test_role_enforcement_blocks_non_admin_from_admin_pages(self, reset_db):
        from dashboard import auth

        with get_session() as session:
            faculty_role = Role(name=RoleName.FACULTY.value, description="Faculty")
            session.add(faculty_role)
            session.flush()
            u = User(
                username="prof1",
                email="prof1@college.edu",
                password_hash=auth.hash_password("FacultyPass!1"),
                is_active=True,
            )
            u.roles.append(faculty_role)
            session.add(u)
            session.commit()

        ok, user_payload, _ = auth.authenticate_user("prof1", "FacultyPass!1")
        assert ok is True
        assert auth.user_has_role(user_payload, None) is True
        assert auth.user_has_role(user_payload, auth.ADMIN_ROLES) is False

    def test_require_auth_stops_when_unauthenticated(self, reset_db, monkeypatch):
        from dashboard import auth

        fake_st = MagicMock()
        fake_st.session_state = {}
        fake_st.form.return_value.__enter__ = MagicMock(return_value=None)
        fake_st.form.return_value.__exit__ = MagicMock(return_value=False)
        fake_st.form_submit_button.return_value = False
        monkeypatch.setitem(sys.modules, "streamlit", fake_st)

        assert auth.require_auth(allowed_roles=auth.ADMIN_ROLES) is False


# ═════════════════════════════════════════════════════════════════════
#  4. Overnight Camera Midnight Rollover
# ═════════════════════════════════════════════════════════════════════


class TestOvernightDateRollover:
    def test_recognition_service_resets_session_cache_on_new_day(self):
        svc = RecognitionService(
            detector=MagicMock(),
            recognizer=MagicMock(),
            enrollment=MagicMock(),
            amfr=MagicMock(),
        )
        day1 = date(2026, 11, 11)
        day2 = day1 + timedelta(days=1)

        with patch("services.recognition_service.date") as mock_date:
            mock_date.today.return_value = day1
            svc._session_date = day1
            with patch("services.recognition_service.AttendanceService.mark", return_value=True) as mk:
                assert svc._maybe_mark_attendance("EMP001", 1, 0.95) is True
                assert svc._maybe_mark_attendance("EMP001", 1, 0.95) is False
                assert mk.call_count == 1

            # Next day after running overnight
            mock_date.today.return_value = day2
            with patch("services.recognition_service.AttendanceService.mark", return_value=True) as mk2:
                assert svc._maybe_mark_attendance("EMP001", 1, 0.95) is True
                assert mk2.call_count == 1


# ═════════════════════════════════════════════════════════════════════
#  5. Idempotent Concurrent Attendance Across Cameras
# ═════════════════════════════════════════════════════════════════════


class TestConcurrentIdempotentAttendance:
    def test_two_cameras_marking_simultaneously_create_single_record(self, reset_db):
        emp = EmployeeService.create(employee_id="CAM-EMP-1", name="Concurrent User")

        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def worker(cam_id: int):
            barrier.wait(timeout=5)
            marked = AttendanceService.mark(
                employee_id=emp.id,
                confidence=0.95,
                camera_id=cam_id,
                employee_name=emp.name,
                employee_code=emp.employee_id,
            )
            with lock:
                results.append(marked)

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert sorted(results) == [False, True]
        with get_session() as session:
            count = session.query(Attendance).filter(Attendance.employee_id == emp.id).count()
        assert count == 1


# ═════════════════════════════════════════════════════════════════════
#  6. Same-Name Disambiguation & Rename Invariance
# ═════════════════════════════════════════════════════════════════════


class TestIdentityDisambiguationAndRename:
    def test_same_name_employees_resolve_and_mark_independently(self, reset_db, tmp_path):
        emp1 = EmployeeService.create(employee_id="EMP101", name="John Smith")
        emp2 = EmployeeService.create(employee_id="EMP102", name="John Smith")

        idx_path = tmp_path / "same_name.index"
        meta_path = tmp_path / "same_name_meta.json"
        enr = FaceEnrollment(index_path=str(idx_path), metadata_path=str(meta_path))

        emb1 = np.zeros(512, dtype=np.float32)
        emb1[0] = 1.0
        emb2 = np.zeros(512, dtype=np.float32)
        emb2[1] = 1.0

        enr.enroll(emp1.name, emb1, employee_id=emp1.employee_id)
        enr.enroll(emp2.name, emb2, employee_id=emp2.employee_id)

        m1 = enr.search(emb1, k=1, threshold=0.5)
        m2 = enr.search(emb2, k=1, threshold=0.5)
        assert m1[0]["employee_id"] == "EMP101"
        assert m2[0]["employee_id"] == "EMP102"

        # RecognitionService resolves each to its own DB employee and marks both
        r1 = RecognitionService._resolve_employee(name=m1[0]["name"], employee_id=m1[0]["employee_id"])
        r2 = RecognitionService._resolve_employee(name=m2[0]["name"], employee_id=m2[0]["employee_id"])
        assert r1 is not None and r1.id == emp1.id
        assert r2 is not None and r2.id == emp2.id

        assert (
            AttendanceService.mark(
                employee_id=r1.id, confidence=0.95, employee_name=r1.name, employee_code=r1.employee_id
            )
            is True
        )
        assert (
            AttendanceService.mark(
                employee_id=r2.id, confidence=0.94, employee_name=r2.name, employee_code=r2.employee_id
            )
            is True
        )

        today_csv = Path(cfg.ATTENDANCE_DIR) / f"{date.today().isoformat()}.csv"
        with open(today_csv, "r") as f:
            rows = list(csv.DictReader(f))
        codes = {row.get("employee_id") for row in rows}
        assert {"EMP101", "EMP102"}.issubset(codes)

    def test_renaming_employee_keeps_identity_resolution_and_leaves_colleague_intact(
        self, reset_db, tmp_path, monkeypatch
    ):
        emp1 = EmployeeService.create(employee_id="EMP201", name="Alex Taylor")
        EmployeeService.create(employee_id="EMP202", name="Alex Taylor")

        idx_path = tmp_path / "rename.index"
        meta_path = tmp_path / "rename_meta.json"
        monkeypatch.setattr(cfg, "FAISS_INDEX_PATH", str(idx_path))
        monkeypatch.setattr(cfg, "METADATA_PATH", str(meta_path))

        enr = FaceEnrollment(index_path=str(idx_path), metadata_path=str(meta_path))
        emb1 = np.zeros(512, dtype=np.float32)
        emb1[10] = 1.0
        emb2 = np.zeros(512, dtype=np.float32)
        emb2[20] = 1.0
        enr.enroll("Alex Taylor", emb1, employee_id="EMP201")
        enr.enroll("Alex Taylor", emb2, employee_id="EMP202")

        # Rename EMP201 only
        updated = EmployeeService.update("EMP201", name="Alexandra Taylor")
        assert updated is not None and updated.name == "Alexandra Taylor"

        enr_reloaded = FaceEnrollment(index_path=str(idx_path), metadata_path=str(meta_path))
        m1 = enr_reloaded.search(emb1, k=1, threshold=0.5)[0]
        m2 = enr_reloaded.search(emb2, k=1, threshold=0.5)[0]
        assert m1["employee_id"] == "EMP201"
        assert m1["name"] == "Alexandra Taylor"
        assert m2["employee_id"] == "EMP202"
        assert m2["name"] == "Alex Taylor"  # Unchanged!

        # Even if FAISS metadata had stale name, employee_id still resolves EMP201
        resolved = RecognitionService._resolve_employee(name="Alex Taylor", employee_id="EMP201")
        assert resolved is not None and resolved.id == emp1.id

        # Deleting EMP201 leaves EMP202's embedding intact
        assert EmployeeService.delete("EMP201") is True
        enr_after_del = FaceEnrollment(index_path=str(idx_path), metadata_path=str(meta_path))
        assert enr_after_del.count() == 1
        assert enr_after_del.search(emb2, k=1, threshold=0.5)[0]["employee_id"] == "EMP202"


class TestAdditionalProductionVerification:
    def test_four_concurrent_cameras_idempotent(self, reset_db):
        emp = EmployeeService.create(employee_id="CAM-EMP-4X", name="Four Cam User")
        barrier = threading.Barrier(4)
        results = []
        lock = threading.Lock()

        def worker(cam_id: int):
            barrier.wait(timeout=5)
            marked = AttendanceService.mark(
                employee_id=int(emp.id),  # type: ignore[arg-type]
                confidence=0.96,
                camera_id=cam_id,
                employee_name=emp.name,
                employee_code=emp.employee_id,
            )
            with lock:
                results.append(marked)

        threads = [threading.Thread(target=worker, args=(cid,)) for cid in range(1, 5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert results.count(True) == 1
        assert results.count(False) == 3
        with get_session() as session:
            count = session.query(Attendance).filter(Attendance.employee_id == emp.id).count()
        assert count == 1

    def test_live_detection_clears_session_on_midnight_rollover(self):
        from app.live_detection import LiveDetection

        ld = LiveDetection.__new__(LiveDetection)
        day1 = date(2026, 11, 11)
        day2 = day1 + timedelta(days=1)
        ld._session_date = day1
        ld._marked_this_session = {"EMP001"}
        ld._frame_count = 0
        ld.frame_skip = 100
        ld._fps = 0.0
        ld._prev_time = 0.0
        ld._last_recognised = []
        ld._draw_overlay = MagicMock(side_effect=lambda f, r: f)

        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        with patch("app.live_detection.date") as mock_date:
            mock_date.today.return_value = day2
            ld.process_frame(frame)

        assert ld._session_date == day2
        assert ld._marked_this_session == set()

    @pytest.mark.parametrize("brightness", [0.6, 1.0, 1.3])
    def test_screen_glare_and_moire_spoof_detection_across_lighting(self, brightness):
        det = LivenessDetector(use_deep_liveness=False)
        # Simulate periodic LCD pixel grid + bright specular glare strip
        xx, yy = np.meshgrid(np.arange(120), np.arange(120))
        pattern = ((np.sin(2 * np.pi * xx / 3.0) + np.sin(2 * np.pi * yy / 3.0)) * 50 + 128).astype(
            np.float32
        )
        face = np.stack([pattern, pattern, pattern], axis=-1)
        face = np.clip(face * brightness, 0, 255).astype(np.uint8)
        face[10:35, 20:100] = 252  # Specular reflection band from phone glass
        landmarks = np.array([[35, 45], [85, 45], [60, 75], [42, 95], [78, 95]], dtype=np.float32)
        result = det.analyze_frame(face, landmarks=landmarks)
        assert result.screen_score > 0.6
        assert "screen_detected" in result.reasons
        assert result.is_live is False

    def test_api_attendance_service_time_window_grace_period(self):
        from datetime import datetime as _dt
        from api.attendance_service import AttendanceService as APIAttendanceService
        from database.models import Timetable

        assert (
            APIAttendanceService.is_within_time_window(
                _dt(2026, 1, 15, 10, 5), "09:00:00", "10:00:00", grace_minutes=10
            )
            is True
        )
        assert (
            APIAttendanceService.is_within_time_window(
                _dt(2026, 1, 15, 10, 15), "09:00:00", "10:00:00", grace_minutes=10
            )
            is False
        )
        tt = Timetable(
            section_id=42, classroom_id=1, day_of_week=0, start_time="09:00:00", end_time="10:00:00"
        )
        assert "section=42" in repr(tt)

    def test_api_attendance_response_accepts_nullable_student_id(self):
        from datetime import datetime as _dt
        from api.main import AttendanceResponse

        resp = AttendanceResponse(
            id=1,
            student_id=None,
            student_name="Unknown",
            timestamp=_dt(2026, 1, 15, 9, 0),
            confidence=0.95,
            method="FACE_RECOGNITION",
            status="PRESENT",
        )
        assert resp.student_id is None
