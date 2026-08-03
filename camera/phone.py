"""
Phone Camera Implementation — Android & iPhone
===============================================

Supports four phone camera modes matching the architecture diagram:

1. **Android USB**  — Via DroidCam (``droidcam://`` or OpenCV index)
2. **Android Wi-Fi** — Via IP Webcam app (HTTP/RTSP stream)
3. **iPhone USB**    — Via EpocCam or DroidCam OBS (virtual camera)
4. **iPhone Wi-Fi**  — Via EpocCam Wi-Fi (RTSP/HTTP stream)

Usage::

    from camera.phone import AndroidWiFiSource, iPhoneUSBSource

    # Android IP Webcam (Wi-Fi)
    cam = AndroidWiFiSource(url="http://192.168.1.100:8080/video")
    cam.open()
    ret, frame = cam.read()
    cam.release()
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import cv2
import numpy as np
import requests

from camera.base import CameraSource, CameraError
from utils.logging_setup import get_logger, redact_url

logger = get_logger(__name__)


# ==================================================================
# Android — Wi-Fi (IP Webcam)
# ==================================================================

class AndroidWiFiSource(CameraSource):
    """Android phone camera via IP Webcam HTTP stream.

    Install `IP Webcam <https://play.google.com/store/apps/details?id=com.pas.webcam>`_
    on your Android device and start the server. The URL is shown in the app.

    Args:
        url: IP Webcam video URL (e.g. ``http://192.168.1.100:8080/video``).
    """

    def __init__(self, url: str = "http://192.168.1.100:8080/video") -> None:
        self._url = url
        self._cap: Optional[cv2.VideoCapture] = None
        self._width: int = 640
        self._height: int = 480
        self._base_url = self._parse_base_url(url)

    @staticmethod
    def _parse_base_url(url: str) -> str:
        """Extract base URL from video URL (e.g. ``http://192.168.1.100:8080``)."""
        parts = url.split("/video")
        return parts[0] if parts else url

    @property
    def name(self) -> str:
        return f"Android (Wi-Fi) — {self._base_url}"

    @property
    def source_type(self) -> str:
        return "android_wifi"

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self) -> bool:
        """Test connectivity and open the MJPEG stream."""
        # First test if the IP Webcam is reachable
        try:
            resp = requests.get(self._base_url, timeout=5)
            if resp.status_code != 200:
                logger.warning("IP Webcam server unreachable (HTTP %s)", resp.status_code)
                return False
            logger.info("IP Webcam reachable at %s", redact_url(self._base_url))
        except requests.RequestException as exc:
            logger.error("IP Webcam connection failed: %s", redact_url(str(exc)))
            return False

        # Open the video stream via OpenCV
        self._cap = cv2.VideoCapture(self._url)
        if not self._cap.isOpened():
            logger.error("Failed to open IP Webcam video stream")
            return False

        self.set_resolution(self._width, self._height)
        logger.info("IP Webcam stream opened from %s", redact_url(self._url))
        return True

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
            "url": self._url,
            "base_url": self._base_url,
            "resolution": list(self.get_resolution()),
            "is_opened": self.is_opened(),
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()


# ==================================================================
# Android — USB (DroidCam)
# ==================================================================

class AndroidUSBSource(CameraSource):
    """Android phone camera via DroidCam USB connection.

    Install `DroidCam <https://www.dev47apps.com/>`_ on both your
    Android device and computer. Connect via USB, open DroidCam,
    and select **USB** mode. The camera appears as an OpenCV device.

    Args:
        droidcam_ip: IP of the DroidCam WiFi endpoint (optional fallback).
        device_id: OpenCV device index if detected.
    """

    def __init__(self, droidcam_ip: str = "192.168.1.100:4747",
                 device_id: int = 1) -> None:
        self._droidcam_ip = droidcam_ip
        self._device_id = device_id
        self._cap: Optional[cv2.VideoCapture] = None
        self._mode: str = "usb"  # "usb" or "wifi"
        self._width: int = 640
        self._height: int = 480

    @property
    def name(self) -> str:
        return f"Android (USB) — DroidCam #{self._device_id}"

    @property
    def source_type(self) -> str:
        return "android_usb"

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self) -> bool:
        """Try USB first (OpenCV device index), then Wi-Fi fallback."""
        # Try USB mode
        try:
            cap = cv2.VideoCapture(self._device_id, cv2.CAP_DSHOW)
            if cap.isOpened():
                self._cap = cap
                self._mode = "usb"
                self.set_resolution(self._width, self._height)
                logger.info("DroidCam USB opened at device #%s", self._device_id)
                return True
        except Exception:
            pass

        # Fallback: Wi-Fi mode (DroidCam TCP stream)
        try:
            wifi_url = f"http://{self._droidcam_ip}/video"
            cap = cv2.VideoCapture(wifi_url)
            if cap.isOpened():
                self._cap = cap
                self._mode = "wifi"
                logger.info("DroidCam Wi-Fi fallback at %s", redact_url(wifi_url))
                return True
        except Exception:
            pass

        logger.warning("DroidCam not found (tried USB and Wi-Fi)")
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
            "mode": self._mode,
            "device_id": self._device_id,
            "droidcam_ip": self._droidcam_ip,
            "resolution": list(self.get_resolution()),
            "is_opened": self.is_opened(),
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()


