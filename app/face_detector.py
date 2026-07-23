"""
Face Detection Module — YOLO Person Detector
=============================================

Uses Ultralytics YOLO (yolo11n.pt) for fast person detection
across the full frame. Each person bounding box is then passed
to RetinaFace (in recognizer.py) for refined face detection.

Pipeline role:  YOLO → (crop) → RetinaFace → ArcFace → FAISS
                 ↑
            You are here

Model: yolo11n.pt (COCO-trained, detects "person" class)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

import config.config as cfg


class FaceDetector:
    """YOLO-based person/face detector.

    Attributes:
        model: Loaded Ultralytics YOLO model.
        person_class_id: COCO class ID for "person" (default 0).
    """

    def __init__(self, model_path: str = cfg.YOLO_MODEL_PATH) -> None:
        """Initialise the YOLO detector.

        Args:
            model_path: Path to the YOLO weights file.
        """
        self.model = YOLO(model_path)
        self.person_class_id = 0  # COCO person class

    # ── Public API ────────────────────────────────────────────

    def detect(self, frame: np.ndarray, conf_threshold: float = cfg.YOLO_CONFIDENCE
               ) -> List[dict]:
        """Detect people in a frame.

        Only detections of class ``person`` (COCO class 0) are returned.

        Args:
            frame: BGR image (H×W×3).
            conf_threshold: Minimum confidence to keep a detection.

        Returns:
            List of detection dicts, each with keys:
                - ``bbox``: (x1, y1, x2, y2) as ints.
                - ``confidence``: float score.
                - ``class_id``: int COCO class (always 0 = person).
        """
        results = self.model(frame, conf=conf_threshold, verbose=False)
        if not results:
            return []

        detections: List[dict] = []
        boxes = results[0].boxes
        if boxes is None:
            return []

        for box in boxes:
            class_id = int(box.cls[0])
            # Filter to person class only
            if class_id != self.person_class_id:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            confidence = float(box.conf[0])

            detections.append({
                "bbox": (x1, y1, x2, y2),
                "confidence": confidence,
                "class_id": class_id,
            })

        return detections

    def crop_person(self, frame: np.ndarray, bbox: Tuple[int, int, int, int],
                    padding: float = 0.15) -> np.ndarray:
        """Crop the person region from the frame with padding.

        Args:
            frame: Source BGR image.
            bbox: (x1, y1, x2, y2).
            padding: Fractional padding applied to each side.

        Returns:
            Cropped BGR sub-image (could be empty if out-of-bounds).
        """
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        pad_x = int((x2 - x1) * padding)
        pad_y = int((y2 - y1) * padding)

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        return frame[y1:y2, x1:x2]

    # ── Helpers ───────────────────────────────────────────────

    def get_largest_detection(self, detections: List[dict]) -> Optional[dict]:
        """Return the detection with the largest bounding-box area."""
        if not detections:
            return None

        def _area(d: dict) -> int:
            x1, y1, x2, y2 = d["bbox"]
            return (x2 - x1) * (y2 - y1)

        return max(detections, key=_area)
