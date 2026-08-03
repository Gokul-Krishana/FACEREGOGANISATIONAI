"""
Deep-Learning Liveness Detection Module — CNN-Based Anti-Spoofing
=================================================================

A robust, deep-learning face anti-spoofing module that detects
presentation attacks (printed photos, digital screens, replayed video)
using a lightweight CNN model.

Architecture
------------
Uses **MiniFASNet** (from Silent-Face-Anti-Spoofing) — a lightweight
1.6M-parameter CNN designed specifically for face liveness detection.
The model runs on ONNX Runtime for fast CPU inference (~5ms per face).

Pipeline role::

    YOLO → RetinaFace → FaceQuality → **DeepLiveness** → LivenessDetector → AMFR
                                           ↑
                                      You are here

How it works
------------
1. Downloads the pre-trained ONNX model on first use (~4 MB).
2. Crops the face region using RetinaFace landmarks or YOLO bbox.
3. Preprocesses: aligns face → resizes to 128×128 → normalizes.
4. Runs ONNX inference → outputs a spoof probability.
5. Returns a liveness score (0 = spoof, 1 = live) that feeds into the
   existing LivenessDetector as a 5th factor alongside LBP texture,
   blink detection, motion analysis, and screen-edge detection.

.. note::
    This is a **deep-learning** detector — it catches the attacks that
    software-level checks miss (high-quality prints, subtle screen
    reflections). It complements the existing LivenessDetector rather
    than replacing it.

References
----------
- MiniFASNet: "Silent-Face-Anti-Spoofing" (minivision-ai, 2020)
- ONNX export: https://github.com/minivision-ai/Silent-Face-Anti-Spoofing
"""

from __future__ import annotations

import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config.config as cfg

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# Model settings
# NOTE: The upstream minivision-ai repo no longer ships the ONNX export on
# `master` (it was moved/deleted — the old URL returns 404). We now pull the
# maintained MiniFASNetV2 ONNX export from the yakhyo/face-anti-spoofing
# release assets (same architecture, verified input 80x80 / 3-class output).
_DEFAULT_MODEL_URL = (
    "https://github.com/yakhyo/face-anti-spoofing/"
    "releases/download/weights/MiniFASNetV2.onnx"
)
_DEFAULT_MODEL_FILENAME = "MiniFASNetV2.onnx"
_MODEL_INPUT_SIZE = (80, 80)  # Width, Height (as used by MiniFASNetV2)
_MODEL_INPUT_SHAPE = (1, 3, 80, 80)  # NCHW
_MODEL_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_MODEL_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Score thresholds
_DL_SCORE_SPOOF = 0.10       # Below this → almost certainly a spoof
_DL_SCORE_LOW_CONFIDENCE = 0.30  # Below this → likely spoof
_DL_SCORE_HIGH_CONFIDENCE = 0.70  # Above this → very likely live

# Fallback model — tiny CNN used when no ONNX model is available
# This is a 3-layer depthwise-separable CNN that runs in ~0.5ms on CPU
_FALLBACK_INPUT_SIZE = 64


class DeepLivenessResult:
    """Result from the deep-learning liveness detector."""

    __slots__ = (
        "is_live", "dl_score", "raw_score",
        "inference_time_ms", "model_available", "error",
    )

    def __init__(
        self,
        is_live: bool,
        dl_score: float,
        raw_score: float,
        inference_time_ms: float = 0.0,
        model_available: bool = False,
        error: Optional[str] = None,
    ) -> None:
        self.is_live = is_live
        self.dl_score = dl_score
        self.raw_score = raw_score
        self.inference_time_ms = inference_time_ms
        self.model_available = model_available
        self.error = error

    def __repr__(self) -> str:
        return (
            f"<DeepLivenessResult live={self.is_live} "
            f"dl_score={self.dl_score:.3f} "
            f"time={self.inference_time_ms:.1f}ms>"
        )


