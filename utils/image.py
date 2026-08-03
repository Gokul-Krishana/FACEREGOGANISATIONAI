"""
Image processing utilities.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


def read_image(path: str) -> Optional[np.ndarray]:
    """Read an image file safely. Returns None on failure."""
    img = cv2.imread(str(path))
    if img is None:
        print(f"Warning: Could not read image at {path}")
    return img


def save_image(path: str, img: np.ndarray) -> bool:
    """Save an image, creating parent directories if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return cv2.imwrite(str(path), img)


def resize_to_height(img: np.ndarray, target_height: int) -> np.ndarray:
    """Resize an image preserving aspect ratio to a target height."""
    h, w = img.shape[:2]
    scale = target_height / h
    new_width = int(w * scale)
    return cv2.resize(img, (new_width, target_height))


def draw_rounded_rect(
    img: np.ndarray,
    top_left: Tuple[int, int],
    bottom_right: Tuple[int, int],
    color: Tuple[int, int, int],
    thickness: int = 2,
    radius: int = 10,
) -> None:
    """Draw a rounded rectangle on an image."""
    x1, y1 = top_left
    x2, y2 = bottom_right

    # Top edge
    cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness)
    # Bottom edge
    cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness)
    # Left edge
    cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness)
    # Right edge
    cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness)
    # Corners
    cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness)
    cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness)
    cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness)
    cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness)
