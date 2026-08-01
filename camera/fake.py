"""
FakeCameraSource — Synthetic Camera for Hardware-Free Testing
===============================================================

Generates synthetic BGR frames at a target frame rate so the raw
Camera → FrameBuffer → display pipeline can be measured and tested
WITHOUT any physical camera (Camera Stabilization Priority 3).

Design:
    - Implements the full ``CameraSource`` interface → a drop-in
      replacement for ``WebcamSource`` everywhere a camera is consumed.
    - Frames are cheap synthetic test patterns (moving disc + gradient
      + frame counter) so consecutive frames differ and latency / drop
      measurement is meaningful.
    - ``read()`` self-regulates to ``fps`` using a monotonic clock
      (``time.perf_counter``), optionally with jitter to simulate real
      USB/webcam timing.

Usage::

    from camera.fake import FakeCameraSource

    cam = FakeCameraSource(fps=30)
    cam.open()
    while True:
        ret, frame = cam.read()   # yields ~30 frames/sec
        ...
    cam.release()

A ready-to-run benchmark that measures Camera → FrameBuffer → display
FPS/latency with this source is
``scripts/benchmarks/fake_camera_validation.py``.
"""

from __future__ import annotations

import random
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from camera.base import CameraSource


class FakeCameraSource(CameraSource):
    """Synthetic camera that produces frames without any hardware.

    Args:
        width: Frame width (default 640).
        height: Frame height (default 480).
        fps: Target capture rate (default 30).
        pattern: ``"gradient"`` (moving rainbow + face disc) or
            ``"solid"`` (flat color) — gradient is the default so
            consecutive frames visibly differ.
        jitter_ms: Optional random read delay in milliseconds added
            per frame to simulate real USB/webcam timing (default 0).
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        fps: float = 30.0,
        pattern: str = "gradient",
        jitter_ms: float = 0.0,
    ) -> None:
        if fps <= 0:
            raise ValueError(f"fps must be > 0, got {fps}")
        self._width = int(width)
        self._height = int(height)
        self._target_fps = float(fps)
        self._pattern = pattern
        self._jitter = float(jitter_ms) / 1000.0
        self._opened = False
        self._frame_index = 0
        self._t0 = time.perf_counter()

    # ── Metadata ──────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return "Fake Camera (synthetic)"

    @property
    def source_type(self) -> str:
        return "fake"

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self) -> bool:
        self._opened = True
        self._frame_index = 0
        self._t0 = time.perf_counter()
        return True

    def release(self) -> None:
        self._opened = False

    # ── Frame Capture ─────────────────────────────────────────────
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Return the next synthetic frame, throttled to ``fps``.

        The caller may run in its own thread — the monotonic clock
        guarantees even pacing regardless of who calls ``read()``.
        Single-producer assumption (no lock on ``_frame_index``),
        which matches every camera consumer in this codebase.
        """
        if not self._opened:
            return False, None
        interval = 1.0 / self._target_fps
        expected = self._frame_index * interval
        elapsed = time.perf_counter() - self._t0
        if elapsed < expected:
            time.sleep(expected - elapsed)
        if self._jitter:
            time.sleep(random.uniform(0.0, self._jitter))
        self._frame_index += 1
        return True, self._generate_frame(self._frame_index)

    # ── Properties ────────────────────────────────────────────────
    def is_opened(self) -> bool:
        return self._opened

    def set_resolution(self, width: int, height: int) -> None:
        self._width = int(width)
        self._height = int(height)

    def get_resolution(self) -> Tuple[int, int]:
        return self._width, self._height

    # ── Info ──────────────────────────────────────────────────────
    def info(self) -> dict:
        return {
            "source_type": self.source_type,
            "name": self.name,
            "resolution": [self._width, self._height],
            "target_fps": self._target_fps,
            "pattern": self._pattern,
            "is_opened": self.is_opened(),
            "frames_generated": self._frame_index,
        }

    # ── Frame generation ──────────────────────────────────────────
    def _generate_frame(self, index: int) -> np.ndarray:
        h, w = self._height, self._width
        if self._pattern == "solid":
            frame = np.full((h, w, 3), (90, 130, 200), dtype=np.uint8)
        else:  # gradient — moving rainbow background + "face" disc
            t = index % 256
            ramp = np.arange(w, dtype=np.int16)
            frame = np.empty((h, w, 3), dtype=np.uint8)
            frame[..., 0] = ((ramp + t) % 256).astype(np.uint8)
            frame[..., 1] = ((ramp * 2 + t) % 256).astype(np.uint8)
            frame[..., 2] = ((255 - ramp) % 256).astype(np.uint8)
            # "face" disc drifting left → right so consecutive frames differ
            cx = int((index * 3) % max(1, w - 1))
            cy = h // 2
            r = max(2, min(h, w) // 8)
            cv2.circle(frame, (cx, cy), r, (60, 200, 90), -1)
            cv2.circle(frame, (cx, cy), max(1, r // 3), (0, 0, 0), 2)
        cv2.putText(frame, f"FAKE FRAME {index}", (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
                    cv2.LINE_AA)
        cv2.putText(frame, f"{self._target_fps:.0f} fps target", (8, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
                    cv2.LINE_AA)
        return frame

    # ── Convenience (parity with WebcamSource) ────────────────────
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()
