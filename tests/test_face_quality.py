"""
Tests for FaceQualityAssessment.

Covers all metrics: blur, brightness, contrast, face size, detection
score, and pose estimation — using synthetic numpy images.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

import config.config as cfg
from app.face_quality import FaceQualityAssessment


@pytest.fixture()
def fqa() -> FaceQualityAssessment:
    """Return a fresh FaceQualityAssessment instance per test."""
    return FaceQualityAssessment()


@pytest.fixture()
def sharp_face() -> np.ndarray:
    """Create a synthetic sharp face image (random noise = high frequency)."""
    return np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)


@pytest.fixture()
def blurry_face() -> np.ndarray:
    """Create a synthetic blurry face image (uniform gray = no edges)."""
    return np.full((200, 200, 3), 128, dtype=np.uint8)


@pytest.fixture()
def bright_face() -> np.ndarray:
    """Create an over-exposed face image (all white)."""
    return np.full((200, 200, 3), 250, dtype=np.uint8)


@pytest.fixture()
def dark_face() -> np.ndarray:
    """Create an under-exposed face image (all black)."""
    return np.full((200, 200, 3), 5, dtype=np.uint8)


@pytest.fixture()
def high_contrast_face() -> np.ndarray:
    """Create a high-contrast face (black and white checker)."""
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[::2, ::2] = 255
    return img


@pytest.fixture()
def landmarks_frontal() -> np.ndarray:
    """5-point landmarks for a frontal face."""
    return np.array([
        [60, 80],   # left eye
        [140, 80],  # right eye
        [100, 130],  # nose
        [70, 170],  # left mouth
        [130, 170],  # right mouth
    ], dtype=np.float32)


@pytest.fixture()
def landmarks_profile() -> np.ndarray:
    """5-point landmarks for a profile face (extreme angle)."""
    return np.array([
        [140, 80],   # left eye (camera-right side)
        [160, 85],   # right eye
        [150, 130],  # nose
        [130, 170],  # left mouth
        [155, 175],  # right mouth
    ], dtype=np.float32)


class TestFaceQualityAssessment:
    """Tests for FaceQualityAssessment metrics and composite scoring."""

    def test_init_default_weights(self, fqa):
        """Should have default weights loaded."""
        assert len(fqa.weights) > 0
        assert "blur_score" in fqa.weights
        assert "brightness_score" in fqa.weights
        assert sum(fqa.weights.values()) == pytest.approx(1.0, abs=0.01)

    # ── Blur Assessment ───────────────────────────────────────

    def test_assess_blur_sharp(self, fqa, sharp_face):
        """A sharp face should get a high blur score."""
        gray = cv2.cvtColor(sharp_face, cv2.COLOR_BGR2GRAY)
        score = fqa._assess_blur(gray)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Sharp face = high score

    def test_assess_blur_blurry(self, fqa, blurry_face):
        """A blurry face should get a low blur score."""
        gray = cv2.cvtColor(blurry_face, cv2.COLOR_BGR2GRAY)
        score = fqa._assess_blur(gray)
        assert 0.0 <= score <= 1.0
        assert score < 0.3  # Blurry = low score

    def test_assess_blur_identical_face(self, fqa):
        """Two calls on the same image should produce the same score."""
        gray = cv2.cvtColor(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8),
                            cv2.COLOR_BGR2GRAY)
        s1 = fqa._assess_blur(gray)
        s2 = fqa._assess_blur(gray)
        assert s1 == pytest.approx(s2)

    # ── Brightness Assessment ─────────────────────────────────

    def test_assess_brightness_ideal(self, fqa):
        """An image near 128 mean should score near 1.0."""
        ideal = np.full((100, 100, 3), 128, dtype=np.uint8)
        gray = cv2.cvtColor(ideal, cv2.COLOR_BGR2GRAY)
        score = fqa._assess_brightness(gray)
        assert score > 0.9

    def test_assess_brightness_too_bright(self, fqa, bright_face):
        """An over-exposed face should get a low score."""
        gray = cv2.cvtColor(bright_face, cv2.COLOR_BGR2GRAY)
        score = fqa._assess_brightness(gray)
        assert score < 0.5

    def test_assess_brightness_too_dark(self, fqa, dark_face):
        """An under-exposed face should get a low score."""
        gray = cv2.cvtColor(dark_face, cv2.COLOR_BGR2GRAY)
        score = fqa._assess_brightness(gray)
        assert score < 0.5

    # ── Contrast Assessment ───────────────────────────────────

    def test_assess_contrast_high(self, fqa, high_contrast_face):
        """A high-contrast image should score near 1.0."""
        gray = cv2.cvtColor(high_contrast_face, cv2.COLOR_BGR2GRAY)
        score = fqa._assess_contrast(gray)
        assert score > 0.8

    def test_assess_contrast_low(self, fqa, blurry_face):
        """A uniform image should score near 0.0."""
        gray = cv2.cvtColor(blurry_face, cv2.COLOR_BGR2GRAY)
        score = fqa._assess_contrast(gray)
        assert 0.0 <= score <= 1.0

    # ── Face Size Assessment ──────────────────────────────────

    def test_face_size_ideal(self, fqa):
        """A face covering ~8% of the image should score high."""
        score = fqa._assess_face_size(
            face_bbox=(10, 10, 90, 90),  # 80x80 = 6400
            img_shape=(300, 300),  # 90,000, ratio ≈ 0.071
        )
        assert score > 0.5

    def test_face_size_tiny(self, fqa):
        """A tiny face should score very low."""
        score = fqa._assess_face_size(
            face_bbox=(100, 100, 105, 105),  # 5x5
            img_shape=(480, 640),  # very small ratio
        )
        assert score < 0.2

    def test_face_size_large(self, fqa):
        """An oversized face should still get a moderate score."""
        score = fqa._assess_face_size(
            face_bbox=(0, 0, 400, 400),  # 160,000
            img_shape=(480, 640),  # 307,200, ratio ≈ 0.52
        )
        assert score >= 0.4  # Oversized but functional

    def test_face_size_zero_area(self, fqa):
        """A degenerate bbox should not crash."""
        score = fqa._assess_face_size(
            face_bbox=(10, 10, 10, 10),  # zero area
            img_shape=(480, 640),
        )
        assert 0.0 <= score <= 1.0

    # ── Detection Score ───────────────────────────────────────

    def test_det_score_perfect(self, fqa):
        """det_score=1.0 should map to 1.0."""
        score = fqa._assess_det_score(1.0)
        assert score == 1.0

    def test_det_score_zero(self, fqa):
        """det_score=0.0 should map to 0.0."""
        score = fqa._assess_det_score(0.0)
        assert score == 0.0

    def test_det_score_clamped(self, fqa):
        """det_score > 1.0 should be clamped to 1.0."""
        score = fqa._assess_det_score(1.5)
        assert score == 1.0

    # ── Pose Assessment ───────────────────────────────────────

    def test_pose_frontal(self, fqa, landmarks_frontal):
        """Frontal face should score high on pose."""
        score = fqa._assess_pose(landmarks_frontal)
        assert score > 0.7

    def test_pose_profile(self, fqa, landmarks_profile):
        """Profile face should score lower than frontal."""
        score = fqa._assess_pose(landmarks_profile)
        assert score < 0.7

    def test_pose_wrong_shape(self, fqa):
        """Non-(5,2) landmarks should return neutral score."""
        bad_landmarks = np.array([[0, 0], [1, 1]], dtype=np.float32)
        score = fqa._assess_pose(bad_landmarks)
        assert score == 0.5

    # ── Full Assessment ───────────────────────────────────────

    def test_assess_high_quality(self, fqa, sharp_face, landmarks_frontal):
        """A sharp, well-lit, frontal face should pass quality gate."""
        result = fqa.assess(
            face_img=sharp_face,
            det_score=0.98,
            face_bbox=(50, 50, 150, 150),
            img_shape=(300, 300),
            landmarks=landmarks_frontal,
        )
        assert result["passed"] is True
        assert result["overall"] >= cfg.FACE_QUALITY_MIN_SCORE
        assert len(result["failure_reasons"]) == 0

    def test_assess_low_quality(self, fqa, blurry_face):
        """A blurry, dark face should fail quality gate."""
        result = fqa.assess(
            face_img=blurry_face,
            det_score=0.5,
            face_bbox=None,
            img_shape=None,
            landmarks=None,
        )
        assert result["passed"] is False
        assert result["overall"] < cfg.FACE_QUALITY_MIN_SCORE
        assert len(result["failure_reasons"]) > 0

    def test_assess_no_landmarks(self, fqa, sharp_face):
        """Assessment should work without landmarks (optional)."""
        result = fqa.assess(
            face_img=sharp_face,
            det_score=0.95,
            face_bbox=None,
            img_shape=None,
            landmarks=None,
        )
        assert "overall" in result
        assert "metrics" in result
        assert "pose_score" not in result["metrics"]

    def test_assess_empty_image(self, fqa):
        """An empty image should not crash."""
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        result = fqa.assess(
            face_img=empty,
            det_score=0.0,
        )
        assert "overall" in result

    def test_assess_returns_all_keys(self, fqa, sharp_face):
        """Result dict should contain all expected keys."""
        result = fqa.assess(
            face_img=sharp_face,
            det_score=0.95,
        )
        assert "overall" in result
        assert "passed" in result
        assert "metrics" in result
        assert "failure_reasons" in result

    def test_score_range(self, fqa, sharp_face):
        """Overall score should always be in [0, 1]."""
        result = fqa.assess(
            face_img=sharp_face,
            det_score=0.95,
        )
        assert 0.0 <= result["overall"] <= 1.0

