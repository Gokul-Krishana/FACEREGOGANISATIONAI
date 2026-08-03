"""
CameraOwner — Centralized Camera Ownership Management
======================================================

Ensures single camera ownership across Streamlit reruns and prevents
resource conflicts between multiple components.

Usage:
    from dashboard.camera_owner import CameraOwner

    owner = CameraOwner.get()

    # Check if we can acquire
    if owner.can_acquire():
        owner.acquire(camera, pipeline)
        # ... use camera ...

    # Release when done
    owner.release()
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from importlib import import_module
    from camera.base import CameraSource

    # NOTE: "04_Live" is not a valid Python module identifier (starts with a
    # digit), so it cannot be used in a plain ``from ... import`` statement.
    # Load it via importlib for static type checkers only (never runs).
    _live_page = import_module("dashboard.pages.04_Live")
    LiveRecognitionPipeline = _live_page.LiveRecognitionPipeline


class CameraOwner:
    """
    Singleton that manages exclusive camera ownership.

    Key principles:
    1. Only one owner at a time
    2. Clean START→STOP→START transitions
    3. Survives Streamlit reruns
    4. Thread-safe operations
    """

    _instance: Optional["CameraOwner"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CameraOwner":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self) -> None:
        """Initialize camera owner state."""
        self._camera: Optional["CameraSource"] = None
        self._pipeline: Optional["LiveRecognitionPipeline"] = None
        self._owner_id: Optional[str] = None
        self._state: str = "FREE"  # FREE, ACQUIRED, RELEASING
        self._state_lock = threading.Lock()

    @classmethod
    def get(cls) -> "CameraOwner":
        """Get singleton instance."""
        return cls()

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing/debugging)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._force_release()
                cls._instance = None

    @property
    def camera(self) -> Optional["CameraSource"]:
        """Get current camera if owned."""
        return self._camera

    @property
    def pipeline(self) -> Optional["LiveRecognitionPipeline"]:
        """Get current pipeline if owned."""
        return self._pipeline

    @property
    def state(self) -> str:
        """Get current ownership state."""
        with self._state_lock:
            return self._state

    def can_acquire(self, pipeline_id: Optional[str] = None) -> bool:
        """Check if camera can be acquired.

        Args:
            pipeline_id: Reserved for future use — the caller's pipeline
                identifier. Kept for API compatibility.
        """
        with self._state_lock:
            return self._state == "FREE"

    def acquire(self, camera: "CameraSource", pipeline: "LiveRecognitionPipeline") -> bool:
        """
        Acquire camera ownership.

        Returns True if acquisition successful, False if already owned.
        """
        with self._state_lock:
            if self._state != "FREE":
                return False

            self._camera = camera
            self._pipeline = pipeline
            self._owner_id = f"pipeline_{id(pipeline)}"
            self._state = "ACQUIRED"
            return True

    def release(self) -> None:
        """Release camera ownership and clean up resources.

        Pipeline/camera teardown runs OUTSIDE the state lock so a slow
        ``pipeline.stop()`` (which joins the capture thread, up to ~3s)
        never blocks concurrent ``can_acquire()``/``acquire()`` calls.

        NOTE: ordering assumption — state becomes FREE *before* teardown
        completes. In the Streamlit flow this is safe because teardown is
        synchronous before any new START, and a new pipeline always creates
        a fresh camera. Do not introduce a concurrent acquire() that shares
        the old camera without revisiting this.
        """
        with self._state_lock:
            if self._state == "FREE":
                return
            self._state = "RELEASING"
            pipeline = self._pipeline
            camera = self._camera
            self._pipeline = None
            self._camera = None
            self._owner_id = None
            self._state = "FREE"

        # Stop pipeline first (outside the lock)
        if pipeline is not None:
            try:
                pipeline.stop()
            except Exception:
                pass

        # Release camera (outside the lock)
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass

    def _force_release(self) -> None:
        """Force release without cleanup (for reset)."""
        try:
            if self._pipeline is not None:
                self._pipeline.stop()
        except Exception:
            pass

        try:
            if self._camera is not None:
                self._camera.release()
        except Exception:
            pass

        self._camera = None
        self._pipeline = None
        self._owner_id = None
        self._state = "FREE"

    def is_owned(self) -> bool:
        """Check if camera is currently owned."""
        with self._state_lock:
            return self._state == "ACQUIRED"

    def get_status(self) -> dict:
        """Get detailed ownership status."""
        with self._state_lock:
            return {
                "state": self._state,
                "has_camera": self._camera is not None,
                "has_pipeline": self._pipeline is not None,
                "owner_id": self._owner_id,
            }
