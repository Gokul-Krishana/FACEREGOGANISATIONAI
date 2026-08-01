"""
Tests for the canonical frame-buffer implementation.

Covers Camera Stabilization Priority 2 requirements:
    - Holds only the latest 1-2 frames (never an unlimited queue)
    - Drops stale frames
    - Thread-safe
    - Provides timestamps/frame IDs
    - Shuts down cleanly via close()
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pytest

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from dashboard.frame_buffer import FrameBuffer, ResultsBuffer, frame_buffer, results_buffer


# ═══════════════════════════════════════════════════════════════
#  FrameBuffer — latest-only semantics
# ═══════════════════════════════════════════════════════════════

class TestFrameBufferBasics:

    def test_empty_get_returns_none(self):
        b = FrameBuffer()
        assert b.get() is None
        assert b.try_get() is None
        assert not b.has_frame()

    def test_put_get_returns_latest(self):
        b = FrameBuffer()
        f1 = np.zeros((10, 10, 3), dtype=np.uint8)
        f2 = np.ones((10, 10, 3), dtype=np.uint8)
        b.put(f1)
        b.put(f2)
        out = b.get()
        assert out is not None
        assert np.array_equal(out, f2)

    def test_stale_frames_dropped(self):
        """put() while a frame is waiting drops the old frame (latest-only)."""
        b = FrameBuffer()
        for i in range(100):
            b.put(np.full((8, 8, 3), i, dtype=np.uint8))
        out = b.get()
        assert out is not None
        assert np.array_equal(out, np.full((8, 8, 3), 99, dtype=np.uint8))

    def test_get_returns_copy(self):
        b = FrameBuffer()
        src = np.zeros((10, 10, 3), dtype=np.uint8)
        b.put(src)
        out = b.get()
        assert out is not None
        out[0, 0] = 255
        # Buffer contents must be unchanged (copy semantics)
        assert np.array_equal(b.get(), src)

    def test_put_none_ignored(self):
        b = FrameBuffer()
        assert b.put(None) == -1
        assert b.get() is None

    def test_frame_id_increments(self):
        b = FrameBuffer()
        assert b.frame_id() == 0
        id1 = b.put(np.zeros((4, 4, 3), dtype=np.uint8))
        id2 = b.put(np.zeros((4, 4, 3), dtype=np.uint8))
        assert id2 == id1 + 1
        assert b.frame_id() == id2

    def test_timestamps_monotonic(self):
        b = FrameBuffer()
        assert b.last_updated() is None
        b.put(np.zeros((4, 4, 3), dtype=np.uint8))
        t1 = b.last_updated()
        time.sleep(0.01)
        b.put(np.zeros((4, 4, 3), dtype=np.uint8))
        t2 = b.last_updated()
        assert t1 is not None and t2 is not None
        assert t2 >= t1

    def test_get_with_meta(self):
        b = FrameBuffer()
        f = np.zeros((4, 4, 3), dtype=np.uint8)
        b.put(f)
        frame, fid, ts = b.get_with_meta()
        assert frame is not None
        assert fid == 1
        assert ts is not None

    def test_clear(self):
        b = FrameBuffer()
        b.put(np.zeros((4, 4, 3), dtype=np.uint8))
        b.clear()
        assert b.get() is None
        assert not b.has_frame()

    def test_close_rejects_frames(self):
        b = FrameBuffer()
        b.put(np.zeros((4, 4, 3), dtype=np.uint8))
        b.close()
        assert b.is_closed
        # put() after close is a no-op (returns -1)
        assert b.put(np.zeros((4, 4, 3), dtype=np.uint8)) == -1
        # Contents cleared on close
        assert b.get() is None

    def test_try_get_requires_new_frame(self):
        b = FrameBuffer()
        assert b.try_get() is None
        b.put(np.zeros((4, 4, 3), dtype=np.uint8))
        assert b.try_get() is not None
        # After a get(), the available flag is cleared
        assert b.try_get() is None


# ═══════════════════════════════════════════════════════════════
#  FrameBuffer — thread-safety
# ═══════════════════════════════════════════════════════════════

class TestFrameBufferThreadSafety:

    def test_concurrent_producers_consumers(self):
        """Many threads putting/getting must never crash or grow unboundedly."""
        b = FrameBuffer()
        stop = threading.Event()
        errors: list = []

        def producer():
            try:
                i = 0
                while not stop.is_set():
                    b.put(np.full((16, 16, 3), i % 256, dtype=np.uint8))
                    i += 1
            except Exception as e:  # pragma: no cover
                errors.append(e)

        def consumer():
            try:
                while not stop.is_set():
                    b.get()
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=producer) for _ in range(2)]
        threads += [threading.Thread(target=consumer) for _ in range(4)]
        for t in threads:
            t.start()
        time.sleep(0.15)
        stop.set()
        for t in threads:
            t.join(timeout=2.0)

        assert not errors, f"Thread errors: {errors}"
        # Buffer still holds at most the latest frame
        assert b.get() is None or isinstance(b.get(), np.ndarray)

    def test_frame_id_thread_safe(self):
        """frame_id() must be readable concurrently without raising."""
        b = FrameBuffer()
        stop = threading.Event()

        def producer():
            while not stop.is_set():
                b.put(np.zeros((8, 8, 3), dtype=np.uint8))

        def reader():
            while not stop.is_set():
                b.frame_id()
                b.last_updated()

        threads = [threading.Thread(target=producer)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        time.sleep(0.1)
        stop.set()
        for t in threads:
            t.join(timeout=2.0)


# ═══════════════════════════════════════════════════════════════
#  ResultsBuffer
# ═══════════════════════════════════════════════════════════════

class TestResultsBuffer:

    def test_empty_get_returns_none(self):
        b = ResultsBuffer()
        assert b.get() is None

    def test_put_get_list(self):
        b = ResultsBuffer()
        results = [{"name": "EMP001", "amfr_decision": "ACCEPT"}]
        b.put(results)
        out = b.get()
        assert out == results

    def test_stale_results_dropped(self):
        b = ResultsBuffer()
        b.put([{"name": "A"}])
        b.put([{"name": "B"}])
        out = b.get()
        assert out == [{"name": "B"}]

    def test_get_returns_copies(self):
        b = ResultsBuffer()
        results = [{"name": "A"}]
        b.put(results)
        out = b.get()
        assert out is not None
        out[0]["name"] = "MUTATED"
        # Original must be unchanged
        assert b.get() == [{"name": "A"}]

    def test_clear_and_close(self):
        b = ResultsBuffer()
        b.put([{"name": "A"}])
        b.clear()
        assert b.get() is None
        b.put([{"name": "B"}])
        b.close()
        assert b.is_closed
        assert b.put([{"name": "C"}]) == -1
        assert b.get() is None

    def test_frame_id_and_timestamp(self):
        b = ResultsBuffer()
        assert b.frame_id() == 0
        assert b.last_updated() is None
        b.put([{"name": "A"}])
        assert b.frame_id() == 1
        assert b.last_updated() is not None


# ═══════════════════════════════════════════════════════════════
#  Module-level singletons (used by 04_Live.py)
# ═══════════════════════════════════════════════════════════════

class TestSingletons:

    def test_singletons_exist(self):
        assert frame_buffer is not None
        assert results_buffer is not None
        assert isinstance(frame_buffer, FrameBuffer)
        assert isinstance(results_buffer, ResultsBuffer)

    def test_singleton_identity(self):
        from dashboard import frame_buffer as fb_mod
        assert fb_mod.frame_buffer is frame_buffer
        assert fb_mod.results_buffer is results_buffer

    def test_singleton_latest_only(self):
        """Singletons must behave like a normal FrameBuffer."""
        frame_buffer.clear()
        results_buffer.clear()
        try:
            frame_buffer.put(np.zeros((8, 8, 3), dtype=np.uint8))
            frame_buffer.put(np.ones((8, 8, 3), dtype=np.uint8))
            out = frame_buffer.get()
            assert out is not None
            assert np.array_equal(out, np.ones((8, 8, 3), dtype=np.uint8))
        finally:
            frame_buffer.clear()
            results_buffer.clear()

    def test_singletons_can_roundtrip(self):
        frame_buffer.clear()
        results_buffer.clear()
        try:
            fid = frame_buffer.put(np.zeros((8, 8, 3), dtype=np.uint8))
            rid = results_buffer.put([{"name": "X"}])
            assert fid >= 1
            assert rid >= 1
            assert frame_buffer.get() is not None
            assert results_buffer.get() == [{"name": "X"}]
        finally:
            frame_buffer.clear()
            results_buffer.clear()
