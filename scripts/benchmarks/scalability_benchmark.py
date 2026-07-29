"""
Database Scalability Benchmark — with Throughput & Acceptance Targets
======================================================================

Measures database performance at 1K, 10K, 100K, 500K student scale
with associated attendance + recognition log records.

Metrics (per size):
    - Student search (prefix lookup) latency + QPS
    - Attendance page (latest 50) latency + QPS
    - Recognition log page latency + QPS
    - Student count aggregation
    - Bulk write throughput (attendance + recognition writes/sec)

Acceptance targets (500K):
    - Student search ≤ 50 ms (PASS)
    - Attendance page ≤ 100 ms (PASS)
    - Recognition page ≤ 100 ms (PASS)
    - Bulk writes ≥ 5000 rows/sec (PASS)

Usage:
    python scripts/benchmarks/scalability_benchmark.py
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker

from database.models import Base, Student, Attendance, RecognitionLog

# ── Acceptance targets (500K scale) ────────────────────────────────
ACCEPTANCE_TARGETS: Dict[str, Dict[str, float]] = {
    "student_search": {"elapsed_ms_max": 50.0},
    "attendance_page": {"elapsed_ms_max": 100.0},
    "recognition_page": {"elapsed_ms_max": 100.0},
    "attendance_write_throughput": {"rows_per_sec_min": 5000},
    "recognition_write_throughput": {"rows_per_sec_min": 5000},
}


# ── Helpers ─────────────────────────────────────────────────────────


def _chunks(items: List, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _seed_dataset(
    session,
    num_students: int,
    attendance_per_student: int,
    recognition_per_student: int,
    batch_size: int = 5000,
) -> None:
    for batch_start in range(0, num_students, batch_size):
        batch_end = min(num_students, batch_start + batch_size)
        students = [
            Student(
                id=i + 1,
                student_id=f"STU{i + 1:07d}",
                name=f"Student {i + 1:07d}",
                email=f"student{i + 1}@college.edu",
                is_active=True,
            )
            for i in range(batch_start, batch_end)
        ]
        session.bulk_save_objects(students)
        session.commit()

        attendance_rows = []
        recognition_rows = []
        for student_id in range(batch_start + 1, batch_end + 1):
            for j in range(attendance_per_student):
                attendance_rows.append(
                    Attendance(
                        student_id=student_id,
                        confidence=0.85 + (j % 10) * 0.01,
                        method="FACE_RECOGNITION",
                        status="PRESENT",
                    )
                )
            for j in range(recognition_per_student):
                recognition_rows.append(
                    RecognitionLog(
                        student_id=student_id,
                        is_known=True,
                        confidence=0.80 + (j % 10) * 0.01,
                        liveness_confidence=0.75,
                        is_spoof=False,
                    )
                )

        for batch in _chunks(attendance_rows, batch_size):
            session.bulk_save_objects(batch)
            session.commit()
        for batch in _chunks(recognition_rows, batch_size):
            session.bulk_save_objects(batch)
            session.commit()


def _measure(label: str, func_to_run: Callable) -> dict:
    tracemalloc.start()
    start = time.perf_counter()
    result = func_to_run()
    elapsed = time.perf_counter() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "label": label,
        "elapsed_ms": round(elapsed * 1000, 2),
        "queries_per_sec": round(1.0 / max(elapsed, 1e-9), 2),
        "peak_mb": round(peak / (1024 * 1024), 2),
        "result_count": len(result) if hasattr(result, "__len__") else result,
    }


def _measure_throughput(
    label: str, func_to_run: Callable, num_rows: int
) -> dict:
    """Measure write throughput in rows/sec."""
    start = time.perf_counter()
    func_to_run()
    elapsed = time.perf_counter() - start
    return {
        "label": label,
        "elapsed_ms": round(elapsed * 1000, 2),
        "rows_written": num_rows,
        "rows_per_sec": round(num_rows / max(elapsed, 1e-9), 2),
    }


# ── Per-size benchmark ──────────────────────────────────────────────


def benchmark_size(
    engine_url: str,
    size: int,
    attendance_per_student: int,
    recognition_per_student: int,
):
    engine = create_engine(engine_url)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        _seed_dataset(
            session, size, attendance_per_student, recognition_per_student
        )

        # ── Read benchmarks ──────────────────────────────────
        student_search = _measure(
            "student_search",
            lambda: session.query(Student)
            .filter(Student.name.ilike("Student 0001%"))
            .order_by(Student.name, Student.id)
            .limit(50)
            .all(),
        )
        attendance_page = _measure(
            "attendance_page",
            lambda: session.query(Attendance)
            .order_by(desc(Attendance.timestamp))
            .limit(50)
            .all(),
        )
        recognition_page = _measure(
            "recognition_page",
            lambda: session.query(RecognitionLog)
            .order_by(desc(RecognitionLog.timestamp))
            .limit(50)
            .all(),
        )
        pagination_count = _measure(
            "student_count",
            lambda: session.query(func.count(Student.id)).scalar() or 0,
        )

        # ── Write throughput benchmarks ──────────────────────
        # Measure attendance writes
        def write_attendance_batch():
            batch = [
                Attendance(
                    student_id=(i % max(size, 1)) + 1,
                    confidence=0.92,
                    method="FACE_RECOGNITION",
                    status="PRESENT",
                )
                for i in range(10000)
            ]
            session.bulk_save_objects(batch)
            session.commit()

        attendance_throughput = _measure_throughput(
            "attendance_write_throughput", write_attendance_batch, 10000
        )

        # Measure recognition writes
        def write_recognition_batch():
            batch = [
                RecognitionLog(
                    student_id=(i % max(size, 1)) + 1,
                    is_known=True,
                    confidence=0.85,
                    liveness_confidence=0.80,
                    is_spoof=False,
                )
                for i in range(10000)
            ]
            session.bulk_save_objects(batch)
            session.commit()

        recognition_throughput = _measure_throughput(
            "recognition_write_throughput",
            write_recognition_batch,
            10000,
        )

    return {
        "size": size,
        "attendance_per_student": attendance_per_student,
        "recognition_per_student": recognition_per_student,
        "benchmarks": [
            student_search,
            attendance_page,
            recognition_page,
            pagination_count,
            attendance_throughput,
            recognition_throughput,
        ],
    }


def _assess_targets(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Check acceptance targets for the largest size."""
    assessments = []
    for r in results:
        size = r["size"]
        size_assess: Dict[str, Any] = {
            "size": size,
            "checks": [],
            "overall": "PASS",
        }
        for b in r["benchmarks"]:
            label = b["label"]
            if label in ACCEPTANCE_TARGETS:
                targets = ACCEPTANCE_TARGETS[label]
                for key, threshold in targets.items():
                    if key in b:
                        actual = b[key]
                        passed = actual <= threshold if "max" in key else actual >= threshold
                        size_assess["checks"].append({
                            "check": f"{label} {key} {'≤' if 'max' in key else '≥'} {threshold}",
                            "measured": actual,
                            "passed": passed,
                        })
                        if not passed:
                            size_assess["overall"] = "FAIL"
        assessments.append(size_assess)
    return assessments


