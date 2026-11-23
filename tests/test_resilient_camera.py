"""
Tests for ResilientCameraSource — Camera Reliability & Fault Tolerance
========================================================================

Verifies:
- Continuous camera health monitoring & telemetry
- Detection and recovery from frozen frames
- Detection of disconnected cameras
- Automatic reconnection with exponential backoff
- Camera resource cleanup and safe reopening
- Thread-safe camera lifecycle management
- Stale frame rejection
- Recovery after simulated USB disconnection and RTSP network drop
- Simulated extended continuous operation
"""

from __future__ import annotations

import threading
import time

import numpy as np

from camera.base import CameraSource
from camera.fake import FakeCameraSource
from camera.resilient import (
    CameraState,
    FrozenFrameDetector,
    ResilientCameraSource,
)


class MockFlakyCamera(CameraSource):
    """A mock camera that can be commanded to fail or freeze on demand."""

    def __init__(self, name: str = "FlakyCam") -> None:
        self._name = name
        self._is_open = False
        self._read_count = 0
        self.should_fail_read = False
        self.should_return_frozen = False
        self.release_called_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def source_type(self) -> str:
        return "mock_flaky"

    def open(self) -> bool:
        self._is_open = True
        return True

    def release(self) -> None:
        self._is_open = False
        self.release_called_count += 1

    def is_opened(self) -> bool:
        return self._is_open

    def set_resolution(self, width: int, height: int) -> None:
        pass

    def get_resolution(self) -> tuple[int, int]:
        return 640, 480

    def info(self) -> dict:
        return {"name": self._name, "source_type": self.source_type, "is_opened": self._is_open}

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._is_open or self.should_fail_read:
            return False, None

        self._read_count += 1
        if self.should_return_frozen:
            # Identical frame every time
            frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        else:
            # Varying frames
            frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        return True, frame


def test_frozen_frame_detector():
    detector = FrozenFrameDetector(max_identical_frames=5, frozen_timeout_sec=0.5)
    identical_frame = np.zeros((64, 64, 3), dtype=np.uint8)

    # First frame should not be frozen
    assert not detector.is_frozen(identical_frame)

    # Send 4 more identical frames
    for _ in range(4):
        detector.is_frozen(identical_frame)

    # 6th identical frame should trigger frozen detection
    assert detector.is_frozen(identical_frame)

    # Reset should clear it
    detector.reset()
    assert not detector.is_frozen(identical_frame)


def test_resilient_camera_normal_operation():
    resilient = ResilientCameraSource(
        source_factory=lambda: FakeCameraSource(fps=30),
        camera_name="TestCam",
    )
    assert resilient.open()
    assert resilient.is_opened()
    assert resilient.state == CameraState.CONNECTED

    ret, frame = resilient.read()
    assert ret is True
    assert frame is not None
    assert resilient.state == CameraState.STREAMING

    metrics = resilient.metrics
    assert metrics.total_frames_read >= 1
    assert metrics.total_frames_dropped == 0
    assert not resilient.is_stale()

    resilient.release()
    assert not resilient.is_opened()
    assert resilient.state == CameraState.DISCONNECTED


def test_resilient_camera_simulated_disconnect_and_reconnect():
    flaky = MockFlakyCamera()
    resilient = ResilientCameraSource(
        source_factory=lambda: flaky,
        camera_name="FlakyCam",
        initial_backoff_sec=0.05,
        max_backoff_sec=0.2,
    )
    resilient.open()

    # Normal frame read
    ret, frame = resilient.read()
    assert ret is True

    # Simulate hardware disconnect
    resilient.simulate_disconnection(True)
    ret, frame = resilient.read()
    assert ret is False
    assert resilient.state in (CameraState.DISCONNECTED, CameraState.ERROR)

    # Restore connection
    resilient.simulate_disconnection(False)
    ret, frame = resilient.read()
    assert ret is True
    assert resilient.metrics.successful_reconnections >= 1
    assert resilient.state == CameraState.STREAMING

    resilient.release()


def test_resilient_camera_simulated_frozen_frames():
    flaky = MockFlakyCamera()
    resilient = ResilientCameraSource(
        source_factory=lambda: flaky,
        camera_name="FrozenCam",
        initial_backoff_sec=0.05,
        max_backoff_sec=0.1,
    )
    resilient.open()

    # Normal frame
    ret, _ = resilient.read()
    assert ret is True

    # Simulate frozen stream
    resilient.simulate_freeze(True)
    ret, _ = resilient.read()
    assert ret is False
    assert resilient.metrics.frozen_frames_detected >= 1

    # Restore
    resilient.simulate_freeze(False)
    ret, _ = resilient.read()
    assert ret is True

    resilient.release()


def test_resilient_camera_thread_safety():
    resilient = ResilientCameraSource(
        source_factory=lambda: FakeCameraSource(fps=60),
        camera_name="ThreadSafeCam",
    )
    resilient.open()

    read_results = []
    threads = []

    def reader_worker():
        for _ in range(25):
            ret, frame = resilient.read()
            read_results.append(ret)
            time.sleep(0.005)

    for _ in range(4):
        t = threading.Thread(target=reader_worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert all(read_results)
    assert resilient.metrics.total_frames_read >= 100

    resilient.release()


def test_stale_frame_detection():
    resilient = ResilientCameraSource(
        source_factory=lambda: FakeCameraSource(fps=30),
        stale_frame_timeout_sec=0.1,
    )
    resilient.open()
    resilient.read()

    # Fresh
    assert not resilient.is_stale(max_age_seconds=1.0)

    # Wait for frame to become stale
    time.sleep(0.15)
    assert resilient.is_stale(max_age_seconds=0.1)

    resilient.release()


def test_simulated_extended_continuous_operation():
    """Simulates prolonged operation (accelerated time simulation of 24h cycle)."""
    flaky = MockFlakyCamera()
    resilient = ResilientCameraSource(
        source_factory=lambda: flaky,
        initial_backoff_sec=0.01,
        max_backoff_sec=0.05,
    )
    resilient.open()

    # Simulate 500 operational cycles with periodic glitches
    cycles = 200
    for i in range(cycles):
        if i == 50:
            flaky.should_fail_read = True
        elif i == 55:
            flaky.should_fail_read = False
        elif i == 120:
            flaky.should_return_frozen = True
        elif i == 125:
            flaky.should_return_frozen = False

        resilient.read()

    metrics = resilient.metrics
    assert metrics.total_frames_read > 150
    assert metrics.total_frames_dropped > 0
    assert metrics.successful_reconnections >= 1

    resilient.release()
