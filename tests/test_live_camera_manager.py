"""
Tests for services/live_camera_manager.py
=========================================

The live-camera layer owns one camera per session and runs a capture
thread plus an AI worker thread. These tests exercise its invariants
without hardware by substituting a fake camera source and a fake
recognition service:

- LatestFrameBuffer is a single-slot, newest-wins buffer.
- CameraSession start/stop lifecycle (including failure paths) never
  leaks threads or leaves the camera open.
- Results are rescaled from the 320x240 AI processing size back to the
  capture resolution before being exposed/annotated.
- Recognition events are throttled to 1/s per track and only broadcast
  for meaningful AMFR decisions.
- The manager registry enforces one session per key and supports
  stop/stop_all.
"""

from __future__ import annotations

import time
from typing import List, Optional, Tuple

import numpy as np
import pytest

import services.live_camera_manager as lcm
from services.live_camera_manager import CameraSession, LatestFrameBuffer, LiveCameraManager

# ── Fakes ──────────────────────────────────────────────────────────


class FakeCamera:
    """Minimal CameraSource stand-in (no hardware, no threads)."""

    def __init__(self, opens: bool = True) -> None:
        self.opens = opens
        self.released = False
        self.resolution: Optional[Tuple[int, int]] = None
        self._frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def open(self) -> bool:
        return self.opens

    def set_resolution(self, width: int, height: int) -> None:
        self.resolution = (width, height)

    def read(self):
        time.sleep(0.005)  # keep the capture loop from spinning hot
        return (not self.released), self._frame.copy()

    def is_opened(self) -> bool:
        return self.opens and not self.released

    def release(self) -> None:
        self.released = True


class FakeRecognitionService:
    """Returns canned per-frame results; counts calls."""

    def __init__(self, results: Optional[List[dict]] = None) -> None:
        self.results = results or []
        self.calls = 0

    def process_frame_detailed(self, frame):
        self.calls += 1
        return True, [dict(r) for r in self.results]


def _wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


# ── LatestFrameBuffer ──────────────────────────────────────────────


class TestLatestFrameBuffer:
    def test_initially_empty(self) -> None:
        frame, ts, seq = LatestFrameBuffer().get()
        assert frame is None and ts is None and seq == 0

    def test_newest_wins_and_drops_counted(self) -> None:
        buf = LatestFrameBuffer()
        f1 = np.zeros((4, 4, 3), dtype=np.uint8)
        f2 = np.ones((4, 4, 3), dtype=np.uint8)
        buf.put(f1)
        frame, _, seq1 = buf.get()
        assert frame is f1 and seq1 == 1
        assert buf.dropped == 0
        buf.put(f2)
        frame, _, seq2 = buf.get()
        assert frame is f2 and seq2 == 2
        assert buf.dropped == 1  # f1 was superseded, never queued

    def test_timestamps_advance(self) -> None:
        buf = LatestFrameBuffer()
        buf.put(np.zeros((2, 2, 3), dtype=np.uint8))
        _, ts1, _ = buf.get()
        time.sleep(0.01)
        buf.put(np.zeros((2, 2, 3), dtype=np.uint8))
        _, ts2, _ = buf.get()
        assert ts2 > ts1


# ── CameraSession lifecycle ────────────────────────────────────────


