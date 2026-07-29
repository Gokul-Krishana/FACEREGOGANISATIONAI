"""
Multi-Frame Tracker — Temporal Identity Smoothing
===================================================

Tracks individuals across successive frames using bounding-box IoU
matching.  Accumulates recognition, liveness, and quality scores over
time for reliable AMFR decisions.

Pipeline role:  YOLO → RetinaFace → Quality → Liveness → ArcFace → FAISS
                                    ↓
                              **Tracker**  ← assigns track_id, smooths identity
                                    ↓
                               AMFR Engine
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

import config.config as cfg


@dataclass
class TrackState:
    """Mutable state for a single tracked individual."""

    track_id: str
    first_seen: float                   # Seconds since epoch
    last_seen: float                    # Seconds since epoch
    total_frames: int = 0
    consistent_frames: int = 0          # Frames with same identity match
    unknown_frames: int = 0             # Frames where identity was unknown

    # Bounding box (smoothed)
    bbox: Optional[Tuple[int, int, int, int]] = None

    # Best-guess identity
    identity: Optional[str] = None
    identity_confidence: float = 0.0

    # Score accumulators
    arcface_distances: List[float] = field(default_factory=list)
    liveness_scores: List[float] = field(default_factory=list)
    quality_scores: List[float] = field(default_factory=list)
    amfr_decisions: List[str] = field(default_factory=list)

    # Whether attendance has been marked for this track this session
    attendance_marked: bool = False

    # Spoof/alert tracking
    spoof_frame_count: int = 0
    security_alert_triggered: bool = False

    @property
    def avg_arcface_distance(self) -> float:
        return float(np.mean(self.arcface_distances)) if self.arcface_distances else 999.0

    @property
    def avg_liveness_score(self) -> float:
        return float(np.mean(self.liveness_scores)) if self.liveness_scores else 0.0

    @property
    def avg_quality_score(self) -> float:
        return float(np.mean(self.quality_scores)) if self.quality_scores else 0.0

    @property
    def identity_stability(self) -> float:
        """Ratio of frames where identity was consistent."""
        if self.total_frames == 0:
            return 0.0
        return self.consistent_frames / self.total_frames

    def __repr__(self) -> str:
        return (
            f"<Track {self.track_id[:8]} "
            f"identity={self.identity or 'unknown'} "
            f"frames={self.total_frames} "
            f"stable={self.identity_stability:.2f}>"
        )


class MultiFrameTracker:
    """IoU-based multi-person tracker with identity smoothing.

    Usage::

        tracker = MultiFrameTracker(
            iou_threshold=0.4,
            max_disappeared=30,
        )

        # Per frame:
        tracks = tracker.update(detections, frame_shape)
        for track in tracks:
            # track.identity, track.identity_stability, etc.
            pass
    """

    def __init__(
        self,
        iou_threshold: float = 0.4,
        max_disappeared: int = 30,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_disappeared = max_disappeared
        self._tracks: Dict[str, TrackState] = {}
        self._disappeared: Dict[str, int] = defaultdict(int)
        self._next_track_id: int = 0

    # ── Public API ────────────────────────────────────────────

    def update(
        self,
        detections: List[Dict],
        frame_shape: Tuple[int, int],
    ) -> List[TrackState]:
        """Update track state with the current frame's detections.

        Each detection dict should contain at minimum a ``bbox`` key.
        When available, ``identity``, ``arcface_distance``,
        ``liveness_score``, and ``quality_score`` enhance the track.

        Args:
            detections: List of detection dicts from the pipeline.
            frame_shape: ``(height, width)`` of the frame.

        Returns:
            List of active ``TrackState`` objects for the current frame.
        """
        if not detections:
            # No detections — mark all existing tracks as disappeared
            self._mark_all_disappeared()
            return self._active_tracks()

        # Extract bboxes from detections
        input_bboxes = np.array([d["bbox"] for d in detections], dtype=np.int32)

        if not self._tracks:
            # First frame — create new tracks for all detections
            self._create_tracks(detections)
        else:
            # Match detections to existing tracks via IoU
            track_ids = list(self._tracks.keys())
            track_bboxes = np.array(
                [self._tracks[tid].bbox for tid in track_ids],
                dtype=np.int32,
            )

            # Compute IoU matrix
            iou_matrix = self._compute_iou_matrix(track_bboxes, input_bboxes)

            # Greedy assignment
            assigned_tracks, assigned_detections = self._greedy_assign(iou_matrix)

            # Update matched tracks
            for track_idx, det_idx in zip(assigned_tracks, assigned_detections):
                tid = track_ids[track_idx]
                self._update_track(tid, detections[det_idx])
                self._disappeared[tid] = 0

            # Mark unmatched tracks as disappeared
            unmatched_tracks = set(range(len(track_ids))) - set(assigned_tracks)
            for idx in unmatched_tracks:
                tid = track_ids[idx]
                self._disappeared[tid] += 1

            # Remove tracks that disappeared for too long
            self._prune_lost_tracks()

            # Create new tracks for unmatched detections
            unmatched_detections = set(range(len(detections))) - set(assigned_detections)
            for idx in unmatched_detections:
                self._create_track(detections[idx])

        return self._active_tracks()

    def reset(self) -> None:
        """Clear all tracks (use when changing scenes or cameras)."""
        self._tracks.clear()
        self._disappeared.clear()
        self._next_track_id = 0

    def get_track(self, track_id: str) -> Optional[TrackState]:
        """Get a specific track by ID."""
        return self._tracks.get(track_id)

    def active_track_count(self) -> int:
        return len(self._active_tracks())

    # ── Internal Matching ─────────────────────────────────────

    @staticmethod
    def _compute_iou_matrix(
        track_bboxes: np.ndarray,
        det_bboxes: np.ndarray,
    ) -> np.ndarray:
        """Compute IoU between every track and detection pair."""
        iou_matrix = np.zeros((len(track_bboxes), len(det_bboxes)), dtype=np.float32)

        for t, tbox in enumerate(track_bboxes):
            for d, dbox in enumerate(det_bboxes):
                iou_matrix[t, d] = MultiFrameTracker._iou(tbox, dbox)

        return iou_matrix

    @staticmethod
    def _iou(
        box_a: Tuple[int, int, int, int],
        box_b: Tuple[int, int, int, int],
    ) -> float:
        """Intersection-over-Union of two bounding boxes."""
        xa = max(box_a[0], box_b[0])
        ya = max(box_a[1], box_b[1])
        xb = min(box_a[2], box_b[2])
        yb = min(box_a[3], box_b[3])

        inter = max(0, xb - xa) * max(0, yb - ya)
        if inter == 0:
            return 0.0

        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / max(union, 1e-6)

    @staticmethod
    def _greedy_assign(
        iou_matrix: np.ndarray,
    ) -> Tuple[List[int], List[int]]:
        """Greedy bipartite matching from highest IoU to lowest.

        Returns:
            ``(track_indices, detection_indices)`` of matched pairs.
        """
        assigned_tracks: List[int] = []
        assigned_dets: List[int] = []

        if iou_matrix.size == 0:
            return assigned_tracks, assigned_dets

        # Work on a copy
        remaining_tracks = set(range(iou_matrix.shape[0]))
        remaining_dets = set(range(iou_matrix.shape[1]))

        # Iteratively pick the highest IoU pair
        while remaining_tracks and remaining_dets:
            max_iou = -1.0
            best_t = -1
            best_d = -1
            for t in remaining_tracks:
                for d in remaining_dets:
                    if iou_matrix[t, d] > max_iou:
                        max_iou = iou_matrix[t, d]
                        best_t = t
                        best_d = d

            if max_iou < 0.01:  # No meaningful match
                break

            assigned_tracks.append(best_t)
            assigned_dets.append(best_d)
            remaining_tracks.remove(best_t)
            remaining_dets.remove(best_d)

        return assigned_tracks, assigned_dets

    # ── State Management ──────────────────────────────────────

    def _create_tracks(self, detections: List[Dict]) -> None:
        """Create a new track for each detection."""
        for det in detections:
            self._create_track(det)

    def _create_track(self, det: Dict) -> TrackState:
        """Create and store a new track from a single detection."""
        tid = f"T{self._next_track_id:06d}-{uuid.uuid4().hex[:6]}"
        self._next_track_id += 1

        now = time.time()
        track = TrackState(
            track_id=tid,
            first_seen=now,
            last_seen=now,
            bbox=det["bbox"],
            total_frames=1,
        )
        self._tracks[tid] = track
        self._apply_detection(track, det)
        return track

    def _apply_detection(self, track: TrackState, det: Dict) -> None:
        """Fold one detection into a track's running statistics."""
        name = det.get("name")
        arcface_dist = det.get("arcface_distance", 999.0)
        liveness = det.get("liveness_score", 0.5)
        quality = det.get("quality_score", 0.5)
        amfr_decision = det.get("amfr_decision", "PENDING")

        track.arcface_distances.append(arcface_dist)
        track.liveness_scores.append(liveness)
        track.quality_scores.append(quality)
        track.amfr_decisions.append(amfr_decision)

        if name and name not in ("Unknown", "No Face"):
            score = 1.0 - arcface_dist / max(cfg.RECOGNITION_THRESHOLD * 2, 1)
            if track.identity is None:
                track.identity = name
                track.identity_confidence = score
                track.consistent_frames += 1
            elif track.identity == name:
                track.consistent_frames += 1
                track.identity_confidence = track.identity_confidence * 0.9 + score * 0.1
            else:
                track.identity = name
                track.identity_confidence = track.identity_confidence * 0.5
        else:
            track.unknown_frames += 1

        if amfr_decision == "REJECT_SPOOF":
            track.spoof_frame_count += 1

    def _update_track(self, tid: str, det: Dict) -> None:
        """Update an existing track with a new detection."""
        track = self._tracks[tid]
        track.last_seen = time.time()
        track.total_frames += 1
        track.bbox = det["bbox"]  # Simple last-bbox (could EMA-smooth here)

        # Identity
        name = det.get("name")
        arcface_dist = det.get("arcface_distance", 999.0)
        liveness = det.get("liveness_score", 0.5)
        quality = det.get("quality_score", 0.5)
        amfr_decision = det.get("amfr_decision", "PENDING")

        # Accumulate scores
        track.arcface_distances.append(arcface_dist)
        track.liveness_scores.append(liveness)
        track.quality_scores.append(quality)
        track.amfr_decisions.append(amfr_decision)

        # Identity consistency
        if name and name not in ("Unknown", "No Face"):
            if track.identity is None:
                track.identity = name
                track.identity_confidence = 1.0 - arcface_dist / max(cfg.RECOGNITION_THRESHOLD * 2, 1)
                track.consistent_frames += 1
            elif track.identity == name:
                track.consistent_frames += 1
                # Decaying EMA for confidence
                track.identity_confidence = track.identity_confidence * 0.9 + (1.0 - arcface_dist / max(cfg.RECOGNITION_THRESHOLD * 2, 1)) * 0.1
            else:
                # Identity changed — could be ID switch
                track.identity = name
                track.identity_confidence = track.identity_confidence * 0.5  # Penalise
        else:
            track.unknown_frames += 1

        # Spoof tracking
        if amfr_decision == "REJECT_SPOOF":
            track.spoof_frame_count += 1

    def _mark_all_disappeared(self) -> None:
        """Increment disappear count for all tracks."""
        for tid in list(self._tracks.keys()):
            self._disappeared[tid] += 1
        self._prune_lost_tracks()

    def _prune_lost_tracks(self) -> None:
        """Remove tracks that have been lost for too long."""
        lost = [
            tid
            for tid, count in self._disappeared.items()
            if count > self.max_disappeared
        ]
        for tid in lost:
            del self._tracks[tid]
            del self._disappeared[tid]

    def _active_tracks(self) -> List[TrackState]:
        """Return the current active tracks, newest first."""
        tracks = sorted(
            self._tracks.values(),
            key=lambda t: t.last_seen,
            reverse=True,
        )
        return tracks
