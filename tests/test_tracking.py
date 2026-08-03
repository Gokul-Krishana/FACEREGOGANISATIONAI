"""
Tests for MultiFrameTracker (IoU-based multi-person tracking).

Covers track creation, IoU matching, greedy assignment, track updates,
disappearance handling, pruning, identity smoothing, and edge cases.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pytest

from app.tracking import MultiFrameTracker, TrackState


@pytest.fixture()
def tracker() -> MultiFrameTracker:
    """Return a fresh MultiFrameTracker with default settings."""
    return MultiFrameTracker(iou_threshold=0.4, max_disappeared=10)


@pytest.fixture()
def two_boxes() -> List[Dict]:
    """Two distinct bounding boxes."""
    return [
        {"bbox": (10, 10, 50, 50)},
        {"bbox": (200, 200, 300, 300)},
    ]


def _make_detections(bboxes: List[Tuple[int, int, int, int]]) -> List[Dict]:
    """Convert bbox tuples to detection dicts."""
    return [{"bbox": b} for b in bboxes]


class TestTrackState:
    """Tests for the TrackState dataclass."""

    def test_initial_state(self):
        """A new track should start with default values."""
        track = TrackState(
            track_id="T000001-abc123",
            first_seen=1000.0,
            last_seen=1000.0,
        )
        assert track.total_frames == 0
        assert track.consistent_frames == 0
        assert track.identity is None
        assert track.attendance_marked is False
        assert track.spoof_frame_count == 0

    def test_avg_arcface_empty(self):
        """Empty arcface list should return a sentinel value."""
        track = TrackState(track_id="T1", first_seen=0.0, last_seen=0.0)
        assert track.avg_arcface_distance == 999.0

    def test_avg_arcface_with_values(self):
        """Average should be computed correctly."""
        track = TrackState(track_id="T1", first_seen=0.0, last_seen=0.0)
        track.arcface_distances = [1.0, 2.0, 3.0]
        assert track.avg_arcface_distance == 2.0

    def test_identity_stability_zero(self):
        """No frames → stability is 0."""
        track = TrackState(track_id="T1", first_seen=0.0, last_seen=0.0)
        assert track.identity_stability == 0.0

    def test_identity_stability_half(self):
        """Half consistent → stability = 0.5."""
        track = TrackState(track_id="T1", first_seen=0.0, last_seen=0.0)
        track.total_frames = 4
        track.consistent_frames = 2
        assert track.identity_stability == 0.5

    def test_repr(self):
        """String representation should include key info."""
        track = TrackState(track_id="T000001-abc123", first_seen=0.0, last_seen=0.0)
        r = repr(track)
        assert "Track" in r
        assert "T000001" in r


class TestMultiFrameTracker:
    """Tests for MultiFrameTracker."""

    # ── IoU ───────────────────────────────────────────────────

    def test_iou_identical(self, tracker):
        """IoU of identical boxes should be 1.0."""
        box = (10, 10, 50, 50)
        iou = tracker._iou(box, box)
        assert iou == pytest.approx(1.0)

    def test_iou_no_overlap(self, tracker):
        """IoU of non-overlapping boxes should be 0.0."""
        box_a = (10, 10, 50, 50)
        box_b = (200, 200, 300, 300)
        iou = tracker._iou(box_a, box_b)
        assert iou == 0.0

    def test_iou_partial(self, tracker):
        """IoU of partially overlapping boxes should be in (0, 1)."""
        box_a = (10, 10, 100, 100)
        box_b = (50, 50, 150, 150)
        iou = tracker._iou(box_a, box_b)
        assert 0.0 < iou < 1.0

    def test_iou_zero_area(self, tracker):
        """IoU involving a zero-area box should not crash."""
        box_a = (10, 10, 50, 50)
        box_b = (10, 10, 10, 10)  # zero area
        iou = tracker._iou(box_a, box_b)
        assert iou == 0.0

    # ── Greedy Assignment ─────────────────────────────────────

    def test_greedy_basic(self, tracker):
        """Simple 2x2 assignment should match highest IoU pairs."""
        matrix = np.array([[0.9, 0.1], [0.1, 0.8]], dtype=np.float32)
        tracks, dets = tracker._greedy_assign(matrix)
        assert len(tracks) == 2
        assert len(dets) == 2
        assert tracks[0] == 0  # Highest = (0, 0)
        assert tracks[1] == 1  # Next = (1, 1)

    def test_greedy_empty(self, tracker):
        """Empty matrix should return empty assignments."""
        matrix = np.zeros((0, 0), dtype=np.float32)
        tracks, dets = tracker._greedy_assign(matrix)
        assert tracks == []
        assert dets == []

    def test_greedy_no_match(self, tracker):
        """All IoUs below threshold should return no matches."""
        matrix = np.array([[0.001, 0.002], [0.003, 0.004]], dtype=np.float32)
        tracks, dets = tracker._greedy_assign(matrix)
        assert len(tracks) == 0 or len(dets) == 0

    def test_greedy_uneven(self, tracker):
        """More tracks than detections should only match available."""
        matrix = np.array([[0.9, 0.0], [0.0, 0.9], [0.5, 0.0]], dtype=np.float32)
        tracks, dets = tracker._greedy_assign(matrix)
        assert len(tracks) == 2
        assert len(dets) == 2

    # ── First Frame ───────────────────────────────────────────

    def test_first_frame(self, tracker, two_boxes):
        """First frame should create tracks for all detections."""
        tracks = tracker.update(two_boxes, (480, 640))
        assert len(tracks) == 2
        for track in tracks:
            assert track.track_id is not None
            assert track.total_frames == 1
            assert track.bbox is not None

    # ─── Track Identity ──────────────────────────────────────

    def test_track_identity_assigned(self, tracker, two_boxes):
        """Track should store identity from detection."""
        # First frame — create tracks
        tracker.update(two_boxes, (480, 640))
        # Second frame — update with same boxes + names
        updated = [
            {"bbox": (10, 10, 50, 50), "name": "Alice", "arcface_distance": 0.5},
            {"bbox": (200, 200, 300, 300), "name": "Bob", "arcface_distance": 0.6},
        ]
        tracks = tracker.update(updated, (480, 640))
        names = [t.identity for t in tracks if t.identity]
        assert len(names) > 0

    # ── Disappearance → Pruning ───────────────────────────────

    def test_disappeared_then_pruned(self, tracker):
        """Tracks that disappear for max_disappeared should be removed."""
        det = [{"bbox": (10, 10, 50, 50)}]
        tracker.update(det, (480, 640))
        assert tracker.active_track_count() == 1

        # Send empty frames until track disappears
        for _ in range(tracker.max_disappeared + 2):
            tracker.update([], (480, 640))

        assert tracker.active_track_count() == 0

    def test_reappear_after_disappear(self, tracker):
        """A track that disappears briefly and reappears should resume."""
        det = [{"bbox": (10, 10, 50, 50)}]
        tracker.update(det, (480, 640))
        original_ids = {t.track_id for t in tracker._active_tracks()}

        # A few empty frames
        for _ in range(3):
            tracker.update([], (480, 640))

        # Same person reappears
        tracker.update(det, (480, 640))
        new_ids = {t.track_id for t in tracker._active_tracks()}

        # Track should still be the same (not pruned since < max_disappeared)
        assert original_ids == new_ids

    # ── Score Accumulation ─────────────────────────────────────

    def test_score_accumulation(self, tracker):
        """Track should accumulate scores across frames."""
        det = [
            {
                "bbox": (10, 10, 50, 50),
                "name": "Alice",
                "arcface_distance": 0.5,
                "liveness_score": 0.8,
                "quality_score": 0.9,
                "amfr_decision": "ACCEPT",
            }
        ]
        for _ in range(5):
            tracker.update(det, (480, 640))

        tracks = tracker._active_tracks()
        assert len(tracks) == 1
        assert tracks[0].total_frames == 5
        assert len(tracks[0].arcface_distances) == 5
        assert len(tracks[0].liveness_scores) == 5
        assert len(tracks[0].quality_scores) == 5
        assert len(tracks[0].amfr_decisions) == 5

    # ── No Detections ─────────────────────────────────────────

    def test_no_detections_first_frame(self, tracker):
        """Empty first frame should return no tracks."""
        tracks = tracker.update([], (480, 640))
        assert tracks == []

    def test_no_detections_after_tracks(self, tracker):
        """Empty frame after established tracks should mark them disappeared."""
        det = [{"bbox": (10, 10, 50, 50)}]
        tracker.update(det, (480, 640))
        assert tracker.active_track_count() == 1

        tracker.update([], (480, 640))
        # Track still exists (not pruned yet)
        assert tracker.active_track_count() == 1

    # ── Reset ─────────────────────────────────────────────────

    def test_reset_clears_all(self, tracker):
        """Reset should remove all tracks and reset counter."""
        det = [{"bbox": (10, 10, 50, 50)}]
        tracker.update(det, (480, 640))
        assert tracker.active_track_count() == 1

        tracker.reset()
        assert tracker.active_track_count() == 0
        assert len(tracker._tracks) == 0

    # ── Multiple Persons ──────────────────────────────────────

    def test_multiple_persons_separate_tracks(self, tracker):
        """Different bounding boxes should create separate tracks."""
        bboxes = [
            {"bbox": (10, 10, 50, 50)},
            {"bbox": (200, 200, 300, 300)},
            {"bbox": (400, 10, 500, 100)},
        ]
        tracks = tracker.update(bboxes, (640, 480))
        assert len(tracks) == 3
        # All track IDs should be unique
        ids = [t.track_id for t in tracks]
        assert len(set(ids)) == 3

    # ── Identity Switching ────────────────────────────────────

    def test_identity_switch_penalty(self, tracker):
        """When identity changes, confidence should be penalised."""
        det_a = [
            {
                "bbox": (10, 10, 50, 50),
                "name": "Alice",
                "arcface_distance": 0.5,
            }
        ]
        tracker.update(det_a, (480, 640))
        track = tracker._active_tracks()[0]
        orig_confidence = track.identity_confidence

        # Identity switches to Bob
        det_b = [
            {
                "bbox": (10, 10, 50, 50),
                "name": "Bob",
                "arcface_distance": 0.6,
            }
        ]
        tracker.update(det_b, (480, 640))

        # Confidence should be penalised (halved)
        assert track.identity_confidence < orig_confidence * 0.6

    # ── Spoof Tracking ────────────────────────────────────────

    def test_spoof_frame_tracking(self, tracker):
        """Repeated REJECT_SPOOF decisions should increment spoof count."""
        det = [
            {
                "bbox": (10, 10, 50, 50),
                "name": "Unknown",
                "amfr_decision": "REJECT_SPOOF",
            }
        ]
        for _ in range(5):
            tracker.update(det, (480, 640))

        tracks = tracker._active_tracks()
        assert tracks[0].spoof_frame_count == 5

    def test_attendance_marked(self, tracker):
        """Attendance flag should persist on track."""
        det = [{"bbox": (10, 10, 50, 50)}]
        tracker.update(det, (480, 640))
        track = tracker._active_tracks()[0]
        assert track.attendance_marked is False
