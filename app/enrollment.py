"""
Face Enrollment Module — FAISS Database
========================================

Manages a persistent store of face embeddings using FAISS (Facebook AI
Similarity Search).

Features:
- Enroll new faces (name + embedding → FAISS index).
- Search for the nearest match.
- Serialise/deserialise the index and metadata to disk.

Pipeline role:  YOLO → RetinaFace → ArcFace → FAISS
                                                ↑
                                           You are here
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import faiss

import config.config as cfg


class FaceEnrollment:
    """FAISS‑based face embedding store.

    Attributes:
        index: FAISS ``IndexFlatL2`` for brute-force L2 search.
        metadata: List of ``{"name": str, "id": int}`` entries.
        dimension: Embedding dimensionality (512 for ArcFace).
    """

    def __init__(self, index_path: str = cfg.FAISS_INDEX_PATH,
                 metadata_path: str = cfg.METADATA_PATH) -> None:
        """Load an existing index or create a new one.

        Args:
            index_path: Path to the serialised FAISS index.
            metadata_path: Path to the JSON metadata file.
        """
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)
        self.dimension = cfg.EMBEDDING_DIM

        # Ensure directories exist
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        if self.index_path.exists() and self.metadata_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            with open(self.metadata_path, "r") as f:
                self.metadata: List[Dict] = json.load(f)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata: List[Dict] = []

    # ── Public API ────────────────────────────────────────────

    def enroll(self, name: str, embedding: np.ndarray) -> bool:
        """Add a new face to the database.

        Args:
            name: Person's display name.
            embedding: 512‑D float32 embedding vector.

        Returns:
            ``True`` on success.
        """
        emb = embedding.reshape(1, -1).astype(np.float32)
        person_id = len(self.metadata)
        self.index.add(emb)
        self.metadata.append({"name": name, "id": person_id})
        self._save()
        return True

    def search(self, embedding: np.ndarray, k: int = 1,
               threshold: float = cfg.RECOGNITION_THRESHOLD) -> List[Dict]:
        """Find the *k* nearest neighbours in the embedding space.

        Args:
            embedding: 512‑D query vector.
            k: Number of neighbours to retrieve.
            threshold: Maximum L2 distance for a valid match
                       (lower = stricter, higher = more tolerant).

        Returns:
            List of match dicts sorted by distance (ascending)::

                [
                    {"name": "...", "confidence": 0.92, "distance": 0.48},
                    ...
                ]

            Empty list if the index is empty or no match passes the threshold.
        """
        if self.index.ntotal == 0:
            return []

        query = embedding.reshape(1, -1).astype(np.float32)
        distances, indices = self.index.search(query, k)

        results: List[Dict] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue

            dist = float(dist)
            name = self.metadata[idx]["name"]

            if dist > threshold:
                continue

            # Convert L2 distance to a [0, 1] confidence score.
            # Uses a non-linear mapping (1/(1+d²)) that gives intuitive percentages:
            #   dist=0.0  → 100%  (identical)
            #   dist=0.3  →  92%  (very close)
            #   dist=0.5  →  80%  (good match)
            #   dist=0.7  →  67%  (decent)
            #   dist=1.0  →  50%  (borderline)
            #   dist=1.5  →  31%  (probably different)
            #   dist=2.0  →  20%  (different person)
            confidence = 1.0 / (1.0 + dist * dist)
            results.append({
                "name": name,
                "confidence": round(confidence, 4),
                "distance": round(dist, 4),
            })

        return results

    def remove(self, name: str) -> None:
        """Remove all entries for a given name.

        .. warning::
            ``NotImplemented`` — FAISS does **not** support deletion natively
            and embeddings are not stored independently in this version.
            Calling this will raise ``NotImplementedError``.

            To implement properly, store raw embeddings as ``.npy`` files
            alongside metadata so the index can be faithfully rebuilt.
        """
        raise NotImplementedError(
            "FAISS does not support deletion. To implement this, store "
            "raw embeddings separately (e.g. as .npy files) alongside "
            "metadata, then rebuild the index from scratch. "
            "# TODO: implement proper deletion with separate .npy embedding store"
        )

    def clear(self) -> None:
        """Remove **all** enrolled faces."""
        self.metadata = []
        self.index = faiss.IndexFlatL2(self.dimension)
        self._save()

    # ── Queries ───────────────────────────────────────────────

    def all_persons(self) -> List[str]:
        """Return sorted list of unique enrolled names."""
        return sorted({m["name"] for m in self.metadata})

    def count(self) -> int:
        """Total number of enrolled embeddings."""
        return self.index.ntotal

    def unique_count(self) -> int:
        """Number of unique persons enrolled."""
        return len(self.all_persons())

    def status(self) -> Dict:
        """Return a summary dict of the enrollment state."""
        return {
            "total_embeddings": self.count(),
            "unique_persons": self.unique_count(),
            "persons": self.all_persons(),
        }

    # ── Persistence ───────────────────────────────────────────

    def _save(self) -> None:
        """Write the index and metadata to disk."""
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def _rebuild_index(self) -> None:
        """Rebuild the FAISS index from scratch.

        .. warning::
            Embeddings are **not** stored independently in this simple
            implementation, so rebuilding clears the index entirely.
            A production system should store raw embeddings separately
            (e.g. as ``.npy`` files) so the index can be faithfully
            reconstructed.
        """
        old_count = self.index.ntotal
        self.index = faiss.IndexFlatL2(self.dimension)
        self._save()
        if old_count > 0:
            print(f"⚠️  FAISS index rebuilt — {old_count} embedding(s) lost. "
                  f"Metadata for {len(self.metadata)} person(s) preserved.")
