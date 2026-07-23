"""
Tests for IPCameraSource — generic IP/RTSP/HTTP camera source.

Uses ``unittest.mock`` to simulate ``cv2.VideoCapture`` since IP cameras
are not available in test environments.  The tests verify:

- Construction and metadata (name, source_type)
- Successful open/read/release lifecycle
- Failure modes (connection refused, camera not found)
- Resolution management
- Context manager protocol (__enter__ / __exit__)
- info() dictionary format
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from camera.phone import IPCameraSource


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture()
def sample_frame() -> np.ndarray:
    """Return a fake 480x640 BGR frame."""
    return np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)


# ═══════════════════════════════════════════════════════════════
#  Mock helpers
# ═══════════════════════════════════════════════════════════════

def _mock_cap_opened(ret_read: bool = True, frame=None):
    """Create a mock ``cv2.VideoCapture`` that reports as opened."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    # Simulate cap.read() -> (ret, frame)
    # When ret_read is False, return (False, None) to match real behavior
    if ret_read:
        mock_cap.read.return_value = (
            True,
            frame if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8),
        )
    else:
        mock_cap.read.return_value = (False, None)
    # Simulate cap.get(prop) returning values like 640, 480
    def mock_get(prop):
        if prop == 3:   # CAP_PROP_FRAME_WIDTH
            return 640.0
        if prop == 4:   # CAP_PROP_FRAME_HEIGHT
            return 480.0
        return 0.0
    mock_cap.get.side_effect = mock_get
    mock_cap.set.return_value = True
    return mock_cap


