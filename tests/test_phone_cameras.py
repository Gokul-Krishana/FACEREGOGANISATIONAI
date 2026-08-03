"""
Tests for AndroidWiFiSource and iPhoneWiFiSource — phone camera sources.

Uses ``unittest.mock`` to simulate ``cv2.VideoCapture`` (and
``requests.get`` for AndroidWiFiSource's connectivity check) since
phone cameras are not available in test environments.

AndroidWiFiSource tests also cover the ``_parse_base_url`` helper and
the HTTP connectivity check that happens before opening the video stream.

iPhoneWiFiSource follows the same pattern as IPCameraSource — it simply
opens ``cv2.VideoCapture`` with the RTSP/HTTP URL.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import requests

from camera.phone import AndroidWiFiSource, iPhoneWiFiSource


# ═══════════════════════════════════════════════════════════════
#  Shared fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture()
def sample_frame() -> np.ndarray:
    """Return a fake 480x640 BGR frame."""
    return np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)


# ═══════════════════════════════════════════════════════════════
#  Shared mock helpers
# ═══════════════════════════════════════════════════════════════


def _mock_cap_opened(ret_read: bool = True, frame=None):
    """Create a mock ``cv2.VideoCapture`` that reports as opened."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    if ret_read:
        mock_cap.read.return_value = (
            True,
            frame if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8),
        )
    else:
        mock_cap.read.return_value = (False, None)

    def mock_get(prop):
        if prop == 3:  # CAP_PROP_FRAME_WIDTH
            return 640.0
        if prop == 4:  # CAP_PROP_FRAME_HEIGHT
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


def _mock_requests_ok():
    """Create a mock ``requests.get`` response that returns HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    return mock_resp


def _mock_requests_fail(status_code: int = 404):
    """Create a mock ``requests.get`` response with a non-200 status."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    return mock_resp


# ═══════════════════════════════════════════════════════════════
#  Tests: AndroidWiFiSource
# ═══════════════════════════════════════════════════════════════