class TestCameraSessionLifecycle:
    def _session(self, cam: FakeCamera, service=None, key: str = "test-0") -> CameraSession:
        return CameraSession(
            key=key,
            source_type="webcam",
            camera_kwargs={"device_id": 0},
            service=service or FakeRecognitionService(),
        )

    def test_start_fails_when_camera_cannot_open(self, monkeypatch) -> None:
        monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: FakeCamera(opens=False))
        session = self._session(FakeCamera(opens=False))
        assert session.start() is False
        assert session.status == "ERROR"
        assert session.error is not None
        assert session.running is False

    def test_start_handles_create_camera_exception(self, monkeypatch) -> None:
        def boom(*_args, **_kwargs):
            raise RuntimeError("no camera backend")

        monkeypatch.setattr(lcm, "create_camera", boom)
        session = self._session(FakeCamera())
        assert session.start() is False
        assert session.status == "ERROR"
        assert "no camera backend" in (session.error or "")

    def test_stop_before_start_is_safe(self) -> None:
        session = self._session(FakeCamera())
        session.stop()
        assert session.status == "STOPPED"
        assert session.running is False

    def test_start_stop_releases_camera_and_joins_threads(self, monkeypatch) -> None:
        cam = FakeCamera()
        monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: cam)
        session = self._session(cam)
        assert session.start() is True
        assert session.running is True
        # Threads come up and the capture loop flips status to LIVE.
        assert _wait_for(lambda: session.status == "LIVE")
        assert _wait_for(lambda: session.frame_count > 0)
        session.stop()
        assert session.running is False
        assert session.status == "STOPPED"
        assert cam.released is True
        assert all(not t.is_alive() for t in session._threads or []) or session._threads == []

    def test_results_rescaled_to_capture_resolution(self, monkeypatch) -> None:
        """A 320x240-space bbox must be multiplied back to 640x480 space."""
        cam = FakeCamera()
        monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: cam)
        service = FakeRecognitionService(
            results=[{"bbox": (10, 10, 20, 20), "amfr_decision": "ACCEPT", "emp_name": "X"}]
        )
        session = self._session(cam, service=service)
        try:
            assert session.start() is True
            assert _wait_for(lambda: session.latest_results() != [])
            result = session.latest_results()[0]
            # 640/320 = 2.0 and 480/240 = 2.0
            assert result["bbox"] == (20, 20, 40, 40)
        finally:
            session.stop()

    def test_latest_results_expire(self, monkeypatch) -> None:
        cam = FakeCamera()
        monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: cam)
        session = self._session(cam, service=FakeRecognitionService([{"bbox": (1, 1, 2, 2)}]))
        try:
            assert session.start() is True
            assert _wait_for(lambda: session.latest_results() != [])
            with session._results_lock:
                session._results_ts = time.time() - lcm.RESULTS_TTL - 0.1
            assert session.latest_results() == []  # stale overlays dropped
        finally:
            session.stop()

    def test_annotated_frame_draws_overlays(self, monkeypatch) -> None:
        cam = FakeCamera()
        monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: cam)
        service = FakeRecognitionService(
            results=[{"bbox": (10, 10, 100, 100), "amfr_decision": "ACCEPT", "emp_name": "Alice"}]
        )
        session = self._session(cam, service=service)
        try:
            assert session.start() is True
            assert _wait_for(lambda: session.latest_results() != [])
            raw, _, _ = session.buffer.get()
            annotated = session.annotated_frame()
            assert annotated is not None
            assert annotated.shape == raw.shape
            assert not np.array_equal(annotated, raw)  # overlays were drawn
        finally:
            session.stop()

    def test_status_payload_shape(self) -> None:
        session = self._session(FakeCamera())
        payload = session.status_payload()
        for field in (
            "key",
            "source_type",
            "status",
            "error",
            "capture_fps",
            "ai_fps",
            "last_latency_ms",
            "frame_count",
            "dropped_frames",
        ):
            assert field in payload
        assert payload["key"] == "test-0"


# ── Event publishing ───────────────────────────────────────────────


