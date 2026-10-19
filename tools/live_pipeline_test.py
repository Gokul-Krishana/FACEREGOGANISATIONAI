#!/usr/bin/env python
"""
Live Pipeline Hardware Test (no UI)
===================================

Runs the same capture -> AI path the Live page uses, headlessly, to
measure real hardware behaviour without Streamlit:

    camera -> capture thread -> latest-frame buffer -> RecognitionService
    (YOLO11 -> RetinaFace -> ArcFace -> FAISS -> AMFR) at 320x240

Reports (updated every 2 s):
- Capture FPS and AI FPS (separately)
- Pipeline latency P50 / P95 / P99 (ms)
- Frame age at AI consumption (ms)
- Dropped/superseded frames, failed reads, worker errors

Usage::

    python tools/live_pipeline_test.py                # 30 s
    python tools/live_pipeline_test.py --duration 1800  # 30-minute soak
    python tools/live_pipeline_test.py --index 1

NOTE: a recognition that reaches ACCEPT will mark attendance through the
normal service path. Run with an empty/development database if you do not
want real attendance rows.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2  # noqa: E402

from camera.selector import create_camera  # noqa: E402

AI_PROCESS_SIZE = (320, 240)


class LatestFrameBuffer:
    """Thread-safe single-slot buffer (capacity 1, newest wins)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame = None
        self._ts: Optional[float] = None
        self._seq = 0
        self._superseded = 0

    def put(self, frame) -> None:
        with self._lock:
            if self._frame is not None:
                self._superseded += 1
            self._frame = frame
            self._ts = time.time()
            self._seq += 1

    def get(self):
        with self._lock:
            return self._frame, self._ts, self._seq

    @property
    def superseded(self) -> int:
        with self._lock:
            return self._superseded


def percentile(vals: List[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
    return s[k]


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless live-pipeline hardware benchmark")
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--interval", type=float, default=0.10, help="AI cadence in seconds")
    args = parser.parse_args()

    print("Loading recognition models (YOLO11, InsightFace, FAISS, AMFR)...")
    t0 = time.perf_counter()
    from services.recognition_service import RecognitionService  # heavy imports after arg parsing

    service = RecognitionService()
    service.frame_skip = 1  # worker decides cadence
    print(
        f"Models loaded in {time.perf_counter() - t0:.1f}s — enrolled embeddings: {service.enrollment.count()}"
    )

    cam = create_camera("webcam", device_id=args.index)
    if cam is None or not cam.open():
        print("[FAIL] could not open camera")
        return 2
    cam.set_resolution(640, 480)

    buf = LatestFrameBuffer()
    running = True
    failed_reads = [0]

    def capture_loop() -> None:
        while running:
            ok, frame = cam.read()
            if not ok or frame is None:
                failed_reads[0] += 1
                time.sleep(0.02)
                continue
            buf.put(frame)

    print(f"Running pipeline for {args.duration:.0f}s (AI cadence {args.interval * 1000:.0f}ms)...")
    capture_fps_ema = 0.0
    last_cap_t = time.perf_counter()
    latencies: List[float] = []
    ages: List[float] = []
    ai_fps_ema = 0.0
    last_ai_t = time.perf_counter()
    people_counts: List[int] = []
    errors = 0
    last_report = time.perf_counter()
    start = last_report
    last_seq = 0

    t = threading.Thread(target=capture_loop, name="capture", daemon=True)
    t.start()

    try:
        while True:
            now = time.perf_counter()
            if now - start >= args.duration:
                break
            if now - last_report >= 2.0:
                last_report = now
                print(
                    f"[{now - start:6.1f}s] cap_fps={capture_fps_ema:5.1f} ai_fps={ai_fps_ema:4.1f} "
                    f"lat_ms p50={percentile(latencies, 50):6.1f} p95={percentile(latencies, 95):6.1f} "
                    f"p99={percentile(latencies, 99):6.1f}  age_ms p95={percentile(ages, 95):6.1f} "
                    f"superseded={buf.superseded} failed_reads={failed_reads[0]} "
                    f"people={people_counts[-1] if people_counts else 0} errors={errors}"
                )

            frame, ts, seq = buf.get()
            if frame is None or seq == last_seq:
                time.sleep(0.01)
                continue
            last_seq = seq

            # capture fps from buffer arrival rate
            cap_dt = time.perf_counter() - last_cap_t
            last_cap_t = time.perf_counter()
            if cap_dt > 0:
                inst = 1.0 / cap_dt
                capture_fps_ema = inst if capture_fps_ema == 0 else 0.9 * capture_fps_ema + 0.1 * inst

            if ts is not None:
                ages.append((time.time() - ts) * 1000.0)

            if time.perf_counter() - last_ai_t < args.interval:
                time.sleep(0.01)
                continue
            last_ai_t = time.perf_counter()

            small = cv2.resize(frame, AI_PROCESS_SIZE, interpolation=cv2.INTER_LINEAR)
            ai_start = time.perf_counter()
            try:
                _, results = service.process_frame_detailed(small)
            except Exception as exc:  # keep the run alive; count errors
                errors += 1
                print(f"  pipeline error: {exc}")
                time.sleep(0.5)
                continue
            lat = (time.perf_counter() - ai_start) * 1000.0
            latencies.append(lat)
            people_counts.append(len(results))
            ai_now = time.perf_counter()
            ai_dt = ai_now - last_ai_t
            if ai_dt > 0:
                inst = 1.0 / ai_dt
                ai_fps_ema = inst if ai_fps_ema == 0 else 0.9 * ai_fps_ema + 0.1 * inst
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        running = False
        t.join(timeout=2.0)
        try:
            cam.release()
        except Exception:
            pass

    total = time.perf_counter() - start
    print("\n-- Summary " + "-" * 50)
    print(f"  Duration:            {total:.1f} s")
    print(f"  Capture FPS (EMA):   {capture_fps_ema:.1f}")
    print(f"  AI FPS (EMA):        {ai_fps_ema:.1f}")
    print(f"  AI runs:             {len(latencies)}")
    if latencies:
        print(
            f"  Pipeline latency ms: p50={percentile(latencies, 50):.1f} "
            f"p95={percentile(latencies, 95):.1f} p99={percentile(latencies, 99):.1f} "
            f"max={percentile(latencies, 100):.1f}"
        )
    if ages:
        print(f"  Frame age ms:        p50={percentile(ages, 50):.1f} p95={percentile(ages, 95):.1f}")
    print(f"  Superseded frames:   {buf.superseded} (dropped by newest-wins buffer)")
    print(f"  Failed reads:        {failed_reads[0]}")
    print(f"  Worker errors:       {errors}")
    print(f"  Max people seen:     {max(people_counts) if people_counts else 0}")
    ok = len(latencies) > 0 and errors == 0 and capture_fps_ema > 5
    print(f"\n  Result: {'[ OK ]' if ok else '[WARN]'} pipeline ran headlessly on real hardware")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
