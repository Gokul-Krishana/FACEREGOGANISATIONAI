"""
Adaptive Multi-Factor Recognition (AMFR) Engine
=================================================

The risk-aware decision engine that combines all recognition factors
into a single confidence score and decision:

.. code-block:: text

    ArcFace similarity
          +
    Liveness confidence
          +
    Face quality score
          +
    Multi-frame consistency
          +
    Tracking stability
          ↓
       AMFR Engine
          ↓
    Risk score + Decision

Decision states::

    HIGH CONFIDENCE + LIVE  ──→ ACCEPT     (attendance marked)
    BORDERLINE              ──→ BORDERLINE (collect more frames)
    LOW CONFIDENCE          ──→ UNKNOWN    (treated as unknown person)
    SPOOF DETECTED          ──→ REJECT     (reject + security alert)

Pipeline role:  YOLO → RetinaFace → Quality → Liveness → ArcFace → FAISS → **AMFR**
                                                                               ↑
                                                                          You are here
"""

from __future__ import annotations

import enum
import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

import config.config as cfg
from app.face_quality import FaceQualityAssessment
from app.liveness_detector import LivenessDetector
from app.tracking import MultiFrameTracker, TrackState

logger = logging.getLogger(__name__)


class AMFRDecision(str, enum.Enum):
    """The four possible outcomes of the AMFR engine."""

    ACCEPT = "ACCEPT"               # High confidence, live — mark attendance
    BORDERLINE = "BORDERLINE"       # Reasonable but uncertain — collect more frames
    LOW_CONFIDENCE = "LOW_CONFIDENCE"  # Poor match or quality — treat as unknown
    REJECT_SPOOF = "REJECT_SPOOF"   # Spoof detected — reject + security alert
    PENDING = "PENDING"             # Not enough data yet


