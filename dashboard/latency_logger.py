"""
LatencyLogger — Rolling E2E Frame-Latency Statistics
=====================================================

Thread-safe logger that records end-to-end (E2E) frame latency samples
in milliseconds and computes rolling P50/P95/avg statistics. Used by the
Live Recognition pipeline to measure Camera → FrameBuffer → display
latency during a live session.

The frame buffer stores a wall-clock timestamp at ``put()`` time and
``get_with_meta()`` returns ``(frame, frame_id, timestamp)``. The live
session's latency sampler reads the buffer at the display cadence and
records ``now - timestamp`` — how long the latest frame sat in the buffer
before a consumer read it — i.e. the E2E capture → display latency.

Design:
    - Bounded window (``deque`` maxlen) so memory stays flat and stats
      reflect the recent session, not all-time history.
    - All mutations/reads under a single lock (sampler thread writes,
      Streamlit UI thread reads concurrently).
    - Percentiles use linear interpolation, matching
      ``scripts/benchmarks/camera_validation.py``.

Usage:
    logger = LatencyLogger(max_samples=500)

    # Producer (live session)
    logger.record((time.time() - ts) * 1000.0)

    # Consumer (Streamlit UI)
    stats = logger.stats()          # {count, p50_ms, p95_ms, avg_ms, last_ms}
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, Dict, Optional


class LatencyLogger:
    """Thread-safe rolling-window statistics of latency samples (ms)."""

    def __init__(self, max_samples: int = 500) -> None:
        self._samples: Deque[float] = deque(maxlen=max(10, int(max_samples)))
        self._lock = threading.Lock()

    def record(self, ms: float) -> None:
        """Append one latency sample (ms). Thread-safe, never raises."""
        with self._lock:
            self._samples.append(float(ms))

    def reset(self) -> None:
        """Clear all recorded samples (used on START)."""
        with self._lock:
            self._samples.clear()

    @property
    def count(self) -> int:
        """Number of samples currently retained."""
        with self._lock:
            return len(self._samples)

    def percentile(self, p: float) -> Optional[float]:
        """Linear-interpolated percentile (same math as the benchmark)."""
        with self._lock:
            samples = sorted(self._samples)
        if not samples:
            return None
        k = (len(samples) - 1) * (p / 100.0)
        lo = int(k)
        hi = min(lo + 1, len(samples) - 1)
        frac = k - lo
        return samples[lo] * (1 - frac) + samples[hi] * frac

    def p50(self) -> Optional[float]:
        return self.percentile(50.0)

    def p95(self) -> Optional[float]:
        return self.percentile(95.0)

    def average(self) -> Optional[float]:
        with self._lock:
            if not self._samples:
                return None
            return sum(self._samples) / len(self._samples)

    def last(self) -> Optional[float]:
        """Most recently recorded sample (None when empty)."""
        with self._lock:
            return self._samples[-1] if self._samples else None

    def stats(self) -> Dict[str, object]:
        """Summary dict for UI display: count (int), p50/p95/avg/last ms."""
        return {
            "count": self.count,
            "p50_ms": self.p50(),
            "p95_ms": self.p95(),
            "avg_ms": self.average(),
            "last_ms": self.last(),
        }
