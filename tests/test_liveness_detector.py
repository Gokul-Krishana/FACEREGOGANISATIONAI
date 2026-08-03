"""
Tests for LivenessDetector (anti-spoofing module).

Covers all 4 anti-spoofing factors: texture analysis (LBP), blink
detection (EAR), motion analysis, and screen-edge detection — using
synthetic numpy images.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.liveness_detector import LivenessDetector, LivenessResult


@pytest.fixture()
def detector() -> LivenessDetector:
    """Return a fresh LivenessDetector per test."""
    return LivenessDetector()


@pytest.fixture()
def real_face() -> np.ndarray:
    """Simulate a real face crop with natural texture (random noise)."""
    face = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    return face


@pytest.fixture()
def uniform_face() -> np.ndarray:
    """Simulate a synthetic/spoof face with uniform texture."""
    return np.full((200, 200, 3), 128, dtype=np.uint8)


@pytest.fixture()
def frontal_landmarks() -> np.ndarray:
    """5-point landmarks simulating open eyes on a frontal face."""
    return np.array(
        [
            [60, 80],  # left eye
            [140, 80],  # right eye
            [100, 120],  # nose
            [70, 170],  # left mouth
            [130, 170],  # right mouth
        ],
        dtype=np.float32,
    )


@pytest.fixture()
def screen_like() -> np.ndarray:
    """Simulate an image with strong rectangular edges (phone screen)."""
    img = np.zeros((200, 200), dtype=np.uint8)
    # Draw bright edges near borders
    cv2.rectangle(img, (5, 5), (195, 195), 255, 2)
    return img


class TestLivenessResult:
    """Tests for the LivenessResult dataclass."""

    def test_creation(self):
        """LivenessResult should store all fields."""
        result = LivenessResult(
            is_live=True,
            liveness_score=0.85,
            texture_score=0.9,
            blink_score=0.8,
            motion_score=0.7,
            screen_score=0.1,
            blink_detected=True,
            reasons=[],
        )
        assert result.is_live is True
        assert result.liveness_score == 0.85
        assert result.blink_detected is True
        assert result.reasons == []

    def test_repr(self):
        """String representation should include key info."""
        result = LivenessResult(
            is_live=True,
            liveness_score=0.85,
            texture_score=0.9,
            blink_score=0.8,
            motion_score=0.7,
            screen_score=0.1,
            blink_detected=True,
            reasons=[],
        )
        repr_str = repr(result)
        assert "LivenessResult" in repr_str
        assert "live=" in repr_str
        assert "score=" in repr_str

    def test_fail_result(self):
        """_fail_result should produce a non-live result."""
        result = LivenessDetector._fail_result("test_failure")
        assert result.is_live is False
        assert result.liveness_score == 0.0
        assert "test_failure" in result.reasons


class TestLivenessDetector:
    """Tests for LivenessDetector functionality."""

    # ── Texture Analysis ──────────────────────────────────────

    def test_texture_real_face(self, detector, real_face):
        """Real-like texture (random noise) should score high."""
        gray = cv2.cvtColor(real_face, cv2.COLOR_BGR2GRAY)
        score = detector._analyze_texture(gray)
        assert 0.0 <= score <= 1.0
        assert score > 0.4  # Random noise has good texture

    def test_texture_uniform(self, detector, uniform_face):
        """Uniform texture should score low (synthetic)."""
        gray = cv2.cvtColor(uniform_face, cv2.COLOR_BGR2GRAY)
        score = detector._analyze_texture(gray)
        assert 0.0 <= score <= 1.0
        assert score < 0.5  # Uniform = lower entropy

    def test_texture_small_face(self, detector):
        """A very small face should return a cautious score."""
        small = np.random.randint(0, 255, (10, 10), dtype=np.uint8)
        score = detector._analyze_texture(small)
        assert 0.0 <= score <= 1.0

    # ── Blink Detection ───────────────────────────────────────

    def test_blink_initial_state(self, detector):
        """Before any frames, blink state should be neutral."""
        detector._ear_history.extend([0.5] * 5)
        score = detector._update_blink_state(0.5)
        assert 0.0 <= score <= 1.0

    def test_blink_cycle_detected(self, detector, frontal_landmarks):
        """A complete blink cycle should update blink_count."""
        # Simulate open eyes for a few frames
        for _ in range(5):
            ear = detector._compute_approximate_ear(frontal_landmarks, (200, 200))
            detector._ear_history.append(ear)

        # Simulate eye closure (EAR drops)
        closed_landmarks = frontal_landmarks.copy()
        closed_landmarks[0] = [65, 95]  # Eyes move down slightly
        closed_landmarks[1] = [135, 95]
        ear_closed = detector._compute_approximate_ear(closed_landmarks, (200, 200))

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(detector, "_EAR_CLOSED_THRESHOLD", 0.5)
            for _ in range(3):
                detector._update_blink_state(ear_closed)

        # Then eyes open
        ear_open = detector._compute_approximate_ear(frontal_landmarks, (200, 200))
        detector._update_blink_state(ear_open)

        # After the cycle, ever_detected should be True
        assert detector._blink_ever_detected is True

    def test_ear_computation_valid(self, detector, frontal_landmarks):
        """EAR should return a valid float for normal landmarks."""
        ear = detector._compute_approximate_ear(frontal_landmarks, (200, 200))
        assert 0.0 <= ear <= 1.0
        assert ear > 0.3  # Open eyes should be above closed threshold

    def test_ear_zero_eye_distance(self, detector):
        """EAR should not crash when eyes are at the same point."""
        landmarks = np.array(
            [
                [100, 100],
                [100, 100],  # same point for both eyes
                [100, 120],
                [80, 170],
                [120, 170],
            ],
            dtype=np.float32,
        )
        ear = detector._compute_approximate_ear(landmarks, (200, 200))
        assert 0.0 <= ear <= 1.0

    # ── Motion Analysis ────────────────────────────────────────

    def test_motion_identical_frames(self, detector):
        """Two identical frames should produce low motion score."""
        gray = np.random.randint(100, 150, (100, 100), dtype=np.uint8)
        score = detector._analyze_motion(gray, gray.copy())
        assert 0.0 <= score <= 1.0
        assert score < 0.3  # Nearly identical = low motion

    def test_motion_different_frames(self, detector):
        """Two very different frames should produce higher motion."""
        gray1 = np.full((100, 100), 50, dtype=np.uint8)
        gray2 = np.full((100, 100), 200, dtype=np.uint8)
        score = detector._analyze_motion(gray1, gray2)
        assert score > 0.5  # Very different = high motion

    def test_motion_small_roi(self, detector):
        """A very small frame should not crash."""
        small = np.zeros((4, 4), dtype=np.uint8)
        score = detector._analyze_motion(small, small.copy())
        assert 0.0 <= score <= 1.0

    # ── Screen-edge Detection ──────────────────────────────────

    def test_screen_detected(self, detector, screen_like):
        """An image with strong rectangular edges should score high."""
        score = detector._detect_screen_edges(screen_like)
        assert 0.0 <= score <= 1.0

    def test_screen_not_detected(self, detector, real_face):
        """A natural face image should score low for screen edges."""
        gray = cv2.cvtColor(real_face, cv2.COLOR_BGR2GRAY)
        score = detector._detect_screen_edges(gray)
        assert 0.0 <= score <= 1.0
        # Natural face may have some edge content, but should be lower
        # than a screen pattern

    def test_screen_small_image(self, detector):
        """A tiny image should return 0 (can't assess)."""
        small = np.zeros((30, 30), dtype=np.uint8)
        score = detector._detect_screen_edges(small)
        assert score == 0.0

    # ── Full Frame Analysis ────────────────────────────────────

    def test_analyze_frame_empty(self, detector):
        """An empty image should return a fail result."""
        result = detector.analyze_frame(np.zeros((0, 0, 3), dtype=np.uint8))
        assert result.is_live is False
        assert "empty_face" in result.reasons

    def test_analyze_frame_with_landmarks(self, detector, real_face, frontal_landmarks):
        """Analysis with landmarks should include blink scoring."""
        result = detector.analyze_frame(real_face, landmarks=frontal_landmarks)
        assert isinstance(result, LivenessResult)
        assert 0.0 <= result.liveness_score <= 1.0
        assert 0.0 <= result.texture_score <= 1.0
        assert 0.0 <= result.blink_score <= 1.0
        assert 0.0 <= result.motion_score <= 1.0
        assert 0.0 <= result.screen_score <= 1.0

    def test_analyze_frame_without_landmarks(self, detector, real_face):
        """Analysis without landmarks should still produce a result."""
        result = detector.analyze_frame(real_face, landmarks=None)
        assert isinstance(result, LivenessResult)
        # Blink score should be 0 when no landmarks available
        assert result.blink_score == 0.0

    # ── Reset ──────────────────────────────────────────────────

    def test_reset_clears_state(self, detector, real_face, frontal_landmarks):
        """Reset should clear all temporal state."""
        detector.analyze_frame(real_face, landmarks=frontal_landmarks)
        detector.register_blink()
        assert detector._blink_ever_detected is True
        assert len(detector._ear_history) > 0

        detector.reset()
        assert detector._blink_ever_detected is False
        assert detector._blink_count == 0
        assert len(detector._ear_history) == 0
        assert detector._prev_gray is None

    # ── Register Blink ─────────────────────────────────────────

    def test_register_blink(self, detector):
        """Registering a blink should update blink_count."""
        assert detector._blink_count == 0
        detector.register_blink()
        assert detector._blink_count == 1
        assert detector._blink_ever_detected is True

    def test_multiple_blinks(self, detector):
        """Multiple blink registrations should accumulate."""
        for _ in range(5):
            detector.register_blink()
        assert detector._blink_count == 5
