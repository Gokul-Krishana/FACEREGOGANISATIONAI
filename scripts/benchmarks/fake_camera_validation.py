"""
Fake-Camera Validation — Measure Camera → FrameBuffer → Display WITHOUT Hardware
================================================================================

Measures the raw pipeline (Camera Stabilization Priority 3) using the
synthetic ``FakeCameraSource`` so capture/display FPS, the dropped-frame
rate, and end-to-end latency can be validated on ANY machine — no webcam
required. This mirrors Phase A of ``scripts/benchmarks/camera_validation.py``
so results are directly comparable to the real-hardware run.

Metrics produced:
    - Capture FPS          rate the fake source generates frames
    - Display FPS          rate a Streamlit-style consumer (0.05s cadence)
                           reads the frame buffer
    - Dropped frames       frames overwritten before first display
    - E2E latency P50/P95  time from capture put() to first consumer read

Usage:
    python scripts/benchmarks/fake_camera_validation.py
    python scripts/benchmarks/fake_camera_validation.py --fps 30 --seconds 8
    python scripts/benchmarks/fake_camera_validation.py --fps 60 --cadence 0.03
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from camera.fake import FakeCameraSource
from dashboard.frame_buffer import frame_buffer

DISPLAY_CADENCE = 0.05  # matches 04_Live.py time.sleep(0.05) + st.rerun()


def _pct(values: List[float], p: float) -> float:
    """Linear-interpolated percentile of a list of values.

    Kept local (rather than importing from camera_validation.py) so this
    raw-pipeline script doesn't pull in the whole AI model stack.
    """
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def measure_raw_camera(fake: FakeCameraSource, seconds: float,
                       cadence: float) -> Dict:
    """Producer thread → frame_buffer → consumer loop (same shape as the
    real-camera Phase A harness)."""
    print("\n" + "=" * 70)
    print("  FAKE CAMERA -> FrameBuffer -> Display (no AI)")  # ASCII only (Windows cp1252 console)
    print("=" * 70)
    print(f"  Source        : {fake.info()['name']}")
    print(f"  Resolution    : {fake.get_resolution()}")
    print(f"  Target FPS    : {fake.info()['target_fps']}")

    frame_buffer.clear()
    stop = threading.Event()
    captures = 0
    put_times: Dict[int, float] = {}  # frame_id -> perf_counter at put
    errors: List[str] = []

    def producer():
        nonlocal captures
        try:
            while not stop.is_set():
                ret, frame = fake.read()
                if ret and frame is not None:
                    fid = frame_buffer.put(frame)
                    put_times[fid] = time.perf_counter()
                    captures += 1
        except Exception as e:  # pragma: no cover
            errors.append(str(e))

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    # Consumer — Streamlit-like rerun cadence
    consumed = 0
    unique_shown = set()
    e2e: List[float] = []
    wall_start = time.perf_counter()
    while time.perf_counter() - wall_start < seconds:
        fr, fid, _ = frame_buffer.get_with_meta()
        if fr is not None:
            consumed += 1
            # Measure time-to-first-display per unique frame (skip re-reads
            # of the same frame so latency isn't inflated when the consumer
            # re-reads the latest frame each tick).
            if fid not in unique_shown:
                unique_shown.add(fid)
                put = put_times.get(fid)
                if put is not None:
                    e2e.append((time.perf_counter() - put) * 1000)
        time.sleep(cadence)
    stop.set()
    t.join(timeout=3.0)
    wall = time.perf_counter() - wall_start

    cap_fps = captures / wall
    disp_fps = consumed / wall
    dropped = max(0, captures - len(unique_shown))
    e2e_p50 = _pct(e2e, 50)
    e2e_p95 = _pct(e2e, 95)

    print(f"  Capture FPS   : {cap_fps:.1f} (requested {fake.info()['target_fps']:.0f})")
    print(f"  Display FPS   : {disp_fps:.1f} (consumer read rate @ {cadence * 1000:.0f}ms)")
    print(f"  Frames read   : {captures}")
    print(f"  Frames shown  : {consumed} (unique {len(unique_shown)})")
    print(f"  Dropped frames: {dropped} (consumer slower than producer)")
    print(f"  E2E latency   : P50={e2e_p50:.1f}ms  P95={e2e_p95:.1f}ms  (n={len(e2e)})")
    if errors:
        print(f"  Errors        : {errors[:3]}")

    return {
        "capture_fps": round(cap_fps, 1),
        "display_fps": round(disp_fps, 1),
        "dropped": dropped,
        "e2e_p50_ms": round(e2e_p50, 1),
        "e2e_p95_ms": round(e2e_p95, 1),
        "frames_read": captures,
        "frames_shown": consumed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hardware-free Camera → FrameBuffer → display benchmark")
    parser.add_argument("--fps", type=float, default=30.0,
                        help="Target synthetic capture rate (default 30)")
    parser.add_argument("--seconds", type=float, default=8.0,
                        help="Measurement window in seconds (default 8)")
    parser.add_argument("--width", type=int, default=640,
                        help="Frame width (default 640)")
    parser.add_argument("--height", type=int, default=480,
                        help="Frame height (default 480)")
    parser.add_argument("--cadence", type=float, default=DISPLAY_CADENCE,
                        help="Consumer read cadence in seconds "
                             "(default 0.05, matches the Live page)")
    parser.add_argument("--pattern", choices=["gradient", "solid"],
                        default="gradient",
                        help="Synthetic test pattern (default gradient)")
    parser.add_argument("--jitter", type=float, default=0.0,
                        help="Random read delay in ms per frame to simulate "
                             "USB timing (default 0)")
    args = parser.parse_args()

    print("Fake-Camera Validation — Face Recognition AI")
    print(f"  Source FPS    : {args.fps}  |  Window: {args.seconds}s")
    print(f"  Resolution    : {args.width}x{args.height}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    cam = FakeCameraSource(
        width=args.width,
        height=args.height,
        fps=args.fps,
        pattern=args.pattern,
        jitter_ms=args.jitter,
    )
    cam.open()
    try:
        r = measure_raw_camera(cam, args.seconds, args.cadence)
    finally:
        cam.release()
        frame_buffer.clear()

    print("\n" + "=" * 70)
    print("  VALIDATION SUMMARY")
    print("=" * 70)
    print(f"  Capture FPS      : {r['capture_fps']} (requested {args.fps:.0f})")
    print(f"  Display FPS      : {r['display_fps']}")
    print(f"  Dropped frames   : {r['dropped']}")
    print(f"  E2E latency P50  : {r['e2e_p50_ms']} ms")
    print(f"  E2E latency P95  : {r['e2e_p95_ms']} ms")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