# ── Main ────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Database scalability benchmark with throughput measurements."
    )
    parser.add_argument(
        "--database-url",
        default="sqlite:///"
        + str(Path(tempfile.gettempdir()) / "faceai_benchmark.db"),
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=[1000, 10000, 100000, 500000],
    )
    parser.add_argument("--attendance-per-student", type=int, default=2)
    parser.add_argument("--recognition-per-student", type=int, default=2)
    parser.add_argument(
        "--output",
        default=str(Path("outputs") / "scalability_benchmark.json"),
    )
    args = parser.parse_args()

    sep = "=" * 72
    print(sep)
    print("Database Scalability & Throughput Benchmark")
    print(f"Sizes: {args.sizes}")
    print(f"Attendance/student: {args.attendance_per_student}")
    print(f"Recognition/student: {args.recognition_per_student}")
    print(sep)

    results = [
        benchmark_size(
            args.database_url,
            size,
            args.attendance_per_student,
            args.recognition_per_student,
        )
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
        print(
            f"  SIZE: {s:,}  |  Acceptance: {r['acceptance']['overall']}"
        )
        print(sep2)
        for b in r["benchmarks"]:
            label = b["label"]
            ms = b["elapsed_ms"]
            qps = b.get("queries_per_sec", 0)
            rows_sec = b.get("rows_per_sec", 0)
            peak = b.get("peak_mb", 0)
            count = b.get("result_count", "")

            if rows_sec > 0:
                print(
                    f"  {label:40s}  {ms:>8.2f} ms  |  {rows_sec:>10.2f} rows/s"
                )
            else:
                print(
                    f"  {label:40s}  {ms:>8.2f} ms  |  {qps:>10.2f} QPS  |  peak={peak} MB  |  count={count}"
                )

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
