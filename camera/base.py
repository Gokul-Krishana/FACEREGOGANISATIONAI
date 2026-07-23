"""
Camera Interface — Abstract Base Class
=======================================

Defines the unified ``CameraSource`` protocol that every camera
implementation must satisfy. The AI pipeline never needs to know
whether a frame came from a laptop webcam, Android, or iPhone.

Usage::

    from camera import CameraSource, create_camera

    # Factory method
    cam = create_camera(source_type="webcam", device_id=0)

    # Polymorphic usage
    while True:
        ret, frame = cam.read()
        if not ret:
            break
        pipeline.process_frame(frame)

    cam.release()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import cv2
import numpy as np


class CameraSource(ABC):
    """Abstract camera source that all implementations must follow."""

    # ── Metadata ──────────────────────────────────────────────────
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable camera name (e.g. ``"Laptop Webcam"``)."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Short slug identifying the source type (e.g. ``"webcam"``, ``"android_wifi"``)."""

    # ── Lifecycle ─────────────────────────────────────────────────
    @abstractmethod
    def open(self) -> bool:
        """Open the camera connection.

        Returns:
            ``True`` if the connection was successfully established.
        """

    @abstractmethod
    def release(self) -> None:
        """Close the camera and free resources."""

    # ── Frame Capture ─────────────────────────────────────────────
    @abstractmethod
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read a single frame from the camera.

        Returns:
            Tuple of ``(success: bool, frame: np.ndarray | None)``.
            ``frame`` is a BGR image if ``success`` is ``True``.
        """

    # ── Properties ────────────────────────────────────────────────
    @abstractmethod
    def is_opened(self) -> bool:
        """Check whether the camera connection is active."""

    @abstractmethod
    def set_resolution(self, width: int, height: int) -> None:
        """Request a specific capture resolution."""

    @abstractmethod
    def get_resolution(self) -> Tuple[int, int]:
        """Get the current capture resolution ``(width, height)``."""

    # ── Info ──────────────────────────────────────────────────────
    @abstractmethod
    def info(self) -> dict:
        """Return diagnostic metadata about this camera source."""


class CameraError(Exception):
    """Raised when a camera operation fails."""
