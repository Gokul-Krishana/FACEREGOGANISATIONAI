"""
HNSW Parameter Tuning - 100K x 512-D (L2-normalized)
======================================================

Tests M (16-64), efConstruction (100-400), and efSearch (32-512)
to find the optimal recall-vs-latency tradeoff for production.

Also tests incremental insertion performance.

WARNING: Full index construction at 500K with HNSW can take
several minutes per combination. Defaults to 100K for reasonable times.

Usage:
    python scripts/benchmarks/tune_hnsw.py --size 100000
    python scripts/benchmarks/tune_hnsw.py --size 100000 --ef-search-values 32 64 128 256 512
"""

from __future__ import annotations

import argparse
import json
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
    tmp = Path(tempfile.gettempdir()) / "hnsw_tune.index"
    faiss.write_index(index, str(tmp))
    mb = tmp.stat().st_size / (1024 * 1024)
    tmp.unlink()
    return {"index_size_mb": round(mb, 2)}


def tune_hnsw(size: int, dim: int, queries: int, k: int,
              m_values: List[int], ef_construction_values: List[int],
              ef_search_values: List[int], seed: int = 42) -> List[Dict[str, Any]]:
    rng = np.random.default_rng(seed)
    vectors = _normalize(rng.random((size, dim), dtype=np.float32))
    probe = _normalize(rng.random((queries, dim), dtype=np.float32))

    print("  Building exact index for ground truth...")
    exact = faiss.IndexFlatL2(dim)
    exact.add(vectors)
    _, gt = exact.search(probe, k)

    results: List[Dict[str, Any]] = []
    for m in m_values:
        for ef_construction in ef_construction_values:
            print(f"  Building HNSW: M={m}, efConstruction={ef_construction}...", end=" ", flush=True)
            t0 = time.perf_counter()
            hnsw = faiss.IndexHNSWFlat(dim, m)
            hnsw.hnsw.efConstruction = ef_construction
            hnsw.add(vectors)
            build_time = time.perf_counter() - t0
            mem = _serialize_size(hnsw)
            print(f"build={build_time*1000:.0f}ms, size={mem['index_size_mb']:.1f}MB")

            for ef_search in ef_search_values:
                hnsw.hnsw.efSearch = ef_search
                actual_idx, lat = _search_per_query(hnsw, probe, k)
                r1 = _recall(gt, actual_idx, 1)
                r5 = _recall(gt, actual_idx, 5)
                r10 = _recall(gt, actual_idx, 10)
                qps = round(1000.0 / max(lat["avg_ms"], 1e-9), 2)
                print(f"    efSearch={ef_search:3d} | "
                      f"Recall@1={r1:.4f}  Recall@5={r5:.4f}  "
                      f"avg={lat['avg_ms']:.4f}ms  P95={lat['p95_ms']:.4f}ms  QPS={qps}")
                results.append({
                    "M": m, "efConstruction": ef_construction, "efSearch": ef_search,
                    "size": size, "dimension": dim,
                    "recall_at_1": round(r1, 4), "recall_at_5": round(r5, 4), "recall_at_10": round(r10, 4),
                    "build_ms": round(build_time * 1000, 2), "queries_per_sec": qps,
                    **lat, **mem,
                })
    return results


def test_incremental_insertion(size: int, dim: int, batch_sizes: List[int],
                                m: int = 32, ef_construction: int = 200, seed: int = 42) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    all_vectors = _normalize(rng.random((size, dim), dtype=np.float32))
    results: Dict[str, Any] = {"M": m, "efConstruction": ef_construction, "total_vectors": size, "batches": []}
    hnsw = faiss.IndexHNSWFlat(dim, m)
    hnsw.hnsw.efConstruction = ef_construction
    inserted = 0
    for batch_size in batch_sizes:
        batch = all_vectors[inserted : inserted + batch_size]
        if len(batch) == 0:
            break
        t0 = time.perf_counter()
        hnsw.add(batch)
        elapsed = time.perf_counter() - t0
        inserted += len(batch)
        results["batches"].append({
            "batch_size": len(batch), "total_after": inserted,
            "insert_ms": round(elapsed * 1000, 2),
            "insert_per_vec_ms": round((elapsed / len(batch)) * 1000, 4),
        })
    results["total_insert_ms"] = round(sum(b["insert_ms"] for b in results["batches"]), 2)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="HNSW parameter tuning at 512-D")
    parser.add_argument("--size", type=int, default=100000)
    parser.add_argument("--dim", type=int, default=512)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--m-values", nargs="+", type=int, default=[16, 32, 48, 64])
    parser.add_argument("--ef-construction-values", nargs="+", type=int, default=[100, 200, 400])
    parser.add_argument("--ef-search-values", nargs="+", type=int, default=[32, 64, 128, 256, 512])
    parser.add_argument("--output", default=str(Path("outputs") / "hnsw_tuning.json"))
    parser.add_argument("--incremental", action="store_true")
    args = parser.parse_args()

    print("=" * 72)
    print("HNSW Parameter Tuning")
    print(f"Size: {args.size:,} | Dimension: {args.dim} | Queries: {args.queries} | k: {args.k}")
    print(f"M values: {args.m_values}")
    print(f"efConstruction values: {args.ef_construction_values}")
    print(f"efSearch values: {args.ef_search_values}")
    print("=" * 72)

    dash = "-" * 72
    print(f"\n{dash}")
    print("  PARAMETER SWEEP")
    print(dash)

    tuning_results = tune_hnsw(args.size, args.dim, args.queries, args.k,
                                args.m_values, args.ef_construction_values, args.ef_search_values)

    output: Dict[str, Any] = {
        "config": {
            "size": args.size, "dimension": args.dim, "queries": args.queries, "k": args.k,
            "m_values": args.m_values, "ef_construction_values": args.ef_construction_values,
            "ef_search_values": args.ef_search_values,
            "note": "Synthetic L2-normalized 512-D vectors. Final selection needs real data validation.",
        },
        "parameter_sweep": tuning_results,
    }

    if args.incremental:
        print(f"\n{dash}")
        print("  INCREMENTAL INSERTION PERFORMANCE")
        print(dash)
        batch_sizes = [100, 1000, 10000, 50000, args.size - 61100]
        inc_result = test_incremental_insertion(args.size, args.dim, batch_sizes)
        output["incremental_insertion"] = inc_result
        print(f"  Total insert time: {inc_result['total_insert_ms']:.2f} ms")
        for b in inc_result["batches"]:
            print(f"    Batch {b['batch_size']:>6}: {b['insert_ms']:>8.2f} ms  "
                  f"({b['insert_per_vec_ms']:.4f} ms/vec)")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nResults saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