class AMFREngine:
    """Core AMFR recognition decision engine.

    Combines all recognition factors into a single risk score and
    decision, implementing the full:

        RetinaFace → FaceQuality → Liveness → ArcFace → FAISS → AMFR

    pipeline in a single call.

    Usage::

        engine = AMFREngine()

        # Process a full frame
        decisions = engine.process_frame(frame, yolo_detections)

        for d in decisions:
            print(d["name"], d["amfr_decision"], d["risk_score"])
    """

    def __init__(self) -> None:
        self.quality = FaceQualityAssessment()
        self.tracker = MultiFrameTracker()

        # Per-track liveness detector instances.
        # Each tracked person needs their own blink/motion history
        # so that person A blinking doesn't affect person B's score.
        self._liveness_instances: Dict[str, LivenessDetector] = {}

        # Cached from the last tracker.update() call for status queries
        self._last_tracks: List[TrackState] = []

    # ── Public API ────────────────────────────────────────────

    def process_frame(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        embeddings: List[Optional[np.ndarray]],
        faiss_results: List[List[Dict]],
        face_data: List[Optional[Dict]],    # from recognizer.detect_face()
    ) -> List[Dict]:
        """Run the full AMFR pipeline on a frame's detections.

        Each element in the returned list corresponds to one detection
        and augments it with AMFR decision fields.

        Args:
            frame: Full BGR frame.
            detections: YOLO detection dicts with ``bbox`` key.
            embeddings: ArcFace embedding per detection (or ``None``).
            faiss_results: ``FaceEnrollment.search()`` result per detection.
            face_data: Output of ``recognizer.detect_face()`` per detection.

        Returns:
            Each input detection dict enhanced with:
                - ``name``
                - ``confidence``
                - ``amfr_decision`` (``AMFRDecision`` value)
                - ``risk_score`` (float 0-1)
                - ``amfr_details`` (dict of per-factor scores)
        """
        # ── Step A: Assign each detection a track_id via IoU matching ─
        # Done BEFORE full evaluation so each detection gets its own
        # per-track liveness detector (blink/motion state stays isolated).
        bbox_only = [{"bbox": d["bbox"], "name": "", "confidence": 0.0} for d in detections]
        self._last_tracks = self.tracker.update(bbox_only, frame.shape[:2])
        active_tracks = {t.track_id: t for t in self._last_tracks}

        # Clean up stale liveness detectors for tracks that disappeared
        self._cleanup_stale_liveness(set(active_tracks.keys()))

        # Match each input detection to its track_id
        det_to_track: List[Optional[str]] = []
        for det in detections:
            matched_tid: Optional[str] = None
            best_iou = 0.0
            for track in self._last_tracks:
                if track.bbox is not None:
                    iou = MultiFrameTracker._iou(track.bbox, det["bbox"])
                    if iou > best_iou and iou > 0.3:
                        best_iou = iou
                        matched_tid = track.track_id
            det_to_track.append(matched_tid)

        # ── Step B: Single-pass full evaluation with correct track_id ─
        results: List[Dict] = []
        for i, det in enumerate(detections):
            embedding = embeddings[i] if i < len(embeddings) else None
            faiss = faiss_results[i] if i < len(faiss_results) else []
            face = face_data[i] if i < len(face_data) else None
            track_id = det_to_track[i]

            result = self._evaluate_person(
                frame, det, embedding, faiss, face,
                track_id=track_id,
            )
            results.append(result)

        # ── Step C: Re-update tracker with enriched results ──────────
        # This is critical: it feeds identity/confidence info back into
        # the tracker so subsequent frames can use identity_stability,
        # consistent_frames, and other temporal smoothing features.
        self._last_tracks = self.tracker.update(results, frame.shape[:2])

        # Augment results with tracking metadata
        track_map = {t.track_id: t for t in self._last_tracks}
        for i, result in enumerate(results):
            track_id = det_to_track[i]
            if track_id and track_id in track_map:
                track = track_map[track_id]
                result["track_id"] = track_id
                result["track_frames"] = track.total_frames
                if track.identity is not None:
                    result["identity_stability"] = round(track.identity_stability, 3)

        return results

    def reset(self) -> None:
        """Reset all temporal state (scene change, camera switch, etc.)."""
        self.tracker.reset()
        self._liveness_instances.clear()

    def get_all_tracks(self) -> List[TrackState]:
        """Return current active tracker states."""
        return self._last_tracks

    def status(self) -> Dict:
        """Return a snapshot of AMFR engine state."""
        tracks = self.get_all_tracks()
        spoofed = sum(1 for t in tracks if t.spoof_frame_count > 2)
        accepted = sum(1 for t in tracks if t.attendance_marked)
        return {
            "active_tracks": len(tracks),
            "spoof_detected": spoofed,
            "attendance_marked": accepted,
        }

    # ── Single-Person Evaluation ──────────────────────────────

    def _get_liveness_detector(self, track_id: str) -> LivenessDetector:
        """Get or create a per-track liveness detector.

        Each tracked person gets their own LivenessDetector instance so
        that blink history, motion baselines, and texture observations
        are isolated per individual.
        """
        if track_id not in self._liveness_instances:
            self._liveness_instances[track_id] = LivenessDetector()
        return self._liveness_instances[track_id]

    def _cleanup_stale_liveness(self, active_tracks: set) -> None:
        """Remove liveness detectors for tracks that no longer exist."""
        stale = set(self._liveness_instances.keys()) - active_tracks
        for tid in stale:
            del self._liveness_instances[tid]

    def _evaluate_person(
        self,
        frame: np.ndarray,
        det: Dict,
        embedding: Optional[np.ndarray],
        faiss: List[Dict],
        face: Optional[Dict],
        track_id: Optional[str] = None,
    ) -> Dict:
        """Evaluate a single detected person through the full AMFR stack.

        Returns:
            Augmented detection dict with AMFR fields.
        """
        bbox = det["bbox"]
        name = "Unknown"
        confidence = 0.0

        # ── Step 1: Face data from RetinaFace ────────────────
        det_score = face.get("det_score", 0.0) if face else 0.0
        landmarks = np.array(face["landmarks"]) if face and face.get("landmarks") else None
        face_bbox = face.get("bbox") if face else None

        # ── Step 2: Face Quality Assessment ──────────────────
        quality_result = None
        if face and face.get("embedding") is not None:
            if face_bbox:
                x1, y1, x2, y2 = face_bbox
                face_crop = frame[y1:y2, x1:x2] if y2 > y1 and x2 > x1 else None
            else:
                face_crop = None

            if face_crop is not None and face_crop.size > 0:
                quality_result = self.quality.assess(
                    face_img=face_crop,
                    det_score=det_score,
                    face_bbox=face_bbox,
                    img_shape=frame.shape[:2],
                    landmarks=landmarks,
                )
        quality_score = quality_result["overall"] if quality_result else 0.5

        # ── Step 3: FAISS search result ──────────────────────
        arcface_distance = 999.0
        if faiss:
            name = faiss[0]["name"]
            confidence = faiss[0]["confidence"]
            arcface_distance = faiss[0].get("distance", 999.0)

        # ── Step 4: Liveness Detection (per-track instance) ──
        liveness_result = None
        face_for_liveness = None
        if face and face_bbox:
            x1, y1, x2, y2 = face_bbox
            face_for_liveness = frame[y1:y2, x1:x2] if y2 > y1 and x2 > x1 else None

        if face_for_liveness is not None and face_for_liveness.size > 0:
            # Use per-track liveness detector for isolated blink/motion state
            liveness_detector = self._get_liveness_detector(track_id or "_default")
            liveness_result = liveness_detector.analyze_frame(
                face_img=face_for_liveness,
                landmarks=landmarks,
            )
        liveness_score = liveness_result.liveness_score if liveness_result else 0.5
        is_live = liveness_result.is_live if liveness_result else True

        # ── Step 5: AMFR Decision ────────────────────────────
        amfr_decision, risk_score, decision_details = self._decide(
            arcface_distance=arcface_distance,
            liveness_score=liveness_score,
            quality_score=quality_score,
            is_live=is_live,
            faiss_confidence=confidence,
        )

        # ── Build result ─────────────────────────────────────
        result = {
            "bbox": bbox,
            "name": name if amfr_decision != AMFRDecision.LOW_CONFIDENCE else "Unknown",
            "confidence": round(confidence, 4),
            "is_known": amfr_decision == AMFRDecision.ACCEPT,
            "is_live": is_live,
            "amfr_decision": amfr_decision.value,
            "risk_score": round(risk_score, 4),
            "arcface_distance": round(arcface_distance, 4),
            "liveness_score": round(liveness_score, 4),
            "quality_score": round(quality_score, 4),
            "amfr_details": {
                **decision_details,
                "quality": quality_result,
                "liveness": {
                    "texture_score": round(liveness_result.texture_score, 4) if liveness_result else None,
                    "blink_score": round(liveness_result.blink_score, 4) if liveness_result else None,
                    "motion_score": round(liveness_result.motion_score, 4) if liveness_result else None,
                    "screen_score": round(liveness_result.screen_score, 4) if liveness_result else None,
                    "blink_detected": liveness_result.blink_detected if liveness_result else False,
                    "reasons": liveness_result.reasons if liveness_result else [],
                } if liveness_result else None,
            },
            "trigger_security_alert": amfr_decision == AMFRDecision.REJECT_SPOOF,
        }

        return result

    # ── Decision Logic ────────────────────────────────────────

    def _decide(
        self,
        arcface_distance: float,
        liveness_score: float,
        quality_score: float,
        is_live: bool,
        faiss_confidence: float,
    ) -> Tuple[AMFRDecision, float, Dict]:
        """Core AMFR risk-aware decision.

        Calculates a composite risk score and decides the outcome.

        Returns:
            ``(decision, risk_score, details_dict)``.
        """
        details: Dict = {}

        # ── 1. Liveness gate (hard reject on spoof) ──────────
        if not is_live:
            details["liveness_gate"] = "FAILED"
            if liveness_score < cfg.LIVENESS_SPOOF_THRESHOLD:
                details["spoof_reason"] = "liveness_below_spoof_threshold"
                return AMFRDecision.REJECT_SPOOF, 0.0, details

        details["liveness_gate"] = "PASSED"

        # ── 2. Quality gate ──────────────────────────────────
        if quality_score < cfg.FACE_QUALITY_MIN_SCORE:
            details["quality_gate"] = "FAILED"
            # Still possible, but heavily penalised
        else:
            details["quality_gate"] = "PASSED"

        # ── 3. ArcFace similarity score ──────────────────────
        # Normalise: 0.0 → identical, threshold → borderline, >2*threshold → unknown
        # Map to [0, 1] confidence where 1 = perfect match
        if arcface_distance >= 999.0:
            arcface_score = 0.0  # No FAISS match at all
        else:
            arcface_score = 1.0 / (1.0 + (arcface_distance / max(cfg.RECOGNITION_THRESHOLD, 0.1)) ** 2)

        details["arcface_score"] = round(float(arcface_score), 4)

        # ── 4. Composite risk score ──────────────────────────
        # Weights determined by empirical testing priorities
        risk_score = (
            arcface_score * cfg.AMFR_WEIGHT_ARCFACE
            + liveness_score * cfg.AMFR_WEIGHT_LIVENESS
            + quality_score * cfg.AMFR_WEIGHT_QUALITY
        )
        risk_score = float(np.clip(risk_score, 0.0, 1.0))
        details["risk_score"] = round(risk_score, 4)

        # ── 5. Decision ──────────────────────────────────────
        if liveness_score < cfg.LIVENESS_SPOOF_THRESHOLD:
            decision = AMFRDecision.REJECT_SPOOF
        elif risk_score >= cfg.AMFR_HIGH_CONFIDENCE_THRESHOLD:
            decision = AMFRDecision.ACCEPT
        elif risk_score >= cfg.AMFR_BORDERLINE_THRESHOLD:
            decision = AMFRDecision.BORDERLINE
        elif arcface_score > 0.3 and quality_score > 0.4:
            # Low risk but arcface says possible match — borderline
            decision = AMFRDecision.BORDERLINE
        else:
            decision = AMFRDecision.LOW_CONFIDENCE

        details["decision"] = decision.value
        details["thresholds"] = {
            "high_confidence": cfg.AMFR_HIGH_CONFIDENCE_THRESHOLD,
            "borderline": cfg.AMFR_BORDERLINE_THRESHOLD,
            "spoof": cfg.LIVENESS_SPOOF_THRESHOLD,
        }

        return decision, risk_score, details
