"""
FAISS 512-D Scalability Benchmark — IndexFlat vs HNSW vs IVF
===============================================================

Tests 1K, 10K, 100K, 500K embeddings at **512-D** (ArcFace-compatible,
normalised L2).  Reports:

    - Recall@1, Recall@5, Recall@k
    - avg / P50 / P95 / P99 query latency
    - build time, QPS, memory, index size
    - **acceptance PASS/FAIL** against production targets

Usage:
    python scripts/benchmarks/faiss_benchmark.py
    python scripts/benchmarks/faiss_benchmark.py --sizes 1000 10000 100000 500000

Acceptance targets (for 500K at 512-D):
    - HNSW Recall@1 >= 0.95
    - HNSW avg query <= 2.0 ms
    - IVF Recall@1 >= 0.90
    - IVF avg query <= 1.0 ms
    - Baseline search <= 500 ms total (500K)
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

# ── Acceptance targets (for 500K @ 512-D) ──────────────────────────
ACCEPTANCE_TARGETS: Dict[str, Dict[str, float]] = {
    "hnsw": {
        "recall_at_1_min": 0.95,
        "avg_query_ms_max": 2.0,
    },
    "ivf": {
        "recall_at_1_min": 0.90,
        "avg_query_ms_max": 1.0,
    },
    "baseline": {
        "search_ms_max_500k": 500.0,
    },
}


def _normalize(vectors: np.ndarray) -> np.ndarray:
    faiss.normalize_L2(vectors)
    return vectors


def _build_exact(vectors: np.ndarray) -> tuple[faiss.IndexFlatL2, float]:
    start = time.perf_counter()
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)
    return index, time.perf_counter() - start


def _build_hnsw(
    vectors: np.ndarray, m: int = 32, ef_construction: int = 200
) -> tuple[faiss.IndexHNSWFlat, float]:
    start = time.perf_counter()
    index = faiss.IndexHNSWFlat(vectors.shape[1], m)
    index.hnsw.efConstruction = ef_construction
    index.add(vectors)
    return index, time.perf_counter() - start


def _build_ivf(
    vectors: np.ndarray, nlist: int | None = None
) -> tuple[faiss.IndexIVFFlat, float]:
    dim = vectors.shape[1]
    nlist = nlist or max(32, int(math.sqrt(len(vectors))))
    quantizer = faiss.IndexFlatL2(dim)
    index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_L2)
    train_size = min(len(vectors), max(nlist * 20, 1000))
    start = time.perf_counter()
    index.train(vectors[:train_size])
    index.add(vectors)
    index.nprobe = min(16, nlist)
    return index, time.perf_counter() - start


def _serialize_size(index) -> int:
    tmp = (
        Path(tempfile.gettempdir())
        / f"faiss_{type(index).__name__}.index"
    )
    faiss.write_index(index, str(tmp))
    return tmp.stat().st_size


def _recall(reference: np.ndarray, actual: np.ndarray, k: int) -> float:
    """Compute recall@k: fraction of queries where a ground-truth
    neighbour appears in the first *k* results."""
    hits = 0
    for ref_row, actual_row in zip(reference, actual):
        ref_set = set(ref_row[:k])
        if any(candidate in ref_set for candidate in actual_row[:k]):
            hits += 1
    return hits / len(reference)


def _search_per_query(
    index, queries: np.ndarray, k: int
) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
    """Search all queries and return results plus per-query latency stats.

    Returns:
        ``(distances, indices, latency_stats)`` where latency_stats
        contains ``avg_ms``, ``p50_ms``, ``p95_ms``, ``p99_ms``,
        ``min_ms``, ``max_ms``.
    """
    n = len(queries)
    per_times = np.empty(n, dtype=np.float64)
    all_distances = np.empty((n, k), dtype=np.float32)
    all_indices = np.empty((n, k), dtype=np.int64)

    for i in range(n):
        q = queries[i : i + 1]  # keep 2-D
        t0 = time.perf_counter()
        D, I = index.search(q, k)
        t1 = time.perf_counter()
        per_times[i] = (t1 - t0) * 1000  # milliseconds
        all_distances[i] = D[0]
        all_indices[i] = I[0]

    per_times.sort()
    return all_distances, all_indices, {
        "avg_ms": round(float(per_times.mean()), 4),
        "p50_ms": round(float(np.median(per_times)), 4),
        "p95_ms": round(float(per_times[int(n * 0.95)]), 4),
        "p99_ms": round(float(per_times[int(n * 0.99)]), 4),
        "min_ms": round(float(per_times[0]), 4),
        "max_ms": round(float(per_times[-1]), 4),
    }


def _assess_targets(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Check acceptance targets and add PASS/FAIL to each size result."""
    assessments: List[Dict[str, Any]] = []
    for r in results:
        size = r["size"]
        size_assess: Dict[str, Any] = {"size": size, "checks": [], "overall": "PASS"}

        # Baseline check (500K only)
        if size == 500000:
            base_ms = r["baseline"]["search_ms"]
            target = ACCEPTANCE_TARGETS["baseline"]["search_ms_max_500k"]
            passed = base_ms <= target
            size_assess["checks"].append({
                "check": f"baseline_search_ms <= {target}",
                "measured": round(base_ms, 2),
                "passed": passed,
            })
            if not passed:
                size_assess["overall"] = "FAIL"

        # HNSW checks
        hnsw_r1 = r["hnsw"]["recall_at_1"]
        target_r1 = ACCEPTANCE_TARGETS["hnsw"]["recall_at_1_min"]
        passed_r1 = hnsw_r1 >= target_r1
        size_assess["checks"].append({
            "check": f"HNSW Recall@1 >= {target_r1}",
            "measured": hnsw_r1,
            "passed": passed_r1,
        })

        hnsw_ms = r["hnsw"]["avg_query_ms"]
        target_ms = ACCEPTANCE_TARGETS["hnsw"]["avg_query_ms_max"]
        passed_ms = hnsw_ms <= target_ms
        size_assess["checks"].append({
            "check": f"HNSW avg_query_ms <= {target_ms}",
            "measured": hnsw_ms,
            "passed": passed_ms,
        })
        if not (passed_r1 and passed_ms):
            size_assess["overall"] = "FAIL"

        # IVF checks
        ivf_r1 = r["ivf"]["recall_at_1"]
        target_ivf_r1 = ACCEPTANCE_TARGETS["ivf"]["recall_at_1_min"]
        passed_ivf_r1 = ivf_r1 >= target_ivf_r1
        size_assess["checks"].append({
            "check": f"IVF Recall@1 >= {target_ivf_r1}",
            "measured": ivf_r1,
            "passed": passed_ivf_r1,
        })

        ivf_ms = r["ivf"]["avg_query_ms"]
        target_ivf_ms = ACCEPTANCE_TARGETS["ivf"]["avg_query_ms_max"]
        passed_ivf_ms = ivf_ms <= target_ivf_ms
        size_assess["checks"].append({
            "check": f"IVF avg_query_ms <= {target_ivf_ms}",
            "measured": ivf_ms,
            "passed": passed_ivf_ms,
        })
        if not (passed_ivf_r1 and passed_ivf_ms):
            size_assess["overall"] = "FAIL"

        assessments.append(size_assess)

    return assessments


