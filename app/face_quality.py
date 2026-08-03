"""
Face Quality Assessment Module
================================

Evaluates the quality of a detected face image before passing it to
recognition. Poor-quality faces (blurry, too dark/bright, too small,
extreme angles) are flagged so the AMFR engine can down-weight them
or request additional frames.

Metrics:
    - **Blur score**: Laplacian variance, mapped to [0, 1].
    - **Brightness score**: Mean pixel intensity, penalising under/over exposure.
    - **Face size score**: Face bounding-box area relative to the image.
    - **Detection score**: RetinaFace ``det_score`` (confidence a face exists).
    - **Pose score**: Head-pose estimate from facial landmarks.
    - **Contrast score**: Standard deviation of pixel intensities.

Pipeline role:  YOLO → RetinaFace → **FaceQuality** → Liveness → ArcFace → FAISS → AMFR
                                        ↑
                                   You are here
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config.config as cfg


# ── Default Weights ──────────────────────────────────────────────────
# How much each metric contributes to the overall quality score.
_DEFAULT_QUALITY_WEIGHTS: Dict[str, float] = {
    "blur_score": 0.30,
    "brightness_score": 0.15,
    "contrast_score": 0.10,
    "face_size_score": 0.15,
    "det_score": 0.20,
    "pose_score": 0.10,
}

# Soft thresholds (below this → score starts dropping)
_BLUR_LAPLACIAN_MIN = 50.0  # Min Laplacian variance for a sharp face
_BRIGHTNESS_IDEAL = 128.0  # Ideal mean pixel value
_BRIGHTNESS_TOLERANCE = 60.0  # Allowed deviation from ideal
_FACE_SIZE_MIN_RATIO = 0.02  # Minimum face area / image area
_FACE_SIZE_IDEAL_RATIO = 0.08  # Ideal ratio
_CONTRAST_MIN = 30.0  # Min pixel stddev


class FaceQualityAssessment:
    """Assesses face-image quality across multiple dimensions.

    Usage::

        fqa = FaceQualityAssessment()

        result = fqa.assess(
            face_img=person_crop,
            det_score=0.98,
            face_bbox=(100, 50, 200, 180),
            img_shape=(480, 640),
            landmarks=[[x,y], ...],
        )
        # result["overall"]  → 0.87
        # result["metrics"]  → {"blur_score": 0.92, ...}
        # result["passed"]   → True / False
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = weights or dict(_DEFAULT_QUALITY_WEIGHTS)

    # ── Public API ────────────────────────────────────────────

    def assess(
        self,
        face_img: np.ndarray,
        det_score: float,
        face_bbox: Optional[Tuple[int, int, int, int]] = None,
        img_shape: Optional[Tuple[int, int]] = None,
        landmarks: Optional[np.ndarray] = None,
    ) -> Dict:
        """Run all quality checks and return a composite score.

        Args:
            face_img: BGR face crop.
            det_score: RetinaFace detection confidence (0–1).
            face_bbox: ``(x1, y1, x2, y2)`` of the face within the crop.
            img_shape: ``(height, width)`` of the *original* frame.
            landmarks: 5-point facial landmarks ``(5, 2)``.

        Returns:
            Dict with ``overall``, ``passed``, ``metrics``, and
            ``failure_reasons``.
        """
        if face_img is None or face_img.size == 0:
            return {
                "overall": 0.0,
                "passed": False,
                "metrics": {},
                "failure_reasons": ["empty_face"],
            }

        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        h, w = face_img.shape[:2]

        # Compute individual metrics
        blur_score = self._assess_blur(gray)
        brightness_score = self._assess_brightness(gray)
        contrast_score = self._assess_contrast(gray)
        det_score_val = self._assess_det_score(det_score)

        metrics: Dict[str, float] = {
            "blur_score": blur_score,
            "brightness_score": brightness_score,
            "contrast_score": contrast_score,
            "det_score": det_score_val,
        }

        # Optional: face size relative to original frame
        if face_bbox is not None and img_shape is not None:
            size_score = self._assess_face_size(face_bbox, img_shape)
            metrics["face_size_score"] = size_score
        else:
            size_score = None

        # Optional: pose from landmarks
        if landmarks is not None and len(landmarks) == 5:
            pose_score = self._assess_pose(landmarks)
            metrics["pose_score"] = pose_score
        else:
            pose_score = None

        # Weighted composite
        total_weight = 0.0
        weighted_sum = 0.0
        for key, weight in self.weights.items():
            if key in metrics:
                weighted_sum += metrics[key] * weight
                total_weight += weight

        overall = weighted_sum / total_weight if total_weight > 0 else 0.5
        overall = float(np.clip(overall, 0.0, 1.0))

        # Failure reasons (any metric below 0.3 is a concern)
        failure_reasons: List[str] = []
        if blur_score < 0.3:
            failure_reasons.append("blurry")
        if brightness_score < 0.3:
            failure_reasons.append("poor_lighting")
        if contrast_score < 0.3:
            failure_reasons.append("low_contrast")
        if size_score is not None and size_score < 0.2:
            failure_reasons.append("face_too_small")
        if pose_score is not None and pose_score < 0.3:
            failure_reasons.append("extreme_angle")

        return {
            "overall": round(overall, 4),
            "passed": overall >= cfg.FACE_QUALITY_MIN_SCORE,
            "metrics": {k: round(v, 4) for k, v in metrics.items()},
            "failure_reasons": failure_reasons,
        }

    # ── Individual Metrics ────────────────────────────────────

    @staticmethod
    def _assess_blur(gray: np.ndarray) -> float:
        """Blur score via Laplacian variance.

        Higher Laplacian variance = more edges = sharper image.

        Returns:
            0.0 (blurry) → 1.0 (very sharp).
        """
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        if laplacian_var >= _BLUR_LAPLACIAN_MIN * 4:
            return 1.0
        if laplacian_var <= 0:
            return 0.0

        # Smooth sigmoid-like mapping
        ratio = laplacian_var / _BLUR_LAPLACIAN_MIN
        score = 1.0 - np.exp(-ratio * 1.2)
        return float(np.clip(score, 0.0, 1.0))

    @staticmethod
    def _assess_brightness(gray: np.ndarray) -> float:
        """Brightness score — penalise under/over-exposed faces.

        Returns:
            0.0 (too dark/bright) → 1.0 (ideal exposure).
        """
        mean = float(np.mean(gray))

        if mean < 30 or mean > 225:
            return 0.15  # Extremely bad
        deviation = abs(mean - _BRIGHTNESS_IDEAL)
        if deviation <= _BRIGHTNESS_TOLERANCE:
            return 1.0
        # Linear decay beyond tolerance
        excess = deviation - _BRIGHTNESS_TOLERANCE
        score = max(0.15, 1.0 - excess / (_BRIGHTNESS_IDEAL - _BRIGHTNESS_TOLERANCE))
        return float(score)

    @staticmethod
    def _assess_contrast(gray: np.ndarray) -> float:
        """Contrast score via pixel standard deviation.

        Returns:
            0.0 (flat / washed out) → 1.0 (good contrast).
        """
        std = float(np.std(gray))

        if std >= _CONTRAST_MIN * 3:
            return 1.0
        if std <= 0:
            return 0.0

        ratio = std / _CONTRAST_MIN
        score = 1.0 - np.exp(-ratio * 1.5)
        return float(np.clip(score, 0.0, 1.0))

    @staticmethod
    def _assess_face_size(
        face_bbox: Tuple[int, int, int, int],
        img_shape: Tuple[int, int],
    ) -> float:
        """Face size score — larger faces (up to a point) score higher.

        Returns:
            0.0 (tiny / huge) → 1.0 (ideal size).
        """
        x1, y1, x2, y2 = face_bbox
        face_area = (x2 - x1) * (y2 - y1)
        img_area = img_shape[0] * img_shape[1]
        ratio = face_area / max(img_area, 1)

        if ratio < 0.005:
            return 0.05  # Essentially invisible
        if ratio < _FACE_SIZE_MIN_RATIO:
            # Ramp from 0.05 → 0.4
            return float(0.05 + (ratio / _FACE_SIZE_MIN_RATIO) * 0.35)

        ideal = _FACE_SIZE_IDEAL_RATIO
        if ratio <= ideal:
            return float(0.4 + (ratio / ideal) * 0.6)

        # Larger than ideal — still ok but slightly penalised
        if ratio <= 0.25:
            return float(1.0 - (ratio - ideal) / (0.25 - ideal) * 0.2)
        return 0.6  # Very large face

    @staticmethod
    def _assess_det_score(det_score: float) -> float:
        """Map RetinaFace detection confidence to a quality sub-score.

        ``det_score`` is already 0–1; we just pass it through with
        a soft floor so very low-confidence detections still get a
        non-zero but low score.
        """
        return float(max(min(det_score, 1.0), 0.0))

    @staticmethod
    def _assess_pose(landmarks: np.ndarray) -> float:
        """Estimate head-pose quality from 5 facial landmarks.

        Uses the symmetry of eye positions and the nose-mouth triangle
        to estimate whether the face is roughly frontal.

        Args:
            landmarks: ``(5, 2)`` array of ``(x, y)`` points in order:
                       left-eye, right-eye, nose, left-mouth, right-mouth.

        Returns:
            0.0 (profile / extreme angle) → 1.0 (frontal).
        """
        if landmarks.shape != (5, 2):
            return 0.5  # Can't assess — return neutral

        left_eye, right_eye, nose, left_mouth, right_mouth = landmarks

        # 1. Eye symmetry: left/right eye y-coordinates should be similar
        eye_y_diff = abs(float(left_eye[1] - right_eye[1]))
        eye_dist = np.linalg.norm(left_eye - right_eye)
        if eye_dist < 1:
            return 0.3  # Eyes too close — probably not a usable face
        eye_symmetry = max(0.0, 1.0 - eye_y_diff / (eye_dist * 0.5))

        # 2. Nose centered between eyes
        eye_center_x = (left_eye[0] + right_eye[0]) / 2.0
        nose_offset = abs(float(nose[0] - eye_center_x)) / max(float(eye_dist), 1)
        nose_centered = max(0.0, 1.0 - nose_offset * 2.0)

        # 3. Mouth symmetry (similar to eyes)
        mouth_y_diff = abs(float(left_mouth[1] - right_mouth[1]))
        mouth_dist = np.linalg.norm(left_mouth - right_mouth)
        mouth_symmetry = (
            max(0.0, 1.0 - mouth_y_diff / (max(float(mouth_dist), 1) * 0.5)) if mouth_dist > 1 else 0.5
        )

        combined = eye_symmetry * 0.4 + nose_centered * 0.4 + mouth_symmetry * 0.2  # type: ignore[operator]
        return float(np.clip(combined * 0.9, 0.0, 1.0))
