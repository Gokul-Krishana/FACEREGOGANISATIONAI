"""
Laptop / USB Webcam Implementation
===================================

Wraps OpenCV ``cv2.VideoCapture`` with multi-backend support
(DirectShow → MSMF → Default) for maximum compatibility on Windows.

Supports:
- Built-in laptop webcam
- External USB webcam
- Any camera accessible via OpenCV device index
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from camera.base import CameraSource
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class WebcamSource(CameraSource):
    """OpenCV-based webcam source.

    Args:
        device_id: Camera device index (0 = default webcam).

    Attributes:
        device_id: The OpenCV camera index.
    """

    def __init__(self, device_id: int = 0) -> None:
        self.device_id = device_id
        self._cap: Optional[cv2.VideoCapture] = None
        self._width: int = 640
        self._height: int = 480

    # ── Metadata ──────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return f"Webcam #{self.device_id}"

    @property
    def source_type(self) -> str:
        return "webcam"

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self) -> bool:
        """Open the webcam with multiple backend fallback."""
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (None, "Default"),
        ]
        for backend, backend_name in backends:
            try:
                if backend is None:
                    cap = cv2.VideoCapture(self.device_id)
                else:
                    cap = cv2.VideoCapture(self.device_id, backend)
                if cap.isOpened():
                    self._cap = cap
                    self.set_resolution(self._width, self._height)
                    logger.info("Webcam opened camera #%s via %s", self.device_id, backend_name)
                    return True
            except Exception:
                continue
        self._cap = None
        return False

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # ── Frame Capture ─────────────────────────────────────────────
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._cap is None:
            return False, None
        ret, frame = self._cap.read()
        return ret, frame

    # ── Properties ────────────────────────────────────────────────
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def set_resolution(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def get_resolution(self) -> Tuple[int, int]:
        if self._cap is not None:
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if w > 0 and h > 0:
                return w, h
        return self._width, self._height

    # ── Info ──────────────────────────────────────────────────────
    def info(self) -> dict:
        return {
            "source_type": self.source_type,
            "device_id": self.device_id,
            "resolution": list(self.get_resolution()),
            "is_opened": self.is_opened(),
        }

    # ── Convenience ───────────────────────────────────────────────
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()


def list_webcams(max_devices: int = 5) -> List[int]:
    """Probe device indices to find available webcams.

    Args:
        max_devices: Maximum number of indices to probe.

    Returns:
        List of available device indices.
    """
    available: List[int] = []
    for idx in range(max_devices):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            available.append(idx)
            cap.release()
    return available


def list_all_cameras(max_devices: int = 10) -> List[Dict]:
    """Probe device indices 0..*max_devices* and return detailed info
    about each available camera, including a name hint when possible.

    This is used by ``USBAnySource`` to auto-discover the correct index
    for any USB-connected camera (Android UVC webcam mode, DroidCam,
    EpocCam, regular webcams, etc.).

    Args:
        max_devices: Maximum number of indices to probe (default 10).

    Returns:
        List of dicts with ``index``, ``name``, ``has_frame`` keys.
    """
    results: List[Dict] = []
    for idx in range(max_devices):
        # Try DirectShow first, then default backend
        for backend in (cv2.CAP_DSHOW, None):
            try:
                if backend is None:
                    cap = cv2.VideoCapture(idx)
                else:
                    cap = cv2.VideoCapture(idx, backend)
                if cap.isOpened():
                    # Read a test frame to confirm it works
                    ret, frame = cap.read()
                    has_frame = ret and frame is not None
                    h, w = frame.shape[:2] if has_frame else (0, 0)
                    cap.release()
                    backend_name = "DirectShow" if backend == cv2.CAP_DSHOW else "Default"
                    results.append(
                        {
                            "index": idx,
                            "name": f"Camera #{idx} ({backend_name}, {w}x{h})",
                            "has_frame": has_frame,
                            "resolution": (w, h),
                            "backend": backend_name,
                        }
                    )
                    break  # Found on this backend, don't try the other
            except Exception:
                continue
    return results


# ═══════════════════════════════════════════════════════════════
#  USB Auto — auto-detect any USB camera (plug & play)
# ═══════════════════════════════════════════════════════════════


class USBAnySource(CameraSource):
    """Auto-detect any USB-connected camera by scanning device indices.

    This is the **plug-and-play** option for users who just want to
    connect a phone via USB and have it work without installing
    DroidCam, EpocCam, or other apps.

    **Android**: Enable ``Developer Options`` → ``USB Webcam``
    (Android 14+). The phone appears as a standard UVC camera
    visible to OpenCV.

    **iPhone**: If EpocCam is installed, it will appear as a
    DirectShow camera and be detected automatically.

    **Regular webcams**: Also detected — works like ``WebcamSource``
    but finds the right index automatically.

    The source probes indices 0..*max_devices* and uses the **first
    available camera** that can successfully read a frame. If you
    have multiple cameras, use ``list_all_cameras()`` to see all
    available indices and then use ``WebcamSource(device_id=N)``
    instead.

    Args:
        prefer_index: Optional preferred device index (0..10).
                      If set, this index is tried first before
                      falling back to scanning all indices.
        max_devices: Maximum number of indices to scan.
    """

    def __init__(self, prefer_index: int = -1, max_devices: int = 10):
        self._prefer_index = prefer_index
        self._max_devices = max_devices
        self._cap: Optional[cv2.VideoCapture] = None
        self._width: int = 640
        self._height: int = 480
        self._found_index: Optional[int] = None

    @property
    def name(self) -> str:
        if self._found_index is not None:
            return f"USB Auto — Camera #{self._found_index}"
        return "USB Auto — (scanning...)"

    @property
    def source_type(self) -> str:
        return "usb_auto"

    def open(self) -> bool:
        """Scan device indices to find any working USB camera."""
        indices_to_try: List[int] = []

        # If a preferred index was provided, try it first
        if 0 <= self._prefer_index < self._max_devices:
            indices_to_try.append(self._prefer_index)

        # Then scan all indices to find the first working camera
        indices_to_try.extend(i for i in range(self._max_devices) if i != self._prefer_index)

        for idx in indices_to_try:
            try:
                # Try DirectShow first, then default
                for backend in (cv2.CAP_DSHOW, None):
                    try:
                        if backend is None:
                            cap = cv2.VideoCapture(idx)
                        else:
                            cap = cv2.VideoCapture(idx, backend)
                        if cap.isOpened():
                            # Verify with a test read
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                self._cap = cap
                                self._found_index = idx
                                self.set_resolution(self._width, self._height)
                                backend_name = "DirectShow" if backend == cv2.CAP_DSHOW else "Default"
                                logger.info("USBAny found camera #%s via %s", idx, backend_name)
                                return True
                            cap.release()
                    except Exception:
                        continue
            except Exception:
                continue

        logger.warning("USBAny: no camera found after scanning %s indices", self._max_devices)
        return False

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            self._found_index = None

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._cap is None:
            return False, None
        ret, frame = self._cap.read()
        return ret, frame

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def set_resolution(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def get_resolution(self) -> Tuple[int, int]:
        if self._cap is not None:
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if w > 0 and h > 0:
                return w, h
        return self._width, self._height

    def info(self) -> dict:
        return {
            "source_type": self.source_type,
            "device_index": self._found_index,
            "resolution": list(self.get_resolution()),
            "is_opened": self.is_opened(),
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()
