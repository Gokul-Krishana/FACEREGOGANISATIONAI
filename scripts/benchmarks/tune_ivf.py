"""
IVF Parameter Tuning - 500K x 512-D (L2-normalized)
=====================================================

Tests nprobe (8-256) and nlist variants to find the optimal
recall-vs-latency tradeoff for production.

Uses synthetic L2-normalized vectors (matching the production
ArcFace strategy).  **Final index selection requires validation
on real face embeddings.**
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import faiss
import numpy as np


def _normalize(vectors: np.ndarray) -> np.ndarray:
    faiss.normalize_L2(vectors)
    return vectors


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
    return all_indices, {
        "avg_ms": round(float(per_times.mean()), 4),
        "p50_ms": round(float(np.median(per_times)), 4),
        "p95_ms": round(float(per_times[int(n * 0.95)]), 4),
        "p99_ms": round(float(per_times[int(n * 0.99)]), 4),
        "min_ms": round(float(per_times[0]), 4),
        "max_ms": round(float(per_times[-1]), 4),
    }


def _recall(reference: np.ndarray, actual: np.ndarray, k: int) -> float:
    hits = 0
    for ref_row, actual_row in zip(reference, actual):
        ref_set = set(ref_row[:k])
        if any(c in ref_set for c in actual_row[:k]):
            hits += 1
    return hits / len(reference)


def _serialize_size(index) -> Dict[str, float]:
    tmp = Path(tempfile.gettempdir()) / "ivf_tune.index"
    faiss.write_index(index, str(tmp))
    mb = tmp.stat().st_size / (1024 * 1024)
    tmp.unlink()
    return {"index_size_mb": round(mb, 2)}


def tune_ivf(size: int, dim: int, queries: int, k: int,
             nprobe_values: List[int], nlist_values: List[int], seed: int = 42) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(seed)
    vectors = _normalize(rng.random((size, dim), dtype=np.float32))
    probe = _normalize(rng.random((queries, dim), dtype=np.float32))

    print("  Building exact index for ground truth...")
    exact = faiss.IndexFlatL2(dim)
    exact.add(vectors)
    _, gt = exact.search(probe, k)

    results: List[Dict[str, Any]] = []
    for nlist in nlist_values:
        for nprobe in nprobe_values:
            print(f"  Testing: nlist={nlist}, nprobe={nprobe}...", end=" ", flush=True)
            quantizer = faiss.IndexFlatL2(dim)
            ivf = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_L2)
            train_size = min(len(vectors), max(nlist * 20, 1000))
            t0 = time.perf_counter()
            ivf.train(vectors[:train_size])
            ivf.add(vectors)
            build_time = time.perf_counter() - t0
            ivf.nprobe = nprobe
            actual_idx, lat = _search_per_query(ivf, probe, k)
            r1 = _recall(gt, actual_idx, 1)
            r5 = _recall(gt, actual_idx, 5)
            r10 = _recall(gt, actual_idx, 10)
            mem = _serialize_size(ivf)
            qps = round(1000.0 / max(lat["avg_ms"], 1e-9), 2)
            print(f"Recall@1={r1:.4f}  Recall@5={r5:.4f}  "
                  f"avg={lat['avg_ms']:.4f}ms  P95={lat['p95_ms']:.4f}ms  QPS={qps}")
            results.append({
                "nlist": nlist, "nprobe": nprobe, "size": size, "dimension": dim,
                "recall_at_1": round(r1, 4), "recall_at_5": round(r5, 4), "recall_at_10": round(r10, 4),
                "build_ms": round(build_time * 1000, 2), "queries_per_sec": qps,
                **lat, **mem,
            })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="IVF parameter tuning at 500K x 512-D")
    parser.add_argument("--sizes", nargs="+", type=int, default=[100000, 500000])
    parser.add_argument("--dim", type=int, default=512)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--nprobe-values", nargs="+", type=int, default=[8, 16, 32, 64, 128, 256])
    parser.add_argument("--nlist-values", nargs="+", type=int, default=None)
    parser.add_argument("--output", default=str(Path("outputs") / "ivf_tuning.json"))
    args = parser.parse_args()

    nlist_values = args.nlist_values or [max(32, int(math.sqrt(s))) for s in args.sizes]

    print("=" * 72)
    print("IVF Parameter Tuning")
    print(f"Dimension: {args.dim} | Queries: {args.queries} | k: {args.k}")
    print(f"Sizes: {args.sizes}")
    print(f"nprobe values: {args.nprobe_values}")
    print(f"nlist values: {nlist_values}")
    print("=" * 72)

    all_results: Dict[str, Any] = {
        "config": {
            "dimension": args.dim, "queries": args.queries, "k": args.k,
            "nprobe_values": args.nprobe_values, "nlist_values": nlist_values,
            "note": "Synthetic L2-normalized 512-D vectors. Final index selection needs real data validation.",
        },
        "results": [],
    }

    for size in args.sizes:
        nlist_candidates = [max(32, int(math.sqrt(size)))]
        nlist_candidates.append(max(16, nlist_candidates[0] // 2))
        nlist_candidates.append(max(64, nlist_candidates[0] * 2))
        nlist_candidates = sorted(set(nlist_candidates))
        dash = "-" * 72
        print(f"\n{dash}")
        print(f"  SIZE: {size:,}")
        print(f"  nlist candidates: {nlist_candidates}")
        print(dash)
        size_results = tune_ivf(size, args.dim, args.queries, args.k,
                                args.nprobe_values, nlist_candidates)
        all_results["results"].extend(size_results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nResults saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
