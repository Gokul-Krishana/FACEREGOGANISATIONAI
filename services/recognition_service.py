"""
Recognition Service — orchestrates the full AI pipeline and database logging.

This is the highest-level service that ties together:
    1. YOLO person detection
    2. RetinaFace face detection + quality + liveness
    3. ArcFace embedding extraction
    4. FAISS similarity search
    5. **AMFR** — Adaptive Multi-Factor Recognition decision engine
    6. Database logging (recognition_log + attendance + unknown_faces)

The dashboard and API layer call this service — they never touch
the AI modules directly.

Updated pipeline::

    YOLO → RetinaFace → FaceQuality → Liveness → ArcFace → FAISS → AMFR → decision
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config.config as cfg
from app.amfr_engine import AMFREngine, AMFRDecision
from app.face_detector import FaceDetector
from app.recognizer import FaceRecognizer
from app.enrollment import FaceEnrollment
from database.database import get_session
from database.repository import (
    AttendanceRepo,
    RecognitionLogRepo,
    UnknownFaceRepo,
)
from services.attendance_service import AttendanceService
from services.audit_service import AuditService
from services.employee_service import EmployeeService

logger = logging.getLogger(__name__)


class RecognitionService:
    """Orchestrates the full AI pipeline with AMFR decision engine.

    Usage::

        service = RecognitionService()
        annotated = service.process_frame(frame)
        service.process_frame_detailed(frame)  # returns (annotated, detections)
    """

    def __init__(self, detector=None, recognizer=None, enrollment=None, amfr=None) -> None:
        """Initialise the recognition pipeline.

        When pre-created AI models are passed, they are reused (sharing
        the expensive YOLO / InsightFace / FAISS / AMFR objects).
        Otherwise new instances are created.

        This allows sharing AI models across multiple camera pipelines
        while each pipeline gets its own per-camera state:

            shared_models = (detector, recognizer, enrollment, amfr)
            pipe1 = RecognitionService(*shared_models)
            pipe2 = RecognitionService(*shared_models)
        """
        self.detector = detector if detector is not None else FaceDetector()
        self.recognizer = recognizer if recognizer is not None else FaceRecognizer()
        self.enrollment = enrollment if enrollment is not None else FaceEnrollment()
        self.amfr = amfr if amfr is not None else AMFREngine()

        # Pipeline configuration
        self.conf_threshold = cfg.YOLO_CONFIDENCE
        self.recog_threshold = cfg.RECOGNITION_THRESHOLD
        self.frame_skip = cfg.FRAME_SKIP
        self._frame_count = 0

        # Session tracking (per-pipeline, not shared)
        self._marked_this_session: set = set()
        self._last_recognised: List[Dict] = []
        self._cooldown: Dict[str, float] = {}  # name -> last_mark_time

        # FPS (per-pipeline, not shared)
        self._fps = 0.0
        self._prev_time = time.time()

    @classmethod
    def with_shared_models(cls, models: 'RecognitionService') -> 'RecognitionService':
        """Create a new pipeline instance sharing the AI models from *models*.

        Use this when you want independent per-camera state (frame counter,
        FPS, session tracking) but share the expensive YOLO / InsightFace /
        FAISS / AMFR objects.

        Example::

            shared = RecognitionService()  # loads models once
            pipe1 = RecognitionService.with_shared_models(shared)
            pipe2 = RecognitionService.with_shared_models(shared)
        """
        return cls(
            detector=models.detector,
            recognizer=models.recognizer,
            enrollment=models.enrollment,
            amfr=models.amfr,
        )

    # ── Public API ────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process a single frame through the full AMFR pipeline.

        Args:
            frame: BGR image (H×W×3).

        Returns:
            Annotated frame with bounding boxes, labels, and HUD.
        """
        annotated, _ = self.process_frame_detailed(frame)
        return annotated

    def process_frame_detailed(
        self, frame: np.ndarray
    ) -> Tuple[np.ndarray, List[Dict]]:
        """Process a frame through the full AMFR pipeline.

        The pipeline is now:

            YOLO person detection
              ↓
            RetinaFace (face detection + landmarks)
              ↓
            FACE QUALITY assessment
              ↓
            LIVENESS detection (texture, blink, motion, screen)
              ↓
            ArcFace embedding
              ↓
            FAISS similarity search
              ↓
            AMFR engine (risk score + decision)
              ↓
            Action: accept / borderline / unknown / reject-spoof
              ↓
            DB logging

        Returns:
            Tuple of ``(annotated_frame, detections)`` where each detection
            contains AMFR decision data.
        """
        self._frame_count += 1

        # FPS
        now = time.time()
        self._fps = 0.9 * self._fps + 0.1 / (now - self._prev_time + 1e-6)
        self._prev_time = now

        # Skip frames
        if self._frame_count % self.frame_skip != 0:
            return self._draw_overlay(frame, self._last_recognised), self._last_recognised

        # Step 1 — YOLO person detection
        detections = self.detector.detect(frame, conf_threshold=self.conf_threshold)

        # Per-person intermediate data
        embeddings: List[Optional[np.ndarray]] = []
        faiss_results: List[List[Dict]] = []
        face_data: List[Optional[Dict]] = []
        yolo_detections: List[Dict] = []

        for det in detections:
            bbox = det["bbox"]
            person_crop = self.detector.crop_person(frame, bbox)
            if person_crop.size == 0:
                continue

            yolo_detections.append(det)

            # Step 2 — RetinaFace detection (detailed face data)
            face = self.recognizer.detect_face(person_crop)
            face_data.append(face)

            # Step 3 — ArcFace embedding
            embedding = self.recognizer.extract_embedding(person_crop)
            embeddings.append(embedding)

            # Step 4 — FAISS similarity search
            if embedding is not None:
                matches = self.enrollment.search(embedding, k=1, threshold=self.recog_threshold)
                faiss_results.append(matches)
            else:
                faiss_results.append([])

        # Step 5 — AMFR decision engine (combines quality + liveness + arcface + tracking)
        amfr_results = self.amfr.process_frame(
            frame=frame,
            detections=yolo_detections,
            embeddings=embeddings,
            faiss_results=faiss_results,
            face_data=face_data,
        )

        # Step 6 — Act on AMFR decisions
        results: List[Dict] = []
        for amfr_detection in amfr_results:
            bbox = amfr_detection["bbox"]
            decision = amfr_detection["amfr_decision"]
            name = amfr_detection["name"]
            risk_score = amfr_detection["risk_score"]
            liveness_score = amfr_detection["liveness_score"]
            quality_score = amfr_detection["quality_score"]
            arcface_distance = amfr_detection["arcface_distance"]

            if decision == AMFRDecision.ACCEPT.value:
                # ── High confidence + live — mark attendance ──
                emp = EmployeeService.get_by_employee_id(name)
                emp_id = emp.id if emp else None

                self._maybe_mark_attendance(
                    name=name,
                    employee_id=emp_id,
                    confidence=risk_score,
                )
                self._log_recognition(
                    employee_id=emp_id,
                    is_known=True,
                    confidence=risk_score,
                    liveness_score=liveness_score,
                    quality_score=quality_score,
                )
                results.append({
                    "bbox": bbox,
                    "name": name,
                    "confidence": risk_score,
                    "is_known": True,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                    "arcface_distance": arcface_distance,
                })

            elif decision == AMFRDecision.BORDERLINE.value:
                # ── Uncertain — known name but needs more frames ──
                # Log the event but don't mark attendance yet
                self._log_recognition(
                    employee_id=None,
                    is_known=True,
                    confidence=risk_score,
                    liveness_score=liveness_score,
                    quality_score=quality_score,
                )
                results.append({
                    "bbox": bbox,
                    "name": f"{name}?",
                    "confidence": risk_score,
                    "is_known": False,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                    "arcface_distance": arcface_distance,
                })

            elif decision == AMFRDecision.REJECT_SPOOF.value:
                # ── Spoof detected — reject + security alert ──
                self._log_recognition(
                    employee_id=None,
                    is_known=False,
                    confidence=0.0,
                    liveness_score=liveness_score,
                    quality_score=quality_score,
                    is_spoof=True,
                )
                AuditService.log(
                    "SPOOF_ATTEMPT",
                    f"Spoof attempt detected — liveness={liveness_score:.2f}, "
                    f"quality={quality_score:.2f}, arcface_distance={arcface_distance:.2f}",
                    operator="system",
                )
                results.append({
                    "bbox": bbox,
                    "name": "SPOOF",
                    "confidence": 0.0,
                    "is_known": False,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                    "arcface_distance": arcface_distance,
                })

            else:  # LOW_CONFIDENCE / no face
                # ── Low confidence or no face — unknown ──
                person_crop = self.detector.crop_person(frame, bbox)
                if person_crop.size > 0:
                    self._handle_unknown_face(person_crop)
                self._log_recognition(
                    employee_id=None,
                    is_known=False,
                    confidence=risk_score,
                    liveness_score=liveness_score,
                    quality_score=quality_score,
                )
                results.append({
                    "bbox": bbox,
                    "name": "Unknown",
                    "confidence": risk_score,
                    "is_known": False,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                    "arcface_distance": arcface_distance,
                })

        self._last_recognised = results
        return self._draw_overlay(frame, results), results

    def status(self) -> Dict:
        """Return a snapshot of the current system state."""
        amfr_state = self.amfr.status()
        return {
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
            "enrolled": self.enrollment.status(),
            "attendance": AttendanceService.get_statistics(),
            "session_marked": len(self._marked_this_session),
            "amfr": amfr_state,
        }

    # ── Internal: Attendance & Logging ────────────────────────

    def reset_tracking(self) -> None:
        """Reset per-pipeline session tracking and AMFR engine.

        Call this when starting a new recognition session (e.g. when
        the user clicks "Reset Session Markers").
        """
        self._marked_this_session.clear()
        self._cooldown.clear()
        self._frame_count = 0
        self._fps = 0.0
        self.amfr.reset()

    def _maybe_mark_attendance(
        self, name: str, employee_id: Optional[int], confidence: float
    ) -> None:
        """Mark attendance with cooldown to avoid spamming."""
        now = time.time()
        last = self._cooldown.get(name, 0)
        cooldown = getattr(cfg, "COOLDOWN_SECONDS", 60)

        if name not in self._marked_this_session and (now - last) > cooldown:
            if employee_id:
                AttendanceService.mark(
                    employee_id=employee_id,
                    confidence=confidence,
                    employee_name=name,
                )
                self._marked_this_session.add(name)
                self._cooldown[name] = now

    def _log_recognition(
        self,
        employee_id: Optional[int],
        is_known: bool,
        confidence: float,
        liveness_score: Optional[float] = None,
        quality_score: Optional[float] = None,
        is_spoof: bool = False,
    ) -> None:
        """Log every recognition event to the database with AMFR data."""
        try:
            with get_session() as session:
                RecognitionLogRepo.create(
                    session,
                    is_known=is_known,
                    confidence=confidence,
                    employee_id=employee_id,
                    liveness_confidence=liveness_score,
                )
        except Exception as exc:
            logger.warning("Failed to log recognition event: %s", exc)

    def _handle_unknown_face(self, face_img: np.ndarray) -> None:
        """Save an unknown face snapshot to disk and database."""
        try:
            timestamp = datetime.now()
            filename = f"unknown_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            save_path = cfg.UNKNOWN_FACES_DIR / filename
            cv2.imwrite(str(save_path), face_img)

            with get_session() as session:
                UnknownFaceRepo.create(
                    session,
                    image_path=str(save_path),
                    confidence=0.0,
                )

            AuditService.log(
                "UNKNOWN_FACE",
                f"Unknown face saved: {filename}",
            )
        except Exception as exc:
            logger.warning("Failed to save unknown face: %s", exc)

    # ── Rendering ─────────────────────────────────────────────

    def _draw_overlay(self, frame: np.ndarray, recognised: List[Dict]) -> np.ndarray:
        """Draw bounding boxes, AMFR decision badges, and HUD on the frame."""
        for item in recognised:
            x1, y1, x2, y2 = item["bbox"]
            name = item["name"]
            conf = item["confidence"]
            decision = item.get("amfr_decision", "")
            liveness = item.get("liveness_score", 0.0)
            risk = item.get("risk_score", 0.0)

            # ── Color by AMFR decision ───────────────────────
            if decision == AMFRDecision.ACCEPT.value:
                color = (0, 220, 0)       # Green — accepted
            elif decision == AMFRDecision.BORDERLINE.value:
                color = (0, 220, 220)     # Yellow — borderline
            elif decision == AMFRDecision.REJECT_SPOOF.value:
                color = (0, 0, 200)       # Red — spoof
            elif name == "No Face":
                color = (0, 165, 255)     # Orange — no face
            else:
                color = (128, 128, 128)   # Grey — unknown/low confidence

            # ── Multi-line label with AMFR info ──────────────
            label = f"{name}"
            if conf > 0:
                label += f" ({conf:.0%})"
            if decision in (AMFRDecision.ACCEPT.value, AMFRDecision.BORDERLINE.value):
                badge = f"[LIVE]" if liveness > 0.5 else f"[live:{liveness:.0%}]"
                label = f"{badge} {label}"
            elif decision == AMFRDecision.REJECT_SPOOF.value:
                label = f"[SPOOF] {name if name != 'SPOOF' else ''}"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # ── HUD ──────────────────────────────────────────────
        enrolled = self.enrollment.count()
        amfr_tracks = len(self.amfr.get_all_tracks()) if hasattr(self, 'amfr') and self.amfr else 0
        lines = [
            f"FPS: {self._fps:.1f}",
            f"Enrolled: {enrolled}",
            f"AMFR tracks: {amfr_tracks}",
        ]
        for i, line in enumerate(lines):
            y = 25 + i * 22
            cv2.putText(frame, line, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        return frame