class TestAndroidWiFiSource:
    """Tests for AndroidWiFiSource — Android IP Webcam over Wi-Fi."""

    # ── Construction & URL parsing ────────────────────────────

    def test_default_construction(self):
        """Default URL and base URL should be set correctly."""
        cam = AndroidWiFiSource()
        assert cam._url == "http://192.168.1.100:8080/video"
        assert cam._base_url == "http://192.168.1.100:8080"
        assert cam._width == 640
        assert cam._height == 480
        assert cam._cap is None

    def test_custom_url_construction(self):
        """Custom URL should be parsed to video URL and base URL."""
        url = "http://10.0.0.50:8080/video"
        cam = AndroidWiFiSource(url=url)
        assert cam._url == url
        assert cam._base_url == "http://10.0.0.50:8080"

    def test_parse_base_url_standard(self):
        """_parse_base_url strips /video suffix correctly."""
        result = AndroidWiFiSource._parse_base_url("http://192.168.1.100:8080/video")
        assert result == "http://192.168.1.100:8080"

    def test_parse_base_url_without_video(self):
        """_parse_base_url returns the full URL if no /video suffix."""
        result = AndroidWiFiSource._parse_base_url("http://192.168.1.100:8080")
        assert result == "http://192.168.1.100:8080"

    def test_parse_base_url_without_video_path(self):
        """_parse_base_url returns the full URL if it doesn't contain '/video'."""
        result = AndroidWiFiSource._parse_base_url("http://10.0.0.50:8080/mjpeg")
        assert result == "http://10.0.0.50:8080/mjpeg"

    # ── Metadata ──────────────────────────────────────────────

    def test_name(self):
        """Name should include the base URL."""
        cam = AndroidWiFiSource(url="http://10.0.0.50:8080/video")
        assert "Android (Wi-Fi)" in cam.name
        assert "http://10.0.0.50:8080" in cam.name

    def test_source_type(self):
        """source_type should be 'android_wifi'."""
        cam = AndroidWiFiSource()
        assert cam.source_type == "android_wifi"

    # ── Lifecycle — open / read / release ─────────────────────

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_open_success(self, mock_requests_get, mock_vc, sample_frame):
        """open() should check connectivity then open the stream."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened(ret_read=True, frame=sample_frame)

        cam = AndroidWiFiSource(url="http://10.0.0.50:8080/video")
        result = cam.open()

        assert result is True
        assert cam.is_opened() is True
        # Verify connectivity check then video stream open
        mock_requests_get.assert_called_once_with("http://10.0.0.50:8080", timeout=5)
        mock_vc.assert_called_once_with("http://10.0.0.50:8080/video")

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_open_http_failure(self, mock_requests_get, mock_vc):
        """open() should return False when IP Webcam returns non-200."""
        mock_requests_get.return_value = _mock_requests_fail(status_code=503)
        # VideoCapture should NOT be called at all
        mock_vc.return_value = _mock_cap_opened()

        cam = AndroidWiFiSource(url="http://10.0.0.50:8080/video")
        result = cam.open()

        assert result is False
        assert cam.is_opened() is False
        mock_vc.assert_not_called()  # VideoCapture should never be reached

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_open_connection_refused(self, mock_requests_get, mock_vc):
        """open() should return False when requests raises an exception."""
        mock_requests_get.side_effect = requests.ConnectionError("Connection refused")
        mock_vc.return_value = _mock_cap_opened()

        cam = AndroidWiFiSource(url="http://10.0.0.50:8080/video")
        result = cam.open()

        assert result is False
        assert cam.is_opened() is False
        mock_vc.assert_not_called()

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_open_video_stream_failure(self, mock_requests_get, mock_vc):
        """open() should return False when VideoCapture cannot open the stream."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_closed()

        cam = AndroidWiFiSource(url="http://10.0.0.50:8080/video")
        result = cam.open()

        assert result is False
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_read_success(self, mock_requests_get, mock_vc, sample_frame):
        """read() should return (True, frame) after successful open."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened(ret_read=True, frame=sample_frame)

        cam = AndroidWiFiSource(url="http://10.0.0.50:8080/video")
        cam.open()
        ret, frame = cam.read()

        assert ret is True
        assert frame is not None
        assert frame.shape == sample_frame.shape

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_read_failure(self, mock_requests_get, mock_vc):
        """read() should return (False, None) when VideoCapture.read fails."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened(ret_read=False)

        cam = AndroidWiFiSource()
        cam.open()
        ret, frame = cam.read()

        assert ret is False
        assert frame is None

    def test_read_before_open(self):
        """read() before open should return (False, None)."""
        cam = AndroidWiFiSource()
        ret, frame = cam.read()
        assert ret is False
        assert frame is None

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_release(self, mock_requests_get, mock_vc):
        """release() should close capture and set _cap to None."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened()

        cam = AndroidWiFiSource()
        cam.open()
        assert cam.is_opened() is True
        cam.release()
        assert cam.is_opened() is False
        assert cam._cap is None
        # Double release should be a no-op
        cam.release()
        assert cam.is_opened() is False

    # ── Resolution management ─────────────────────────────────

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_set_resolution(self, mock_requests_get, mock_vc):
        """set_resolution() should store and apply the requested size."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened()

        cam = AndroidWiFiSource()
        cam.open()
        cam.set_resolution(1280, 720)
        assert cam._width == 1280
        assert cam._height == 720
        cam._cap.set.assert_any_call(3, 1280)
        cam._cap.set.assert_any_call(4, 720)

    @patch("cv2.VideoCapture")
    def test_get_resolution_before_open(self, mock_vc):
        """get_resolution() before open should return the default."""
        cam = AndroidWiFiSource()
        w, h = cam.get_resolution()
        assert w == 640
        assert h == 480

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_get_resolution_after_open(self, mock_requests_get, mock_vc):
        """get_resolution() after open should return the capture's resolution."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened()

        cam = AndroidWiFiSource()
        cam.open()
        w, h = cam.get_resolution()
        assert w == 640
        assert h == 480

    # ── Info dict ─────────────────────────────────────────────

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_info_format(self, mock_requests_get, mock_vc):
        """info() should return the expected keys and types."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened()

        cam = AndroidWiFiSource(url="http://10.0.0.50:8080/video")
        cam.open()
        info = cam.info()
        assert isinstance(info, dict)
        assert info["source_type"] == "android_wifi"
        assert info["url"] == "http://10.0.0.50:8080/video"
        assert info["base_url"] == "http://10.0.0.50:8080"
        assert isinstance(info["resolution"], list)
        assert len(info["resolution"]) == 2
        assert info["is_opened"] is True

    @patch("cv2.VideoCapture")
    def test_info_before_open(self, mock_vc):
        """info() before open should show is_opened=False."""
        cam = AndroidWiFiSource()
        info = cam.info()
        assert info["is_opened"] is False
        assert info["resolution"] == [640, 480]

    # ── Context manager ───────────────────────────────────────

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_context_manager(self, mock_requests_get, mock_vc):
        """Context manager should open on enter and release on exit."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_cap = _mock_cap_opened()
        mock_vc.return_value = mock_cap

        with AndroidWiFiSource(url="http://10.0.0.50:8080/video") as cam:
            assert cam.is_opened() is True
            ret, frame = cam.read()
            assert ret is True

        assert cam.is_opened() is False
        mock_cap.release.assert_called_once()

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_context_manager_on_failure(self, mock_requests_get, mock_vc):
        """Context manager should not raise when connectivity fails."""
        mock_requests_get.return_value = _mock_requests_fail(status_code=503)

        with AndroidWiFiSource(url="http://10.0.0.50:8080/video") as cam:
            assert cam.is_opened() is False

        assert cam.is_opened() is False

    # ── Edge cases ────────────────────────────────────────────

    def test_is_opened_initial(self):
        """is_opened() before any operation should return False."""
        cam = AndroidWiFiSource()
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    @patch("requests.get")
    def test_can_open_twice(self, mock_requests_get, mock_vc):
        """Calling open() twice should succeed both times."""
        mock_requests_get.return_value = _mock_requests_ok()
        mock_vc.return_value = _mock_cap_opened()

        cam = AndroidWiFiSource()
        first = cam.open()
        second = cam.open()
        assert first is True
        assert second is True
        assert cam.is_opened() is True


# ═══════════════════════════════════════════════════════════════
#  Tests: iPhoneWiFiSource
# ═══════════════════════════════════════════════════════════════


class TestiPhoneWiFiSource:
    """Tests for iPhoneWiFiSource — iPhone via EpocCam Wi-Fi."""

    # ── Construction ──────────────────────────────────────────

    def test_default_construction(self):
        """Default RTSP URL and resolution should be set correctly."""
        cam = iPhoneWiFiSource()
        assert cam._rtsp_url == "http://192.168.1.101:8080/video"
        assert cam._width == 640
        assert cam._height == 480
        assert cam._cap is None

    def test_custom_url_construction(self):
        """Custom RTSP URL should be stored."""
        url = "http://10.0.0.60:8080/video"
        cam = iPhoneWiFiSource(rtsp_url=url)
        assert cam._rtsp_url == url

    # ── Metadata ──────────────────────────────────────────────

    def test_name(self):
        """Name should identify it as EpocCam."""
        cam = iPhoneWiFiSource()
        assert "iPhone (Wi-Fi)" in cam.name
        assert "EpocCam" in cam.name

    def test_source_type(self):
        """source_type should be 'iphone_wifi'."""
        cam = iPhoneWiFiSource()
        assert cam.source_type == "iphone_wifi"

    # ── Lifecycle — open / read / release ─────────────────────

    @patch("cv2.VideoCapture")
    def test_open_success(self, mock_vc, sample_frame):
        """open() should return True when VideoCapture is opened."""
        mock_vc.return_value = _mock_cap_opened(ret_read=True, frame=sample_frame)

        cam = iPhoneWiFiSource(rtsp_url="http://10.0.0.60:8080/video")
        result = cam.open()

        assert result is True
        assert cam.is_opened() is True
        mock_vc.assert_called_once_with("http://10.0.0.60:8080/video")

    @patch("cv2.VideoCapture")
    def test_open_failure(self, mock_vc):
        """open() should return False when VideoCapture cannot open."""
        mock_vc.return_value = _mock_cap_closed()

        cam = iPhoneWiFiSource(rtsp_url="http://10.0.0.60:8080/video")
        result = cam.open()

        assert result is False
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    def test_open_failure_exception(self, mock_vc):
        """open() should handle exceptions gracefully and return False."""
        mock_vc.side_effect = RuntimeError("Simulated crash")

        cam = iPhoneWiFiSource(rtsp_url="http://10.0.0.60:8080/video")
        result = cam.open()

        assert result is False
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    def test_read_success(self, mock_vc, sample_frame):
        """read() should return (True, frame) after successful open."""
        mock_vc.return_value = _mock_cap_opened(ret_read=True, frame=sample_frame)

        cam = iPhoneWiFiSource()
        cam.open()
        ret, frame = cam.read()

        assert ret is True
        assert frame is not None
        assert frame.shape == sample_frame.shape

    @patch("cv2.VideoCapture")
    def test_read_failure(self, mock_vc):
        """read() should return (False, None) when VideoCapture.read fails."""
        mock_vc.return_value = _mock_cap_opened(ret_read=False)

        cam = iPhoneWiFiSource()
        cam.open()
        ret, frame = cam.read()

        assert ret is False
        assert frame is None

    def test_read_before_open(self):
        """read() before open should return (False, None)."""
        cam = iPhoneWiFiSource()
        ret, frame = cam.read()
        assert ret is False
        assert frame is None

    @patch("cv2.VideoCapture")
    def test_release(self, mock_vc):
        """release() should close capture and set _cap to None."""
        mock_vc.return_value = _mock_cap_opened()

        cam = iPhoneWiFiSource()
        cam.open()
        assert cam.is_opened() is True
        cam.release()
        assert cam.is_opened() is False
        assert cam._cap is None
        # Double release should be a no-op
        cam.release()
        assert cam.is_opened() is False

    # ── Resolution management ─────────────────────────────────

    @patch("cv2.VideoCapture")
    def test_set_resolution(self, mock_vc):
        """set_resolution() should store and apply the requested size."""
        mock_vc.return_value = _mock_cap_opened()

        cam = iPhoneWiFiSource()
        cam.open()
        cam.set_resolution(1280, 720)
        assert cam._width == 1280
        assert cam._height == 720
        cam._cap.set.assert_any_call(3, 1280)
        cam._cap.set.assert_any_call(4, 720)

    @patch("cv2.VideoCapture")
    def test_get_resolution_before_open(self, mock_vc):
        """get_resolution() before open should return the default."""
        cam = iPhoneWiFiSource()
        w, h = cam.get_resolution()
        assert w == 640
        assert h == 480

    @patch("cv2.VideoCapture")
    def test_get_resolution_after_open(self, mock_vc):
        """get_resolution() after open should return the capture's resolution."""
        mock_vc.return_value = _mock_cap_opened()

        cam = iPhoneWiFiSource()
        cam.open()
        w, h = cam.get_resolution()
        assert w == 640
        assert h == 480

    # ── Info dict ─────────────────────────────────────────────

    @patch("cv2.VideoCapture")
    def test_info_format(self, mock_vc):
        """info() should return the expected keys and types."""
        mock_vc.return_value = _mock_cap_opened()

        cam = iPhoneWiFiSource(rtsp_url="http://10.0.0.60:8080/video")
        cam.open()
        info = cam.info()
        assert isinstance(info, dict)
        assert info["source_type"] == "iphone_wifi"
        assert info["rtsp_url"] == "http://10.0.0.60:8080/video"
        assert isinstance(info["resolution"], list)
        assert len(info["resolution"]) == 2
        assert info["is_opened"] is True

    @patch("cv2.VideoCapture")
    def test_info_before_open(self, mock_vc):
        """info() before open should show is_opened=False."""
        cam = iPhoneWiFiSource()
        info = cam.info()
        assert info["is_opened"] is False
        assert info["resolution"] == [640, 480]

    # ── Context manager ───────────────────────────────────────

    @patch("cv2.VideoCapture")
    def test_context_manager(self, mock_vc):
        """Context manager should open on enter and release on exit."""
        mock_cap = _mock_cap_opened()
        mock_vc.return_value = mock_cap

        with iPhoneWiFiSource(rtsp_url="http://10.0.0.60:8080/video") as cam:
            assert cam.is_opened() is True
            ret, frame = cam.read()
            assert ret is True

        assert cam.is_opened() is False
        mock_cap.release.assert_called_once()

    @patch("cv2.VideoCapture")
    def test_context_manager_on_failure(self, mock_vc):
        """Context manager should not raise when open() fails."""
        mock_vc.return_value = _mock_cap_closed()

        with iPhoneWiFiSource(rtsp_url="http://10.0.0.60:8080/video") as cam:
            assert cam.is_opened() is False

        assert cam.is_opened() is False

    # ── Edge cases ────────────────────────────────────────────

    def test_is_opened_initial(self):
        """is_opened() before any operation should return False."""
        cam = iPhoneWiFiSource()
        assert cam.is_opened() is False

    @patch("cv2.VideoCapture")
    def test_can_open_twice(self, mock_vc):
        """Calling open() twice should succeed both times."""
        mock_cap = _mock_cap_opened()
        mock_vc.return_value = mock_cap

        cam = iPhoneWiFiSource()
        first = cam.open()
        second = cam.open()
        assert first is True
        assert second is True
        assert cam.is_opened() is True

    @patch("cv2.VideoCapture")
    def test_read_after_release(self, mock_vc):
        """read() after release() should return (False, None)."""
        mock_vc.return_value = _mock_cap_opened()

        cam = iPhoneWiFiSource()
        cam.open()
        cam.release()
        ret, frame = cam.read()
        assert ret is False
        assert frame is None
