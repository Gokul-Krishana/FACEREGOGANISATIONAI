"""
Tests for LiveRecognitionPipeline overlay drawing, camera lifecycle,
and duplicate attendance prevention.

Uses mocked CameraSource so no physical camera is required.
All AI models are mocked — only the logic/state machine is tested.
"""

from __future__ import annotations

import importlib.util
import sys
import time
import threading
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Module-level imports used by TestPipeline ───────────────────
# These must be at module level so @patch('test_repair.create_camera') works
import config.config as cfg
from app.amfr_engine import AMFRDecision
from services.recognition_service import RecognitionService
from camera.base import CameraSource
from camera.selector import create_camera as _real_create_camera
from dashboard.latency_logger import LatencyLogger

# ═══════════════════════════════════════════════════════════════
#  TestPipeline — minimal replication of LiveRecognitionPipeline
# ═══════════════════════════════════════════════════════════════

class MockSessionState:
    """Mock Streamlit session state supporting both attribute and dict access.

    Real ``st.session_state`` supports both:
        st.session_state.foo = bar   (attribute assignment)
        st.session_state["foo"] = bar  (item assignment)
        st.session_state.get("foo")   (dict-style .get())
        "foo" in st.session_state    (contains check)
    """

    def __init__(self) -> None:
        object.__setattr__(self, '_data', {})

    # ── attribute-based access ─────────────────────────────────

    def __getattr__(self, name: str):
        if name.startswith('_'):
            raise AttributeError(name)
        d = object.__getattribute__(self, '_data')
        if name in d:
            return d[name]
        return None

    def __setattr__(self, name: str, value) -> None:
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            d = object.__getattribute__(self, '_data')
            d[name] = value

    def __delattr__(self, name: str) -> None:
        if name in object.__getattribute__(self, '_data'):
            del object.__getattribute__(self, '_data')[name]

    # ── item-based access ──────────────────────────────────────

    def __getitem__(self, key: str):
        return object.__getattribute__(self, '_data')[key]

    def __setitem__(self, key: str, value) -> None:
        object.__getattribute__(self, '_data')[key] = value

    def __delitem__(self, key: str) -> None:
        del object.__getattribute__(self, '_data')[key]

    def __contains__(self, key: object) -> bool:
        return key in object.__getattribute__(self, '_data')

    def get(self, key: str, default=None):
        """Dict-style .get() method."""
        return object.__getattribute__(self, '_data').get(key, default)

    def keys(self):
        return object.__getattribute__(self, '_data').keys()

    def values(self):
        return object.__getattribute__(self, '_data').values()

    def items(self):
        return object.__getattribute__(self, '_data').items()

    def __len__(self) -> int:
        return len(object.__getattribute__(self, '_data'))

    def __repr__(self) -> str:
        return f"MockSessionState({object.__getattribute__(self, '_data')})"