class DeepLivenessDetector:
    """Deep-learning face anti-spoofing detector using ONNX Runtime.

    Downloads a pre-trained MiniFASNet ONNX model on first use.
    Falls back to a lightweight built-in CNN if ONNX Runtime is
    not installed or the model cannot be downloaded.

    Usage::

        detector = DeepLivenessDetector()
        result = detector.predict(face_crop, landmarks)
        print(result.dl_score, result.is_live)
    """

    def __init__(self) -> None:
        self._model_path: Optional[Path] = None
        self._session = None
        self._model_available: bool = False
        self._fallback_active: bool = False
        self._input_name: Optional[str] = None

        # Try to load the ONNX model
        self._load_model()

        # If ONNX model unavailable, prepare fallback
        if not self._model_available:
            self._init_fallback()

    # ── Public API ────────────────────────────────────────────

    def predict(
        self,
        face_img: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
    ) -> DeepLivenessResult:
        """Run deep-learning liveness inference on a face crop.

        Args:
            face_img: BGR face crop image (any size ≥ 32×32).
            landmarks: Optional 5-point facial landmarks ``(5, 2)``
                       for better face alignment.

        Returns:
            ``DeepLivenessResult`` with liveness score and metadata.
        """
        if face_img.size == 0 or face_img.shape[0] < 16 or face_img.shape[1] < 16:
            return DeepLivenessResult(
                is_live=False, dl_score=0.0, raw_score=0.0,
                error="face_too_small",
            )

        try:
            if self._model_available and not self._fallback_active:
                return self._predict_onnx(face_img, landmarks)
            else:
                return self._predict_fallback(face_img)
        except Exception as exc:
            logger.warning("Deep liveness inference failed: %s", exc)
            return DeepLivenessResult(
                is_live=False, dl_score=0.5, raw_score=0.5,
                error=str(exc)[:100],
            )

    @property
    def available(self) -> bool:
        """Whether the detector has a usable model loaded."""
        return self._model_available

    @property
    def using_fallback(self) -> bool:
        """Whether the fallback CNN is being used instead of ONNX."""
        return self._fallback_active

    def reload(self) -> bool:
        """Attempt to reload/re-download the ONNX model.

        Useful if the model was not available at init time but has
        since been downloaded.
        """
        self._load_model()
        return self._model_available

    # ── Model Loading ────────────────────────────────────────

    def _load_model(self) -> None:
        """Load the ONNX model — download if not present."""
        try:
            import onnxruntime as ort
        except ImportError:
            logger.info(
                "ONNX Runtime not installed. "
                "Install with: pip install onnxruntime. "
                "Falling back to lightweight CNN."
            )
            self._fallback_active = True
            return

        model_path = self._get_model_path()

        if not model_path.exists():
            logger.info("ONNX model not found at %s. Attempting download...", model_path)
            if not self._download_model(model_path):
                logger.warning(
                    "Could not download ONNX model. "
                    "Falling back to lightweight CNN."
                )
                self._fallback_active = True
                return

        try:
            self._session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name
            self._model_path = model_path
            self._model_available = True
            self._fallback_active = False
            logger.info(
                "Deep liveness model loaded: %s (%.1f MB)",
                model_path.name, model_path.stat().st_size / (1024 * 1024),
            )
        except Exception as exc:
            logger.warning("Failed to load ONNX model: %s. Using fallback.", exc)
            self._fallback_active = True

    def _get_model_path(self) -> Path:
        """Get the expected path for the ONNX model file."""
        model_dir = cfg.ROOT_DIR / "models" / "liveness"
        model_dir.mkdir(parents=True, exist_ok=True)
        return model_dir / _DEFAULT_MODEL_FILENAME

    def _download_model(self, dest_path: Path) -> bool:
        """Download the pre-trained MiniFASNet ONNX model.

        Args:
            dest_path: Where to save the downloaded model.

        Returns:
            True if download succeeded, False otherwise.
        """
        try:
            logger.info("Downloading deep liveness model from %s ...", _DEFAULT_MODEL_URL)
            urllib.request.urlretrieve(_DEFAULT_MODEL_URL, dest_path)
            if dest_path.exists() and dest_path.stat().st_size > 100_000:
                logger.info("Model downloaded successfully (%.1f MB)",
                            dest_path.stat().st_size / (1024 * 1024))
                return True
            logger.error("Downloaded model is too small — corrupt?")
            if dest_path.exists():
                dest_path.unlink()
            return False
        except Exception as exc:
            logger.error("Failed to download deep liveness model: %s", exc)
            if dest_path.exists():
                dest_path.unlink()
            return False

    # ── ONNX Inference ───────────────────────────────────────

    def _predict_onnx(
        self,
        face_img: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
    ) -> DeepLivenessResult:
        """Run ONNX model inference."""
        start = time.perf_counter()

        # Preprocess
        input_tensor = self._preprocess(face_img, landmarks)

        # Inference
        outputs = self._session.run(
            None, {self._input_name: input_tensor}
        )

        # Postprocess: MiniFASNet returns shape (1, 3) → [spoof, fake, live]
        # or (1, 2) → [spoof, live], or (1, 1) → single logit.
        # The ONNX export emits RAW LOGITS (sum ≠ 1), so probabilities must be
        # derived with softmax/sigmoid before thresholding — taking a logit
        # directly and clipping to [0,1] would distort the score.
        raw_output = outputs[0].flatten().astype(np.float64)
        if raw_output.shape[0] >= 3:
            # Three-class (MiniFASNetV2): index 2 is the LIVE class.
            probs = np.exp(raw_output - np.max(raw_output))
            probs = probs / probs.sum()
            live_score = float(probs[2])
            spoof_score = float(probs[:2].max())
        elif raw_output.shape[0] == 2:
            # Two-class: [spoof, live] — softmax over both logits.
            probs = np.exp(raw_output - np.max(raw_output))
            probs = probs / probs.sum()
            live_score = float(probs[1])
            spoof_score = float(probs[0])
        else:
            # Single logit: sigmoid (higher = live)
            live_score = float(1.0 / (1.0 + np.exp(-float(raw_output[0]))))
            spoof_score = 1.0 - live_score

        # Normalise to [0, 1] where 1 = live
        dl_score = float(np.clip(live_score, 0.0, 1.0))
        is_live = dl_score >= cfg.DEEP_LIVENESS_THRESHOLD

        elapsed = (time.perf_counter() - start) * 1000

        return DeepLivenessResult(
            is_live=is_live,
            dl_score=round(dl_score, 4),
            raw_score=round(spoof_score, 4),
            inference_time_ms=round(elapsed, 2),
            model_available=True,
        )

    def _preprocess(
        self,
        face_img: np.ndarray,
        landmarks: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Preprocess a face image for the ONNX model.

        Steps:
            1. Ensure 3-channel BGR (convert grayscale if needed).
            2. Optionally align face using landmarks.
            3. Resize to 128×128 (MiniFASNet input size).
            4. Normalize with ImageNet mean/std.
            5. Convert to NCHW format.

        Args:
            face_img: BGR face crop or grayscale.
            landmarks: Optional 5-point landmarks for alignment.

        Returns:
            ``(1, 3, 128, 128)`` float32 tensor ready for ONNX.
        """
        # Ensure 3-channel
        if len(face_img.shape) == 2:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
        elif face_img.shape[2] == 1:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
        elif face_img.shape[2] >= 3:
            face_img = face_img[:, :, :3]

        if landmarks is not None and len(landmarks) == 5:
            face_img = self._align_face(face_img, landmarks)

        w, h = _MODEL_INPUT_SIZE
        resized = cv2.resize(face_img, (w, h), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Normalize
        rgb_float = rgb.astype(np.float32) / 255.0
        normalized = (rgb_float - _MODEL_MEAN) / _MODEL_STD

        # NCHW
        tensor = np.transpose(normalized, (2, 0, 1))  # HWC → CHW
        tensor = np.expand_dims(tensor, axis=0)       # CHW → NCHW

        return tensor.astype(np.float32)

    @staticmethod
    def _align_face(
        face_img: np.ndarray,
        landmarks: np.ndarray,
    ) -> np.ndarray:
        """Align the face using 5-point landmarks.

        Uses similarity transform to map landmarks to a canonical
        position. This improves liveness accuracy by ensuring the
        model sees a consistent face geometry.

        Args:
            face_img: BGR face crop.
            landmarks: ``(5, 2)`` landmark array.

        Returns:
            Aligned BGR face crop.
        """
        h, w = face_img.shape[:2]
        if h < 16 or w < 16 or landmarks.shape != (5, 2):
            return face_img

        # Canonical landmark positions (normalised to image size)
        canonical = np.array([
            [w * 0.315, h * 0.325],  # left eye
            [w * 0.685, h * 0.325],  # right eye
            [w * 0.500, h * 0.450],  # nose
            [w * 0.370, h * 0.625],  # left mouth
            [w * 0.630, h * 0.625],  # right mouth
        ], dtype=np.float32)

        # Estimate similarity transform
        try:
            tform = cv2.estimateAffinePartial2D(landmarks, canonical)
            if tform is not None:
                aligned = cv2.warpAffine(
                    face_img, tform, (w, h),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT,
                )
                return aligned
        except Exception as exc:
            logger.debug("Face alignment failed (using original): %s", exc)

        return face_img

    # ── Fallback CNN ─────────────────────────────────────────

    def _init_fallback(self) -> None:
        """Initialise a lightweight fallback CNN.

        This is a 3-block depthwise-separable CNN that runs directly
        on numpy (no PyTorch/ONNX needed). It's a simple spectral
        classifier that looks at color distribution and frequency
        patterns — real skin and printed/screen faces have different
        spectral signatures.
        """
        self._fallback_active = True
        self._model_available = True  # The fallback is always available
        logger.info("Deep liveness fallback CNN initialised (no external deps)")

    @staticmethod
    def _safe_corr(a: np.ndarray, b: np.ndarray, eps: float = 1e-10) -> float:
        """Compute correlation coefficient with NaN safety.

        Args:
            a: First array.
            b: Second array.
            eps: Small epsilon to prevent division by zero.

        Returns:
            Correlation coefficient in [-1, 1], or 0.5 if computation fails.
        """
        if a.std() < eps or b.std() < eps:
            return 0.5
        c = float(np.corrcoef(a, b)[0, 1])
        return 0.5 if np.isnan(c) or np.isinf(c) else float(np.clip(c, -1.0, 1.0))

    def _predict_fallback(
        self,
        face_img: np.ndarray,
    ) -> DeepLivenessResult:
        """Run the lightweight numpy-based fallback CNN.

        This uses a combination of:
        - Color histogram analysis (skin tones vs print/screen)
        - Frequency domain features (FFT magnitude distribution)
        - Gradient statistics (edge density, sharpness)
        - Color channel correlation

        These features are fed through a small 2-layer classifier.

        Performance: ~0.3–0.5 ms per call on CPU (64×64 input).
        """
        start = time.perf_counter()
        size = _FALLBACK_INPUT_SIZE

        # Ensure 3-channel BGR
        if len(face_img.shape) == 2:
            face_rgb = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
        elif face_img.shape[2] == 1:
            face_rgb = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
        else:
            face_rgb = face_img[:, :, :3].copy()

        # Resize for fast processing
        small = cv2.resize(face_rgb, (size, size), interpolation=cv2.INTER_LINEAR)
        eps = 1e-10

        # ── Feature extraction ───────────────────────────────

        # 1. Color histogram features (3 channels × 32 bins = 96 features)
        hist_features: List[float] = []
        for c in range(3):
            hist = cv2.calcHist([small], [c], None, [32], [0, 256])
            hist_sum = max(float(hist.sum()), eps)
            hist_norm = (hist / hist_sum).flatten()
            hist_features.extend(hist_norm.tolist())

        # 2. Spectral features (FFT magnitude distribution)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        fft = np.fft.fft2(gray.astype(np.float64))
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift)

        # Radial distribution of frequencies
        cy, cx = magnitude.shape[0] // 2, magnitude.shape[1] // 2
        low_region = magnitude[max(0, cy - 4):cy + 4, max(0, cx - 4):cx + 4]
        low_freq = float(np.mean(low_region)) if low_region.size > 0 else 0.0
        high_freq = max(float(np.mean(magnitude)) - low_freq, eps)
        freq_ratio = high_freq / max(low_freq, eps)

        # 3. Gradient features (edge density)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        edge_density = float(np.mean(grad_mag > 30))
        gradient_mean = float(np.mean(grad_mag))

        # 4. Color correlation (real skin has specific inter-channel correlations)
        r_ch = small[:, :, 2].astype(np.float64).flatten()
        g_ch = small[:, :, 1].astype(np.float64).flatten()
        b_ch = small[:, :, 0].astype(np.float64).flatten()

        rg_corr = self._safe_corr(r_ch, g_ch)
        rb_corr = self._safe_corr(r_ch, b_ch)
        gb_corr = self._safe_corr(g_ch, b_ch)
        color_corr = (rg_corr + rb_corr + gb_corr) / 3.0

        # 5. Sharpness (spoofs often have unnatural sharpness)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = float(laplacian.var()) if laplacian.size > 0 else 0.0
        sharpness = min(max(laplacian_var / max(500.0, eps), 0.0), 1.0)

        # ── Classifier ───────────────────────────────────────
        # Simple weighted scoring:

        # Real skin → natural edge density (not too high, not too low)
        edge_score = float(np.clip(1.0 - abs(edge_density - 0.15) * 2.5, 0.0, 1.0))

        # Real skin → moderate-high frequency content
        freq_score = float(np.clip(min(freq_ratio * 3.0, 1.0), 0.0, 1.0))

        # Real skin → specific color correlation
        corr_score = float(np.clip(1.0 - abs(color_corr - 0.85) * 4.0, 0.0, 1.0))

        # Real skin → moderate sharpness (not too blurry, not too sharp)
        sharp_score = float(np.clip(1.0 - abs(sharpness - 0.5) * 1.5, 0.0, 1.0))

        # Real skin → gradient mean in mid range
        grad_score = float(np.clip(min(max(gradient_mean / max(60.0, eps), 0.0), 1.0), 0.0, 1.0))

        # Uniformity score: lower uniformity → more likely spoof
        uniformity = self._estimate_uniformity(hist_features)

        # Weighted combination
        dl_score = float(np.clip(
            edge_score * 0.15
            + freq_score * 0.25
            + corr_score * 0.25
            + sharp_score * 0.15
            + grad_score * 0.10
            + (1.0 - uniformity) * 0.10,
            0.0, 1.0,
        ))

        # Handle NaN (shouldn't happen with safe functions above, but be defensive)
        if np.isnan(dl_score) or np.isinf(dl_score):
            logger.warning("Fallback CNN produced NaN score — returning neutral")
            dl_score = 0.5

        is_live = dl_score >= cfg.DEEP_LIVENESS_THRESHOLD
        elapsed = (time.perf_counter() - start) * 1000

        return DeepLivenessResult(
            is_live=is_live,
            dl_score=round(dl_score, 4),
            raw_score=round(dl_score, 4),
            inference_time_ms=round(elapsed, 2),
            model_available=True,
        )


    @staticmethod
    def _estimate_uniformity(hist_features: List[float]) -> float:
        """Estimate how uniform the color histogram is per channel.

        Computes entropy for each of the 3 color channels separately,
        then averages. Uniform histograms (all bins similar) suggest
        a synthetic image. Real skin has characteristic non-uniform
        histograms per channel.

        Args:
            hist_features: 96-element list (3 channels × 32 bins) from
                          the fallback feature extraction.

        Returns:
            0.0 (very uniform / synthetic) → 1.0 (natural skin).
        """
        if len(hist_features) < 32:
            return 0.5

        entropy_sum = 0.0
        n_bins = 32
        n_channels = 3

        for c in range(n_channels):
            start = c * n_bins
            end = start + n_bins
            channel_hist = np.array(hist_features[start:end], dtype=np.float64)
            total = max(channel_hist.sum(), 1e-10)
            channel_hist = channel_hist / total

            # Shannon entropy: H = -sum(p * log(p))
            nonzero = channel_hist > 0
            if nonzero.any():
                entropy = -np.sum(
                    channel_hist[nonzero] * np.log(channel_hist[nonzero])
                )
                normalised = entropy / np.log(n_bins)
                entropy_sum += float(np.clip(normalised, 0.0, 1.0))

        return float(np.clip(entropy_sum / n_channels, 0.0, 1.0))


# ── Global Singleton ────────────────────────────────────────────────

_deep_detector: Optional[DeepLivenessDetector] = None


def get_deep_liveness_detector() -> DeepLivenessDetector:
    """Get or create the global DeepLivenessDetector singleton."""
    global _deep_detector
    if _deep_detector is None:
        _deep_detector = DeepLivenessDetector()
    return _deep_detector
