"""
Live Face Detection & Recognition — Real-time Pipeline (AMFR Enabled)
======================================================================

Ties together the full inference chain with AMFR anti-spoofing:

    Webcam frame
        ↓
    ┌────────────────┐
    │  YOLO (person)  │  ← face_detector.py
    └───────┬────────┘
            ↓ (crop per person)
    ┌──────────────────────┐
    │ RetinaFace (detect)   │  ← recognizer.py
    └───────┬──────────────┘
            ↓ (face with landmarks)
    ┌──────────────────────┐
    │ FaceQuality          │  ← face_quality.py  NEW!
    └───────┬──────────────┘
            ↓
    ┌──────────────────────┐
    │ Liveness (anti-spoof) │  ← liveness_detector.py  NEW!
    └───────┬──────────────┘
            ↓
    ┌────────────────┐
    │  ArcFace (emb)  │  ← recognizer.py
    └───────┬────────┘
            ↓ (512‑D vector)
    ┌────────────────┐
    │  FAISS search   │  ← enrollment.py
    └───────┬────────┘
            ↓
    ┌──────────────────────┐
    │  AMFR Engine (risk)   │  ← amfr_engine.py  NEW!
    └───────┬──────────────┘
            ↓ (ACCEPT / BORDERLINE / UNKNOWN / SPOOF)
    ┌────────────────┐
    │  Attendance     │  ← attendance.py
    └────────────────┘

Press ``q`` to quit, ``e`` to enroll the face in view.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path        from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ── Ensure project root is on sys.path for direct script execution ──
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg
from app.amfr_engine import AMFREngine, AMFRDecision
from app.face_detector import FaceDetector
from app.recognizer import FaceRecognizer
from app.enrollment import FaceEnrollment
from app.attendance import AttendanceTracker
from camera.selector import create_camera
from camera.base import CameraSource
from database.database import get_session
from database.repository import AttendanceRepo, UnknownFaceRepo
from services.employee_service import EmployeeService


class LiveDetection:
    """End‑to‑end real‑time face recognition pipeline with AMFR.

    Usage::

        pipeline = LiveDetection()
        pipeline.run()           # webcam loop
        # or
        annotated = pipeline.process_frame(frame)   # single frame
    """

    def __init__(self) -> None:
        """Initialise all sub‑modules including AMFR engine."""
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()
        self.enrollment = FaceEnrollment()
        self.attendance = AttendanceTracker()
        self.amfr = AMFREngine()

        # Pipeline controls
        self.conf_threshold = cfg.YOLO_CONFIDENCE
        self.recog_threshold = cfg.RECOGNITION_THRESHOLD
        self.frame_skip = cfg.FRAME_SKIP
        self._frame_count = 0

        # Track who has been marked this session
        self._marked_this_session: set = set()

        # Cache last detections to avoid flickering on skipped frames
        self._last_recognised: List[dict] = []

        # Cache employee lookups (name -> employee_id) so we don't hit the DB every frame
        self._employee_cache: Dict[str, Optional[str]] = {}

        # Cooldown for saving unknown faces (seconds between saves)
        self._unknown_save_cooldown: float = 3.0
        self._last_unknown_save: float = 0.0

        # FPS tracking
        self._fps = 0.0
        self._prev_time = time.time()

    # ── Frame Processing ──────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Run the full AMFR pipeline on a single frame.

        Args:
            frame: BGR image from camera or file.

        Returns:
            Annotated frame with bounding boxes, AMFR badges, and labels.
        """
        self._frame_count += 1

        # ── FPS calculation ──────────────────────────────────
        now = time.time()
        self._fps = 0.9 * self._fps + 0.1 / (now - self._prev_time + 1e-6)
        self._prev_time = now

        # ── Skip frames for performance ──────────────────────
        if self._frame_count % self.frame_skip != 0:
            return self._draw_overlay(frame, self._last_recognised)

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

            # Step 2 — RetinaFace detection (detailed face with landmarks)
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

        # Step 5 — AMFR decision engine
        # Combines: face quality + liveness + arcface similarity + tracking consistency
        amfr_results = self.amfr.process_frame(
            frame=frame,
            detections=yolo_detections,
            embeddings=embeddings,
            faiss_results=faiss_results,
            face_data=face_data,
        )

        # Step 6 — Act on AMFR decisions and log attendance
        recognised: List[Dict] = []
        for amfr_detection in amfr_results:
            bbox = amfr_detection["bbox"]
            decision = amfr_detection["amfr_decision"]
            name = amfr_detection["name"]
            risk_score = amfr_detection["risk_score"]
            liveness_score = amfr_detection["liveness_score"]
            quality_score = amfr_detection["quality_score"]

            if decision == AMFRDecision.ACCEPT.value:
                # ── High confidence + live → mark attendance ──
                print(f"  ✅ AMFR ACCEPT: {name} | risk={risk_score:.2%} | liveness={liveness_score:.2%}")
                if name not in self._marked_this_session:
                    self.attendance.mark(name, risk_score)
                    self._log_attendance_db(name, risk_score)
                    self._marked_this_session.add(name)
                recognised.append({
                    "bbox": bbox,
                    "name": name,
                    "confidence": risk_score,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                })

            elif decision == AMFRDecision.BORDERLINE.value:
                # ── Uncertain — needs more frames ─────────────
                print(f"  ⚠️  AMFR BORDERLINE: {name}? | risk={risk_score:.2%} | collecting more frames")
                recognised.append({
                    "bbox": bbox,
                    "name": f"{name}?",
                    "confidence": risk_score,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                })

            elif decision == AMFRDecision.REJECT_SPOOF.value:
                # ── Spoof detected! ───────────────────────────
                print(f"  🚨 AMFR SPOOF REJECTED | liveness={liveness_score:.2%} | risk={risk_score:.2%}")
                recognised.append({
                    "bbox": bbox,
                    "name": "SPOOF",
                    "confidence": 0.0,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                })

            else:  # LOW_CONFIDENCE / No Face
                # ── Unknown person ─────────────────────────────
                print(f"  ❌ AMFR UNKNOWN | risk={risk_score:.2%} | quality={quality_score:.2%}")
                person_crop = self.detector.crop_person(frame, bbox)
                if person_crop.size > 0 and (time.time() - getattr(self, '_last_unknown_save', 0)) > self._unknown_save_cooldown:
                    self._save_unknown_face(person_crop)
                    self._last_unknown_save = time.time()
                recognised.append({
                    "bbox": bbox,
                    "name": "Unknown",
                    "confidence": risk_score,
                    "amfr_decision": decision,
                    "risk_score": risk_score,
                    "liveness_score": liveness_score,
                    "quality_score": quality_score,
                })

        self._last_recognised = recognised
        return self._draw_overlay(frame, recognised)

    # ── Shared Camera Helpers ─────────────────────────────────

    @staticmethod
    def open_camera(camera_id: int = cfg.CAMERA_ID, source_type: Optional[str] = None,
                    camera_url: Optional[str] = None) -> Optional[CameraSource]:
        """Open a camera via the unified CameraSource factory.

        All camera types (webcam, usb_auto, android_*, iphone_*, ip_camera)
        go through the same ``create_camera()`` factory in ``camera/selector.py``.

        The ``WebcamSource`` and ``USBAnySource`` classes in ``camera/webcam.py``
        are the **sole** owners of ``cv2.VideoCapture`` — no other module should
        open raw OpenCV camera devices.

        Args:
            camera_id: Camera device index (used for webcam/USB phone cameras).
            source_type: Override configured camera source type (e.g. from CLI).
            camera_url: Override configured camera URL (e.g. from CLI).

        Returns:
            An opened ``CameraSource``, or ``None`` if connection fails.
        """
        source_type = source_type or cfg.CAMERA_SOURCE_TYPE

        logger = __import__('logging').getLogger(__name__)
        logger.info("Opening camera source: %s (device=%s, url=%s)",
                     source_type, camera_id, camera_url or cfg.CAMERA_URL)

        kwargs = {
            "device_id": camera_id,
            "url": camera_url or cfg.CAMERA_URL,
        }
        cam = create_camera(source_type, **kwargs)
        if cam is None:
            logger.error("Could not create camera source: %s", source_type)
            return None

        if cam.open():
            cam.set_resolution(640, 480)
            info = cam.info()
            logger.info("Camera connected: %s (res=%s)", cam.name, info.get('resolution', 'N/A'))
            return cam

        logger.error("Could not open %s camera", source_type)
        return None

    # ── Webcam Loop ───────────────────────────────────────────

    def run(self, camera_id: int = cfg.CAMERA_ID, source_type: Optional[str] = None,
            camera_url: Optional[str] = None) -> None:
        """Open webcam and run live recognition.

        Args:
            camera_id: OpenCV camera device index.
            source_type: Override camera source type (e.g. from CLI).
            camera_url: Override camera URL (e.g. from CLI).
        """
        cap = self.open_camera(camera_id, source_type=source_type, camera_url=camera_url)
        if cap is None:
            print("[FAIL] Could not open camera. Try a different camera ID:")
            print("       python main.py --camera-id 1")
            return

        print("[INFO] Live Detection started")
        print("  [Q] Quit    [E] Enroll face    [R] Reset session")

        enrolled_count = self.enrollment.count()
        print(f"[INFO] Enrolled faces in database: {enrolled_count}")

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Failed to read frame from camera")
                break

            frame = self.process_frame(frame)
            cv2.imshow("Face Recognition AI - Live", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                print("[INFO] Quitting...")
                break
            elif key == ord("e"):
                self._interactive_enroll(frame)
            elif key == ord("r"):
                self._marked_this_session.clear()
                print("[INFO] Session reset - all faces can be re-marked")

        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Live detection ended")

    # ── Image / Video File Processing ─────────────────────────

    def process_image(self, image_path: str | Path) -> np.ndarray:
        """Run the pipeline on a single image file.

        Args:
            image_path: Path to an image (jpg, png, …).

        Returns:
            Annotated image.
        """
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")
        return self.process_frame(frame)

    def process_video(self, video_path: str | Path, output_path: str | Path | None = None
                      ) -> None:
        """Run the pipeline on a video file (optionally saving the result).

        Args:
            video_path: Input video file path.
            output_path: Optional path to save the annotated video.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"Could not open video: {video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer: cv2.VideoWriter | None = None
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"Processing video: {total} frames @ {fps:.1f} fps")

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = self.process_frame(frame)
            if writer:
                writer.write(frame)
            cv2.imshow("Face Recognition AI - Video", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()

    # ── Debug ─────────────────────────────────────────────────

    def _debug_faiss(self, embedding: np.ndarray) -> None:
        """Print raw FAISS distances for debugging recognition.

        Always shows the closest match in the database, its L2 distance,
        derived confidence, and whether it passes the threshold.
        """
        if self.enrollment.index.ntotal == 0:
            print("  [FAISS] Index is empty — 0 enrolled faces")
            return

        query = embedding.reshape(1, -1).astype(np.float32)
        distances, indices = self.enrollment.index.search(query, 1)
        dist = float(distances[0][0])
        idx = int(indices[0][0])

        emb_norm = np.linalg.norm(embedding)
        print("=" * 60)
        print("  FAISS DEBUG")
        print(f"  Embedding norm : {emb_norm:.4f}")
        if idx != -1 and idx < len(self.enrollment.metadata):
            name = self.enrollment.metadata[idx]["name"]
            # Use the same formula as enrollment.search() for consistency
            conf = 1.0 / (1.0 + dist * dist)
            print(f"  Closest match : '{name}'")
            print(f"  L2 distance   : {dist:.4f}")
            print(f"  Confidence    : {conf:.4f} ({conf:.2%})")
            print(f"  Threshold     : {self.recog_threshold}")
            if dist <= self.recog_threshold:
                print(f"  PASSED threshold — would be recognized")
            else:
                print(f"  FAILED threshold — would show Unknown")
        else:
            print(f"  No valid match found (index has {self.enrollment.index.ntotal} entries)")
        print("=" * 60)

    # ── Status ────────────────────────────────────────────────

    def status(self) -> dict:
        """Return a snapshot of the current system state including AMFR."""
        amfr_state = self.amfr.status() if hasattr(self, 'amfr') and self.amfr else {}
        return {
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
            "enrolled": self.enrollment.status(),
            "attendance": self.attendance.statistics(),
            "session_marked": len(self._marked_this_session),
            "amfr": amfr_state,
        }

    # ── Internals ─────────────────────────────────────────────

    def _draw_overlay(self, frame: np.ndarray, recognised: List[dict]) -> np.ndarray:
        """Draw rich info cards with AMFR badges, bounding boxes, and HUD."""
        for item in recognised:
            x1, y1, x2, y2 = item["bbox"]
            name = item["name"]
            conf = item["confidence"]
            decision = item.get("amfr_decision", "")
            liveness = item.get("liveness_score", 0.0)
            risk = item.get("risk_score", 0.0)

            # ── Color and card lines by AMFR decision ────────
            if decision == AMFRDecision.ACCEPT.value:
                color = (0, 200, 0)  # Green
                if name not in self._employee_cache:
                    emp = EmployeeService.get_by_name(name) if name else None
                    self._employee_cache[name] = emp.employee_id if emp else None
                emp_id = self._employee_cache.get(name)
                attendance_str = "[OK] Attendance Marked" if name in self._marked_this_session else ""
                card_lines = [
                    f"[LIVE] {name}",
                    f"ID: {emp_id}" if emp_id else "",
                    f"Risk: {risk:.1%}  Live: {liveness:.1%}",
                    attendance_str,
                ]
                card_lines = [l for l in card_lines if l]
            elif decision == AMFRDecision.BORDERLINE.value:
                color = (0, 200, 200)  # Yellow
                card_lines = [f"{name} (borderline)", f"Risk: {risk:.1%}", "Collecting more frames..."]
            elif decision == AMFRDecision.REJECT_SPOOF.value:
                color = (0, 0, 200)  # Red
                card_lines = ["🚨 SPOOF DETECTED", f"Liveness: {liveness:.1%}", "Rejected + Alerted"]
            elif name == "No Face":
                color = (0, 165, 255)  # Orange
                card_lines = ["No Face Detected"]
            else:
                color = (128, 128, 128)  # Grey (unknown/low confidence)
                card_lines = ["Unknown", f"Risk: {risk:.1%}", f"Quality: {item.get('quality_score', 0):.1%}"]

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            self._draw_info_card(frame, x1, y2, card_lines, color)

        # ── HUD ───────────────────────────────────────────────
        enrolled = self.enrollment.count()
        today_count = len(self.attendance.today())
        amfr_tracks = len(self.amfr.get_all_tracks()) if hasattr(self, 'amfr') and self.amfr else 0
        hud_lines = [
            f"FPS: {self._fps:.1f}",
            f"Enrolled: {enrolled}",
            f"Today: {today_count}",
            f"AMFR tracks: {amfr_tracks}",
            "[Q]uit  [E]nroll  [R]eset",
        ]
        for i, line in enumerate(hud_lines):
            y = 25 + i * 22
            cv2.putText(frame, line, (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        return frame

    def _draw_info_card(self, frame: np.ndarray, bbox_left: int, bbox_bottom: int,
                       lines: List[str], color: Tuple[int, int, int]) -> None:
        """Draw a rich dark-themed info card below a detection bounding box.

        Card layout (example for a known person)::

            ┌─────────────────────────┐
            │  (green circle)  Gokul   │
            │  ID: EMP001              │
            │  Confidence: 96.3%       │
            │  [OK] Attendance         │
            └─────────────────────────┘

        Args:
            frame: The image to draw on (modified in-place).
            bbox_left: Left edge of the bounding box (card aligns to this).
            bbox_bottom: Bottom edge of the bounding box (card drawn below).
            lines: List of text strings to display in the card.
            color: Accent color for border and indicator circle (BGR).
        """
        if not lines:
            return

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.45
        thickness = 1
        line_height = 20
        padding_x = 10
        padding_y = 6
        indicator_r = 5  # radius of the colored circle

        # Measure the widest text line
        max_width = 0
        for line in lines:
            (w, _), _ = cv2.getTextSize(line, font, font_scale, thickness)
            max_width = max(max_width, w)

        # Card width: text width + left padding (circle + gap + text indent) + right padding
        left_indent = padding_x + indicator_r * 2 + 6  # circle + gap
        card_w = max_width + left_indent + padding_x
        card_h = len(lines) * line_height + padding_y * 2

        # Position: below the bounding box, aligned to its left edge
        h_frame, w_frame = frame.shape[:2]
        card_x = min(bbox_left, max(0, w_frame - card_w - 5))
        card_y = bbox_bottom + 5

        # If card would go off the bottom of the frame, draw above the bbox instead
        if card_y + card_h > h_frame - 5:
            card_y = max(5, bbox_bottom - card_h - 10)

        # ── Draw card background (dark semi-transparent) ────
        overlay = frame.copy()
        cv2.rectangle(overlay,
                      (card_x, card_y),
                      (card_x + card_w, card_y + card_h),
                      (25, 25, 25), -1)
        cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)

        # ── Draw colored accent border ─────────────────────
        cv2.rectangle(frame,
                      (card_x, card_y),
                      (card_x + card_w, card_y + card_h),
                      color, 1)

        # ── Draw the colored indicator circle ──────────────
        circle_cx = card_x + padding_x + indicator_r
        circle_cy = card_y + padding_y + line_height // 2
        cv2.circle(frame, (circle_cx, circle_cy), indicator_r, color, -1)

        # ── Draw text lines ────────────────────────────────
        text_x = card_x + padding_x + indicator_r * 2 + 8
        for i, line in enumerate(lines):
            text_y = card_y + padding_y + (i + 1) * line_height - 6
            cv2.putText(frame, line, (text_x, text_y),
                        font, font_scale, (255, 255, 255), thickness)

    def _log_attendance_db(self, name: str, confidence: float) -> None:
        """Log an attendance event to the SQLite database.

        The CSV log is handled by ``AttendanceTracker.mark()`` in the
        caller — this method handles the database side so the dashboard
        can query attendance records.

        Args:
            name: Person's display name (from FAISS match).
            confidence: Recognition confidence score.
        """
        try:
            emp = EmployeeService.get_by_name(name)
            if emp is None:
                return  # no DB record for this person
            with get_session() as session:
                # Avoid duplicates: check if already marked today
                if not AttendanceRepo.is_marked_today(session, emp.id):
                    AttendanceRepo.create(
                        session,
                        employee_id=emp.id,
                        confidence=round(confidence, 4),
                    )
        except Exception as exc:
            print(f"  Failed to log attendance to DB: {exc}")

    def _save_unknown_face(self, face_img: np.ndarray) -> None:
        """Save an unrecognised face snapshot to disk and database.

        Writes the person crop to ``unknown_faces/`` and logs the event
        to the ``unknown_faces`` SQLite table so the dashboard can
        query it later.

        Uses a cooldown (default 3 s) to avoid flooding the directory
        with near-identical frames of the same person.

        Args:
            face_img: BGR image crop of the person (saved as-is).
        """
        now = time.time()
        if now - self._last_unknown_save < self._unknown_save_cooldown:
            return
        self._last_unknown_save = now

        try:
            timestamp = datetime.now()
            filename = f"unknown_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            save_path = cfg.UNKNOWN_FACES_DIR / filename
            ok = cv2.imwrite(str(save_path), face_img)
            if ok:
                print(f"  Saved unknown face: {filename}")
            else:
                print(f"  Could not write unknown face to disk: {filename}")
                return  # don't log to DB if file save failed

            # Log to database for dashboard queries
            with get_session() as session:
                UnknownFaceRepo.create(
                    session,
                    image_path=str(save_path),
                    confidence=0.0,
                )
        except Exception as exc:
            print(f"  Failed to save unknown face: {exc}")

    def _interactive_enroll(self, frame: np.ndarray) -> None:
        """Enroll the largest face currently visible."""
        detections = self.detector.detect(frame, conf_threshold=self.conf_threshold)
        if not detections:
            print("No person detected — cannot enroll.")
            return

        largest = self.detector.get_largest_detection(detections)
        person_crop = self.detector.crop_person(frame, largest["bbox"])
        embedding = self.recognizer.extract_embedding(person_crop)
        if embedding is None:
            print("No face found in the detected person.")
            return

        # Check if already enrolled
        matches = self.enrollment.search(embedding, k=1, threshold=self.recog_threshold)
        if matches:
            print(f"Face already enrolled as: {matches[0]['name']} (conf={matches[0]['confidence']:.2f})")
            return

        # In a real GUI you'd pop an input dialog; here we use the terminal
        name = input("Enter name for enrollment: ").strip()
        if not name:
            print("Name cannot be empty.")
            return

        self.enrollment.enroll(name, embedding)
        print(f"Enrolled '{name}' ({self.enrollment.count()} total embeddings).")
