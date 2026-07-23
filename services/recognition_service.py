"""
Recognition Service — orchestrates the full AI pipeline and database logging.

This is the highest-level service that ties together:
    1. YOLO person detection
    2. RetinaFace face detection
    3. ArcFace embedding extraction
    4. FAISS similarity search
    5. Database logging (recognition_log + attendance + unknown_faces)

The dashboard and API layer call this service — they never touch
the AI modules directly.
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
    """Orchestrates the full recognition pipeline and database logging.

    Usage::

        service = RecognitionService()
        annotated = service.process_frame(frame)
        service.process_frame_detailed(frame)  # returns (annotated, detections)
    """

    def __init__(self) -> None:
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()
        self.enrollment = FaceEnrollment()

        # Pipeline configuration
        self.conf_threshold = cfg.YOLO_CONFIDENCE
        self.recog_threshold = cfg.RECOGNITION_THRESHOLD
        self.frame_skip = cfg.FRAME_SKIP
        self._frame_count = 0

        # Session tracking
        self._marked_this_session: set = set()
        self._last_recognised: List[Dict] = []
        self._cooldown: Dict[str, float] = {}  # name -> last_mark_time

        # FPS
        self._fps = 0.0
        self._prev_time = time.time()

    # ── Public API ────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process a single frame through the full pipeline.

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
        """Process a frame and return both the annotation and detection data.

        Args:
            frame: BGR image (H×W×3).

        Returns:
            Tuple of ``(annotated_frame, detections)`` where each detection
            contains ``bbox``, ``name``, ``confidence``, ``is_known``.
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

        results: List[Dict] = []
        for det in detections:
            bbox = det["bbox"]
            person_crop = self.detector.crop_person(frame, bbox)
            if person_crop.size == 0:
                continue

            # Step 2 — ArcFace embedding
            embedding = self.recognizer.extract_embedding(person_crop)
            if embedding is None:
                results.append({"bbox": bbox, "name": "No Face", "confidence": 0.0, "is_known": False})
                continue

            # Step 3 — FAISS search
            matches = self.enrollment.search(embedding, k=1, threshold=self.recog_threshold)

            if matches:
                name = matches[0]["name"]
                conf = matches[0]["confidence"]
                is_known = True

                # Look up employee from DB
                emp = EmployeeService.get_by_employee_id(name)
                emp_id = emp.id if emp else None

                # Mark attendance with cooldown
                self._maybe_mark_attendance(name, emp_id, conf)

                # Log recognition event
                self._log_recognition(emp_id, True, conf)

                results.append({"bbox": bbox, "name": name, "confidence": conf, "is_known": True})
            else:
                # Unknown face — save snapshot
                self._handle_unknown_face(person_crop)
                results.append({"bbox": bbox, "name": "Unknown", "confidence": 0.0, "is_known": False})

        self._last_recognised = results
        return self._draw_overlay(frame, results), results

    def status(self) -> Dict:
        """Return a snapshot of the current system state."""
        return {
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
            "enrolled": self.enrollment.status(),
            "attendance": AttendanceService.get_statistics(),
            "session_marked": len(self._marked_this_session),
        }

    # ── Internal: Attendance & Logging ────────────────────────

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
        self, employee_id: Optional[int], is_known: bool, confidence: float
    ) -> None:
        """Log every recognition event to the database."""
        try:
            with get_session() as session:
                RecognitionLogRepo.create(
                    session,
                    is_known=is_known,
                    confidence=confidence,
                    employee_id=employee_id,
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
        """Draw bounding boxes, labels, and HUD on the frame."""
        for item in recognised:
            x1, y1, x2, y2 = item["bbox"]
            name = item["name"]
            conf = item["confidence"]
            is_known = item.get("is_known", False)

            if is_known:
                color = (0, 255, 0)  # Green for known faces
            elif name == "No Face":
                color = (0, 165, 255)  # Orange for no face detected
            else:
                color = (0, 0, 255)  # Red for unknown faces
            label = f"{name} ({conf:.2f})" if conf > 0 else name

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # HUD
        enrolled = self.enrollment.count()
        lines = [
            f"FPS: {self._fps:.1f}",
            f"Enrolled: {enrolled}",
            f"Unknown faces saved: {len(self._last_recognised)}",
        ]
        for i, line in enumerate(lines):
            y = 25 + i * 22
            cv2.putText(frame, line, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        return frame
