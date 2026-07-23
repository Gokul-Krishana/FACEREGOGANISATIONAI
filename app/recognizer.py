"""
Face Recognition Module — RetinaFace + ArcFace
===============================================

Uses InsightFace's ``buffalo_l`` model which bundles:
1. **RetinaFace** — precise face detection with 5-point landmarks.
2. **ArcFace** — 512‑dimensional face embedding extraction.

Pipeline role:  YOLO → RetinaFace → ArcFace → FAISS
                                    ↑       ↑
                              You are here  (embedding output)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

import insightface
from insightface.app import FaceAnalysis

import config.config as cfg


class FaceRecognizer:
    """Face recognition via InsightFace (RetinaFace detection + ArcFace embedding).

    Attributes:
        app: InsightFace ``FaceAnalysis`` app instance.
        model_name: The InsightFace model pack name.
    """

    def __init__(self, model_name: str = cfg.INSIGHTFACE_MODEL) -> None:
        """Initialise the InsightFace model.

        Downloads the model pack on first run (cached to ``~/.insightface``).

        Args:
            model_name: InsightFace model pack name (e.g. ``buffalo_l``, ``buffalo_s``).
        """
        self.model_name = model_name
        self.app = FaceAnalysis(
            name=model_name,
            root=cfg.INSIGHTFACE_ROOT,
            providers=["CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=-1, det_size=(640, 640))

    # ── Public API ────────────────────────────────────────────

    def extract_embedding(self, face_img: np.ndarray) -> Optional[np.ndarray]:
        """Extract a 512‑D ArcFace embedding from a face image.

        The embedding is L2‑normalised to unit length so that FAISS L2
        distance comparisons are consistent regardless of lighting/scale.

        Args:
            face_img: BGR image containing a **single** face.

        Returns:
            512‑D float32 embedding vector (unit‑norm), or ``None`` if
            no face is found.
        """
        faces = self.app.get(face_img)
        if not faces:
            return None
        emb = faces[0].embedding.astype(np.float32)
        # L2-normalise so FAISS L2 distance ≈ cosine distance
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb /= norm
        return emb

    def detect_face(self, person_crop: np.ndarray) -> Optional[dict]:
        """Run RetinaFace detection on a person crop.

        Args:
            person_crop: BGR image (typically a YOLO person crop).

        Returns:
            Dict with ``bbox``, ``landmarks``, ``embedding``, ``det_score``,
            or ``None`` if no face is found.
        """
        faces = self.app.get(person_crop)
        if not faces:
            return None
        face = faces[0]
        emb = face.embedding.astype(np.float32)
        # L2-normalise so FAISS L2 distance ≈ cosine distance
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb /= norm
        return {
            "bbox": face.bbox.astype(int).tolist(),
            "landmarks": face.landmark.tolist() if face.landmark is not None else None,
            "embedding": emb,
            "det_score": float(face.det_score),
        }

    def get_landmarks(self, face_img: np.ndarray) -> Optional[np.ndarray]:
        """Get 5 facial landmarks (eyes, nose, mouth corners).

        Args:
            face_img: BGR face image.

        Returns:
            (5, 2) array of (x, y) landmarks, or ``None``.
        """
        faces = self.app.get(face_img)
        if not faces:
            return None
        return faces[0].landmark

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        emb1 = emb1 / (np.linalg.norm(emb1) + 1e-12)
        emb2 = emb2 / (np.linalg.norm(emb2) + 1e-12)
        return float(np.dot(emb1, emb2))

    # ── Model Info ────────────────────────────────────────────

    def embedding_dim(self) -> int:
        """Return the dimension of extracted embeddings."""
        return cfg.EMBEDDING_DIM
