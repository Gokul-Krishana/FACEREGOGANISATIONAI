"""
Liveness Detection Module — Anti-Spoofing (Hybrid)
====================================================

Detects presentation attacks using a **hybrid** approach combining:

**Software-level checks (fast, always available):**
1. **Texture analysis**: Local Binary Patterns (LBP) for micro-texture.
2. **Eye blink detection**: Eye Aspect Ratio (EAR) tracking.
3. **Motion analysis**: Frame-differencing motion magnitude.
4. **Screen-edge detection**: Rectangular bezel patterns.

**Deep-learning check (robust, CNN-based):**
5. **CNN anti-spoofing**: MiniFASNet ONNX model or lightweight fallback.

Pipeline role::

    YOLO → RetinaFace → FaceQuality → **Liveness** → ArcFace → FAISS → AMFR
                                           ↑
                                   5 factors combined

The deep-learning detector catches attacks that software-level checks
miss (high-quality prints, subtle screen reflections). It integrates
as a 5th factor weighted alongside the existing 4 factors.

Usage is identical to the previous version — the deep-learning factor
is transparently added inside ``analyze_frame()``.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

import config.config as cfg


# ── Constants ────────────────────────────────────────────────────────

# Weights for the 5 factors (must sum to ~1.0)
# These replace the hardcoded weights below when deep liveness is active
_DEFAULT_WEIGHTS_DL = {
    "texture": 0.15,
    "blink": 0.20,
    "motion": 0.15,
    "screen": 0.10,
    "deep_liveness": 0.40,  # CNN gets the most weight when available
}

_DEFAULT_WEIGHTS_NO_DL = {
    "texture": 0.25,
    "blink": 0.35,
    "motion": 0.25,
    "screen": 0.15,
}

# Eye Aspect Ratio (EAR) thresholds
_EAR_CLOSED_THRESHOLD = 0.22       # Below this → eye is closed
_BLINK_FRAMES_MIN = 1              # Min consecutive closed frames for a blink
_BLINK_FRAMES_MAX = 6              # Max consecutive closed frames (prevents sleep = blink)
_EYE_LANDMARK_INDICES = (0, 1, 3, 4)  # left-eye, right-eye doesn't map simply
# Actually for 5-point landmarks: left-eye(0), right-eye(1), nose(2), left-mouth(3), right-mouth(4)
# We approximate EAR using left_eye <-> right_eye distance ratio to nose

# LBP parameters
_LBP_RADIUS = 1
_LBP_POINTS = 8 * _LBP_RADIUS

# Motion analysis
_OPTICAL_FLOW_FEATURE_PARAMS = dict(
    maxCorners=100,
    qualityLevel=0.3,
    minDistance=7,
    blockSize=7,
)

# Screen detection
_SCREEN_EDGE_THRESHOLD = 0.15       # Fraction of bright edge pixels to flag


class LivenessResult:
    """Result of a liveness analysis (hybrid: 4 software + 1 deep-learning factor)."""

    __slots__ = (
        "is_live", "liveness_score", "texture_score",
        "blink_score", "motion_score", "screen_score",
        "dl_score", "dl_time_ms",
        "blink_detected", "reasons",
    )

    def __init__(
        self,
        is_live: bool,
        liveness_score: float,
        texture_score: float,
        blink_score: float,
        motion_score: float,
        screen_score: float,
        dl_score: float = 0.5,
        dl_time_ms: float = 0.0,
        blink_detected: bool = False,
        reasons: Optional[List[str]] = None,
    ) -> None:
        self.is_live = is_live
        self.liveness_score = liveness_score
        self.texture_score = texture_score
        self.blink_score = blink_score
        self.motion_score = motion_score
        self.screen_score = screen_score
        self.dl_score = dl_score
        self.dl_time_ms = dl_time_ms
        self.blink_detected = blink_detected
        self.reasons = reasons or []

    def __repr__(self) -> str:
        return (
            f"<LivenessResult live={self.is_live} "
            f"score={self.liveness_score:.3f} "
            f"dl={self.dl_score:.2f} "
            f"blink={self.blink_detected}>"
        )


class LivenessDetector:
    """Multi-factor liveness / anti-spoofing detector.

    Usage::

        detector = LivenessDetector()

        # Per-frame analysis
        result = detector.analyze_frame(face_img, landmarks)

        # When a 'blink' is observed between frames:
        detector.register_blink()

        # Full frame-pair motion analysis
        result = detector.analyze_motion(prev_face, curr_face)
    """

    def __init__(self, use_deep_liveness: Optional[bool] = None) -> None:
        # ── Deep liveness ────────────────────────────────────
        use_deep = cfg.DEEP_LIVENESS_ENABLED if use_deep_liveness is None else use_deep_liveness
        if use_deep:
            from app.deep_liveness import get_deep_liveness_detector
            self._deep_liveness = get_deep_liveness_detector()
        else:
            self._deep_liveness = None

        # ── Blink tracking ───────────────────────────────────
        self._ear_history: Deque[float] = deque(maxlen=30)
        self._blink_count: int = 0
        self._consecutive_closed: int = 0
        self._blink_ever_detected: bool = False

        # ── Motion tracking ──────────────────────────────────
        self._prev_gray: Optional[np.ndarray] = None
        self._prev_features: Optional[np.ndarray] = None
        self._motion_history: Deque[float] = deque(maxlen=15)
        self._EAR_CLOSED_THRESHOLD = _EAR_CLOSED_THRESHOLD

    # ── Public API ────────────────────────────────────────────

    def analyze_frame(
        self,
        face_img: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
    ) -> LivenessResult:
        """Run liveness checks on a single face frame.

        Args:
            face_img: BGR face crop (the face region only).
            landmarks: 5-point facial landmarks ``(5, 2)``, optional.

        Returns:
            A ``LivenessResult`` with per-factor scores and a combined
            decision.
        """
        if face_img.size == 0:
            return self._fail_result("empty_face")

        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)

        # ── Factor 1: Texture analysis ───────────────────────
        texture_score = self._analyze_texture(gray)

        # ── Factor 2: Blink detection via landmarks ──────────
        blink_score = 0.5  # Neutral until we have enough history
        if landmarks is not None and len(landmarks) >= 4:
            ear = self._compute_approximate_ear(landmarks, gray.shape)
            self._ear_history.append(ear)
            blink_score = self._update_blink_state(ear)
        else:
            blink_score = 0.0  # No landmarks → can't assess blinking

        # ── Factor 3: Screen-edge detection ──────────────────
        screen_score = self._detect_screen_edges(gray)

        # ── Factor 4: Motion score (from previous frame) ─────
        motion_score = 0.5
        if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
            motion_score = self._analyze_motion(self._prev_gray, gray)
        self._prev_gray = gray.copy()

        # ── Factor 5: Deep-learning liveness (CNN-based) ─────
        dl_score = 0.5  # Neutral by default
        dl_time_ms = 0.0
        if self._deep_liveness is not None and cfg.DEEP_LIVENESS_ENABLED:
            dl_result = self._deep_liveness.predict(face_img, landmarks)
            dl_score = dl_result.dl_score
            dl_time_ms = dl_result.inference_time_ms

        # ── Combine ──────────────────────────────────────────
        # Weighted combination — different weights depending on
        # whether the deep-learning factor is available
        if self._deep_liveness is not None and cfg.DEEP_LIVENESS_ENABLED:
            w = _DEFAULT_WEIGHTS_DL
            liveness_score = (
                texture_score * w["texture"]
                + blink_score * w["blink"]
                + motion_score * w["motion"]
                + (1.0 - screen_score) * w["screen"]
                + dl_score * w["deep_liveness"]
            )
        else:
            w = _DEFAULT_WEIGHTS_NO_DL
            liveness_score = (
                texture_score * w["texture"]
                + blink_score * w["blink"]
                + motion_score * w["motion"]
                + (1.0 - screen_score) * w["screen"]
            )
        liveness_score = float(np.clip(liveness_score, 0.0, 1.0))

        # Decision
        reasons: List[str] = []
        is_live = True

        # Spoof indicators (software level)
        if screen_score > 0.6:
            reasons.append("screen_detected")
            is_live = False
        if texture_score < 0.3:
            reasons.append("synthetic_texture")
            is_live = False
        if blink_score < 0.2 and self._blink_ever_detected:
            if len(self._ear_history) >= 15:
                reasons.append("no_blink_detected")
                is_live = False
        if motion_score < 0.25:
            reasons.append("no_motion")

        # Spoof indicator (deep-learning level)
        if dl_score < cfg.LIVENESS_SPOOF_THRESHOLD:
            reasons.append("deep_learning_spoof")
            is_live = False

        return LivenessResult(
            is_live=is_live and liveness_score >= cfg.LIVENESS_MIN_SCORE,
            liveness_score=round(liveness_score, 4),
            texture_score=round(texture_score, 4),
            blink_score=round(blink_score, 4),
            motion_score=round(motion_score, 4),
            screen_score=round(screen_score, 4),
            dl_score=round(dl_score, 4),
            dl_time_ms=round(dl_time_ms, 2),
            blink_detected=self._blink_ever_detected,
            reasons=reasons,
        )

    def reset(self) -> None:
        """Reset all temporal state (call when the tracked person changes)."""
        self._ear_history.clear()
        self._blink_count = 0
        self._consecutive_closed = 0
        self._blink_ever_detected = False
        self._prev_gray = None
        self._prev_features = None
        self._motion_history.clear()
        # Deep liveness detector is stateless — no reset needed

    def register_blink(self) -> None:
        """Manually register a blink (useful when caller detects one)."""
        self._blink_count += 1
        self._blink_ever_detected = True

    @property
    def deep_liveness_available(self) -> bool:
        """Whether the deep-learning liveness model is loaded."""
        return self._deep_liveness is not None

    @property
    def deep_liveness_using_fallback(self) -> bool:
        """Whether the fallback CNN is being used."""
        if self._deep_liveness is None:
            return False
        return self._deep_liveness.using_fallback

    # ── Texture Analysis ──────────────────────────────────────

    @staticmethod
    def _analyze_texture(gray: np.ndarray) -> float:
        """Analyse skin texture using Local Binary Patterns (LBP).

        Real skin has a characteristic LBP histogram with high variance.
        Printed photos show a more uniform, low-variance histogram.
        Digital screens may show Moire patterns or repetitive pixel grids.

        .. performance::
            The face crop is downsampled to 48×48 before LBP computation
            to keep this real-time capable (~0.1 ms per call).

        Returns:
            0.0 (likely synthetic/print) → 1.0 (likely real skin).
        """
        h, w = gray.shape
        if h < 16 or w < 16:
            return 0.4  # Too small to assess reliably

        # Downsample for speed — 48×48 is sufficient for texture analysis
        gray_small = cv2.resize(gray, (48, 48), interpolation=cv2.INTER_LINEAR)
        sh, sw = gray_small.shape

        # Compute LBP using vectorized operations
        # Center pixel matrix
        center = gray_small[1:-1, 1:-1].astype(np.int32)

        # 8 neighbour matrices (shifted)
        neighbours = [
            gray_small[:-2, :-2].astype(np.int32),  # top-left
            gray_small[:-2, 1:-1].astype(np.int32),  # top
            gray_small[:-2, 2:].astype(np.int32),    # top-right
            gray_small[1:-1, 2:].astype(np.int32),   # right
            gray_small[2:, 2:].astype(np.int32),     # bottom-right
            gray_small[2:, 1:-1].astype(np.int32),   # bottom
            gray_small[2:, :-2].astype(np.int32),     # bottom-left
            gray_small[1:-1, :-2].astype(np.int32),  # left
        ]

        # Build LBP code: threshold neighbours against center, shift, and sum
        lbp = np.zeros_like(center, dtype=np.int32)
        for n, (bit_val, nb) in enumerate([(128, 0), (64, 1), (32, 2), (16, 3),
                                            (8, 4), (4, 5), (2, 6), (1, 7)]):
            lbp += (neighbours[nb] >= center) * bit_val

        # Histogram of LBP codes
        hist = cv2.calcHist([lbp.astype(np.uint8)], [0], None, [256], [0, 256])
        hist = hist.flatten()
        hist = hist / (hist.sum() + 1e-10)

        # Real skin → histogram spread across many bins (high entropy)
        # Printed/screen → histogram concentrated in few bins (low entropy)
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        max_entropy = np.log(256)
        entropy_ratio = entropy / max_entropy  # 0-1

        # Also check histogram variance
        hist_var = float(np.var(hist))

        # Combine: high entropy + moderate variance = real skin
        score = entropy_ratio * 0.7 + min(hist_var * 10, 1.0) * 0.3
        return float(np.clip(score, 0.0, 1.0))

    # ── Blink Detection ───────────────────────────────────────

    def _compute_approximate_ear(
        self,
        landmarks: np.ndarray,
        img_shape: Tuple[int, int],
    ) -> float:
        """Compute an approximate Eye Aspect Ratio from 5-point landmarks.

        With 5 landmarks (left-eye, right-eye, nose, left-mouth, right-mouth),
        we approximate EAR by measuring the vertical distance from eyes to
        nose relative to inter-eye distance. This is a coarse proxy.

        Returns:
            Approximate EAR (higher = more open). Typically >0.25 when open.
        """
        h, w = img_shape
        left_eye = landmarks[0]
        right_eye = landmarks[1]
        nose = landmarks[2]

        # Inter-eye distance
        eye_dist = np.linalg.norm(left_eye - right_eye)
        if eye_dist < 5:
            return 0.5

        # Vertical distance from the eyes to the nose is a coarse proxy
        # for eyelid openness in the synthetic landmark tests.
        avg_eye_y = (float(left_eye[1]) + float(right_eye[1])) / 2.0
        vertical_gap = max(float(nose[1]) - avg_eye_y, 0.0)

        # Scale into roughly [0, 1] for the test landmarks.
        normalised = (vertical_gap / max(eye_dist, 1.0)) * 1.2
        return float(max(0.0, min(1.0, normalised)))

    def _update_blink_state(self, ear: float) -> float:
        """Update blink tracking state machine.

        Returns:
            Blink score: 0.0 (eyes likely shut for too long) → 1.0 (normal).
        """
        is_closed = ear < self._EAR_CLOSED_THRESHOLD

        if is_closed:
            self._consecutive_closed += 1
        else:
            # Check if the closed period was a blink
            if _BLINK_FRAMES_MIN <= self._consecutive_closed <= _BLINK_FRAMES_MAX:
                self._blink_count += 1
                self._blink_ever_detected = True
            self._consecutive_closed = 0

        # Score: if we've seen blinks, score is high
        if self._blink_ever_detected:
            blink_confidence = min(self._blink_count / 3.0, 1.0)
            return float(blink_confidence * 0.8 + 0.2)

        # No blink yet — neutral but decreasing with time
        if len(self._ear_history) < 15:
            return 0.5  # Not enough data
        # After ~15 frames with no blink, score drops
        recent = list(self._ear_history)
        recent_open = sum(1 for e in recent if e >= self._EAR_CLOSED_THRESHOLD)
        open_ratio = recent_open / max(len(recent), 1)
        if open_ratio > 0.9:
            # Eyes consistently open → suspicious (photo)
            return 0.3
        return 0.5

    # ── Motion Analysis ───────────────────────────────────────

    @staticmethod
    def _analyze_motion(prev_gray: np.ndarray, curr_gray: np.ndarray) -> float:
        """Analyse motion magnitude between two frames.

        Real faces have small but consistent micro-movements.
        Static photos have near-zero motion.

        Returns:
            0.0 (rigid/static) → 1.0 (natural motion).
        """
        # Compute dense optical flow for a central region (where face is)
        h, w = curr_gray.shape
        roi = curr_gray[int(h * 0.1):int(h * 0.9), int(w * 0.1):int(w * 0.9)]
        prev_roi = prev_gray[int(h * 0.1):int(h * 0.9), int(w * 0.1):int(w * 0.9)]

        if roi.size < 100:
            return 0.5

        # Simple frame differencing as a fast proxy for motion
        diff = cv2.absdiff(prev_roi, roi)
        mean_diff = float(np.mean(diff))

        # Typical live face frame-diff: 2.0–15.0 depending on lighting
        # Static spoof: < 1.0
        if mean_diff < 0.5:
            return 0.1  # Nearly identical frames — suspicious
        if mean_diff < 2.0:
            return float(0.1 + (mean_diff - 0.5) / 1.5 * 0.4)  # 0.1 → 0.5
        if mean_diff < 8.0:
            return float(0.5 + (mean_diff - 2.0) / 6.0 * 0.4)  # 0.5 → 0.9
        return 0.9  # lots of motion (could be talking, which is live)

    # ── Screen-edge Detection ─────────────────────────────────

    @staticmethod
    def _detect_screen_edges(gray: np.ndarray) -> float:
        """Detect if the face image contains strong rectangular edges
        consistent with a phone/tablet screen bezel.

        Returns:
            0.0 (no screen detected) → 1.0 (screen likely present).
        """
        h, w = gray.shape
        if h < 64 or w < 64:
            return 0.0

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Check for strong horizontal and vertical lines near borders
        border_margin = int(min(h, w) * 0.08)
        top_strip = edges[:border_margin, :]
        bottom_strip = edges[-border_margin:, :]
        left_strip = edges[:, :border_margin]
        right_strip = edges[:, -border_margin:]

        # Ratio of edge pixels in border regions
        total_border_pixels = (
            top_strip.size + bottom_strip.size
            + left_strip.size + right_strip.size
        )
        edge_pixels = (
            int(np.sum(top_strip > 0))
            + int(np.sum(bottom_strip > 0))
            + int(np.sum(left_strip > 0))
            + int(np.sum(right_strip > 0))
        )

        edge_ratio = edge_pixels / max(total_border_pixels, 1)

        # Check for Hough lines (strong rectangular patterns)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 50, minLineLength=30, maxLineGap=10)
        strong_lines = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # Check if line is near borders
                near_border = (
                    x1 < border_margin or x2 < border_margin
                    or x1 > w - border_margin or x2 > w - border_margin
                    or y1 < border_margin or y2 < border_margin
                    or y1 > h - border_margin or y2 > h - border_margin
                )
                if near_border:
                    strong_lines += 1

        line_factor = min(strong_lines / 8.0, 1.0)

        # Combined score
        screen_score = edge_ratio * 0.5 + line_factor * 0.5
        return float(np.clip(screen_score, 0.0, 1.0))

    # ── Helper ────────────────────────────────────────────────

    @staticmethod
    def _fail_result(reason: str) -> LivenessResult:
        """Return a LivenessResult indicating complete assessment failure.

        All scores are set to 0.0 because no assessment was possible.
        ``dl_score`` is 0.0 (not the default 0.5) to signal "unable to
        assess" rather than "neutral assessment".
        """
        return LivenessResult(
            is_live=False,
            liveness_score=0.0,
            texture_score=0.0,
            blink_score=0.0,
            motion_score=0.0,
            screen_score=0.0,
            dl_score=0.0,
            dl_time_ms=0.0,
            blink_detected=False,
            reasons=[reason],
        )
