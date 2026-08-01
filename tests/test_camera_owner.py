"""
Tests for CameraOwner — centralized camera ownership management.

Covers Camera Stabilization Priority 1 requirements:
    - Only one owner opens each physical camera
    - START → STOP → START works repeatedly
    - Camera is released on STOP
    - No stale camera objects remain
    - Thread-safe operations
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dashboard.camera_owner import CameraOwner


class _MockCamera:
    """Minimal CameraSource-compatible mock."""

    def __init__(self):
        self.released = False

    def release(self) -> None:
        self.released = True


class _MockPipeline:
    """Minimal pipeline-compatible mock."""

    def __init__(self):
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


# ═══════════════════════════════════════════════════════════════
#  Fixture — fresh singleton per test
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _reset_owner():
    """Reset the singleton before and after every test."""
    CameraOwner.reset()
    yield
    CameraOwner.reset()


# ═══════════════════════════════════════════════════════════════
#  Singleton behavior
# ═══════════════════════════════════════════════════════════════

class TestSingleton:

    def test_get_returns_same_instance(self):
        a = CameraOwner.get()
        b = CameraOwner.get()
        assert a is b

    def test_new_returns_same_instance(self):
        a = CameraOwner()
        b = CameraOwner()
        assert a is b

    def test_reset_creates_fresh_instance(self):
        a = CameraOwner.get()
        CameraOwner.reset()
        b = CameraOwner.get()
        assert a is not b


# ═══════════════════════════════════════════════════════════════
#  Acquisition semantics
# ═══════════════════════════════════════════════════════════════

class TestAcquisition:

    def test_can_acquire_when_free(self):
        owner = CameraOwner.get()
        assert owner.can_acquire() is True

    def test_acquire_returns_true_when_free(self):
        owner = CameraOwner.get()
        assert owner.acquire(_MockCamera(), _MockPipeline()) is True

    def test_acquire_returns_false_when_owned(self):
        owner = CameraOwner.get()
        assert owner.acquire(_MockCamera(), _MockPipeline()) is True
        # Second acquisition must fail — only one owner
        assert owner.acquire(_MockCamera(), _MockPipeline()) is False

    def test_can_acquire_false_when_owned(self):
        owner = CameraOwner.get()
        owner.acquire(_MockCamera(), _MockPipeline())
        assert owner.can_acquire() is False

    def test_is_owned_reflects_state(self):
        owner = CameraOwner.get()
        assert owner.is_owned() is False
        owner.acquire(_MockCamera(), _MockPipeline())
        assert owner.is_owned() is True
        owner.release()
        assert owner.is_owned() is False

    def test_state_transitions(self):
        owner = CameraOwner.get()
        assert owner.state == "FREE"
        owner.acquire(_MockCamera(), _MockPipeline())
        assert owner.state == "ACQUIRED"
        owner.release()
        assert owner.state == "FREE"

    def test_acquire_stores_camera_and_pipeline(self):
        owner = CameraOwner.get()
        cam = _MockCamera()
        pipe = _MockPipeline()
        owner.acquire(cam, pipe)
        assert owner.camera is cam
        assert owner.pipeline is pipe
        assert owner.get_status()["has_camera"] is True
        assert owner.get_status()["has_pipeline"] is True


# ═══════════════════════════════════════════════════════════════
#  Release semantics
# ═══════════════════════════════════════════════════════════════

class TestRelease:

    def test_release_stops_pipeline(self):
        owner = CameraOwner.get()
        pipe = _MockPipeline()
        owner.acquire(_MockCamera(), pipe)
        owner.release()
        assert pipe.stopped is True

    def test_release_releases_camera(self):
        owner = CameraOwner.get()
        cam = _MockCamera()
        owner.acquire(cam, _MockPipeline())
        owner.release()
        assert cam.released is True

    def test_release_clears_references(self):
        owner = CameraOwner.get()
        owner.acquire(_MockCamera(), _MockPipeline())
        owner.release()
        assert owner.camera is None
        assert owner.pipeline is None
        assert owner.get_status()["has_camera"] is False
        assert owner.get_status()["has_pipeline"] is False

    def test_release_when_free_is_noop(self):
        owner = CameraOwner.get()
        owner.release()  # Should not raise
        assert owner.state == "FREE"

    def test_release_handles_errors_gracefully(self):
        owner = CameraOwner.get()
        cam = MagicMock()
        cam.release.side_effect = Exception("camera busy")
        pipe = MagicMock()
        pipe.stop.side_effect = Exception("pipeline busy")
        owner.acquire(cam, pipe)
        owner.release()  # Must not raise
        assert owner.state == "FREE"

    def test_release_uses_pipeline_reference(self):
        """release() must stop the OWNED pipeline, not require caller input."""
        owner = CameraOwner.get()
        cam = _MockCamera()
        pipe = _MockPipeline()
        owner.acquire(cam, pipe)
        owner.release()
        assert pipe.stopped is True
        assert cam.released is True


# ═══════════════════════════════════════════════════════════════
#  START → STOP → START cycles
# ═══════════════════════════════════════════════════════════════

class TestStartStopStart:

    def test_start_stop_start_works(self):
        owner = CameraOwner.get()
        # First cycle
        cam1 = _MockCamera()
        pipe1 = _MockPipeline()
        assert owner.acquire(cam1, pipe1) is True
        assert owner.is_owned() is True
        owner.release()
        assert owner.is_owned() is False
        # Second cycle — fresh camera
        cam2 = _MockCamera()
        pipe2 = _MockPipeline()
        assert owner.acquire(cam2, pipe2) is True
        assert owner.pipeline is pipe2
        owner.release()

    def test_previous_camera_released_before_next_acquire(self):
        owner = CameraOwner.get()
        cam1 = _MockCamera()
        owner.acquire(cam1, _MockPipeline())
        owner.release()
        cam2 = _MockCamera()
        owner.acquire(cam2, _MockPipeline())
        # First camera must have been released before second opened
        assert cam1.released is True
        owner.release()

    def test_no_stale_objects_after_cycle(self):
        owner = CameraOwner.get()
        owner.acquire(_MockCamera(), _MockPipeline())
        owner.release()
        owner.acquire(_MockCamera(), _MockPipeline())
        owner.release()
        status = owner.get_status()
        assert status["has_camera"] is False
        assert status["has_pipeline"] is False
        assert status["state"] == "FREE"
        assert status["owner_id"] is None


# ═══════════════════════════════════════════════════════════════
#  Thread safety
# ═══════════════════════════════════════════════════════════════

class TestThreadSafety:

    def test_concurrent_acquire_only_one_wins(self):
        owner = CameraOwner.get()
        results = []
        lock = threading.Lock()

        def try_acquire():
            ok = owner.acquire(_MockCamera(), _MockPipeline())
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=try_acquire) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)

        assert sum(results) == 1, f"Expected exactly 1 successful acquire, got {results}"

    def test_concurrent_release_and_acquire_safe(self):
        owner = CameraOwner.get()
        stop = threading.Event()
        errors: list = []

        def cycle():
            try:
                while not stop.is_set():
                    if owner.acquire(_MockCamera(), _MockPipeline()):
                        owner.release()
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=cycle) for _ in range(4)]
        for t in threads:
            t.start()
        time.sleep(0.15)
        stop.set()
        for t in threads:
            t.join(timeout=2.0)
        assert not errors, f"Thread errors: {errors}"
        # Final state must be consistent
        assert owner.state in ("FREE", "ACQUIRED")