def benchmark_size(size: int, dim: int, queries: int, k: int) -> dict:
    rng = np.random.default_rng(42 + size)
    vectors = _normalize(rng.random((size, dim), dtype=np.float32))
    probe = _normalize(rng.random((queries, dim), dtype=np.float32))

    # ── Build indexes ──────────────────────────────────────────
    exact, exact_build = _build_exact(vectors)
    hnsw, hnsw_build = _build_hnsw(vectors)
    ivf, ivf_build = _build_ivf(vectors)

    # ── Baseline (exact) search ────────────────────────────────
    exact_dist, exact_idx, exact_latency = _search_per_query(exact, probe, k)

    # ── HNSW search ────────────────────────────────────────────
    hnsw_dist, hnsw_idx, hnsw_latency = _search_per_query(hnsw, probe, k)

    # ── IVF search ─────────────────────────────────────────────
    ivf_dist, ivf_idx, ivf_latency = _search_per_query(ivf, probe, k)

    return {
        "size": size,
        "dimension": dim,
        "queries": queries,
        "k": k,
        "baseline": {
            "index": "IndexFlatL2",
            "build_ms": round(exact_build * 1000, 2),
            "search_ms": round(exact_latency["avg_ms"] * queries, 2),
            "avg_query_ms": exact_latency["avg_ms"],
            "p50_ms": exact_latency["p50_ms"],
            "p95_ms": exact_latency["p95_ms"],
            "p99_ms": exact_latency["p99_ms"],
            "min_ms": exact_latency["min_ms"],
            "max_ms": exact_latency["max_ms"],
            "queries_per_sec": round(queries / max(exact_latency["avg_ms"] * queries / 1000, 1e-9), 2),
            "memory_bytes": _serialize_size(exact),
            "memory_mb": round(_serialize_size(exact) / (1024 * 1024), 2),
        },
        "hnsw": {
            "index": "IndexHNSWFlat",
            "build_ms": round(hnsw_build * 1000, 2),
            "search_ms": round(hnsw_latency["avg_ms"] * queries, 2),
            "avg_query_ms": hnsw_latency["avg_ms"],
            "p50_ms": hnsw_latency["p50_ms"],
            "p95_ms": hnsw_latency["p95_ms"],
            "p99_ms": hnsw_latency["p99_ms"],
            "min_ms": hnsw_latency["min_ms"],
            "max_ms": hnsw_latency["max_ms"],
            "queries_per_sec": round(queries / max(hnsw_latency["avg_ms"] * queries / 1000, 1e-9), 2),
            "memory_bytes": _serialize_size(hnsw),
            "memory_mb": round(_serialize_size(hnsw) / (1024 * 1024), 2),
            "recall_at_1": round(_recall(exact_idx, hnsw_idx, 1), 4),
            "recall_at_5": round(_recall(exact_idx, hnsw_idx, 5), 4),
            "recall_at_k": round(_recall(exact_idx, hnsw_idx, k), 4),
        },
        "ivf": {
            "index": "IndexIVFFlat",
            "build_ms": round(ivf_build * 1000, 2),
            "search_ms": round(ivf_latency["avg_ms"] * queries, 2),
            "avg_query_ms": ivf_latency["avg_ms"],
            "p50_ms": ivf_latency["p50_ms"],
            "p95_ms": ivf_latency["p95_ms"],
            "p99_ms": ivf_latency["p99_ms"],
            "min_ms": ivf_latency["min_ms"],
            "max_ms": ivf_latency["max_ms"],
            "queries_per_sec": round(queries / max(ivf_latency["avg_ms"] * queries / 1000, 1e-9), 2),
            "memory_bytes": _serialize_size(ivf),
            "memory_mb": round(_serialize_size(ivf) / (1024 * 1024), 2),
            "recall_at_1": round(_recall(exact_idx, ivf_idx, 1), 4),
            "recall_at_5": round(_recall(exact_idx, ivf_idx, 5), 4),
            "recall_at_k": round(_recall(exact_idx, ivf_idx, k), 4),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="FAISS 512-D scalability benchmark with acceptance targets."
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=[1000, 10000, 100000, 500000],
    )
    parser.add_argument("--dim", type=int, default=512)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument(
        "--output",
        default=str(Path("outputs") / "faiss_benchmark.json"),
    )
    args = parser.parse_args()

    sep = "=" * 72
    print(sep)
    print("FAISS 512-D Scalability Benchmark")
    print(f"Dimension: {args.dim} | Queries: {args.queries} | k: {args.k}")
    print(f"Sizes: {args.sizes}")
    print(sep)

    results = [
        benchmark_size(size, args.dim, args.queries, args.k)
        for size in args.sizes
    ]

    # Acceptance assessment
    assessments = _assess_targets(results)
    for r, a in zip(results, assessments):
        r["acceptance"] = a

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # ── Print results ─────────────────────────────────────────
    for r in results:
        s = r["size"]
        sep2 = "-" * 72
        print()
        print(sep2)
        print(f"  SIZE: {s:,}  |  Dim: {r['dimension']}  |  Acceptance: {r['acceptance']['overall']}")
        print(sep2)

        for label, key in [("Baseline (IndexFlatL2)", "baseline"),
                            ("HNSW", "hnsw"),
                            ("IVF", "ivf")]:
            idx = r[key]
            print(f"  {label}:")
            print(f"    Build: {idx['build_ms']:>8.2f} ms  |  Search: {idx['search_ms']:>8.2f} ms")
            print(f"    Avg: {idx['avg_query_ms']:>8.4f} ms  |  P50: {idx['p50_ms']:>8.4f} ms  |  "
                  f"P95: {idx['p95_ms']:>8.4f} ms  |  P99: {idx['p99_ms']:>8.4f} ms")
            print(f"    Min: {idx['min_ms']:>8.4f} ms  |  Max: {idx['max_ms']:>8.4f} ms  |  "
                  f"QPS: {idx['queries_per_sec']:>8.2f}")
            print(f"    Memory: {idx['memory_mb']:>8.2f} MB")
            if "recall_at_1" in idx:
                print(f"    Recall@1: {idx['recall_at_1']:.4f}  |  "
                      f"Recall@5: {idx['recall_at_5']:.4f}  |  "
                      f"Recall@{r['k']}: {idx['recall_at_k']:.4f}")

        # Acceptance checks
        print(f"\n  Acceptance checks:")
        for check in r["acceptance"]["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            print(f"    {status} | {check['check']}: {check['measured']}")
        print(f"  Overall: {'PASS' if r['acceptance']['overall'] == 'PASS' else 'FAIL'}")

    overall = all(a["overall"] == "PASS" for a in assessments)
    print()
    print("=" * 72)
    print(f"  OVERALL BENCHMARK: {'PASS' if overall else 'FAIL'}")
    print("=" * 72)

    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
