"""
Tests for FaceEnrollment (FAISS database).

Covers enrollment, search, threshold filtering, persistence across
reloads, clear, and edge cases.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import mkdtemp

import numpy as np
import pytest

from app.enrollment import FaceEnrollment


@pytest.fixture()
def temp_dir():
    """Create a temporary directory for test FAISS index files."""
    d = Path(mkdtemp())
    yield d
    shutil.rmtree(d)


@pytest.fixture()
def enrollment(temp_dir):
    """Create a FaceEnrollment instance backed by temporary files."""
    index_path = temp_dir / "test.index"
    meta_path = temp_dir / "test_metadata.json"
    return FaceEnrollment(index_path=str(index_path), metadata_path=str(meta_path))


@pytest.fixture()
def sample_embedding():
    """Return a random 512D embedding (simulates an ArcFace output)."""
    return np.random.rand(512).astype(np.float32)


class TestFaceEnrollment:
    """Tests for FaceEnrollment CRUD and search."""

    def test_init_empty(self, enrollment):
        assert enrollment.count() == 0
        assert enrollment.all_persons() == []

    def test_enroll_single(self, enrollment, sample_embedding):
        result = enrollment.enroll("Alice", sample_embedding)
        assert result is True
        assert enrollment.count() == 1
        assert enrollment.all_persons() == ["Alice"]

    def test_enroll_multiple(self, enrollment):
        emb1 = np.random.rand(512).astype(np.float32)
        emb2 = np.random.rand(512).astype(np.float32)
        enrollment.enroll("Alice", emb1)
        enrollment.enroll("Bob", emb2)
        assert enrollment.count() == 2
        assert enrollment.all_persons() == ["Alice", "Bob"]

    def test_search_exact_match(self, enrollment, sample_embedding):
        enrollment.enroll("Alice", sample_embedding)
        matches = enrollment.search(sample_embedding, k=1, threshold=2.0)
        assert len(matches) == 1
        assert matches[0]["name"] == "Alice"
        assert matches[0]["distance"] == 0.0  # Exact match
        assert matches[0]["confidence"] == 1.0

    def test_search_empty_index(self, enrollment, sample_embedding):
        matches = enrollment.search(sample_embedding, k=1, threshold=2.0)
        assert matches == []

    def test_search_threshold_rejects_far_match(self, enrollment):
        emb1 = np.array([0.0] * 512, dtype=np.float32)
        emb2 = np.array([10.0] * 512, dtype=np.float32)  # Very different
        enrollment.enroll("Alice", emb1)
        matches = enrollment.search(emb2, k=1, threshold=0.5)  # Strict threshold
        assert matches == []  # Should be rejected

    def test_search_threshold_accepts_close_match(self, enrollment):
        emb1 = np.array([0.0] * 512, dtype=np.float32)
        emb2 = np.array([0.01] * 512, dtype=np.float32)  # Very close
        enrollment.enroll("Alice", emb1)
        matches = enrollment.search(emb2, k=1, threshold=2.0)
        assert len(matches) == 1
        assert matches[0]["name"] == "Alice"

    def test_persistence_across_reloads(self, temp_dir, sample_embedding):
        """Enrolled faces should survive FaceEnrollment re-initialization."""
        index_path = temp_dir / "persist_test.index"
        meta_path = temp_dir / "persist_test_metadata.json"

        e1 = FaceEnrollment(index_path=str(index_path), metadata_path=str(meta_path))
        e1.enroll("Alice", sample_embedding)
        assert e1.count() == 1

        e2 = FaceEnrollment(index_path=str(index_path), metadata_path=str(meta_path))
        assert e2.count() == 1
        assert e2.all_persons() == ["Alice"]

        matches = e2.search(sample_embedding, k=1, threshold=2.0)
        assert len(matches) == 1
        assert matches[0]["name"] == "Alice"

    def test_clear_removes_all(self, enrollment, sample_embedding):
        enrollment.enroll("Alice", sample_embedding)
        enrollment.enroll("Bob", sample_embedding.copy())
        assert enrollment.count() == 2

        enrollment.clear()
        assert enrollment.count() == 0
        assert enrollment.all_persons() == []

    def test_search_k_returns_multiple(self, enrollment):
        """FAISS IndexFlatL2 returns squared L2 distances."""
        # Vectors with squared distances: 5.12, 1.28, 0.05 (all under 10)
        query = np.array([0.0] * 512, dtype=np.float32)
        # Distance = sqrt(512 * 0.01^2) = sqrt(0.0512) ≈ 0.226 but squared = 0.0512
        emb_close = np.array([0.01] * 512, dtype=np.float32)
        # Distance squared = 512 * 0.05^2 = 1.28
        emb_medium = np.array([0.05] * 512, dtype=np.float32)
        # Distance squared = 512 * 0.1^2 = 5.12
        emb_far = np.array([0.1] * 512, dtype=np.float32)

        enrollment.enroll("Far", emb_far)
        enrollment.enroll("Medium", emb_medium)
        enrollment.enroll("Close", emb_close)

        matches = enrollment.search(query, k=3, threshold=10.0)
        # FAISS uses squared L2 distance, so 0.05, 1.28, 5.12 are all under 10.0
        assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}: {matches}"
        assert matches[0]["name"] == "Close"  # Closest first (squared dist = 0.05)
        assert matches[2]["name"] == "Far"  # Farthest last (squared dist = 5.12)

    def test_unique_count(self, enrollment):
        emb1 = np.random.rand(512).astype(np.float32)
        emb2 = np.random.rand(512).astype(np.float32)
        enrollment.enroll("Alice", emb1)
        enrollment.enroll("Alice", emb2)  # Same name, different embedding
        assert enrollment.count() == 2  # Two embeddings
        assert enrollment.unique_count() == 1  # One unique person

    def test_status(self, enrollment, sample_embedding):
        enrollment.enroll("Alice", sample_embedding)
        status = enrollment.status()
        assert status["total_embeddings"] == 1
        assert status["unique_persons"] == 1
        assert "Alice" in status["persons"]

    def test_metadata_format(self, temp_dir, sample_embedding):
        """Metadata JSON should be human-readable."""
        index_path = temp_dir / "meta_test.index"
        meta_path = temp_dir / "meta_test_metadata.json"

        e = FaceEnrollment(index_path=str(index_path), metadata_path=str(meta_path))
        e.enroll("Alice", sample_embedding)

        with open(meta_path, "r") as f:
            metadata = json.load(f)
        assert len(metadata) == 1
        assert metadata[0]["name"] == "Alice"
        assert "id" in metadata[0]
