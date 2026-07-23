"""
Live Face Detection & Recognition — Real-time Pipeline
=========================================================

Ties together the full inference chain:

    Webcam frame
        ↓
    ┌────────────────┐
    │  YOLO (person)  │  ← face_detector.py
    └───────┬────────┘
            ↓ (crop per person)
    ┌────────────────┐
    │ RetinaFace      │  ← recognizer.py
    └───────┬────────┘
            ↓ (face crop)
    ┌────────────────┐
    │  ArcFace (emb)  │  ← recognizer.py
    └───────┬────────┘
            ↓ (512‑D vector)
    ┌────────────────┐
    │  FAISS search   │  ← enrollment.py
    └───────┬────────┘
            ↓ (name or "Unknown")
    ┌────────────────┐
    │  Attendance     │  ← attendance.py
    └────────────────┘

Press ``q`` to quit, ``e`` to enroll the face in view.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

# ── Ensure project root is on sys.path for direct script execution ──
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg
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
    """End‑to‑end real‑time face recognition pipeline.

    Usage::

        pipeline = LiveDetection()
        pipeline.run()           # webcam loop
        # or
        annotated = pipeline.process_frame(frame)   # single frame
    """

    def __init__(self) -> None:
        """Initialise all sub‑modules."""
        self.detector = FaceDetector()
        self.recognizer = FaceRecognizer()
        self.enrollment = FaceEnrollment()
        self.attendance = AttendanceTracker()

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
        """Run the full pipeline on a single frame.

        Args:
            frame: BGR image from camera or file.

        Returns:
            Annotated frame with bounding boxes and labels.
        """
        self._frame_count += 1

        # ── FPS calculation ──────────────────────────────────
        now = time.time()
        self._fps = 0.9 * self._fps + 0.1 / (now - self._prev_time + 1e-6)
        self._prev_time = now

        # ── Skip frames for performance ──────────────────────
        if self._frame_count % self.frame_skip != 0:
            # Reuse previous detections to avoid flickering
            return self._draw_overlay(frame, self._last_recognised)

        # Step 1 — YOLO person detection
        detections = self.detector.detect(frame, conf_threshold=self.conf_threshold)

        recognised: List[dict] = []
        for det in detections:
            bbox = det["bbox"]

            # Step 2 — Crop person region
            person_crop = self.detector.crop_person(frame, bbox)
            if person_crop.size == 0:
                continue

            # Step 3 — RetinaFace detection → ArcFace embedding
            embedding = self.recognizer.extract_embedding(person_crop)
            if embedding is None:
                recognised.append({"bbox": bbox, "name": "No Face", "confidence": 0.0})
                continue

            # Step 4 — FAISS nearest-neighbour search
            matches = self.enrollment.search(embedding, k=1, threshold=self.recog_threshold)

            # ── Debug: always show the closest FAISS match ──
            self._debug_faiss(embedding)

            if matches:
                name = matches[0]["name"]
                conf = matches[0]["confidence"]
                print(f"  ✅ MATCH: {name} | confidence={conf:.2%} | distance={matches[0]['distance']:.4f} | threshold={self.recog_threshold}")
                # Mark attendance once per session (CSV + SQLite)
                if name not in self._marked_this_session:
                    self.attendance.mark(name, conf)
                    # Also log to SQLite so the dashboard can query it
                    self._log_attendance_db(name, conf)
                    self._marked_this_session.add(name)
                recognised.append({"bbox": bbox, "name": name, "confidence": conf})
            else:
                print(f"  ❌ NO MATCH — closest known face was rejected by threshold")
                # Save unknown face snapshot (with cooldown to avoid flooding)
                self._save_unknown_face(person_crop)
                recognised.append({"bbox": bbox, "name": "Unknown", "confidence": 0.0})

        # Cache for next skipped frame
        self._last_recognised = recognised
        return self._draw_overlay(frame, recognised)

    # ── Shared Camera Helpers ─────────────────────────────────

    @staticmethod
    def open_camera(camera_id: int = cfg.CAMERA_ID, source_type: Optional[str] = None,
                    camera_url: Optional[str] = None) -> Optional[Union[cv2.VideoCapture, CameraSource]]:
        """Open a camera based on the configured source type.

        Supports ALL camera types via the unified ``CameraSource`` abstraction:
        - 💻 Laptop Webcam
        - 🔌 USB Auto (Plug & Play)
        - 📱 Android (USB / Wi-Fi)
        - 📱 iPhone (USB / Wi-Fi)
        - 🌐 IP Camera (RTSP / HTTP)

        Falls back to ``cv2.VideoCapture`` with DirectShow/MSMF backends
        for the ``"webcam"`` type if the factory path fails.

        Args:
            camera_id: Camera device index (used for webcam and USB phone cameras).
            source_type: Override the configured camera source type (e.g. from CLI).
            camera_url: Override the configured camera URL (e.g. from CLI).

        Returns:
            An opened camera object (``cv2.VideoCapture`` or ``CameraSource``),
            or ``None`` if all connection attempts fail.
        """
        source_type = source_type or cfg.CAMERA_SOURCE_TYPE

        # ── All camera types use the CameraSource factory ──
        # The factory handles webcam, usb_auto, android_*, iphone_*, ip_camera
        print(f"[Camera] Opening source: {source_type}")
        kwargs = {
            "device_id": camera_id,
            "url": camera_url or cfg.CAMERA_URL,
        }
        cam = create_camera(source_type, **kwargs)
        if cam is None:
            print(f"[FAIL] Could not create camera source: {source_type}")
            # Fallback: try DirectShow for raw webcam
            if source_type == "webcam":
                backends = [
                    (cv2.CAP_DSHOW, "DirectShow"),
                    (cv2.CAP_MSMF, "Media Foundation"),
                    (None, "Default"),
                ]
                for backend, name in backends:
                    if backend is None:
                        cap = cv2.VideoCapture(camera_id)
                    else:
                        cap = cv2.VideoCapture(camera_id, backend)
                    if cap.isOpened():
                        print(f"[OK] Webcam opened via {name} backend (device #{camera_id})")
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        return cap
                    print(f"[-] {name} backend failed for device #{camera_id}")
            return None

        if cam.open():
            cam.set_resolution(640, 480)
            info = cam.info()
            print(f"[OK] Camera connected: {cam.name}")
            print(f"     Resolution: {info.get('resolution', 'N/A')}")
            return cam
        print(f"[FAIL] Could not open {source_type} camera")
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
        """Return a snapshot of the current system state."""
        return {
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
            "enrolled": self.enrollment.status(),
            "attendance": self.attendance.statistics(),
            "session_marked": len(self._marked_this_session),
        }

    # ── Internals ─────────────────────────────────────────────

    def _draw_overlay(self, frame: np.ndarray, recognised: List[dict]) -> np.ndarray:
        """Draw rich info cards, bounding boxes, and HUD on the frame."""
        for item in recognised:
            x1, y1, x2, y2 = item["bbox"]
            name = item["name"]
            conf = item["confidence"]

            is_known = name not in ("Unknown", "No Face")

            if is_known:
                color = (0, 200, 0)  # Green
                # Look up employee record to get employee ID (cached per session)
                if name not in self._employee_cache:
                    emp = EmployeeService.get_by_name(name) if name else None
                    self._employee_cache[name] = emp.employee_id if emp else None
                emp_id = self._employee_cache.get(name)
                emp_id_str = f"ID: {emp_id}" if emp_id else ""
                attendance_str = "[OK] Attendance Marked" if name in self._marked_this_session else ""
                card_lines = [name, emp_id_str, f"Confidence: {conf:.1%}", attendance_str]
                card_lines = [l for l in card_lines if l]  # remove empty lines
            elif name == "No Face":
                color = (0, 165, 255)  # Orange
                card_lines = ["No Face Detected"]
            else:
                color = (0, 0, 200)  # Red
                card_lines = ["Unknown", f"Confidence: {conf:.1%}", "Saved to Gallery"]

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw rich info card below the bounding box
            self._draw_info_card(frame, x1, y2, card_lines, color)

        # ── HUD ───────────────────────────────────────────────
        enrolled = self.enrollment.count()
        today_count = len(self.attendance.today())
        hud_lines = [
            f"FPS: {self._fps:.1f}",
            f"Enrolled: {enrolled}",
            f"Today: {today_count}",
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