# ==================================================================
# iPhone — Wi-Fi (EpocCam)
# ==================================================================

class iPhoneWiFiSource(CameraSource):
    """iPhone camera via EpocCam Wi-Fi.

    Install `EpocCam <https://www.elgato.com/us/en/s/epoccam>`_ on
    your iPhone and computer. Connect both to the same Wi-Fi network.
    Open EpocCam on the iPhone — it streams via RTSP.

    Args:
        rtsp_url: EpocCam RTSP URL (default format shown).
    """

    def __init__(self, rtsp_url: str = "http://192.168.1.101:8080/video") -> None:
        self._rtsp_url = rtsp_url
        self._cap: Optional[cv2.VideoCapture] = None
        self._width: int = 640
        self._height: int = 480

    @property
    def name(self) -> str:
        return f"iPhone (Wi-Fi) — EpocCam"

    @property
    def source_type(self) -> str:
        return "iphone_wifi"

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self) -> bool:
        try:
            self._cap = cv2.VideoCapture(self._rtsp_url)
            if self._cap.isOpened():
                self.set_resolution(self._width, self._height)
                logger.info("EpocCam stream opened at %s", redact_url(self._rtsp_url))
                return True
        except Exception as exc:
            logger.error("EpocCam connection failed: %s", redact_url(str(exc)))
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
            "rtsp_url": self._rtsp_url,
            "resolution": list(self.get_resolution()),
            "is_opened": self.is_opened(),
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()


# ==================================================================
# IP Camera — Generic RTSP/HTTP/MJPEG stream
# ==================================================================

class IPCameraSource(CameraSource):
    """Generic IP / network camera via RTSP, HTTP MJPEG, or ONVIF stream.

    Works with:
    - **RTSP cameras** (most IP security cameras, e.g. Hikvision, Dahua, Reolink)
    - **HTTP MJPEG streams** (many network cameras serve MJPEG over HTTP)
    - **Generic ONVIF cameras** (if they expose an RTSP or HTTP stream)
    - **NDI / HDMI capture cards** (via their HTTP or RTSP output)

    Args:
        url: Full stream URL. Examples::

            http://192.168.1.200:8080/video       # MJPEG over HTTP
            rtsp://admin:password@192.168.1.200:554/stream1  # RTSP
            http://192.168.1.200/videostream.cgi  # Some IP cameras

    .. tip::

       Most IP cameras expose their RTSP URL as
       ``rtsp://<username>:<password>@<ip>:554/stream1``.
       Check the camera's documentation for the exact URL format.
    """

    def __init__(self, url: str = "http://192.168.1.200:8080/video") -> None:
        self._url = url
        self._cap: Optional[cv2.VideoCapture] = None
        self._width: int = 640
        self._height: int = 480

    @property
    def name(self) -> str:
        return f"IP Camera — {self._url}"

    @property
    def source_type(self) -> str:
        return "ip_camera"

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self) -> bool:
        """Open the IP camera stream."""
        try:
            self._cap = cv2.VideoCapture(self._url)
            if self._cap.isOpened():
                self.set_resolution(self._width, self._height)
                logger.info("IP camera stream opened: %s", redact_url(self._url))
                return True
        except Exception as exc:
            logger.error("IP camera failed to open: %s", redact_url(str(exc)))
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
            "url": self._url,
            "resolution": list(self.get_resolution()),
            "is_opened": self.is_opened(),
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()


# ==================================================================
# iPhone — USB (EpocCam / Camera)
# ==================================================================

class iPhoneUSBSource(CameraSource):
    """iPhone camera via USB.

    EpocCam and DroidCam OBS both provide a virtual DirectShow camera
    when connected via USB. This typically appears as a high device
    index (e.g., device 2 or 3).

    Args:
        device_id: OpenCV device index for the iPhone virtual camera.
    """

    def __init__(self, device_id: int = 2) -> None:
        self._device_id = device_id
        self._cap: Optional[cv2.VideoCapture] = None
        self._width: int = 640
        self._height: int = 480

    @property
    def name(self) -> str:
        return f"iPhone (USB) — Device #{self._device_id}"

    @property
    def source_type(self) -> str:
        return "iphone_usb"

    # ── Lifecycle ─────────────────────────────────────────────────
    def open(self) -> bool:
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (None, "Default"),
        ]
        for backend, backend_name in backends:
            try:
                if backend is None:
                    cap = cv2.VideoCapture(self._device_id)
                else:
                    cap = cv2.VideoCapture(self._device_id, backend)
                if cap.isOpened():
                    self._cap = cap
                    self.set_resolution(self._width, self._height)
                    logger.info("iPhone USB camera opened via %s", backend_name)
                    return True
            except Exception:
                continue
        return False

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

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
            "device_id": self._device_id,
            "resolution": list(self.get_resolution()),
            "is_opened": self.is_opened(),
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.release()