def _mock_cap_closed():
    """Create a mock ``cv2.VideoCapture`` that reports as not opened."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    return mock_cap


# ═══════════════════════════════════════════════════════════════
#  Tests
# ═══════════════════════════════════════════════════════════════

class TestIPCameraSource:
    """Tests for IPCameraSource construction and metadata."""

    # ── Construction ──────────────────────────────────────────

    def test_default_construction(self):
        """Default URL should be set correctly."""
        cam = IPCameraSource()
        assert cam._url == "http://192.168.1.200:8080/video"
        assert cam._width == 640
        assert cam._height == 480
        assert cam._cap is None

    def test_custom_url_construction(self):
        """Custom RTSP URL should be stored."""
        url = "rtsp://admin:pass@10.0.0.50:554/stream1"
        cam = IPCameraSource(url=url)
        assert cam._url == url

    def test_custom_url_construction_http(self):
        """Custom HTTP MJPEG URL should be stored."""
        url = "http://192.168.1.50/videostream.cgi"
        cam = IPCameraSource(url=url)
        assert cam._url == url

    # ── Metadata ──────────────────────────────────────────────

    def test_name(self):
        """Name should include the stream URL."""
        cam = IPCameraSource(url="rtsp://10.0.0.50:554/stream1")
        assert "IP Camera" in cam.name
        assert "rtsp://10.0.0.50:554/stream1" in cam.name

    def test_source_type(self):
        """source_type should be 'ip_camera'."""
        cam = IPCameraSource()
        assert cam.source_type == "ip_camera"

    # ── Lifecycle — open / read / release ─────────────────────

    @patch("cv2.VideoCapture")
    def test_open_success(self, mock_vc, sample_frame):
        """open() should return True when VideoCapture is opened."""
        mock_vc.return_value = _mock_cap_opened(ret_read=True, frame=sample_frame)
        cam = IPCameraSource(url="http://192.168.1.200:8080/video")
        result = cam.open()
        assert result is True
        assert cam.is_opened() is True
        mock_vc.assert_called_once_with("http://192.168.1.200:8080/video")

    @patch("cv2.VideoCapture")
    def test_open_failure(self, mock_vc):
        """open() should return False when VideoCapture cannot open."""
        mock_vc.return_value = _mock_cap_closed()
        cam = IPCameraSource(url="http://192.168.1.200:8080/video")
        result = cam.open()
        assert result is False
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    def test_open_failure_exception(self, mock_vc):
        """open() should handle exceptions gracefully and return False."""
        mock_vc.side_effect = RuntimeError("Simulated crash")
        cam = IPCameraSource(url="rtsp://192.168.1.200:554/stream1")
        result = cam.open()
        assert result is False
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    def test_read_success(self, mock_vc, sample_frame):
        """read() should return (True, frame) after successful open."""
        mock_vc.return_value = _mock_cap_opened(ret_read=True, frame=sample_frame)
        cam = IPCameraSource()
        cam.open()
        ret, frame = cam.read()
        assert ret is True
        assert frame is not None
        assert frame.shape == sample_frame.shape

    @patch("cv2.VideoCapture")
    def test_read_failure(self, mock_vc):
        """read() should return (False, None) when VideoCapture.read fails."""
        mock_vc.return_value = _mock_cap_opened(ret_read=False)
        cam = IPCameraSource()
        cam.open()
        ret, frame = cam.read()
        assert ret is False
        assert frame is None

    def test_read_before_open(self):
        """read() should return (False, None) when camera is not opened."""
        cam = IPCameraSource()
        ret, frame = cam.read()
        assert ret is False
        assert frame is None

    @patch("cv2.VideoCapture")
    def test_release(self, mock_vc):
        """release() should close the capture and set _cap to None."""
        mock_vc.return_value = _mock_cap_opened()
        cam = IPCameraSource()
        cam.open()
        assert cam.is_opened() is True
        cam.release()
        assert cam.is_opened() is False
        assert cam._cap is None
        # Calling release again should be a no-op
        cam.release()
        assert cam.is_opened() is False

    # ── Resolution management ─────────────────────────────────

    @patch("cv2.VideoCapture")
    def test_set_resolution(self, mock_vc):
        """set_resolution() should store and apply the requested size."""
        mock_vc.return_value = _mock_cap_opened()
        cam = IPCameraSource()
        cam.open()
        cam.set_resolution(1280, 720)
        assert cam._width == 1280
        assert cam._height == 720
        # Verify set() was called on the VideoCapture
        cam._cap.set.assert_any_call(3, 1280)    # CAP_PROP_FRAME_WIDTH
        cam._cap.set.assert_any_call(4, 720)    # CAP_PROP_FRAME_HEIGHT

    @patch("cv2.VideoCapture")
    def test_get_resolution_before_open(self, mock_vc):
        """get_resolution() before open should return the default."""
        cam = IPCameraSource()
        w, h = cam.get_resolution()
        assert w == 640
        assert h == 480

    @patch("cv2.VideoCapture")
    def test_get_resolution_after_open(self, mock_vc):
        """get_resolution() after open should return the capture's resolution."""
        mock_vc.return_value = _mock_cap_opened()
        cam = IPCameraSource()
        cam.open()
        w, h = cam.get_resolution()
        assert w == 640
        assert h == 480

    @patch("cv2.VideoCapture")
    def test_set_resolution_before_open_then_applied(self, mock_vc):
        """set_resolution() before open stores values; applied when open() creates the capture."""
        mock_cap = _mock_cap_opened()
        mock_vc.return_value = mock_cap

        cam = IPCameraSource()
        cam.set_resolution(1920, 1080)
        assert cam._width == 1920
        assert cam._height == 1080

        # open() should create the capture then apply stored resolution
        cam.open()
        # Verify set() was called on the VideoCapture with the stored values
        mock_cap.set.assert_any_call(3, 1920)   # CAP_PROP_FRAME_WIDTH
        mock_cap.set.assert_any_call(4, 1080)  # CAP_PROP_FRAME_HEIGHT

    # ── Info dict ─────────────────────────────────────────────

    @patch("cv2.VideoCapture")
    def test_info_format(self, mock_vc):
        """info() should return the expected keys and types."""
        mock_vc.return_value = _mock_cap_opened()
        cam = IPCameraSource(url="rtsp://10.0.0.50:554/main")
        cam.open()
        info = cam.info()
        assert isinstance(info, dict)
        assert info["source_type"] == "ip_camera"
        assert info["url"] == "rtsp://10.0.0.50:554/main"
        assert isinstance(info["resolution"], list)
        assert len(info["resolution"]) == 2
        assert info["is_opened"] is True

    @patch("cv2.VideoCapture")
    def test_info_before_open(self, mock_vc):
        """info() before open should show is_opened=False."""
        cam = IPCameraSource()
        info = cam.info()
        assert info["is_opened"] is False
        assert info["resolution"] == [640, 480]

    # ── Context manager ───────────────────────────────────────

    @patch("cv2.VideoCapture")
    def test_context_manager(self, mock_vc):
        """Context manager should open on enter and release on exit."""
        mock_cap = _mock_cap_opened()
        mock_vc.return_value = mock_cap

        with IPCameraSource(url="http://10.0.0.50:8080/video") as cam:
            assert cam.is_opened() is True
            ret, frame = cam.read()
            assert ret is True

        # After exit, should be released
        assert cam.is_opened() is False
        mock_cap.release.assert_called_once()

    @patch("cv2.VideoCapture")
    def test_context_manager_on_failure(self, mock_vc):
        """Context manager should not raise when open() fails."""
        mock_vc.return_value = _mock_cap_closed()

        with IPCameraSource(url="http://10.0.0.50:8080/video") as cam:
            assert cam.is_opened() is False

        assert cam.is_opened() is False

    # ── Edge cases ────────────────────────────────────────────

    def test_is_opened_initial(self):
        """is_opened() before any operation should return False."""
        cam = IPCameraSource()
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    def test_can_open_twice(self, mock_vc):
        """Calling open() twice should succeed both times (creates fresh cap)."""
        mock_cap = _mock_cap_opened()
        mock_vc.return_value = mock_cap

        cam = IPCameraSource()
        first = cam.open()
        second = cam.open()
        assert first is True
        assert second is True
        assert cam.is_opened() is True

    @patch("cv2.VideoCapture")
    def test_read_after_release(self, mock_vc):
        """read() after release() should return (False, None)."""
        mock_vc.return_value = _mock_cap_opened()
        cam = IPCameraSource()
        cam.open()
        cam.release()
        ret, frame = cam.read()
        assert ret is False
        assert frame is None
