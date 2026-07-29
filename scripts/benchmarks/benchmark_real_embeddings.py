"""
Real ArcFace Embedding Benchmark - IndexFlat vs IVF vs HNSW
=============================================================

Uses actual ArcFace embeddings from InsightFace (buffalo_l) to compare
FAISS index types on real face data rather than random vectors.

IMPORTANT: With only 5 enrolled identities and ~3 test images in
dataset/, this is a small-scale validation. A full production
benchmark requires a larger curated face dataset.

Usage:
    python scripts/benchmarks/benchmark_real_embeddings.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import faiss

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.recognizer import FaceRecognizer
from app.enrollment import FaceEnrollment


def _search_per_query(index, queries: np.ndarray, k: int) -> Tuple[np.ndarray, Dict[str, float]]:
    n = len(queries)
    per_times = np.empty(n, dtype=np.float64)
    all_indices = np.empty((n, k), dtype=np.int64)
    for i in range(n):
        q = queries[i : i + 1]
        t0 = time.perf_counter()
        _, I = index.search(q, k)
        t1 = time.perf_counter()
        per_times[i] = (t1 - t0) * 1000
        all_indices[i] = I[0]
    per_times.sort()
    return all_indices, {"avg_ms": round(float(per_times.mean()), 4),
                         "p50_ms": round(float(np.median(per_times)), 4),
                         "p95_ms": round(float(per_times[int(n * 0.95)]), 4),
                         "p99_ms": round(float(per_times[int(n * 0.99)]), 4),
                         "min_ms": round(float(per_times[0]), 4),
                         "max_ms": round(float(per_times[-1]), 4)}


def _recall(reference: np.ndarray, actual: np.ndarray, k: int) -> float:
    hits = 0
    for ref_row, actual_row in zip(reference, actual):
        ref_set = set(ref_row[:k])
        if any(c in ref_set for c in actual_row[:k]):
            hits += 1
    return hits / len(reference)


def load_real_embeddings() -> Tuple[List[np.ndarray], List[str], List[str]]:
    recognizer = FaceRecognizer()
    enrollment = FaceEnrollment()
    embeddings: List[np.ndarray] = []
    names: List[str] = []
    sources: List[str] = []

    dataset_dir = ROOT / "dataset"
    if dataset_dir.exists():
        for img_path in sorted(dataset_dir.glob("*.*")):
            if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp"):
                continue
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            emb = recognizer.extract_embedding(img)
            if emb is not None:
                embeddings.append(emb)
                names.append(img_path.stem)
                sources.append(f"dataset/{img_path.name}")

    enrolled_count = enrollment.count()
    enrolled_names = enrollment.all_persons()
    if enrolled_count > 0:
        print(f"\n  Existing FAISS index: {enrolled_count} embeddings ({len(enrolled_names)} unique): {enrolled_names}")
        print(f"  Extracted {len(embeddings)} embeddings from dataset/ images")

    if len(embeddings) < 2:
        print("\n  [WARN] Fewer than 2 embeddings extracted. Results will be limited.")
        print("  Add face images to dataset/ for more data.")

    return embeddings, names, sources


def main() -> int:
    print("=" * 72)
    print("Real ArcFace Embedding Benchmark")
    print("=" * 72)

    print("\n[1/3] Loading real ArcFace embeddings...")
    embs_list, names, sources = load_real_embeddings()
    if len(embs_list) == 0:
        print("\n  [ERROR] No embeddings extracted.")
        print("  Add face images to dataset/ and ensure InsightFace model is installed.")
        return 1

    embeddings = np.array(embs_list, dtype=np.float32)
    print(f"\n[2/3] Running index comparison on {len(embeddings)} embeddings...")

    n = len(embeddings)
    dim = embeddings.shape[1]
    if n < 2:
        print(f"  [ERROR] Need at least 2 embeddings (got {n})")
        return 1

    k = min(5, n)
    nq = n  # leave-one-out

    # Build indexes
    print("  Building indexes...")
    flat_index = faiss.IndexFlatL2(dim)
    flat_index.add(embeddings)
    _, gt = flat_index.search(embeddings[:nq], k)

    nlist = max(4, int(np.sqrt(n)))
    quantizer = faiss.IndexFlatL2(dim)
    ivf = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_L2)
    ivf.train(embeddings[:min(n, max(nlist * 20, n))])
    ivf.add(embeddings)
    ivf.nprobe = min(16, nlist)

    hnsw = faiss.IndexHNSWFlat(dim, 32)
    hnsw.hnsw.efConstruction = 200
    hnsw.add(embeddings)
    hnsw.hnsw.efSearch = 128

    print("  Running searches...")
    _, flat_lat = _search_per_query(flat_index, embeddings[:nq], k)
    ivf_idx, ivf_lat = _search_per_query(ivf, embeddings[:nq], k)
    hnsw_idx, hnsw_lat = _search_per_query(hnsw, embeddings[:nq], k)

    results: Dict[str, Any] = {
        "config": {"n_embeddings": n, "dimension": dim, "queries": nq, "k": k,
                   "names": names[:nq],
                   "note": "Real ArcFace embeddings. Small N - limited statistical significance."},
        "flat_baseline": {"index": "IndexFlatL2 (exact)", **flat_lat, "recall_at_1": 1.0},
        "ivf": {"index": "IndexIVFFlat", "nlist": nlist, "nprobe": ivf.nprobe, **ivf_lat,
                "recall_at_1": round(_recall(gt, ivf_idx, 1), 4),
                "recall_at_5": round(_recall(gt, ivf_idx, 5), 4)},
        "hnsw": {"index": "IndexHNSWFlat", "M": 32, "efConstruction": 200, "efSearch": 128, **hnsw_lat,
                 "recall_at_1": round(_recall(gt, hnsw_idx, 1), 4),
                 "recall_at_5": round(_recall(gt, hnsw_idx, 5), 4)},
    }

    print("\n[3/3] Saving results...")
    output_path = ROOT / "outputs" / "real_embedding_benchmark.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))

    print(f"\n{'='*72}")
    print("  RESULTS SUMMARY")
    print(f"{'='*72}")
    print(f"\n  Database: {n} real ArcFace embeddings, Queries: {nq}")
    for key, label in [("flat_baseline", "IndexFlatL2 (exact)"),
                        ("ivf", f"IVF (nlist={nlist}, nprobe={ivf.nprobe})"),
                        ("hnsw", "HNSW (M=32, efSearch=128)")]:
        idx = results.get(key, {})
        print(f"  {label}:")
        print(f"    Avg: {idx.get('avg_ms', 'N/A'):>8} ms  |  P95: {idx.get('p95_ms', 'N/A'):>8} ms")
        if "recall_at_1" in idx:
            print(f"    Recall@1: {idx['recall_at_1']:.4f}  |  Recall@5: {idx.get('recall_at_5', 'N/A'):>8}")
    print(f"\n  Results saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
