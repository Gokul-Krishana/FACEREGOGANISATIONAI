#!/usr/bin/env python
"""Per-backend camera read-latency matrix (no AI, no FastAPI, no display).

Runs each Windows capture backend SEPARATELY, releasing the camera between
runs so two tests never compete for the same device. Records every cap.read()
duration with a monotonic clock and reports:

- successful / failed frames, average FPS
- read-duration p50/p95/max
- counts of reads exceeding 100 ms / 200 ms / 500 ms
- freeze events (consecutive failed reads) and longest frame gap

Usage::
    python tools/camera_backend_matrix.py --duration 20
    python tools/camera_backend_matrix.py --duration 20 --buffersize 1
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2  # noqa: E402


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
    return s[k]


def run_backend(name: str, backend, index: int, width: int, height: int,
                fps: int, duration: float, buffersize: int | None) -> dict:
    print(f"\n=== {name} ===", flush=True)
    try:
        cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
    except Exception as exc:  # pragma: no cover - driver dependent
        print(f"  open raised: {exc}")
        return {"backend": name, "opened": False, "error": str(exc)}
    if not cap.isOpened():
        cap.release()
        print("  FAILED to open")
        return {"backend": name, "opened": False, "error": "not opened"}

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if buffersize is not None:
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, buffersize)
        except Exception:
            pass

    actual = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "reported_fps": cap.get(cv2.CAP_PROP_FPS),
        "backend_name": cap.getBackendName() if hasattr(cap, "getBackendName") else "?",
    }
    print(f"  opened: {actual}", flush=True)

    reads: list[float] = []
    frames = failed = fail_streak = max_fail_streak = 0
    freeze_events = 0
    longest_gap = 0.0
    last_ok_t: float | None = None
    start = time.perf_counter()
    last_report = start
    warmup_done_at: float | None = None

    try:
        while time.perf_counter() - start < duration:
            t0 = time.perf_counter()
            ok, frame = cap.read()
            t1 = time.perf_counter()
            if not ok or frame is None:
                failed += 1
                fail_streak += 1
                max_fail_streak = max(max_fail_streak, fail_streak)
            else:
                if fail_streak >= 10:
                    freeze_events += 1
                if last_ok_t is not None:
                    longest_gap = max(longest_gap, t1 - last_ok_t)
                fail_streak = 0
                frames += 1
                last_ok_t = t1
                reads.append((t1 - t0) * 1000.0)
                if warmup_done_at is None and (t1 - start) > 2.0:
                    warmup_done_at = t1  # first 2 s discarded from stats
            if time.perf_counter() - last_report >= 5.0:
                last_report = time.perf_counter()
                print(f"  [{time.perf_counter() - start:4.1f}s] frames={frames} failed={failed}", flush=True)
    finally:
        cap.release()

    total = time.perf_counter() - start
    steady = reads[10:] if len(reads) > 20 else reads  # drop warm-up frames
    result = {
        "backend": name,
        "opened": True,
        "duration_s": round(total, 2),
        "actual": actual,
        "frames": frames,
        "failed_reads": failed,
        "max_failed_streak": max_fail_streak,
        "freeze_events": freeze_events,
        "longest_gap_ms": round(longest_gap * 1000.0, 1),
        "avg_fps": round(frames / total, 2) if total else 0.0,
        "read_ms": {
            "p50": round(_pct(steady, 50), 1),
            "p95": round(_pct(steady, 95), 1),
            "max": round(_pct(steady, 100), 1),
            "over_100ms": sum(1 for v in steady if v > 100),
            "over_200ms": sum(1 for v in steady if v > 200),
            "over_500ms": sum(1 for v in steady if v > 500),
            "samples": len(steady),
        },
    }
    print(f"  -> fps={result['avg_fps']} failed={failed} "
          f"p50={result['read_ms']['p50']}ms p95={result['read_ms']['p95']}ms "
          f"max={result['read_ms']['max']}ms >100ms={result['read_ms']['over_100ms']} "
          f">200ms={result['read_ms']['over_200ms']} >500ms={result['read_ms']['over_500ms']} "
          f"longest_gap={result['longest_gap_ms']}ms", flush=True)
    time.sleep(1.0)  # release the device before the next backend
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Camera backend read-latency matrix")
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--buffersize", type=int, default=None)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    backends: list[tuple[str, object]] = []
    if sys.platform == "win32":
        backends += [("DirectShow", cv2.CAP_DSHOW), ("MediaFoundation", cv2.CAP_MSMF)]
    backends.append(("Default", None))

    results = []
    for name, backend in backends:
        results.append(run_backend(name, backend, args.index, args.width, args.height,
                                   args.fps, args.duration, args.buffersize))

    print("\n===== SUMMARY =====")
    for r in results:
        if not r["opened"]:
            print(f"  {r['backend']:18s} OPEN FAILED: {r.get('error')}")
        else:
            m = r["read_ms"]
            print(f"  {r['backend']:18s} fps={r['avg_fps']:5.1f} failed={r['failed_reads']:4d} "
                  f"p50={m['p50']:6.1f} p95={m['p95']:6.1f} max={m['max']:7.1f} "
                  f">100ms={m['over_100ms']:4d} >200ms={m['over_200ms']:4d} >500ms={m['over_500ms']:4d} "
                  f"gap={r['longest_gap_ms']:6.0f}ms")

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote {args.out}")

    return 0 if any(r["opened"] and r["frames"] > 0 for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
