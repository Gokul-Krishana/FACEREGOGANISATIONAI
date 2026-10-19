#!/usr/bin/env python
"""Concurrent camera-owner test: what happens when TWO consumers open index 0.

Hypothesis: multiple components (or a leftover session) opening the same
physical camera cause failed/blocked reads -> frozen-then-jumping video.

Each consumer runs an independent read loop with per-read latency tracking.
Run this standalone; do not run alongside the app.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2  # noqa: E402


def open_cam(index: int, backend_name: str):
    backends = {"DSHOW": cv2.CAP_DSHOW, "MSMF": cv2.CAP_MSMF, "DEFAULT": None}
    b = backends[backend_name]
    cap = cv2.VideoCapture(index, b) if b is not None else cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    return cap


def consumer(name: str, index: int, backend_name: str, duration: float, out: dict):
    cap = open_cam(index, backend_name)
    if cap is None:
        out[name] = {"opened": False}
        return
    reads: list[float] = []
    frames = failed = 0
    longest_gap = 0.0
    last_ok = None
    start = time.perf_counter()
    while time.perf_counter() - start < duration:
        t0 = time.perf_counter()
        ok, frame = cap.read()
        t1 = time.perf_counter()
        if ok and frame is not None:
            frames += 1
            reads.append((t1 - t0) * 1000.0)
            if last_ok is not None:
                longest_gap = max(longest_gap, t1 - last_ok)
            last_ok = t1
        else:
            failed += 1
    cap.release()
    s = sorted(reads[5:]) if len(reads) > 10 else reads
    pct = lambda p: s[min(len(s) - 1, int(p / 100 * (len(s) - 1)))] if s else 0.0  # noqa: E731
    out[name] = {
        "opened": True,
        "frames": frames,
        "failed": failed,
        "fps": round(frames / duration, 2),
        "p50_ms": round(pct(50), 1),
        "p95_ms": round(pct(95), 1),
        "max_ms": round(pct(100), 1),
        "over_100ms": sum(1 for v in s if v > 100),
        "longest_gap_ms": round(longest_gap * 1000, 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--backend", default="DSHOW", choices=["DSHOW", "MSMF", "DEFAULT"])
    args = ap.parse_args()

    print(f"Opening 2 concurrent consumers on camera #{args.index} ({args.backend}) "
          f"for {args.duration}s ...", flush=True)
    out: dict = {}
    t1 = threading.Thread(target=consumer, args=("consumer_A", args.index, args.backend, args.duration, out))
    t2 = threading.Thread(target=consumer, args=("consumer_B", args.index, args.backend, args.duration, out))
    t1.start()
    time.sleep(1.0)  # stagger: B opens while A is already reading
    t2.start()
    t1.join()
    t2.join()

    import json
    print(json.dumps(out, indent=2))
    a, b = out.get("consumer_A", {}), out.get("consumer_B", {})
    if not b.get("opened") or b.get("failed", 0) > max(5, b.get("frames", 0) * 0.1):
        print("\nRESULT: second consumer is BLOCKED or erroring while the first holds the camera")
        print("        -> concurrent opens of the same camera are a real freeze cause")
        return 1
    print("\nRESULT: both consumers read (Windows shares the device here), no failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