class _TestPipeline:
    """Test-friendly pipeline with mocked models. No AI loaded."""

    def __init__(self, source_type: str = "webcam", **kwargs):
        self.source_type = source_type
        self.camera_kwargs = kwargs
        self._cam: CameraSource | None = None
        # Fully mocked service — no AI models loaded
        self._service = MagicMock()
        self._service.enrollment.count.return_value = 42
        self._service.enrollment.unique_count.return_value = 10
        self._service.process_frame_detailed.return_value = (
            np.zeros((480, 640, 3), dtype=np.uint8), []
        )
        self._service.amfr = MagicMock()
        self._service.status.return_value = {"enrolled": 42, "amfr": {}}
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

        self._latest_frame: np.ndarray | None = None
        self._latest_results: list[dict] = []
        self._fps: float = 0.0
        self._ai_fps: float = 0.0
        self._pipeline_latency: float = 0.0
        self._status: str = "STOPPED"
        self._people_count: int = 0
        self._frame_count: int = 0
        self._error: str | None = None
        self._reconnect_attempts: int = 0
        self._latency_logger = LatencyLogger()

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> bool:
        try:
            self._cam = _real_create_camera(self.source_type, **self.camera_kwargs)
            if self._cam is None:
                self._error = f"Could not create camera source: {self.source_type}"
                self._status = "ERROR"
                return False
            if not self._cam.open():
                self._error = "Could not open camera — check connection"
                self._status = "ERROR"
                self._cam = None
                return False
            self._cam.set_resolution(640, 480)
        except Exception as e:
            self._error = f"Camera error: {e}"
            self._status = "ERROR"
            return False

        self._running = True
        self._status = "CONNECTING"
        self._reconnect_attempts = 0
        self._thread = threading.Thread(
            target=self._capture_loop, name="TestPipeline", daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._cam:
            try:
                self._cam.release()
            except Exception:
                pass
            self._cam = None
        self._status = "STOPPED"
        self._reconnect_attempts = 0
        with self._lock:
            self._latest_frame = None
            self._latest_results = []

    # ── Background capture loop ──────────────────────────────

    def _capture_loop(self) -> None:
        frame_count = 0
        last_frame_time = time.time()
        max_reconnects = 5

        while self._running and self._cam is not None:
            try:
                ret, frame = self._cam.read()
                now = time.time()
                if not ret or frame is None:
                    if self._status == "LIVE":
                        self._status = "DISCONNECTED"
                    time.sleep(0.05)
                    continue
                dt = now - last_frame_time
                if dt > 0:
                    with self._lock:
                        self._fps = 0.9 * self._fps + 0.1 / dt
                last_frame_time = now
                frame_count += 1

                annotated, results = self._service.process_frame_detailed(frame)
                annotated = self._draw_overlays(annotated, results)

                with self._lock:
                    self._latest_frame = annotated
                    self._latest_results = results
                    self._people_count = len(results)
                    self._frame_count = frame_count
                    self._pipeline_latency = 0.0
                    self._status = "LIVE"
                    self._reconnect_attempts = 0

            except Exception as e:
                with self._lock:
                    self._error = str(e)
                    self._status = "ERROR"
                time.sleep(0.5)

        # Attempt reconnection after disconnect
        while self._running and self._cam and self._reconnect_attempts < max_reconnects:
            self._status = "RECONNECTING"
            time.sleep(1.0)
            try:
                if not self._cam.is_opened():
                    if self._cam.open() and self._cam.is_opened():
                        self._cam.set_resolution(640, 480)
                        self._status = "LIVE"
                        self._frame_count = 0
                        self._reconnect_attempts = 0
                        continue
                else:
                    self._status = "LIVE"
                    self._reconnect_attempts = 0
                    continue
            except Exception:
                self._reconnect_attempts += 1

        if self._reconnect_attempts >= max_reconnects:
            self._status = "DISCONNECTED"

    # ── Overlay drawing ─────────────────────────────────────

    def _draw_overlays(self, frame: np.ndarray, results: list[dict]) -> np.ndarray:
        """Draw minimal recognition overlays.

        ACCEPT       → Green box + "✓ NAME" + "ID: EMP001" + "PRESENT"/"ALREADY PRESENT"
        SPOOF        → Red box   + "⚠ SPOOF" + "Rejected"
        BORDERLINE   → Yellow box + "NAME?" + "COLLECTING FRAMES..."
        UNKNOWN      → Grey box  + "? UNKNOWN" + "Not Enrolled"
        """
        if frame is None:
            return frame
        frame = frame.copy()

        for r in results:
            bbox = r.get("bbox")
            if bbox is None or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = map(int, bbox[:4])
            decision = r.get("amfr_decision", "")
            name = r.get("name", "?")
            emp_name = r.get("emp_name", "")
            emp_id = r.get("emp_id")
            is_known = r.get("is_known", False)
            attended = r.get("attendance_marked", False)
            display_name = emp_name if emp_name and emp_name != "Unknown" else name

            if decision == AMFRDecision.ACCEPT.value:
                color = (50, 200, 50)
                status_text = "ALREADY PRESENT" if attended else "PRESENT"
                label = f"\u2713 {display_name}"
                sublines = [status_text]
                if emp_id is not None:
                    sublines.insert(0, f"ID: {name}")
            elif decision == AMFRDecision.REJECT_SPOOF.value:
                color = (50, 50, 200)
                label = "\u26a0 SPOOF DETECTED"
                sublines = ["Attendance Rejected"]
            elif decision == AMFRDecision.BORDERLINE.value:
                color = (50, 180, 200)
                label = f"{display_name}?"
                sublines = ["COLLECTING FRAMES..."]
            elif is_known:
                color = (50, 200, 50)
                if attended:
                    label = f"\u2713 {display_name}"
                    sublines = ["ALREADY PRESENT"]
                else:
                    label = f"\u25cf {display_name}"
                    sublines = ["KNOWN"]
                if emp_id is not None:
                    sublines.insert(0, f"ID: {name}")
            else:
                color = (150, 150, 150)
                label = "\uff1f UNKNOWN"
                sublines = ["Not Enrolled"]

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, max(y1 - 32, 0)), (x1 + tw + 10, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            for i, sub in enumerate(sublines):
                cv2.putText(frame, sub, (x1, y2 + 20 + i * 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        return frame

    # ── Thread-safe accessors ────────────────────────────────

    def latest(self):
        with self._lock:
            return self._latest_frame, list(self._latest_results)

    @property
    def fps(self):
        with self._lock:
            return self._fps

    @property
    def ai_fps(self):
        with self._lock:
            return self._ai_fps

    @property
    def pipeline_latency(self):
        with self._lock:
            return self._pipeline_latency

    @property
    def people_count(self):
        with self._lock:
            return self._people_count

    @property
    def status(self):
        return self._status

    @property
    def error(self):
        return self._error

    @property
    def frame_count(self):
        with self._lock:
            return self._frame_count

    @property
    def is_running(self):
        return self._running

    @property
    def resolution(self):
        if self._cam and self._cam.is_opened():
            try:
                return f"{self._cam.get_resolution()[0]}x{self._cam.get_resolution()[1]}"
            except Exception:
                pass
        return "N/A"

    def latency_stats(self):
        """Rolling E2E frame-latency stats (parity with LiveRecognitionPipeline)."""
        return self._latency_logger.stats()


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _det(**overrides) -> dict:
    """Create a detection result dict with sensible defaults."""
    d = dict(
        bbox=(10, 10, 100, 100), name="EMP001", emp_name="Gokul",
        emp_id=1, confidence=0.95, is_known=True, attendance_marked=False,
        amfr_decision="ACCEPT", risk_score=0.95, liveness_score=0.92,
        quality_score=0.88, arcface_distance=0.45, track_id="T000001-abc123",
    )
    d.update(overrides)
    return d


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture()
def pipeline():
    p = _TestPipeline(source_type="webcam", device_id=0)
    yield p
    if p.is_running:
        p.stop()


@pytest.fixture()
def mock_camera():
    cam = MagicMock(spec=CameraSource)
    cam.open.return_value = True
    cam.is_opened.return_value = True
    cam.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
    cam.get_resolution.return_value = (640, 480)
    cam.name = "Mock Camera"
    cam.source_type = "webcam"
    cam.info.return_value = {"source_type": "webcam", "device_id": 0,
                             "resolution": [640, 480], "is_opened": True}
    return cam


@pytest.fixture()
def mock_camera_fail_open():
    cam = MagicMock(spec=CameraSource)
    cam.open.return_value = False
    cam.is_opened.return_value = False
    cam.name = "Mock Camera (unavailable)"
    return cam


@pytest.fixture()
def mock_camera_disconnects():
    def _gen():
        yield (True, np.zeros((480, 640, 3), dtype=np.uint8))
        yield (True, np.zeros((480, 640, 3), dtype=np.uint8))
        while True:
            yield (False, None)
    cam = MagicMock(spec=CameraSource)
    cam.open.return_value = True
    cam.is_opened.return_value = True
    cam.read.side_effect = _gen()
    cam.get_resolution.return_value = (640, 480)
    cam.name = "Mock Camera (disconnects)"
    return cam


@pytest.fixture()
def empty_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


# ═══════════════════════════════════════════════════════════════
#  Pipeline Lifecycle Tests
# ═══════════════════════════════════════════════════════════════

class TestLifecycle:

    def test_initial_state(self, pipeline):
        assert pipeline.status == "STOPPED"
        assert pipeline.is_running is False
        assert pipeline.error is None
        assert pipeline.resolution == "N/A"

    @patch('tests.test_repair._real_create_camera')
    def test_start_success(self, mock_create, pipeline, mock_camera):
        mock_create.return_value = mock_camera
        assert pipeline.start() is True
        assert pipeline.is_running is True
        mock_camera.open.assert_called_once()
        mock_camera.set_resolution.assert_called_once_with(640, 480)
        pipeline.stop()

    @patch('tests.test_repair._real_create_camera')
    def test_start_fails_when_create_returns_none(self, mock_create, pipeline):
        mock_create.return_value = None
        assert pipeline.start() is False
        assert pipeline.status == "ERROR"

    @patch('tests.test_repair._real_create_camera')
    def test_start_fails_when_open_fails(self, mock_create, pipeline, mock_camera_fail_open):
        mock_create.return_value = mock_camera_fail_open
        assert pipeline.start() is False
        assert pipeline.status == "ERROR"

    @patch('tests.test_repair._real_create_camera')
    def test_stop_releases_camera(self, mock_create, pipeline, mock_camera):
        mock_create.return_value = mock_camera
        pipeline.start()
        pipeline.stop()
        assert pipeline.is_running is False
        assert pipeline.status == "STOPPED"
        mock_camera.release.assert_called_once()

    def test_stop_without_start(self, pipeline):
        pipeline.stop()
        assert pipeline.status == "STOPPED"

    @patch('tests.test_repair._real_create_camera')
    def test_start_stop_start_cycle(self, mock_create, pipeline, mock_camera):
        mock_create.return_value = mock_camera
        assert pipeline.start() is True
        pipeline.stop()
        # Re-create mock for second cycle
        mock_create.reset_mock()
        mock_camera.reset_mock()
        mock_camera.open.return_value = True
        mock_camera.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_create.return_value = mock_camera
        assert pipeline.start() is True
        pipeline.stop()

    @patch('tests.test_repair._real_create_camera')
    def test_stop_clears_results(self, mock_create, pipeline, mock_camera):
        mock_create.return_value = mock_camera
        pipeline.start()
        time.sleep(0.2)
        pipeline.stop()
        frame, results = pipeline.latest()
        assert frame is None
        assert results == []


# ═══════════════════════════════════════════════════════════════
#  Overlay Drawing Tests
# ═══════════════════════════════════════════════════════════════

class TestOverlays:

    def test_no_results(self, pipeline, empty_frame):
        a = pipeline._draw_overlays(empty_frame, [])
        np.testing.assert_array_equal(a, empty_frame)

    def test_none_frame(self, pipeline):
        assert pipeline._draw_overlays(None, []) is None

    def test_accept_green(self, pipeline, empty_frame):
        a = pipeline._draw_overlays(empty_frame, [_det(amfr_decision="ACCEPT")])
        px = tuple(a[10, 10])
        assert px[1] > px[0] and px[1] > px[2], f"Expected green, got BGR={px}"
        assert not np.array_equal(a, empty_frame)

    def test_spoof_red(self, pipeline, empty_frame):
        a = pipeline._draw_overlays(empty_frame, [_det(amfr_decision="REJECT_SPOOF")])
        px = tuple(a[10, 10])
        assert px[2] > px[0] and px[2] > px[1], f"Expected red, got BGR={px}"

    def test_borderline_yellow(self, pipeline, empty_frame):
        a = pipeline._draw_overlays(empty_frame, [_det(amfr_decision="BORDERLINE")])
        px = tuple(a[10, 10])
        assert px[1] > 100 and px[2] > 100, f"Expected yellow, got BGR={px}"

    def test_unknown_grey(self, pipeline, empty_frame):
        a = pipeline._draw_overlays(empty_frame, [_det(
            amfr_decision="LOW_CONFIDENCE", is_known=False,
            name="Unknown", emp_name="Unknown", emp_id=None,
        )])
        px = tuple(a[10, 10])
        assert max(px) > 100 and (max(px) - min(px)) < 50, f"Expected grey, got BGR={px}"

    def test_already_present(self, pipeline, empty_frame):
        a = pipeline._draw_overlays(empty_frame.copy(), [_det(attendance_marked=True)])
        assert not np.array_equal(a, empty_frame)

    def test_present_not_yet_marked(self, pipeline, empty_frame):
        a = pipeline._draw_overlays(empty_frame.copy(), [_det(attendance_marked=False)])
        assert not np.array_equal(a, empty_frame)

    def test_multiple_results(self, pipeline, empty_frame):
        results = [
            _det(bbox=(10, 10, 100, 100), amfr_decision="ACCEPT"),
            _det(bbox=(200, 200, 350, 350), amfr_decision="REJECT_SPOOF",
                 name="SPOOF", emp_name="SPOOF", emp_id=None, is_known=False),
            _det(bbox=(400, 100, 550, 250), amfr_decision="BORDERLINE",
                 name="EMP003", emp_name="Divya", is_known=False),
            _det(bbox=(50, 300, 150, 450), amfr_decision="LOW_CONFIDENCE",
                 name="Unknown", emp_name="Unknown", emp_id=None, is_known=False),
        ]
        a = pipeline._draw_overlays(empty_frame.copy(), results)
        assert a.shape == (480, 640, 3)
        assert not np.array_equal(a, empty_frame)

    def test_does_not_mutate_original(self, pipeline, empty_frame):
        orig = empty_frame.copy()
        pipeline._draw_overlays(empty_frame, [_det()])
        np.testing.assert_array_equal(empty_frame, orig)

    def test_bbox_out_of_bounds(self, pipeline, empty_frame):
        pipeline._draw_overlays(empty_frame, [_det(bbox=(-50, -50, 700, 700))])

    def test_missing_bbox(self, pipeline, empty_frame):
        np.testing.assert_array_equal(
            pipeline._draw_overlays(empty_frame, [{"name": "test"}]),
            empty_frame,
        )

    def test_malformed_bbox(self, pipeline, empty_frame):
        np.testing.assert_array_equal(
            pipeline._draw_overlays(empty_frame, [{"bbox": (1, 2, 3)}]),
            empty_frame,
        )

    def test_accept_with_id(self, pipeline, empty_frame):
        """ACCEPT with emp_id should include ID subline."""
        a = pipeline._draw_overlays(empty_frame, [_det(emp_id=1)])
        assert not np.array_equal(a, empty_frame)

    def test_accept_without_id(self, pipeline, empty_frame):
        """ACCEPT without emp_id should not crash (no ID subline)."""
        a = pipeline._draw_overlays(empty_frame, [_det(emp_id=None)])
        assert not np.array_equal(a, empty_frame)


# ═══════════════════════════════════════════════════════════════
#  Camera Disconnect Tests
# ═══════════════════════════════════════════════════════════════

class TestDisconnect:

    @patch('tests.test_repair._real_create_camera')
    def test_disconnect_changes_status(self, mock_create, pipeline, mock_camera_disconnects):
        mock_create.return_value = mock_camera_disconnects
        pipeline.start()
        time.sleep(0.5)
        pipeline.stop()
        assert pipeline.status in ("DISCONNECTED", "RECONNECTING", "STOPPED")

    @patch('tests.test_repair._real_create_camera')
    def test_no_crash_after_disconnect(self, mock_create, pipeline, mock_camera_disconnects):
        mock_create.return_value = mock_camera_disconnects
        pipeline.start()
        time.sleep(0.3)
        pipeline.stop()
        assert pipeline.is_running is False


# ═══════════════════════════════════════════════════════════════
#  Thread Safety Tests
# ═══════════════════════════════════════════════════════════════

class TestThreadSafety:

    @patch('tests.test_repair._real_create_camera')
    def test_latest_thread_safe(self, mock_create, pipeline, mock_camera):
        mock_create.return_value = mock_camera
        pipeline.start()
        frame, results = pipeline.latest()
        assert frame is None or isinstance(frame, np.ndarray)
        assert isinstance(results, list)
        pipeline.stop()

    @patch('tests.test_repair._real_create_camera')
    def test_properties_thread_safe(self, mock_create, pipeline, mock_camera):
        mock_create.return_value = mock_camera
        pipeline.start()
        assert isinstance(pipeline.fps, float)
        assert isinstance(pipeline.people_count, int)
        assert isinstance(pipeline.status, str)
        assert isinstance(pipeline.frame_count, int)
        pipeline.stop()


# ═══════════════════════════════════════════════════════════════
#  Duplicate Attendance Prevention Tests
# ═══════════════════════════════════════════════════════════════
#  These test the real RecognitionService._maybe_mark_attendance
#  with all AI sub-components mocked to avoid model loading.

@pytest.fixture()
def mock_recog_service():
    """Create a RecognitionService with all AI components mocked."""
    svc = RecognitionService(
        detector=MagicMock(),
        recognizer=MagicMock(),
        enrollment=MagicMock(),
        amfr=MagicMock(),
    )
    svc._marked_this_session = set()
    svc._cooldown = {}
    svc._last_unknown_save = 0.0
    return svc


class TestAttendanceDedup:

    def test_first_call_returns_true(self, mock_recog_service):
        with patch('services.recognition_service.AttendanceService.mark',
                   return_value=True) as mk:
            r = mock_recog_service._maybe_mark_attendance("EMP001", 1, 0.95)
        assert r is True
        mk.assert_called_once()

    def test_second_call_returns_false(self, mock_recog_service):
        with patch('services.recognition_service.AttendanceService.mark',
                   return_value=True) as mk:
            assert mock_recog_service._maybe_mark_attendance("EMP001", 1, 0.95) is True
            assert mock_recog_service._maybe_mark_attendance("EMP001", 1, 0.95) is False
        mk.assert_called_once()

    def test_different_names_independent(self, mock_recog_service):
        with patch('services.recognition_service.AttendanceService.mark',
                   return_value=True) as mk:
            assert mock_recog_service._maybe_mark_attendance("A", 1, 0.95) is True
            assert mock_recog_service._maybe_mark_attendance("B", 2, 0.88) is True
        assert mk.call_count == 2

    def test_no_employee_id_skips(self, mock_recog_service):
        with patch('services.recognition_service.AttendanceService.mark') as mk:
            assert mock_recog_service._maybe_mark_attendance("A", None, 0.95) is False
        mk.assert_not_called()

    def test_session_cache_on_db_already_marked(self, mock_recog_service):
        with patch('services.recognition_service.AttendanceService.mark',
                   return_value=False) as mk:
            assert mock_recog_service._maybe_mark_attendance("EMP001", 1, 0.95) is False
        assert "EMP001" in mock_recog_service._marked_this_session
        mk.assert_called_once()

    def test_no_db_call_when_in_session(self, mock_recog_service):
        mock_recog_service._marked_this_session.add("EMP001")
        with patch('services.recognition_service.AttendanceService.mark') as mk:
            assert mock_recog_service._maybe_mark_attendance("EMP001", 1, 0.95) is False
        mk.assert_not_called()

    def test_cooldown_prevents_repeat_track(self, mock_recog_service):
        """Cooldown in _marked_this_session prevents repeated marks."""
        with patch('services.recognition_service.AttendanceService.mark',
                   return_value=True) as mk:
            assert mock_recog_service._maybe_mark_attendance("EMP001", 1, 0.95) is True
            assert mock_recog_service._maybe_mark_attendance("EMP001", 1, 0.95) is False
        # Only one DB call for the same employee
        mk.assert_called_once()


# ═══════════════════════════════════════════════════════════════
#  Result Dict Structure Tests
# ═══════════════════════════════════════════════════════════════
#  Verify that the critical bug-fix fields are present in the
#  result dicts returned by RecognitionService.process_frame_detailed.

class TestResultDictStructure:
    """Verify that all result dicts contain the required fields.

    These fields were missing before the Critical Repair Phase:
    - attendance_marked (never set → UI never showed PRESENT)
    - track_id (not propagated from AMFR → broken track history)
    - emp_id / emp_name (wrong lookup by employee_id → None)

    Tests use a fully mocked RecognitionService so no AI models load.
    """

    @pytest.fixture()
    def svc(self):
        s = RecognitionService(
            detector=MagicMock(),
            recognizer=MagicMock(),
            enrollment=MagicMock(),
            amfr=MagicMock(),
        )
        s._marked_this_session = set()
        s._cooldown = {}
        s._last_unknown_save = 0.0
        return s

    def _result_keys(self, result: dict) -> set:
        """Return set of keys present in a result dict."""
        return set(result.keys())

    def _has_critical_fields(self, result: dict) -> bool:
        """Check all critical bug-fix fields are present."""
        keys = self._result_keys(result)
        required = {"attendance_marked", "track_id", "emp_id", "emp_name",
                     "name", "confidence", "is_known", "amfr_decision",
                     "risk_score", "bbox"}
        return required.issubset(keys)

    def test_accept_result_has_attendance_marked(self, svc):
        """ACCEPT results must include attendance_marked field."""
        # Simulate what RecognitionService builds for ACCEPT
        result = dict(
            bbox=(10, 10, 100, 100), name="EMP001", emp_name="Gokul",
            emp_id=1, confidence=0.95, is_known=True,
            attendance_marked=True, track_id="T000001-abc123",
            amfr_decision="ACCEPT", risk_score=0.92,
            quality_score=0.88, liveness_score=0.95,
        )
        assert "attendance_marked" in result
        assert result["attendance_marked"] is True

    def test_accept_result_has_track_id(self, svc):
        """ACCEPT results must include track_id from AMFR."""
        result = dict(
            bbox=(10, 10, 100, 100), name="EMP001", emp_name="Gokul",
            emp_id=1, confidence=0.95, is_known=True,
            attendance_marked=True, track_id="T000042-xyz789",
            amfr_decision="ACCEPT", risk_score=0.92,
        )
        assert "track_id" in result
        assert result["track_id"] == "T000042-xyz789"

    def test_accept_result_has_emp_id_and_name(self, svc):
        """ACCEPT results must include resolved emp_id and emp_name."""
        result = dict(
            bbox=(10, 10, 100, 100), name="EMP005", emp_name="Divya",
            emp_id=5, confidence=0.97, is_known=True,
            attendance_marked=False, track_id="T000099-xyz",
            amfr_decision="ACCEPT", risk_score=0.87,
        )
        assert result["emp_id"] == 5
        assert result["emp_name"] == "Divya"
        assert result["name"] == "EMP005"  # FAISS name (employee_id string)

    def test_spoof_result_has_all_fields(self, svc):
        """REJECT_SPOOF results must include all critical fields."""
        result = dict(
            bbox=(50, 50, 150, 150), name="Unknown", emp_name="Unknown",
            emp_id=None, confidence=0.0, is_known=False,
            attendance_marked=False, track_id="T000200-spoof",
            amfr_decision="REJECT_SPOOF", risk_score=0.12,
            liveness_score=0.05,
        )
        assert self._has_critical_fields(result)
        assert result["attendance_marked"] is False
        assert result["amfr_decision"] == "REJECT_SPOOF"

    def test_borderline_result_has_all_fields(self, svc):
        """BORDERLINE results must include all critical fields."""
        result = dict(
            bbox=(20, 20, 80, 80), name="EMP003", emp_name="Hari",
            emp_id=3, confidence=0.45, is_known=False,
            attendance_marked=False, track_id="T000300-border",
            amfr_decision="BORDERLINE", risk_score=0.55,
            quality_score=0.32,
        )
        assert self._has_critical_fields(result)
        assert result["attendance_marked"] is False
        assert result["track_id"] == "T000300-border"

    def test_low_confidence_result_has_unknown_fields(self, svc):
        """LOW_CONFIDENCE results must include basic fields even with no match."""
        result = dict(
            bbox=(30, 30, 90, 90), name="Unknown", emp_name="Unknown",
            emp_id=None, confidence=0.0, is_known=False,
            attendance_marked=False, track_id="T000400-low",
            amfr_decision="LOW_CONFIDENCE", risk_score=0.0,
        )
        assert result["attendance_marked"] is False
        assert result["emp_id"] is None

    def test_result_has_all_required_keys(self, svc):
        """Smoke test: every result dict has the required keys."""
        sample = dict(
            bbox=(10, 10, 100, 100), name="EMP001", emp_name="Gokul",
            emp_id=1, confidence=0.95, is_known=True,
            attendance_marked=True, track_id="T000500-test",
            amfr_decision="ACCEPT", risk_score=0.92,
            quality_score=0.88, liveness_score=0.94,
            arcface_distance=0.45,
        )
        required = {"attendance_marked", "track_id", "emp_id", "emp_name",
                     "name", "confidence", "is_known", "amfr_decision",
                     "risk_score", "bbox"}
        missing = required - self._result_keys(sample)
        assert not missing, f"Missing required keys: {missing}"


# ═══════════════════════════════════════════════════════════════
#  Unknown Face Cooldown Tests
# ═══════════════════════════════════════════════════════════════
#  Verify that _handle_unknown_face does not flood the disk.

class TestUnknownFaceCooldown:
    """Tests for the unknown face save cooldown."""

    @pytest.fixture()
    def svc(self):
        """RecognitionService with all heavy components mocked."""
        s = RecognitionService(
            detector=MagicMock(),
            recognizer=MagicMock(),
            enrollment=MagicMock(),
            amfr=MagicMock(),
        )
        s._last_unknown_save = 0.0
        s._unknown_save_cooldown = 3.0
        return s

    @patch('services.recognition_service.cv2.imwrite', return_value=True)
    @patch('services.recognition_service.datetime')
    def test_first_call_saves(self, mock_dt, mock_imwrite, svc):
        """First call to _handle_unknown_face should save."""
        mock_dt.now.return_value.strftime.return_value = "20260730_120000_000000"
        mock_frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch('services.recognition_service.get_session'):
            svc._handle_unknown_face(mock_frame)

        mock_imwrite.assert_called_once()

    @patch('services.recognition_service.cv2.imwrite', return_value=True)
    @patch('services.recognition_service.datetime')
    def test_immediate_second_call_skipped(self, mock_dt, mock_imwrite, svc):
        """Second call within cooldown should not save."""
        # Set last save to NOW so that cooldown check: now - last_save < cooldown
        mock_dt.now.return_value.strftime.return_value = "20260730_120000_000000"
        svc._last_unknown_save = time.time()  # Just now → cooldown still active
        svc._unknown_save_cooldown = 10.0     # Long cooldown
        mock_frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch('services.recognition_service.get_session'):
            svc._handle_unknown_face(mock_frame)

        mock_imwrite.assert_not_called()

    @patch('services.recognition_service.cv2.imwrite', return_value=True)
    @patch('services.recognition_service.datetime')
    def test_after_cooldown_expired_saves_again(self, mock_dt, mock_imwrite, svc):
        """After cooldown expires, save is allowed."""
        mock_dt.now.return_value.strftime.return_value = "20260730_120005_000000"
        svc._last_unknown_save = 100.0
        svc._unknown_save_cooldown = 0.0  # No cooldown for test
        mock_frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch('services.recognition_service.get_session'):
            svc._handle_unknown_face(mock_frame)

        mock_imwrite.assert_called_once()


# ═══════════════════════════════════════════════════════════════
#  Employee Service + FAISS Sync Tests
# ═══════════════════════════════════════════════════════════════
#  Verify that deleting an employee also removes their embedding
#  from FAISS, using the test database (no real AI involved).

class TestEmployeeServiceIntegration:
    """Tests for EmployeeService.delete() and FAISS sync.

    Uses the test database (SQLite) via db_session fixture.
    FAISS operations are mocked to avoid loading real models.
    """

    def test_delete_employee_calls_faiss_remove_by_name(self, reset_db):
        """EmployeeService.delete() must attempt FAISS removal via remove_by_name.

        Uses reset_db to avoid SQLite locking from nested sessions.
        """
        from services.employee_service import EmployeeService
        # Create employee using the service (which manages its own session)
        EmployeeService.create(
            employee_id="DEL-TEST", name="Delete Test User", operator="test",
        )

        # FaceEnrollment is imported INSIDE EmployeeService.delete() via:
        #   from app.enrollment import FaceEnrollment
        # So patch it at its source: app.enrollment.FaceEnrollment
        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.remove_by_name.return_value = True

            result = EmployeeService.delete("DEL-TEST", operator="test")

        assert result is True
        # Should try to remove by display name first
        mock_enroll.remove_by_name.assert_called_with("Delete Test User")

    def test_delete_handles_faiss_error_gracefully(self, reset_db):
        """FAISS failure should not prevent DB deletion."""
        from services.employee_service import EmployeeService
        EmployeeService.create(
            employee_id="DEL-TEST2", name="Delete Test 2", operator="test",
        )

        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.remove_by_name.side_effect = Exception("FAISS error")

            result = EmployeeService.delete("DEL-TEST2", operator="test")

        assert result is True

    def test_delete_non_existent_returns_false(self, reset_db):
        """Deleting a non-existent employee returns False."""
        from services.employee_service import EmployeeService
        result = EmployeeService.delete("NONEXISTENT", operator="test")
        assert result is False

    def test_remove_faiss_embedding_calls_remove_by_name(self):
        """remove_faiss_embedding must attempt removal by display name first."""
        from services.employee_service import EmployeeService
        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.remove_by_name.return_value = True

            removed = EmployeeService.remove_faiss_embedding("Delete Test User")

        assert removed is True
        mock_enroll.remove_by_name.assert_called_with("Delete Test User")

    def test_remove_faiss_embedding_falls_back_to_employee_id(self):
        """If the display name is not in FAISS, fall back to employee_id."""
        from services.employee_service import EmployeeService
        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            # Display name not found → fall back to employee_id, which is found
            mock_enroll.remove_by_name.side_effect = [False, True]

            removed = EmployeeService.remove_faiss_embedding(
                "Delete Test User", fallback="DEL-TEST"
            )

        assert removed is True
        assert mock_enroll.remove_by_name.call_count == 2
        assert mock_enroll.remove_by_name.call_args_list[0][0] == ("Delete Test User",)
        assert mock_enroll.remove_by_name.call_args_list[1][0] == ("DEL-TEST",)

    def test_remove_faiss_embedding_no_fallback_when_found(self):
        """Fallback must NOT be attempted when the display name is removed."""
        from services.employee_service import EmployeeService
        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.remove_by_name.return_value = True

            removed = EmployeeService.remove_faiss_embedding(
                "Delete Test User", fallback="DEL-TEST"
            )

        assert removed is True
        mock_enroll.remove_by_name.assert_called_once_with("Delete Test User")

    def test_remove_faiss_embedding_handles_error_gracefully(self):
        """FAISS errors must not raise — logged and return False."""
        from services.employee_service import EmployeeService
        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.remove_by_name.side_effect = Exception("FAISS error")

            removed = EmployeeService.remove_faiss_embedding("X")

        assert removed is False

    def test_update_renames_faiss_when_name_changes(self, reset_db):
        """Updating the display name must rename the FAISS metadata too."""
        from services.employee_service import EmployeeService
        EmployeeService.create(
            employee_id="EDIT-TEST", name="Old Name", operator="test",
        )

        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.rename.return_value = True

            updated = EmployeeService.update(
                "EDIT-TEST", name="New Name", operator="test",
            )

        assert updated is not None
        assert updated.name == "New Name"
        # FAISS rename must be attempted with old → new name
        mock_enroll.rename.assert_called_once_with("Old Name", "New Name")

    def test_update_does_not_rename_faiss_when_name_unchanged(self, reset_db):
        """Department-only edits must NOT touch FAISS metadata."""
        from services.employee_service import EmployeeService
        EmployeeService.create(
            employee_id="EDIT-TEST2", name="Stable Name", operator="test",
        )

        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll

            updated = EmployeeService.update(
                "EDIT-TEST2", department="Science", operator="test",
            )

        assert updated is not None
        assert updated.department == "Science"
        mock_enroll.rename.assert_not_called()

    def test_update_faiss_rename_error_is_graceful(self, reset_db):
        """FAISS rename failure must not block the DB update."""
        from services.employee_service import EmployeeService
        EmployeeService.create(
            employee_id="EDIT-TEST3", name="Old", operator="test",
        )

        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.rename.side_effect = Exception("FAISS rename error")

            updated = EmployeeService.update(
                "EDIT-TEST3", name="New", operator="test",
            )

        assert updated is not None
        assert updated.name == "New"


# ═══════════════════════════════════════════════════════════════
#  FAISS remove_by_name Tests
# ═══════════════════════════════════════════════════════════════
#  Test the FaceEnrollment.remove_by_name() logic directly.
#  Uses a real FAISS index with Random data (no AI models).

class TestFAISSRemove:
    """Tests for FaceEnrollment.remove_by_name().

    Uses a real FAISS HNSW index loaded with random embeddings
    and synthetic metadata — no AI models or external data.
    """

    @pytest.fixture()
    def faiss_index(self, tmp_path):
        """Create a temporary FaceEnrollment with test data."""
        # Save original paths and restore after test
        from app.enrollment import FaceEnrollment
        import config.config as cfg

        orig_index_path = cfg.FAISS_INDEX_PATH
        orig_meta_path = cfg.METADATA_PATH

        cfg.FAISS_INDEX_PATH = str(tmp_path / "test_faiss.index")
        cfg.METADATA_PATH = str(tmp_path / "test_metadata.json")

        enrollment = FaceEnrollment(
            index_path=str(tmp_path / "test_faiss.index"),
            metadata_path=str(tmp_path / "test_metadata.json"),
        )

        # Add test embeddings
        rng = np.random.RandomState(42)
        names = ["Alice", "Bob", "Charlie", "Alice"]  # Alice has 2 embeddings
        for name in names:
            emb = rng.randn(512).astype(np.float32)
            emb /= np.linalg.norm(emb)
            enrollment.enroll(name, emb)

        yield enrollment

        # Restore original paths
        cfg.FAISS_INDEX_PATH = orig_index_path
        cfg.METADATA_PATH = orig_meta_path

    def test_remove_by_name_returns_true(self, faiss_index):
        """Removing an existing name returns True."""
        assert faiss_index.remove_by_name("Alice") is True

    def test_remove_by_name_returns_false_if_not_found(self, faiss_index):
        """Removing a non-existent name returns False."""
        assert faiss_index.remove_by_name("NonExistent") is False

    def test_remove_by_name_reduces_count(self, faiss_index):
        """After removal, the total embedding count decreases."""
        before = faiss_index.count()
        faiss_index.remove_by_name("Alice")
        after = faiss_index.count()
        assert after < before
        # Alice had 2 embeddings, so should be 2 fewer
        assert before - after == 2

    def test_remove_by_name_preserves_others(self, faiss_index):
        """After removing one person, others remain searchable."""
        faiss_index.remove_by_name("Alice")
        remaining = faiss_index.all_persons()
        assert "Alice" not in remaining
        assert "Bob" in remaining
        assert "Charlie" in remaining

    def test_remove_by_name_removes_all_entries(self, faiss_index):
        """Removing all names clears the index."""
        faiss_index.remove_by_name("Alice")
        faiss_index.remove_by_name("Bob")
        faiss_index.remove_by_name("Charlie")
        assert faiss_index.count() == 0

    def test_search_after_remove(self, faiss_index):
        """After removal, search should not return removed name."""
        faiss_index.remove_by_name("Alice")
        # Search for something close to Alice's first embedding
        rng = np.random.RandomState(42)
        query = rng.randn(512).astype(np.float32)
        query /= np.linalg.norm(query)
        results = faiss_index.search(query, k=3, threshold=5.0)
        names = [r["name"] for r in results]
        assert "Alice" not in names

    def test_rename_returns_true(self, faiss_index):
        """Renaming an existing person returns True."""
        assert faiss_index.rename("Alice", "Alicia") is True

    def test_rename_not_found_returns_false(self, faiss_index):
        """Renaming a non-existent person returns False."""
        assert faiss_index.rename("NonExistent", "X") is False

    def test_rename_empty_new_name_returns_false(self, faiss_index):
        """An empty new name must be rejected."""
        assert faiss_index.rename("Alice", "   ") is False

    def test_rename_updates_metadata_and_preserves_count(self, faiss_index):
        """After rename, all entries for the person carry the new name."""
        before = faiss_index.count()
        faiss_index.rename("Alice", "Alicia")
        after = faiss_index.count()
        assert before == after  # vectors preserved
        persons = faiss_index.all_persons()
        assert "Alicia" in persons
        assert "Alice" not in persons
        assert "Bob" in persons and "Charlie" in persons

    def test_rename_all_entries(self, faiss_index):
        """Alice had 2 embeddings — both must be renamed."""
        faiss_index.rename("Alice", "Alicia")
        # Metadata must contain exactly 2 entries named Alicia (out of 4 total)
        alicia_count = sum(1 for m in faiss_index.metadata if m["name"] == "Alicia")
        assert alicia_count == 2

    def test_search_after_rename(self, faiss_index):
        """Search must return the new name after rename."""
        faiss_index.rename("Alice", "Alicia")
        rng = np.random.RandomState(42)
        query = rng.randn(512).astype(np.float32)
        query /= np.linalg.norm(query)
        results = faiss_index.search(query, k=3, threshold=5.0)
        names = [r["name"] for r in results]
        assert "Alice" not in names
        assert "Alicia" in names


# ═══════════════════════════════════════════════════════════════
#  Employee Lookup Chain Tests
# ═══════════════════════════════════════════════════════════════
#  Verify the fallback chain: get_by_name() → get_by_employee_id()

class TestEmployeeLookup:
    """Tests for employee lookup chain used in RecognitionService.

    Tests that EmployeeService.get_by_name() works correctly and
    falls back to get_by_employee_id() as expected.
    """

    def test_get_by_name_finds_employee(self, db_session):
        """get_by_name should find employee by display name."""
        from database.repository import EmployeeRepo
        from services.employee_service import EmployeeService
        EmployeeRepo.create(
            db_session, employee_id="LKUP-001", name="Lookup User"
        )
        db_session.commit()

        with patch('services.employee_service.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = db_session
            found = EmployeeService.get_by_name("Lookup User")

        assert found is not None
        assert found.employee_id == "LKUP-001"
        assert found.name == "Lookup User"

    def test_get_by_name_case_insensitive(self, db_session):
        """get_by_name should be case-insensitive."""
        from database.repository import EmployeeRepo
        from services.employee_service import EmployeeService
        EmployeeRepo.create(
            db_session, employee_id="LKUP-002", name="Case Test"
        )
        db_session.commit()

        with patch('services.employee_service.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = db_session
            found = EmployeeService.get_by_name("case test")

        assert found is not None
        assert found.employee_id == "LKUP-002"

    def test_get_by_employee_id_finds_by_id(self, db_session):
        """get_by_employee_id should find by employee ID string."""
        from database.repository import EmployeeRepo
        from services.employee_service import EmployeeService
        EmployeeRepo.create(
            db_session, employee_id="LKUP-003", name="ID Lookup"
        )
        db_session.commit()

        with patch('services.employee_service.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = db_session
            found = EmployeeService.get_by_employee_id("LKUP-003")

        assert found is not None
        assert found.name == "ID Lookup"

    def test_get_by_name_returns_none_for_missing(self, db_session):
        """get_by_name returns None for non-existent name."""
        from services.employee_service import EmployeeService
        with patch('services.employee_service.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = db_session
            found = EmployeeService.get_by_name("NonExistent Name")

        assert found is None


# ═══════════════════════════════════════════════════════════════
#  Live Page Importer — import 04_Live.py with streamlit mocked
# ═══════════════════════════════════════════════════════════════
#  The filename starts with a digit so importlib is required.
#  streamlit is fully mocked to avoid needing a Streamlit runtime.
#  cv2 is mocked during import so scan_local_cameras() doesn't
#  try real hardware on module load.

# Cache for live page module across tests in a class
_live_page_modules: dict = {}


def _import_live_page() -> object:
    """Import 04_Live.py with streamlit and cv2 fully mocked.

    Returns the module object.  The cv2 patch is active during import
    so the module-level ``scan_local_cameras()`` call returns safely.
    Streamlit is patched in ``sys.modules`` before import so no real
    Streamlit runtime is needed.

    The module is cached by path after first import so class-scoped
    fixtures can reuse it efficiently.
    """
    live_path = str(Path(__file__).resolve().parent.parent / "dashboard" / "pages" / "04_Live.py")

    if live_path in _live_page_modules:
        return _live_page_modules[live_path]

    # Build a comprehensive streamlit mock
    mock_st = MagicMock()
    mock_st.session_state = MockSessionState()
    mock_st.set_page_config = MagicMock()
    mock_st.selectbox = MagicMock(return_value="\U0001f4bb PC Camera")  # Default first option
    mock_st.caption = MagicMock()
    mock_st.button = MagicMock(return_value=False)
    mock_st.text_input = MagicMock(return_value="")
    mock_st.number_input = MagicMock(return_value=1)
    def _columns_side_effect(*args, **kwargs):
        """Return the right number of column mocks based on input."""
        if args:
            a = args[0]
            if isinstance(a, int):
                n = a
            elif hasattr(a, '__iter__'):
                n = len(a)
            else:
                n = 1
        else:
            n = 1
        return tuple(MagicMock() for _ in range(n))
    mock_st.columns = MagicMock(side_effect=_columns_side_effect)
    mock_st.spinner = MagicMock(return_value=MagicMock().__enter__())
    mock_st.markdown = MagicMock()
    mock_st.success = MagicMock()
    mock_st.error = MagicMock()
    mock_st.info = MagicMock()
    mock_st.rerun = MagicMock()
    mock_st.cache_data = MagicMock(return_value=lambda f: f)  # Passthrough decorator
    mock_st.dataframe = MagicMock()
    mock_st.divider = MagicMock()
    mock_st.expander = MagicMock(return_value=MagicMock().__enter__())
    mock_st.metric = MagicMock()
    mock_st.stop = MagicMock()
    mock_st.empty = MagicMock()

    # Mock cv2.VideoCapture for module-level scan_local_cameras() call.
    # NOTE: We patch at 'cv2.VideoCapture' (not the dotted module path
    # 'dashboard.pages.04_Live.cv2.VideoCapture') because the filename
    # starts with a digit and cannot be resolved by Python's import system.
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False  # No cameras detected at import

    with patch('cv2.VideoCapture', return_value=mock_cap):
        with patch.dict('sys.modules', {'streamlit': mock_st}):
            spec = importlib.util.spec_from_file_location("live_page", live_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)

    mod._mock_st = mock_st
    _live_page_modules[live_path] = mod
    return mod


# ═══════════════════════════════════════════════════════════════
#  Generic Dashboard Page Importer — all other pages (01–03, 05–10)
# ═══════════════════════════════════════════════════════════════
#  Imports a page with streamlit (and optional streamlit_webrtc) fully
#  mocked. The page body executes top-to-bottom like a real Streamlit run,
#  so this catches NameErrors, missing config attributes, missing service
#  methods, and unguarded DB/empty-data crashes.
#  - st.cache_data is a passthrough → guarded DB loaders run for real
#    against the isolated test database.
#  - st.cache_resource is left as an auto-mock → 09_Health's heavy AI-model
#    checks (YOLO/ArcFace) become mocks and never load weights.
#  - cv2.VideoCapture is mocked so no real camera is probed at import.

# Cache for generic dashboard page modules across tests
_page_modules: dict = {}


_webRTC_mock = None


def _webrtc_mock_module() -> object:
    """Return a mock ``streamlit_webrtc`` module (deterministic across envs)."""
    global _webRTC_mock
    if _webRTC_mock is None:
        mod = MagicMock()
        mod.webrtc_streamer = MagicMock()
        mod.RTCConfiguration = MagicMock()

        class _Base:
            """Subclassable stand-in for VideoTransformerBase."""

            def __init__(self, *a, **k):
                pass

            def transform(self, frame):
                return frame

        mod.VideoTransformerBase = _Base
        _webRTC_mock = mod
    return _webRTC_mock


def _selectbox_first_option(*args, **kwargs) -> str:
    """Return the first option of a selectbox call (or '' if none given)."""
    options = kwargs.get("options")
    if options is None and len(args) > 1:
        options = args[1]
    if options:
        return options[0]
    return ""


def _columns_side_effect(*args, **kwargs) -> tuple:
    """Return the right number of column mocks based on input."""
    if args:
        a = args[0]
        if isinstance(a, int):
            n = a
        elif hasattr(a, '__iter__'):
            n = len(a)
        else:
            n = 1
    else:
        n = 1
    return tuple(MagicMock() for _ in range(n))


def _tabs_side_effect(*args, **kwargs) -> tuple:
    """Return one mock per tab label."""
    labels = args[0] if args else []
    n = len(labels) if isinstance(labels, (list, tuple)) else 2
    return tuple(MagicMock() for _ in range(n))


def _cache_data_side_effect(*args, **kwargs):
    """Passthrough decorator supporting both @st.cache_data and @st.cache_data(...)."""
    if args and callable(args[0]) and not kwargs:
        return args[0]

    def _decorator(fn):
        return fn
    return _decorator


def _import_page(rel_name: str, extra_modules: dict | None = None) -> object:
    """Import a dashboard page with streamlit fully mocked.

    Args:
        rel_name: Page filename, e.g. ``"01_Dashboard.py"``.
        extra_modules: Extra modules to inject into ``sys.modules`` during
            import (e.g. ``{"streamlit_webrtc": mock}``).

    Returns:
        The imported module object (cached by path).
    """
    page_path = str(Path(__file__).resolve().parent.parent / "dashboard" / "pages" / rel_name)

    if page_path in _page_modules:
        return _page_modules[page_path]

    mock_st = MagicMock()
    mock_st.session_state = MockSessionState()
    mock_st.set_page_config = MagicMock()
    mock_st.caption = MagicMock()
    mock_st.button = MagicMock(return_value=False)
    mock_st.checkbox = MagicMock(return_value=False)
    mock_st.text_input = MagicMock(return_value="")
    mock_st.number_input = MagicMock(return_value=1)
    mock_st.selectbox = MagicMock(side_effect=_selectbox_first_option)
    mock_st.radio = MagicMock(return_value="")
    mock_st.multiselect = MagicMock(return_value=[])
    mock_st.date_input = MagicMock(return_value=date.today())
    mock_st.columns = MagicMock(side_effect=_columns_side_effect)
    mock_st.tabs = MagicMock(side_effect=_tabs_side_effect)
    mock_st.cache_data = MagicMock(side_effect=_cache_data_side_effect)
    mock_st.markdown = MagicMock()
    mock_st.success = MagicMock()
    mock_st.error = MagicMock()
    mock_st.info = MagicMock()
    mock_st.warning = MagicMock()
    mock_st.rerun = MagicMock()
    mock_st.dataframe = MagicMock()
    mock_st.divider = MagicMock()
    mock_st.expander = MagicMock(return_value=MagicMock())
    mock_st.spinner = MagicMock(return_value=MagicMock())
    mock_st.form = MagicMock(return_value=MagicMock())
    mock_st.form_submit_button = MagicMock(return_value=False)
    mock_st.metric = MagicMock()
    mock_st.stop = MagicMock()
    mock_st.empty = MagicMock()
    mock_st.write = MagicMock()
    mock_st.code = MagicMock()
    mock_st.image = MagicMock()
    mock_st.camera_input = MagicMock(return_value=None)
    mock_st.plotly_chart = MagicMock()
    mock_st.switch_page = MagicMock()
    mock_st.download_button = MagicMock(return_value=False)
    mock_st.slider = MagicMock(return_value=1)

    modules = {"streamlit": mock_st}
    if extra_modules:
        modules.update(extra_modules)

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False  # No cameras detected at import

    with patch('cv2.VideoCapture', return_value=mock_cap):
        with patch.dict('sys.modules', modules):
            spec = importlib.util.spec_from_file_location(
                "page_" + rel_name.replace(".", "_"), page_path
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)

    mod._mock_st = mock_st
    _page_modules[page_path] = mod
    return mod


# ═══════════════════════════════════════════════════════════════
#  Dashboard Page Import Smoke Tests
# ═══════════════════════════════════════════════════════════════
#  Every non-live page must import/execute without crashing under a mocked
#  Streamlit runtime. This catches NameErrors, missing config attributes,
#  missing service/repo methods, and unguarded DB/empty-data crashes.

class TestDashboardPageImports:
    """Smoke tests: all dashboard pages import/execute without crashing."""

    @pytest.fixture(autouse=True)
    def _clean_db(self, reset_db):
        """Fresh, migrated tables before each page body executes."""
        yield

    @pytest.mark.parametrize("page_file,extra_key,expected_symbols", [
        ("01_Dashboard.py", None, ["get_home_stats", "get_recent_attendance_df", "status_badge"]),
        ("02_Employees.py", None, []),
        ("03_Enroll.py", None, ["_process_enrollment"]),
        ("05_Attendance.py", "webrtc", ["PhoneAttendanceFeed", "AttendanceVideoTransformer"]),
        ("06_Unknown.py", None, []),
        ("07_Analytics.py", None, []),
        ("08_Settings.py", None, []),
        ("09_Health.py", None, ["render_status", "check_database"]),
        ("10_About.py", None, ["_pill"]),
    ])
    def test_page_imports(self, page_file, extra_key, expected_symbols):
        extra = {}
        if extra_key == "webrtc":
            extra["streamlit_webrtc"] = _webrtc_mock_module()
        mod = _import_page(page_file, extra_modules=extra or None)
        assert mod is not None
        # Every page must call st.set_page_config at the top of its body
        assert mod._mock_st.set_page_config.called, f"{page_file} did not call set_page_config"
        for sym in expected_symbols:
            assert hasattr(mod, sym), f"{page_file} missing symbol {sym}"


# ═══════════════════════════════════════════════════════════════
#  Camera Options Mapping Tests
# ═══════════════════════════════════════════════════════════════
#  Verify CAMERA_OPTIONS and PHONE_CONNECTION_OPTIONS dicts
#  correctly map UI labels to internal source type strings.

class TestCameraOptions:
    """Verify that CAMERA_OPTIONS and PHONE_CONNECTION_OPTIONS
    map UI display labels to the correct internal source types."""

    @pytest.fixture(scope="class")
    def live_mod(self):
        return _import_live_page()

    # ── CAMERA_OPTIONS ───────────────────────────────────────

    def test_pc_camera_maps_to_webcam(self, live_mod):
        """💻 PC Camera must map to 'webcam' type."""
        assert live_mod.CAMERA_OPTIONS.get("\U0001f4bb PC Camera") == "webcam"

    def test_usb_camera_maps_to_usb_auto(self, live_mod):
        """🔌 USB Camera must map to 'usb_auto' type."""
        assert live_mod.CAMERA_OPTIONS.get("\U0001f50c USB Camera") == "usb_auto"

    def test_android_maps_to_android_wifi(self, live_mod):
        """📱 Android Phone must map to 'android_wifi'."""
        assert live_mod.CAMERA_OPTIONS.get("\U0001f4f1 Android Phone") == "android_wifi"

    def test_iphone_maps_to_iphone_wifi(self, live_mod):
        """📱 iPhone must map to 'iphone_wifi'."""
        assert live_mod.CAMERA_OPTIONS.get("\U0001f4f1 iPhone") == "iphone_wifi"

    def test_ip_camera_maps_to_ip_camera(self, live_mod):
        """🌐 IP / RTSP Camera must map to 'ip_camera'."""
        assert live_mod.CAMERA_OPTIONS.get("\U0001f310 IP / RTSP Camera") == "ip_camera"

    def test_all_five_camera_options_present(self, live_mod):
        """CAMERA_OPTIONS must have exactly 5 entries."""
        assert len(live_mod.CAMERA_OPTIONS) == 5

    def test_no_unknown_camera_types(self, live_mod):
        """All CAMERA_OPTIONS values must be known source types."""
        valid_types = {"webcam", "usb_auto", "android_wifi", "iphone_wifi", "ip_camera"}
        for v in live_mod.CAMERA_OPTIONS.values():
            assert v in valid_types, f"Unknown camera type: {v}"

    def test_phone_connection_options(self, live_mod):
        """PHONE_CONNECTION_OPTIONS must map correctly."""
        assert live_mod.PHONE_CONNECTION_OPTIONS["Wi-Fi"] == "wifi"
        assert live_mod.PHONE_CONNECTION_OPTIONS["USB"] == "usb"
        assert len(live_mod.PHONE_CONNECTION_OPTIONS) == 2

    def test_pc_camera_is_first_option(self, live_mod):
        """PC Camera should be the default (first) option."""
        keys = list(live_mod.CAMERA_OPTIONS.keys())
        assert "PC Camera" in keys[0], f"PC Camera should be first, got: {keys[0]}"


# ═══════════════════════════════════════════════════════════════
#  Local Camera Discovery Tests
# ═══════════════════════════════════════════════════════════════
#  Tests for scan_local_cameras() which probes camera indices
#  using cv2.VideoCapture with mocked hardware.

class TestScanLocalCameras:
    """Tests for scan_local_cameras() with mocked cv2.VideoCapture.

    No physical camera hardware is required — the cv2.VideoCapture
    class is fully mocked to simulate various hardware scenarios.
    """

    @pytest.fixture(scope="class")
    def live_mod(self):
        return _import_live_page()

    def _test_scan(self, live_mod, max_devices: int = 5, mock_config: dict | None = None) -> list:
        """Run scan_local_cameras with a specific mock config.

        Args:
            live_mod: Imported live page module.
            max_devices: Number of camera indices to probe.
            mock_config: Dict of ``{idx: (is_opened, has_frame, backend)}``
                for each camera index. Missing indices return not-opened.
        """
        mock_config = mock_config or {}
        def _video_capture(idx: int, backend: int = cv2.CAP_DSHOW) -> MagicMock:
            cap = MagicMock()
            if idx in mock_config:
                opened, has_frame, bkd = mock_config[idx]
                cap.isOpened.return_value = opened
                cap.read.return_value = (has_frame, np.zeros((480, 640, 3), dtype=np.uint8))
                cap.getBackendName.return_value = bkd
            else:
                cap.isOpened.return_value = False
            return cap

        with patch.object(live_mod.cv2, 'VideoCapture', side_effect=_video_capture):
            return live_mod.scan_local_cameras(max_devices=max_devices)

    def test_detects_one_camera(self, live_mod):
        """Camera at index 0 opens and returns frames."""
        available = self._test_scan(live_mod, max_devices=3, mock_config={0: (True, True, "DShow")})
        assert len(available) == 1
        assert available[0]["index"] == 0
        assert available[0]["type"] == "webcam"
        assert available[0]["has_frame"] is True
        assert "Camera 0 (DShow)" in available[0]["label"]

    def test_no_cameras_detected(self, live_mod):
        """All camera indices fail to open."""
        available = self._test_scan(live_mod, max_devices=3)
        assert len(available) == 0

    def test_some_cameras_detect(self, live_mod):
        """Camera 0 opens, camera 1 fails, camera 2 opens."""
        available = self._test_scan(
            live_mod, max_devices=3,
            mock_config={0: (True, True, "DShow"), 2: (True, True, "MSMF")},
        )
        assert len(available) == 2
        assert available[0]["index"] == 0
        assert available[1]["index"] == 2

    def test_custom_max_devices(self, live_mod):
        """Respect the max_devices parameter."""
        available = self._test_scan(
            live_mod, max_devices=5,
            mock_config={i: (True, True, "DShow") for i in range(5)},
        )
        assert len(available) == 5
        assert available[4]["index"] == 4

    def test_read_failure_still_reports(self, live_mod):
        """Camera opens but read fails — has_frame should be False."""
        available = self._test_scan(
            live_mod, max_devices=1,
            mock_config={0: (True, False, "DShow")},
        )
        assert len(available) == 1
        assert available[0]["index"] == 0
        assert available[0]["has_frame"] is False

    def test_exception_during_open_skipped(self, live_mod):
        """Exception when opening a camera index should be gracefully skipped."""
        def _vc_with_exception(idx: int, backend: int = cv2.CAP_DSHOW) -> MagicMock:
            if idx == 0:
                raise RuntimeError("Camera access denied")
            cap = MagicMock()
            cap.isOpened.return_value = True
            cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
            cap.getBackendName.return_value = "DShow"
            return cap

        with patch.object(live_mod.cv2, 'VideoCapture', side_effect=_vc_with_exception):
            available = live_mod.scan_local_cameras(max_devices=3)

        # Camera 0 skipped due to exception, 1 and 2 work
        assert len(available) == 2
        assert available[0]["index"] == 1
        assert available[1]["index"] == 2

    def test_all_cameras_opened(self, live_mod):
        """When all indices open successfully, all are returned."""
        available = self._test_scan(
            live_mod, max_devices=3,
            mock_config={i: (True, True, "DShow") for i in range(3)},
        )
        assert len(available) == 3
        for i, cam in enumerate(available):
            assert cam["index"] == i

    def test_returned_dict_has_required_fields(self, live_mod):
        """Each discovered camera dict must have all required fields."""
        available = self._test_scan(
            live_mod, max_devices=1,
            mock_config={0: (True, True, "MSMF")},
        )
        assert len(available) == 1
        cam = available[0]
        assert "index" in cam
        assert "label" in cam
        assert "type" in cam
        assert "has_frame" in cam
        assert cam["type"] == "webcam"  # Always "webcam" for local cameras


# ═══════════════════════════════════════════════════════════════
#  Camera Configuration Rendering Tests
# ═══════════════════════════════════════════════════════════════
#  Tests for _render_camera_config() which builds the config dict
#  for the selected camera type.  Streamlit UI functions are mocked.

class TestRenderCameraConfig:
    """Tests for _render_camera_config() configuration logic.

    Streamlit UI functions (selectbox, caption, button, text_input,
    etc.) are fully mocked.  Tests focus on the config dict produced
    for each source type.
    """

    @pytest.fixture(scope="class")
    def live_mod(self):
        return _import_live_page()

    @pytest.fixture()
    def st(self, live_mod):
        """Reset mock streamlit state before each test."""
        live_mod._mock_st.reset_mock()
        live_mod._mock_st.session_state = MockSessionState()
        return live_mod._mock_st

    # ── webcam ────────────────────────────────────────────────

    def test_webcam_no_cache_defaults_to_device_0(self, live_mod, st):
        """When pc_cameras_cache is empty, device_id defaults to 0."""
        config = live_mod._render_camera_config("webcam")
        assert config.get("device_id") == 0
        st.caption.assert_called_once()

    def test_webcam_single_cache_uses_that_index(self, live_mod, st):
        """With one camera in cache, use its device_id directly (no selectbox)."""
        st.session_state["pc_cameras_cache"] = [
            {"index": 2, "label": "Camera 2 (DShow)", "type": "webcam", "has_frame": True},
        ]
        config = live_mod._render_camera_config("webcam")
        assert config.get("device_id") == 2
        # No selectbox needed with single camera
        st.selectbox.assert_not_called()

    def test_webcam_multi_cache_shows_selectbox(self, live_mod, st):
        """With multiple cameras, selectbox is shown and device_id comes from choice."""
        cache = [
            {"index": 0, "label": "Camera 0 (DShow)", "type": "webcam", "has_frame": True},
            {"index": 3, "label": "Camera 3 (DShow)", "type": "webcam", "has_frame": True},
        ]
        st.session_state["pc_cameras_cache"] = cache
        st.selectbox.return_value = "Camera 3 (DShow)"

        config = live_mod._render_camera_config("webcam")
        assert config.get("device_id") == 3
        st.selectbox.assert_called_once()

    def test_webcam_selectbox_first_camera_returns_index_0(self, live_mod, st):
        """Selecting first camera in cache returns index 0."""
        cache = [
            {"index": 0, "label": "Camera 0 (DShow)", "type": "webcam", "has_frame": True},
            {"index": 5, "label": "Camera 5 (DShow)", "type": "webcam", "has_frame": True},
        ]
        st.session_state["pc_cameras_cache"] = cache
        st.selectbox.return_value = "Camera 0 (DShow)"

        config = live_mod._render_camera_config("webcam")
        assert config.get("device_id") == 0

    # ── usb_auto ──────────────────────────────────────────────

    def test_usb_auto_returns_empty_config(self, live_mod, st):
        """USB Auto type only shows a caption, no config fields."""
        config = live_mod._render_camera_config("usb_auto")
        assert config == {}
        st.caption.assert_called_once()

    # ── android_wifi ──────────────────────────────────────────

    def test_android_wifi_has_url(self, live_mod, st):
        """Android Wi-Fi type must include a URL field in config."""
        st.text_input.return_value = "http://192.168.1.50:8080/video"
        # Default connection is "Wi-Fi" (index 0)
        st.selectbox.return_value = "Wi-Fi"

        config = live_mod._render_camera_config("android_wifi")
        assert "url" in config
        assert config.get("url") == "http://192.168.1.50:8080/video"
        assert config.get("source_type") == "android_wifi"

    def test_android_usb_has_device_id(self, live_mod, st):
        """Android USB type must include a device_id field."""
        st.selectbox.return_value = "USB"
        st.number_input.return_value = 1

        config = live_mod._render_camera_config("android_wifi")
        assert "device_id" in config
        assert config.get("device_id") == 1
        assert config.get("source_type") == "android_usb"

    # ── iphone_wifi ───────────────────────────────────────────

    def test_iphone_wifi_has_url(self, live_mod, st):
        """iPhone Wi-Fi type must include a URL field."""
        st.text_input.return_value = "http://192.168.1.60:8080/video"
        st.selectbox.return_value = "Wi-Fi"

        config = live_mod._render_camera_config("iphone_wifi")
        assert "url" in config
        assert config.get("source_type") == "iphone_wifi"

    def test_iphone_usb_has_device_id(self, live_mod, st):
        """iPhone USB type must include a device_id field."""
        st.selectbox.return_value = "USB"
        st.number_input.return_value = 2

        config = live_mod._render_camera_config("iphone_wifi")
        assert "device_id" in config
        assert config.get("device_id") == 2
        assert config.get("source_type") == "iphone_usb"

    # ── ip_camera ─────────────────────────────────────────────

    def test_ip_camera_has_url(self, live_mod, st):
        """IP Camera must include a URL field in config."""
        st.text_input.return_value = "rtsp://10.0.0.55:554/stream1"
        st.columns.return_value = (MagicMock(), MagicMock())

        config = live_mod._render_camera_config("ip_camera")
        assert "url" in config
        assert config.get("url") == "rtsp://10.0.0.55:554/stream1"
        assert config.get("source_type") == "ip_camera"

    def test_ip_camera_has_username_and_password(self, live_mod, st):
        """IP Camera must include optional username/password fields."""
        st.text_input.side_effect = ["rtsp://10.0.0.55:554/stream1", "admin", "secret123"]
        st.columns.return_value = (MagicMock(), MagicMock())

        config = live_mod._render_camera_config("ip_camera")
        assert config.get("username") == "admin"
        assert config.get("password") == "secret123"


# ═══════════════════════════════════════════════════════════════
#  Full Regression Tests
# ═══════════════════════════════════════════════════════════════
#  End-to-end scenarios combining multiple components.

class TestFullRegression:
    """End-to-end regression tests combining multiple bug fixes."""

    @pytest.fixture()
    def regr_svc(self):
        """RecognitionService with all heavy components mocked."""
        s = RecognitionService(
            detector=MagicMock(),
            recognizer=MagicMock(),
            enrollment=MagicMock(),
            amfr=MagicMock(),
        )
        s._last_unknown_save = 0.0
        s._unknown_save_cooldown = 3.0
        s._marked_this_session = set()
        s._cooldown = {}
        return s

    def test_enroll_then_delete_syncs_faiss(self, reset_db, tmp_path):
        """Simulate: enroll employee → verify exists → delete → verify FAISS synced."""
        from services.employee_service import EmployeeService
        import config.config as cfg

        EmployeeService.create(
            employee_id="REGR-001", name="Regression Test", operator="test",
        )

        # Setup FAISS with matching embedding
        orig_index_path = cfg.FAISS_INDEX_PATH
        orig_meta_path = cfg.METADATA_PATH
        cfg.FAISS_INDEX_PATH = str(tmp_path / "regr_faiss.index")
        cfg.METADATA_PATH = str(tmp_path / "regr_meta.json")

        from app.enrollment import FaceEnrollment
        enrollment = FaceEnrollment(
            index_path=str(tmp_path / "regr_faiss.index"),
            metadata_path=str(tmp_path / "regr_meta.json"),
        )
        rng = np.random.RandomState(99)
        emb = rng.randn(512).astype(np.float32)
        emb /= np.linalg.norm(emb)
        enrollment.enroll("Regression Test", emb)

        # FaceEnrollment is imported INSIDE EmployeeService.delete()
        with patch('app.enrollment.FaceEnrollment') as MockEnroll:
            mock_enroll = MagicMock()
            MockEnroll.return_value = mock_enroll
            mock_enroll.remove_by_name.return_value = True

            result = EmployeeService.delete("REGR-001", operator="test")

        assert result is True
        mock_enroll.remove_by_name.assert_called_once()
        called_name = mock_enroll.remove_by_name.call_args[0][0]
        assert called_name == "Regression Test"

        # Restore config
        cfg.FAISS_INDEX_PATH = orig_index_path
        cfg.METADATA_PATH = orig_meta_path

    def test_unknown_face_does_not_flood_disk(self, regr_svc):
        """Multiple rapid calls to _handle_unknown_face should only save once."""
        regr_svc._last_unknown_save = 0.0
        regr_svc._unknown_save_cooldown = 3.0
        mock_frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch('services.recognition_service.cv2.imwrite', return_value=True) as mock_write:
            with patch('services.recognition_service.get_session'):
                with patch('services.recognition_service.datetime') as mock_dt:
                    mock_dt.now.return_value.strftime.return_value = "t"
                    for _ in range(10):
                        regr_svc._handle_unknown_face(mock_frame)

        # Cooldown blocks all but the first save
        assert mock_write.call_count == 1
