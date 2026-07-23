"""
Face Alignment Module — RetinaFace Landmark-based Alignment
===========================================================

Uses the 5 facial landmarks detected by RetinaFace (eyes, nose, mouth
corners) to perform an affine transformation that normalizes the face
to a canonical orientation.

This significantly improves ArcFace recognition accuracy because:
- The embedding model sees faces at a consistent angle
- Variations in head pose are removed before feature extraction
- Matching is more robust across different camera angles

Pipeline role:  YOLO → RetinaFace → **Face Alignment** → ArcFace → FAISS
                                        ↑
                                   You are here
"""

from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


# Canonical face landmarks (in normalized coordinates [0, 1]):
#   [left_eye, right_eye, nose, left_mouth, right_mouth]
CANONICAL_LANDMARKS = np.array([
    [0.315, 0.350],  # Left eye
    [0.685, 0.350],  # Right eye
    [0.500, 0.500],  # Nose tip
    [0.370, 0.650],  # Left mouth corner
    [0.630, 0.650],  # Right mouth corner
], dtype=np.float64)

# Output face size (pixels)
ALIGN_SIZE = 224


def align_face(
    img: np.ndarray,
    landmarks: np.ndarray,
    output_size: int = ALIGN_SIZE,
) -> Optional[np.ndarray]:
    """Align a face using an affine transform based on facial landmarks.

    The function estimates a similarity transformation (rotation + scale +
    translation) that maps the detected landmarks to canonical positions,
    then warps the face region to a fixed size.

    Args:
        img: Source BGR image containing the face.
        landmarks: (5, 2) array of (x, y) landmark coordinates from
                   RetinaFace (left_eye, right_eye, nose, left_mouth, right_mouth).
        output_size: Size of the output square face crop (default 224).

    Returns:
        Aligned BGR face image of shape ``(output_size, output_size, 3)``,
        or ``None`` if alignment fails.
    """
    if landmarks is None or len(landmarks) != 5:
        return None

    landmarks = landmarks.astype(np.float64)

    # Scale canonical landmarks to the desired output size
    target_pts = CANONICAL_LANDMARKS * output_size

    # Estimate the similarity transform (partial affine: rotation, scale, translation)
    try:
        transform_matrix, _ = cv2.estimateAffinePartial2D(
            landmarks,
            target_pts,
            method=cv2.LMEDS,  # Robust to outliers
        )
    except cv2.error:
        return None

    if transform_matrix is None:
        return None

    # Apply the warp
    aligned = cv2.warpAffine(
        img,
        transform_matrix,
        (output_size, output_size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )

    return aligned


def align_face_from_bbox(
    img: np.ndarray,
    bbox: Tuple[int, int, int, int],
    landmarks: np.ndarray,
    output_size: int = ALIGN_SIZE,
    padding: float = 0.2,
) -> Optional[np.ndarray]:
    """Align and crop a face from a bounding box with padding.

    First pads the bounding box, then applies alignment. Useful when
    you have the YOLO person bbox and RetinaFace landmarks separately.

    Args:
        img: Source BGR image.
        bbox: (x1, y1, x2, y2) bounding box of the face or person.
        landmarks: (5, 2) RetinaFace landmarks.
        output_size: Output alignment size.
        padding: Fractional padding to add around the face bbox.

    Returns:
        Aligned face crop or ``None``.
    """
    x1, y1, x2, y2 = bbox
    h, w = img.shape[:2]

    # Add padding
    pad_w = int((x2 - x1) * padding)
    pad_h = int((y2 - y1) * padding)

    x1 = max(0, x1 - pad_w)
    y1 = max(0, y1 - pad_h)
    x2 = min(w, x2 + pad_w)
    y2 = min(h, y2 + pad_h)

    face_crop = img[y1:y2, x1:x2]

    # Adjust landmarks relative to the cropped region
    adjusted_landmarks = landmarks.copy()
    adjusted_landmarks[:, 0] -= x1
    adjusted_landmarks[:, 1] -= y1

    return align_face(face_crop, adjusted_landmarks, output_size)


def normalize_intensity(img: np.ndarray) -> np.ndarray:
    """Apply basic photometric normalization to a face image.

    Uses CLAHE (Contrast Limited Adaptive Histogram Equalization) on
    the luminance channel to reduce lighting variation effects.

    Args:
        img: BGR face image.

    Returns:
        Normalized BGR image.
    """
    # Convert to LAB color space
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # Apply CLAHE to L-channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_eq = clahe.apply(l)

    # Merge back
    lab_eq = cv2.merge([l_eq, a, b])
    return cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)
