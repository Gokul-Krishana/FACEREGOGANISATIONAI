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
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import faiss

import config.config as cfg

logger = logging.getLogger(__name__)


class FaceEnrollment:
    """FAISS‑based face embedding store.

    Supports three index types configured via ``config/settings.yaml``:

    - **flat** — ``IndexFlatL2`` brute-force exact search (best recall)
    - **hnsw**  — ``IndexHNSWFlat`` approximate ANN (best speed/recall)
    - **ivf**   — ``IndexIVFFlat`` inverted file index (good at scale)

    Attributes:
        index: FAISS index (type depends on configuration).
        metadata: List of ``{"name": str, "id": int}`` entries.
        dimension: Embedding dimensionality (512 for ArcFace).
    """

    def __init__(self, index_path: Optional[str] = None, metadata_path: Optional[str] = None) -> None:
        """Load an existing index or create a new one.

        Args:
            index_path: Path to the serialised FAISS index.
            metadata_path: Path to the JSON metadata file.
        """
        self.index_path = Path(index_path if index_path is not None else cfg.FAISS_INDEX_PATH)
        self.metadata_path = Path(metadata_path if metadata_path is not None else cfg.METADATA_PATH)
        self.dimension = cfg.EMBEDDING_DIM

        # Ensure directories exist
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        if self.index_path.exists() and self.metadata_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            # Restore HNSW search parameters (not persisted by faiss.write_index)
            if hasattr(self.index, "hnsw"):
                self.index.hnsw.efSearch = cfg.FAISS_HNSW_EF_SEARCH
            with open(self.metadata_path, "r") as f:
                self.metadata: List[Dict] = json.load(f)
        else:
            self.index = self._create_index()
            self.metadata = []

    def _create_index(self) -> faiss.Index:
        """Create a new FAISS index based on the configured index type.

        Returns:
            A FAISS index configured with the tuned parameters from
            ``config/settings.yaml``.
        """
        index_type = cfg.FAISS_INDEX_TYPE.lower()

        if index_type == "hnsw":
            index = faiss.IndexHNSWFlat(
                self.dimension,
                cfg.FAISS_HNSW_M,
            )
            index.hnsw.efConstruction = cfg.FAISS_HNSW_EF_CONSTRUCTION
            index.hnsw.efSearch = cfg.FAISS_HNSW_EF_SEARCH
            return index

        elif index_type == "ivf":
            quantizer = faiss.IndexFlatL2(self.dimension)
            index = faiss.IndexIVFFlat(  # type: ignore[assignment]
                quantizer,
                self.dimension,
                cfg.FAISS_IVF_NLIST,
            )
            index.nprobe = cfg.FAISS_IVF_NPROBE  # type: ignore[attr-defined]
            return index

        else:
            # Default: flat brute-force (exact search)
            return faiss.IndexFlatL2(self.dimension)

    # ── Public API ────────────────────────────────────────────

    def enroll(
        self,
        name: str,
        embedding: np.ndarray,
        employee_id: Optional[str] = None,
        employee_db_id: Optional[int] = None,
    ) -> bool:
        """Add a new face to the database.

        Args:
            name: Person's display name.
            embedding: 512‑D float32 embedding vector.
            employee_id: Unique employee identifier (e.g. ``EMP001``).
                Stored alongside ``name`` so two people with the same
                display name remain distinguishable and renames never
                break identity resolution.
            employee_db_id: Immutable database primary key (``Employee.id``).

        Returns:
            ``True`` on success.
        """
        emb = embedding.reshape(1, -1).astype(np.float32)
        person_id = len(self.metadata)
        self.index.add(emb)
        entry: Dict = {"name": name, "id": person_id}
        if employee_id:
            entry["employee_id"] = str(employee_id)
        if employee_db_id is not None:
            entry["employee_db_id"] = int(employee_db_id)
        self.metadata.append(entry)
        self._save()
        return True

    def search(
        self,
        embedding: np.ndarray,
        k: int = 1,
        threshold: float = cfg.RECOGNITION_THRESHOLD,
        ambiguity_margin: float = 0.15,
    ) -> List[Dict]:
        """Find the *k* nearest neighbours in the embedding space.

        Args:
            embedding: 512‑D query vector.
            k: Number of neighbours to retrieve.
            threshold: Maximum L2 distance for a valid match
                       (lower = stricter, higher = more tolerant).
            ambiguity_margin: Minimum L2 distance separation required between
                              top-1 and top-2 distinct candidates before flagging
                              as ambiguous.

        Returns:
            List of match dicts sorted by distance (ascending).
            When multiple candidates are returned, the top match includes
            ``is_ambiguous`` indicating whether a competing distinct identity
            matches with a close score within ``ambiguity_margin``.
        """
        if self.index.ntotal == 0:
            return []

        # If k=1 requested, retrieve at least 2 internally to evaluate ambiguity margin
        search_k = max(2, k) if self.index.ntotal >= 2 else 1

        query = embedding.reshape(1, -1).astype(np.float32)
        distances, indices = self.index.search(query, search_k)

        results: List[Dict] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue

            dist = float(dist)
            entry = self.metadata[idx]
            name = entry["name"]

            if dist > threshold:
                continue

            confidence = 1.0 / (1.0 + dist * dist)
            match: Dict = {
                "name": name,
                "confidence": round(confidence, 4),
                "distance": round(dist, 4),
                "faiss_id": int(idx),
            }
            if entry.get("employee_id"):
                match["employee_id"] = entry["employee_id"]
            if entry.get("employee_db_id") is not None:
                match["employee_db_id"] = entry["employee_db_id"]
            results.append(match)

        # ── Ambiguity Check between top-1 and top-2 candidates ───────
        if len(results) >= 2:
            top1 = results[0]
            top2 = results[1]
            # Compare whether top1 and top2 are distinct identities
            is_different_person = False
            if top1.get("employee_db_id") is not None and top2.get("employee_db_id") is not None:
                is_different_person = top1["employee_db_id"] != top2["employee_db_id"]
            elif top1.get("employee_id") and top2.get("employee_id"):
                is_different_person = top1["employee_id"] != top2["employee_id"]
            else:
                is_different_person = top1["name"] != top2["name"]

            if is_different_person:
                dist_margin = top2["distance"] - top1["distance"]
                conf_margin = top1["confidence"] - top2["confidence"]
                if dist_margin < ambiguity_margin or conf_margin < 0.08:
                    top1["is_ambiguous"] = True
                    top1["ambiguity_margin"] = round(dist_margin, 4)
                    top1["competing_name"] = top2["name"]
                    top1["competing_employee_id"] = top2.get("employee_id")
                else:
                    top1["is_ambiguous"] = False
            else:
                top1["is_ambiguous"] = False
        elif len(results) == 1:
            results[0]["is_ambiguous"] = False

        # If user originally asked for k=1, trim back to k results
        if k == 1 and len(results) > 1:
            return results[:1]

        return results[:k]

    def remove(self, name: str) -> bool:
        """Remove all entries for a given name.

        This is an alias for ``remove_by_name`` for API consistency.
        Rebuilds the FAISS index from scratch keeping only entries
        that do NOT match *name*.  O(N) in the number of embeddings.

        Args:
            name: The name (employee_id string) to remove.

        Returns:
            ``True`` if any entries were removed, ``False`` otherwise.
        """
        return self.remove_by_name(name)

    def remove_by_employee_id(self, employee_id: str) -> bool:
        """Remove all embeddings matching a unique ``employee_id``."""
        return self._remove_where(lambda m: m.get("employee_id") == employee_id, label=employee_id)

    def remove_by_name(self, name: str) -> bool:
        """Remove all embeddings for a given name from the index."""
        return self._remove_where(lambda m: m.get("name") == name, label=name)

    def _remove_where(self, predicate, label: str) -> bool:
        """Rebuild the FAISS index keeping entries that do NOT match *predicate*."""
        before = sum(1 for m in self.metadata if predicate(m))
        if before == 0:
            return False

        kept_metadata = [m for m in self.metadata if not predicate(m)]
        kept_count = len(kept_metadata)

        if kept_count == 0:
            self.metadata = []
            self.index = self._create_index()
        else:
            new_index = self._create_index()
            kept_ids = [i for i, m in enumerate(self.metadata) if not predicate(m)]

            if hasattr(self.index, "reconstruct"):
                for kid in kept_ids:
                    vec = self.index.reconstruct(kid)
                    new_index.add(vec.reshape(1, -1))
                self.index = new_index
            else:
                logger.warning(
                    "FAISS index type %s does not support reconstruction. Clearing all embeddings.",
                    type(self.index).__name__,
                )
                self.index = self._create_index()

            # Re-number metadata IDs while preserving employee_id and other fields
            self.metadata = []
            for i, old_m in enumerate(kept_metadata):
                item = dict(old_m)
                item["id"] = i
                self.metadata.append(item)

        self._save()
        removed = before - (len(self.metadata) - kept_count)
        logger.info("Removed %d embedding(s) for '%s' from FAISS index", removed, label)
        return True

    def rename_by_employee_id(self, employee_id: str, new_name: str) -> bool:
        """Rename embeddings matching a unique ``employee_id``."""
        if not new_name or not new_name.strip():
            return False
        new_name = new_name.strip()
        matched = 0
        for m in self.metadata:
            if m.get("employee_id") == employee_id:
                m["name"] = new_name
                matched += 1
        if matched == 0:
            return False
        self._save()
        logger.info(
            "Renamed %d embedding(s) for employee_id '%s' → '%s' in FAISS", matched, employee_id, new_name
        )
        return True

    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename all embeddings for a person in the FAISS metadata.

        Preserves all vectors intact without clearing or altering the FAISS index.

        Args:
            old_name: Current name stored in the metadata.
            new_name: Replacement name (must be non-empty).

        Returns:
            ``True`` if at least one entry was renamed, ``False`` if
            ``old_name`` was not found (or ``new_name`` is empty).
        """
        if not new_name or not new_name.strip():
            return False
        new_name = new_name.strip()

        renamed_count = 0
        for m in self.metadata:
            if m.get("name") == old_name:
                m["name"] = new_name
                renamed_count += 1

        if renamed_count > 0:
            self._save()
            logger = logging.getLogger(__name__)
            logger.info("Renamed %d embedding(s) '%s' → '%s' in metadata", renamed_count, old_name, new_name)
            return True
        return False

    def rename_by_employee_id(self, employee_id: str, new_name: str) -> bool:
        """Rename all embeddings for a specific employee identified by unique ``employee_id``."""
        if not new_name or not new_name.strip():
            return False
        new_name = new_name.strip()

        renamed_count = 0
        for m in self.metadata:
            if str(m.get("employee_id")) == str(employee_id):
                m["name"] = new_name
                renamed_count += 1

        if renamed_count > 0:
            self._save()
            logger = logging.getLogger(__name__)
            logger.info("Renamed employee_id '%s' → name '%s' in metadata (%d records)", employee_id, new_name, renamed_count)
            return True
        return False

    def update_employee_id(self, old_emp_id: str, new_emp_id: str) -> bool:
        """Safely update an employee's identifier in FAISS metadata."""
        if not new_emp_id or not new_emp_id.strip():
            return False
        new_emp_id = new_emp_id.strip()

        updated_count = 0
        for m in self.metadata:
            if str(m.get("employee_id")) == str(old_emp_id):
                m["employee_id"] = new_emp_id
                updated_count += 1

        if updated_count > 0:
            self._save()
            return True
        return False

    def clear(self) -> None:
        """Remove **all** enrolled faces."""
        self.metadata = []
        self.index = self._create_index()
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

    # ── Persistence ───────────────────────────────────────────

    def _save(self) -> None:
        """Write the index and metadata to disk."""
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def _rebuild_index(self) -> None:
        """Rebuild the FAISS index from scratch.

        Reconstructs every vector from the old index into a fresh one.
        If any vector fails to reconstruct, its metadata entry is also
        dropped so index-metadata alignment is never broken.

        .. note::
            This is a safety utility. Normal mutation flows
            (``remove_by_name``, ``rename``, ``clear``) already handle
            index rebuilds internally.
        """
        old_count = self.index.ntotal
        if old_count == 0:
            self.metadata = []
            return

        new_index = self._create_index()
        new_metadata: List[Dict] = []
        dropped = 0

        if hasattr(self.index, "reconstruct"):
            for i in range(old_count):
                try:
                    vec = self.index.reconstruct(i)
                    new_index.add(vec.reshape(1, -1))
                    # Only keep metadata if reconstruction succeeded
                    if i < len(self.metadata):
                        item = dict(self.metadata[i])
                        item["id"] = len(new_metadata)
                        new_metadata.append(item)
                except Exception as exc:
                    dropped += 1
                    logger.warning("Failed to reconstruct embedding %d: %s", i, exc)
            self.index = new_index
        else:
            logger.warning(
                "FAISS index type %s does not support reconstruction. Clearing all embeddings.",
                type(self.index).__name__,
            )
            self.index = self._create_index()
            new_metadata = []
            dropped = old_count

        self.metadata = new_metadata
        self._save()

        if dropped > 0:
            logger.warning(
                "FAISS index rebuilt — %d/%d embedding(s) preserved, %d dropped."
                " Metadata for %d person(s) updated.",
                self.index.ntotal,
                old_count,
                dropped,
                len(self.metadata),
            )
        else:
            logger.info(
                "FAISS index rebuilt — all %d embedding(s) preserved. Metadata for %d person(s) updated.",
                self.index.ntotal,
                len(self.metadata),
            )

    def status(self) -> Dict:
        """Return a summary dict of the enrollment state."""
        index_type = cfg.FAISS_INDEX_TYPE.lower()
        index_info: Dict = {"type": index_type}
        if index_type == "hnsw":
            index_info["M"] = cfg.FAISS_HNSW_M
            index_info["ef_construction"] = cfg.FAISS_HNSW_EF_CONSTRUCTION
            index_info["ef_search"] = cfg.FAISS_HNSW_EF_SEARCH
        elif index_type == "ivf":
            index_info["nlist"] = cfg.FAISS_IVF_NLIST
            index_info["nprobe"] = cfg.FAISS_IVF_NPROBE
        else:
            index_info["type"] = "flat"
        return {
            "total_embeddings": self.count(),
            "unique_persons": self.unique_count(),
            "persons": self.all_persons(),
            "index": index_info,
        }
