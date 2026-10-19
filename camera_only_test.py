#!/usr/bin/env python
"""
Camera-Only Freeze Diagnostic
==============================

Displays the raw camera feed **without loading any AI models** so that
freeze causes can be bisected:

- Smooth camera-only playback  → investigate the application pipeline
  (AI inference, database writes, Streamlit reruns, buffering).
- Freezing during camera-only playback → investigate the backend
  (driver, DirectShow, USB bandwidth, power management, other apps
  holding the camera).
- Camera cannot open → camera index, permissions, resource ownership.

What it measures (printed every ~2 s, not every frame):

- Capture FPS (EMA + overall average)
- Failed reads and their streaks
- Per-read latency (P50 / P95 / max)
- Frames delivered vs expected at the requested camera FPS

Usage::

    python camera_only_test.py                 # camera 0, 640x480, press Q to quit
    python camera_only_test.py --index 1       # different camera
    python camera_only_test.py --duration 30   # auto-exit after 30 s (headless runs)
    python camera_only_test.py --no-display    # capture + metrics only (no window)

Backend order on Windows: DirectShow → MSMF → default, matching
``camera/webcam.py``. Only ONE capture handle is ever open here - never
run this while the dashboard or any other app is using the same camera.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import cv2  # noqa: E402


def _open_capture(index: int, width: int, height: int, fps: int):
    """Open the camera with backend fallback; returns (capture, backend_name)."""
    backends = []
    if sys.platform == "win32":
        backends += [(cv2.CAP_DSHOW, "DirectShow"), (cv2.CAP_MSMF, "Media Foundation")]
    backends.append((None, "Default"))

    for backend, name in backends:
        try:
            cap = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
        except Exception:
            continue
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            # Keep the internal buffer tiny so we always show the newest
            # frame - a deep buffer is a classic source of "frozen but
            # eventually updates" video.
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass
            return cap, name
        cap.release()
    return None, None


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = min(len(sorted_vals) - 1, int(round(p / 100 * (len(sorted_vals) - 1))))
    return sorted_vals[k]


def main() -> int:
    parser = argparse.ArgumentParser(description="Camera-only freeze diagnostic (no AI models)")
    parser.add_argument("--index", type=int, default=0, help="Camera device index (default 0)")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30, help="Requested camera FPS")
    parser.add_argument("--duration", type=float, default=0, help="Auto-exit after N seconds (0 = until Q)")
    parser.add_argument("--no-display", action="store_true", help="Skip the video window")
    args = parser.parse_args()

    print(f"Opening camera #{args.index} at {args.width}x{args.height}@{args.fps}fps ...")
    cap, backend = _open_capture(args.index, args.width, args.height, args.fps)
    if cap is None:
        print("ERROR: could not open camera with any backend.")
        print("Check: device index, permissions (Windows Privacy settings),")
        print("and that no other application is holding the camera.")
        return 2

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Opened via {backend} - actual {actual_w}x{actual_h} @ {actual_fps:.1f} fps (requested)\n")

    window = "camera_only_test (press Q to quit)"
    if not args.no_display:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    frames = 0
    failed = 0
    failed_streak = 0
    max_failed_streak = 0
    read_latencies = []  # rolling window (ms)
    start = time.perf_counter()
    last_report = start
    ema_fps = 0.0
    last_frame_t = start
    freeze_events = 0
    longest_freeze = 0.0
    last_frame_ts = start

    try:
        while True:
            t0 = time.perf_counter()
            ok, frame = cap.read()
            t1 = time.perf_counter()

            if not ok or frame is None:
                failed += 1
                failed_streak += 1
                max_failed_streak = max(max_failed_streak, failed_streak)
            else:
                if failed_streak >= 10:
                    # Recovered from a >=10-frame read failure - that IS a freeze event
                    freeze_events += 1
                gap = t1 - last_frame_ts
                longest_freeze = max(longest_freeze, gap)
                failed_streak = 0
                frames += 1
                last_frame_ts = t1

                dt = t1 - last_frame_t
                last_frame_t = t1
                if dt > 0:
                    inst = 1.0 / dt
                    ema_fps = inst if ema_fps == 0 else 0.9 * ema_fps + 0.1 * inst

                read_latencies.append((t1 - t0) * 1000.0)
                if len(read_latencies) > 600:
                    read_latencies = read_latencies[-600:]

                if not args.no_display:
                    cv2.imshow(window, frame)

            now = time.perf_counter()
            if now - last_report >= 2.0:
                last_report = now
                srt = sorted(read_latencies)
                total = now - start
                print(
                    f"[{total:6.1f}s] fps={ema_fps:5.1f}  frames={frames}  failed={failed}  "
                    f"fail_streak={failed_streak} (max {max_failed_streak})  "
                    f"read_ms p50={_percentile(srt, 50):.1f} p95={_percentile(srt, 95):.1f} "
                    f"max={_percentile(srt, 100):.1f}  freeze_events={freeze_events} "
                    f"longest_gap={longest_freeze * 1000:.0f}ms"
                )

            if not args.no_display:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == ord("Q"):
                    print("\nUser pressed Q - exiting.")
                    break
            if args.duration and (now - start) >= args.duration:
                print(f"\nDuration {args.duration}s reached - exiting.")
                break
    except KeyboardInterrupt:
        print("\nInterrupted - exiting.")
    finally:
        cap.release()
        if not args.no_display:
            cv2.destroyAllWindows()

    total = time.perf_counter() - start
    avg_fps = frames / total if total > 0 else 0.0
    srt = sorted(read_latencies)
    print("\n-- Summary " + "-" * 45)
    print(f"  Duration:            {total:.1f} s")
    print(f"  Frames captured:     {frames}")
    print(f"  Failed reads:        {failed}")
    print(f"  Max failed streak:   {max_failed_streak}")
    print(f"  Freeze events (>=10 consecutive failed reads): {freeze_events}")
    print(f"  Longest frame gap:   {longest_freeze * 1000:.0f} ms")
    print(f"  Average FPS:         {avg_fps:.1f}")
    print(f"  EMA FPS (final):     {ema_fps:.1f}")
    if srt:
        print(
            f"  Read latency ms:     p50={_percentile(srt, 50):.1f}  p95={_percentile(srt, 95):.1f}  max={_percentile(srt, 100):.1f}"
        )
    print("\nInterpretation:")
    if frames == 0:
        print("  [FAIL] No frames captured - camera/driver/permission problem.")
        return 2
    if freeze_events > 0 or _percentile(srt, 95) > 500:
        print("  [FAIL] Freezing detected WITHOUT any AI loaded - investigate")
        print("    the camera backend/driver/USB path, not the app pipeline.")
        return 1
    print("  [ OK ] Smooth camera-only playback - if the app freezes, the cause")
    print("    is in the application pipeline (AI/database/UI), not the camera.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
