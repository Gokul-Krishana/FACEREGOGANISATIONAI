"""
Tests for dashboard/latency_logger.LatencyLogger and its integration
with dashboard.frame_buffer (get_with_meta) used by the Live page's
E2E latency sampler.

Covers:
    - Recording + linear-interpolated P50/P95/avg (matches benchmark math)
    - Bounded rolling window (never grows unboundedly)
    - reset() / empty-state behavior
    - Thread safety (sampler writes, UI reads concurrently)
    - Latency math: now - put_timestamp via get_with_meta()
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dashboard.frame_buffer import FrameBuffer
from dashboard.latency_logger import LatencyLogger


# ═══════════════════════════════════════════════════════════════
#  LatencyLogger — percentile & window semantics
# ═══════════════════════════════════════════════════════════════

class TestLatencyLogger:

    def test_empty_state(self):
        lg = LatencyLogger()
        assert lg.count == 0
        assert lg.p50() is None
        assert lg.p95() is None
        assert lg.average() is None
        assert lg.last() is None
        s = lg.stats()
        assert s["count"] == 0
        assert s["p50_ms"] is None
        assert s["p95_ms"] is None

    def test_record_and_count(self):
        lg = LatencyLogger()
        lg.record(10.0)
        lg.record(20.0)
        lg.record(30.0)
        assert lg.count == 3
        assert lg.last() == 30.0

    def test_p50_linear_interpolation(self):
        """P50 of [10,20,30,40] = 25 (linear interp, matches benchmark pct())."""
        lg = LatencyLogger()
        for v in (10.0, 20.0, 30.0, 40.0):
            lg.record(v)
        assert lg.p50() == pytest.approx(25.0)

    def test_p95_linear_interpolation(self):
        lg = LatencyLogger()
        for v in (10.0, 20.0, 30.0, 40.0):
            lg.record(v)
        # k = (4-1)*0.95 = 2.85 → s[2]*0.15 + s[3]*0.85 = 30*0.15+40*0.85 = 38.5
        assert lg.p95() == pytest.approx(38.5)

    def test_p50_odd_count_median(self):
        lg = LatencyLogger()
        for v in (5.0, 1.0, 3.0):
            lg.record(v)
        assert lg.p50() == pytest.approx(3.0)  # sorted [1,3,5] → 3

    def test_average(self):
        lg = LatencyLogger()
        for v in (10.0, 20.0, 30.0):
            lg.record(v)
        assert lg.average() == pytest.approx(20.0)

    def test_reset(self):
        lg = LatencyLogger()
        lg.record(10.0)
        lg.record(20.0)
        lg.reset()
        assert lg.count == 0
        assert lg.last() is None

    def test_rolling_window_bounded(self):
        """Only the most recent N samples are retained."""
        lg = LatencyLogger(max_samples=25)
        for i in range(100):
            lg.record(float(i))
        assert lg.count == 25
        assert lg.last() == pytest.approx(99.0)  # last of 100 recorded
        # Retained window is [75..99]; median of 25 values → s[12] = 87
        assert lg.p50() == pytest.approx(87.0)

    def test_minimum_window_floor(self):
        """A tiny max_samples still keeps a usable 10-sample floor so
        percentiles remain meaningful."""
        lg = LatencyLogger(max_samples=1)
        for i in range(20):
            lg.record(float(i))
        assert lg.count == 10  # floor
        assert lg.last() == pytest.approx(19.0)

    def test_stats_dict_shape(self):
        lg = LatencyLogger()
        lg.record(1.0)
        lg.record(2.0)
        s = lg.stats()
        assert set(s.keys()) == {"count", "p50_ms", "p95_ms", "avg_ms", "last_ms"}
        assert s["count"] == 2
        assert s["p50_ms"] == pytest.approx(1.5)
        assert s["last_ms"] == pytest.approx(2.0)

    def test_thread_safety(self):
        """Concurrent writers + readers must never corrupt state."""
        lg = LatencyLogger(max_samples=1000)
        n_threads = 8
        per_thread = 200
        errors: list = []

        def writer():
            try:
                for i in range(per_thread):
                    lg.record(float(i))
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(n_threads)]
        for t in threads:
            t.start()
        # Read concurrently while writers run
        for _ in range(50):
            lg.stats()
            time.sleep(0.001)
        for t in threads:
            t.join()
        assert not errors
        assert lg.count == min(1000, n_threads * per_thread)
        # All samples are in range; percentiles valid
        p50 = lg.p50()
        p95 = lg.p95()
        assert p50 is not None and 0.0 <= p50 <= per_thread
        assert p95 is not None and 0.0 <= p95 <= per_thread


# ═══════════════════════════════════════════════════════════════
#  Integration — latency math used by _latency_loop
# ═══════════════════════════════════════════════════════════════

class TestFrameBufferLatencyIntegration:

    def test_get_with_meta_timestamp_after_put(self):
        """A frame put into the buffer carries a wall-clock timestamp."""
        buf = FrameBuffer()
        buf.put(np.zeros((10, 10, 3), dtype=np.uint8))
        frame, fid, ts = buf.get_with_meta()
        assert frame is not None
        assert fid == 1
        assert ts is not None and ts > 0

    def test_latency_is_time_since_put(self):
        """Latency sample = now - put_timestamp, grows with elapsed time."""
        buf = FrameBuffer()
        lg = LatencyLogger()
        buf.put(np.zeros((10, 10, 3), dtype=np.uint8))
        time.sleep(0.05)
        _, _, ts = buf.get_with_meta()
        assert ts is not None
        lat = (time.time() - ts) * 1000.0
        lg.record(lat)
        assert lg.count == 1
        assert lat >= 45.0  # at least ~50ms elapsed
        assert lg.last() == pytest.approx(lat)

    def test_no_timestamp_when_empty(self):
        """Empty buffer → get_with_meta returns None timestamp (sampler skips)."""
        buf = FrameBuffer()
        frame, fid, ts = buf.get_with_meta()
        assert frame is None
        assert ts is None

    def test_sampler_skips_when_no_timestamp(self):
        """The live sampler only records when a timestamp is present."""
        buf = FrameBuffer()
        lg = LatencyLogger()
        _, _, ts = buf.get_with_meta()
        if ts is not None:
            lg.record((time.time() - ts) * 1000.0)
        assert lg.count == 0
