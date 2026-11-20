"""Camera Abstraction Layer — Multi-source camera support.

Provides a unified interface for:
- Laptop webcam (DirectShow, MSMF, V4L2)
- Android phone (USB via DroidCam / Wi-Fi via IP Webcam)
- iPhone (USB via EpocCam / Wi-Fi via EpocCam)
- USB Webcam (generic)
- Resilient fault-tolerant reconnecting wrapper
"""

from camera.base import CameraSource
from camera.selector import create_camera, CAMERA_CHOICES, CAMERA_REGISTRY
from camera.resilient import ResilientCameraSource, CameraState, CameraHealthMetrics

__all__ = [
    "CameraSource",
    "create_camera",
    "CAMERA_CHOICES",
    "CAMERA_REGISTRY",
    "ResilientCameraSource",
    "CameraState",
    "CameraHealthMetrics",
]
