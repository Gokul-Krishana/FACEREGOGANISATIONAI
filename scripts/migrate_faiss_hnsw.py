"""
FAISS Index Migration Script
=============================
Extracts all embeddings from the current FAISS index (Flat),
rebuilds with current HNSW config from settings.yaml, and re-adds them.

Usage:
    python scripts/migrate_faiss_hnsw.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import faiss

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg  # noqa: E402
from app.enrollment import FaceEnrollment  # noqa: E402


def main() -> int:
    enroll = FaceEnrollment()

    old_count = enroll.index.ntotal
    old_type = type(enroll.index).__name__
    print(f"Current index: {old_type} ({old_count} vectors)")

    if old_count == 0:
        print("No embeddings to migrate. Creating new empty HNSW index.")
        enroll.index = enroll._create_index()
        enroll._save()
    else:
        # 1. Extract existing embeddings and metadata
        print(f"Extracting {old_count} embeddings from {old_type}...")
        embeddings = enroll.index.reconstruct_n(0, old_count)
        metadata = list(enroll.metadata)  # copy

        # 2. Verify config is now HNSW
        new_type = cfg.FAISS_INDEX_TYPE.lower()
        print(f"Configured index type: {new_type}")
        print(
            f"HNSW M={cfg.FAISS_HNSW_M}, efConstruction={cfg.FAISS_HNSW_EF_CONSTRUCTION}, efSearch={cfg.FAISS_HNSW_EF_SEARCH}"
        )

        # 3. Rebuild with new config
        print("Rebuilding index with new configuration...")
        enroll.index = enroll._create_index()
        enroll.metadata = []

        # 4. Check if IVF needs training
        if cfg.FAISS_INDEX_TYPE.lower() == "ivf":
            print("Training IVF index...")
            enroll.index.train(embeddings)

        # 5. Re-add all embeddings
        print(f"Re-adding {old_count} embeddings...")
        for i, emb in enumerate(embeddings):
            name = metadata[i]["name"]
            enroll.enroll(name, emb.reshape(1, -1).astype(np.float32))

    # 6. Verify
    final_type = type(enroll.index).__name__
    final_count = enroll.index.ntotal

    print("\n[OK] Migration complete!")
    print(f"   Index type: {old_type} -> {final_type}")
    print(f"   Vectors: {old_count} -> {final_count}")
    print(f"   Metadata: {len(enroll.metadata)} entries")

    if enroll.index.ntotal > 0:
        # Quick search test
        test_vec = (
            embeddings[0:1] if old_count > 0 else np.random.randn(1, cfg.EMBEDDING_DIM).astype(np.float32)
        )
        faiss.normalize_L2(test_vec)
        D, idx = enroll.index.search(test_vec, min(5, enroll.index.ntotal))
        print(f"   Search test: top-1 distance={D[0][0]:.4f}, index={idx[0][0]}")

    # Show status
    status = enroll.status()
    print(f"\nStatus: {json.dumps(status, indent=2)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
