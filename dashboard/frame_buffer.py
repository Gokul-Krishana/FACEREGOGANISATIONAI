"""
FrameBuffer — Latest-Frame-Only Buffer for Camera Pipeline
============================================================

**Canonical implementation note:** this module (``dashboard/frame_buffer.py``)
is the SINGLE, canonical frame-buffer implementation for the camera pipeline.
There is intentionally no ``camera/frame_buffer.py`` — every consumer imports
from here. Verified across the main tree and all worktrees.

Implements thread-safe buffers that only keep the most recent frame(s),
dropping older frames to prevent queue buildup during Streamlit reruns.

Guarantees (Camera Stabilization Priority 2):
    - Holds only the latest 1–2 frames (never an unlimited queue)
    - Drops stale frames (writer never blocks, reader never lags behind)
    - Thread-safe via a single lock per buffer
    - Provides frame IDs and wall-clock timestamps for latency measurement
    - Shuts down cleanly via ``close()`` (used on STOP)

Usage:
    from dashboard.frame_buffer import FrameBuffer, frame_buffer

    # Producer thread (camera capture)
    while running:
        frame = camera.read()
        frame_buffer.put(frame)  # Drops old frame if buffer full

    # Consumer (Streamlit display)
    frame = frame_buffer.get()  # Gets latest frame or None
"""

from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

import numpy as np


class FrameBuffer:
    """
    Thread-safe buffer that holds only the most recent frame.

    Design:
    - Single slot buffer (acts like a volatile variable)
    - Writer drops frames if reader is slow
    - No blocking - put() never waits
    - get() returns None if no frame available
    - Tracks a monotonically increasing frame ID + timestamp per put()
    """

    def __init__(self, maxlen: int = 1):
        self._maxlen = max(1, int(maxlen))
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._available = threading.Event()
        self._frame_id: int = 0
        self._timestamp: Optional[float] = None
        self._closed: bool = False

    def put(self, frame: Optional[np.ndarray]) -> int:
        """
        Put a frame into the buffer.

        If there's already a frame waiting, it's dropped.
        This ensures the buffer always contains the latest frame.

        Returns:
            The new frame ID, or -1 if the buffer is closed or frame is None.
        """
        if frame is None:
            return -1
        with self._lock:
            if self._closed:
                return -1
            self._frame = frame.copy() if isinstance(frame, np.ndarray) else frame
            self._frame_id += 1
            self._timestamp = time.time()
        self._available.set()
        return self._frame_id

    def get(self) -> Optional[np.ndarray]:
        """
        Get the latest frame from the buffer.

        Returns None if no frame is available.
        Clears the available flag after reading.
        """
        with self._lock:
            if self._frame is None:
                return None
            frame = self._frame.copy() if isinstance(self._frame, np.ndarray) else self._frame
        self._available.clear()
        return frame

    def get_with_meta(self) -> Tuple[Optional[np.ndarray], int, Optional[float]]:
        """
        Get the latest frame plus its frame ID and timestamp.

        Returns:
            ``(frame, frame_id, timestamp)`` — frame may be None when empty;
            frame_id/timestamp reflect the most recent successful ``put()``.
        """
        with self._lock:
            if self._frame is None:
                return None, self._frame_id, self._timestamp
            frame = self._frame.copy() if isinstance(self._frame, np.ndarray) else self._frame
        self._available.clear()
        return frame, self._frame_id, self._timestamp

    def try_get(self) -> Optional[np.ndarray]:
        """
        Try to get frame without blocking.

        Returns None if no frame available or buffer is empty.
        """
        if not self._available.is_set():
            return None
        return self.get()

    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._frame = None
        self._available.clear()

    def close(self) -> None:
        """Shut the buffer down: reject new frames and clear contents."""
        with self._lock:
            self._closed = True
            self._frame = None
        self._available.clear()

    @property
    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    def has_frame(self) -> bool:
        """Check if a frame is available."""
        return self._available.is_set()

    def last_updated(self) -> Optional[float]:
        """Get wall-clock timestamp of the most recent frame put()."""
        with self._lock:
            return self._timestamp

    def frame_id(self) -> int:
        """Get the most recent frame ID (0 = never put)."""
        with self._lock:
            return self._frame_id


class ResultsBuffer:
    """
    Thread-safe buffer for recognition results.

    Similar to FrameBuffer but for recognition results (list of dicts).
    Holds only the latest result list — stale results are dropped.
    """

    def __init__(self, maxlen: int = 1):
        self._maxlen = max(1, int(maxlen))
        self._results: Optional[list] = None
        self._lock = threading.Lock()
        self._available = threading.Event()
        self._frame_id: int = 0
        self._timestamp: Optional[float] = None
        self._closed: bool = False

    def put(self, results: Optional[list]) -> int:
        """Put recognition results (a list of dicts) into buffer."""
        if results is None:
            results = []
        with self._lock:
            if self._closed:
                return -1
            self._results = list(results)
            self._frame_id += 1
            self._timestamp = time.time()
        self._available.set()
        return self._frame_id

    def get(self) -> Optional[list]:
        """Get the latest recognition results (a list, or None if empty)."""
        with self._lock:
            if self._results is None:
                return None
            results = [dict(r) if isinstance(r, dict) else r for r in self._results]
        self._available.clear()
        return results

    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._results = None
        self._available.clear()

    def close(self) -> None:
        """Shut the buffer down: reject new results and clear contents."""
        with self._lock:
            self._closed = True
            self._results = None
        self._available.clear()

    @property
    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    def has_results(self) -> bool:
        """Check if results are available."""
        return self._available.is_set()

    def last_updated(self) -> Optional[float]:
        """Get wall-clock timestamp of the most recent results put()."""
        with self._lock:
            return self._timestamp

    def frame_id(self) -> int:
        """Get the most recent results frame ID (0 = never put)."""
        with self._lock:
            return self._frame_id


# ── Module-level singletons ─────────────────────────────────────
# Shared by the background capture thread (producer) and the Streamlit
# display loop (consumer) so the latest frame survives Streamlit reruns
# without reopening the camera or duplicating capture threads.
frame_buffer = FrameBuffer(maxlen=1)
results_buffer = ResultsBuffer(maxlen=1)