class TestPublishEvents:
    def _session(self, sink) -> CameraSession:
        return CameraSession(
            key="evt",
            source_type="webcam",
            camera_kwargs={},
            service=FakeRecognitionService(),
            event_sink=sink,
        )

    def test_only_meaningful_decisions_are_broadcast(self) -> None:
        events: List[dict] = []
        session = self._session(events.append)
        session._publish_events(
            [
                {"track_id": 1, "amfr_decision": "BORDERLINE", "name": "A"},
                {"track_id": 2, "amfr_decision": "LOW_CONFIDENCE", "name": "B"},
            ],
            latency_ms=10.0,
        )
        assert events == []  # neither decision is meaningful

    def test_accept_is_broadcast_with_payload(self) -> None:
        events: List[dict] = []
        session = self._session(events.append)
        session._publish_events(
            [
                {
                    "track_id": 7,
                    "amfr_decision": "ACCEPT",
                    "emp_name": "Alice",
                    "risk_score": 0.9,
                    "liveness_score": 0.98,
                    "attendance_marked": True,
                }
            ],
            latency_ms=42.5,
        )
        assert len(events) == 1
        evt = events[0]
        assert evt["type"] == "recognition"
        assert evt["camera_key"] == "evt"
        assert evt["track_id"] == 7
        assert evt["student_name"] == "Alice"
        assert evt["amfr_decision"] == "ACCEPT"
        assert evt["latency_ms"] == 42.5
        assert evt["attendance_marked"] is True

    def test_throttled_to_one_event_per_track_per_second(self) -> None:
        events: List[dict] = []
        session = self._session(events.append)
        result = {"track_id": 7, "amfr_decision": "ACCEPT", "emp_name": "Alice"}
        session._publish_events([result], latency_ms=1.0)
        session._publish_events([result], latency_ms=2.0)  # within 1s window
        assert len(events) == 1
        session._last_event_at["7"] = time.time() - 1.5  # window elapsed
        session._publish_events([result], latency_ms=3.0)
        assert len(events) == 2

    def test_sink_errors_do_not_propagate(self) -> None:
        def bad_sink(_event: dict) -> None:
            raise RuntimeError("ws down")

        session = self._session(bad_sink)
        session._publish_events(  # must not raise
            [{"track_id": 1, "amfr_decision": "ACCEPT"}], latency_ms=1.0
        )


# ── LiveCameraManager registry ─────────────────────────────────────


class TestLiveCameraManager:
    @pytest.fixture()
    def manager(self, monkeypatch) -> LiveCameraManager:
        mgr = LiveCameraManager()
        monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: FakeCamera())
        mgr._service = FakeRecognitionService()
        yield mgr
        mgr.stop_all()

    def test_start_is_idempotent_per_key(self, manager: LiveCameraManager) -> None:
        first = manager.start("webcam-0", source_type="webcam", camera_kwargs={"device_id": 0})
        second = manager.start("webcam-0", source_type="webcam", camera_kwargs={"device_id": 0})
        assert first is second  # one owner per key
        assert len(manager.list_sessions()) == 1

    def test_get_and_list_sessions(self, manager: LiveCameraManager) -> None:
        session = manager.start("webcam-0", source_type="webcam", camera_kwargs={})
        assert manager.get("webcam-0") is session
        assert manager.get("missing") is None
        payloads = manager.list_sessions()
        assert [p["key"] for p in payloads] == ["webcam-0"]

    def test_stop_removes_session_and_reports(self, manager: LiveCameraManager) -> None:
        manager.start("webcam-0", source_type="webcam", camera_kwargs={})
        assert manager.stop("webcam-0") is True
        assert manager.stop("webcam-0") is False  # already gone
        assert manager.get("webcam-0") is None

    def test_stop_all_clears_registry(self, manager: LiveCameraManager) -> None:
        manager.start("a-0", source_type="webcam", camera_kwargs={})
        manager.start("b-0", source_type="webcam", camera_kwargs={})
        manager.stop_all()
        assert manager.list_sessions() == []

    def test_new_session_after_stop_gets_fresh_threads(self, manager: LiveCameraManager) -> None:
        first = manager.start("webcam-0", source_type="webcam", camera_kwargs={})
        first.stop()
        second = manager.start("webcam-0", source_type="webcam", camera_kwargs={})
        assert second is not first
        assert _wait_for(lambda: second.status == "LIVE")
