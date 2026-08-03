"""
Real-Camera Validation Harness
================================

Measures the complete camera pipeline on REAL hardware (Camera Stabilization
Priorities 3 & 5):

    Camera → FrameBuffer → (display consumer)
    Camera → YOLO11 → RetinaFace → Quality → Liveness → ArcFace → FAISS → AMFR
    → identity → attendance → PRESENT

Metrics produced:
    - Capture FPS          (rate of successful cam.read())
    - Display FPS          (rate the Streamlit-style consumer reads the buffer)
    - Recognition FPS      (rate of full AI pipeline processing)
    - AI pipeline latency  (ms per process_frame_detailed call)
    - End-to-end latency   (P50/P95 — time from capture to consumer read)
    - Dropped frames       (frames lost when consumer was slower than capture)

Measurement notes:
    - All timing uses ``time.perf_counter()`` (monotonic). The frame buffer's
      own ``time.time()`` timestamp is NOT used for latency math; instead the
      producer records ``frame_id -> perf_counter`` at put time and the
      consumer looks up latency by the frame_id returned by get_with_meta().
    - AI models are pre-warmed (RecognitionService constructed + a few warm-up
      frames) BEFORE the measurement window so lazy model loads don't skew
      the numbers.
    - E2E latency is measured at the display sampling cadence (0.05s, matching
      the Live page rerun loop), so it includes display-sampling delay.

Usage:
    python scripts/benchmarks/camera_validation.py
    python scripts/benchmarks/camera_validation.py --seconds 10 --device 0
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

import cv2  # noqa: E402

import config.config as cfg  # noqa: E402
from camera.selector import create_camera  # noqa: E402
from services.recognition_service import RecognitionService  # noqa: E402
from dashboard.frame_buffer import frame_buffer, results_buffer  # noqa: E402

AI_PROCESS_SIZE = (320, 240)
DISPLAY_CADENCE = 0.05  # matches 04_Live.py time.sleep(0.05) + st.rerun()


def pct(values: List[float], p: float) -> float:
    """Linear-interpolated percentile of a list of values."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def _open_cam(device_id: int):
    cam = create_camera("webcam", device_id=device_id)
    if cam is None or not cam.open():
        raise RuntimeError(f"Could not open webcam #{device_id}")
    cam.set_resolution(640, 480)
    # Cap FPS like the Live page to reduce USB bandwidth
    try:
        cam.set(cv2.CAP_PROP_FPS, 15)
    except Exception:
        pass
    return cam


def phase_raw_camera(device_id: int, seconds: float) -> Dict:
    """Phase A — raw Camera → FrameBuffer (no AI)."""
    print("\n" + "=" * 70)
    print("  PHASE A — Raw Camera → FrameBuffer (no AI)")
    print("=" * 70)
    cam = _open_cam(device_id)
    try:
        print(f"  Camera        : {cam.info()['resolution']}")
        frame_buffer.clear()

        stop = threading.Event()
        captures = 0
        put_times: Dict[int, float] = {}  # frame_id -> perf_counter at put
        errors: List[str] = []

        def producer():
            nonlocal captures
            try:
                while not stop.is_set():
                    ret, frame = cam.read()
                    if ret and frame is not None:
                        fid = frame_buffer.put(frame)
                        put_times[fid] = time.perf_counter()
                        captures += 1
            except Exception as e:
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
                # Measure time-to-first-display per unique frame. Skipping
                # re-reads of the same frame avoids inflating latency when
                # capture FPS < display cadence (the consumer re-reads the
                # latest frame each tick).
                if fid not in unique_shown:
                    unique_shown.add(fid)
                    put = put_times.get(fid)
                    if put is not None:
                        e2e.append((time.perf_counter() - put) * 1000)
            time.sleep(DISPLAY_CADENCE)
        stop.set()
        t.join(timeout=3.0)
        wall = time.perf_counter() - wall_start

        cap_fps = captures / wall
        disp_fps = consumed / wall
        dropped = max(0, captures - len(unique_shown))
        e2e_p50 = pct(e2e, 50)
        e2e_p95 = pct(e2e, 95)

        print(f"  Capture FPS   : {cap_fps:.1f}")
        print(f"  Display FPS   : {disp_fps:.1f} (consumer read rate)")
        print(f"  Frames read   : {captures}")
        print(f"  Frames shown  : {consumed} (unique {len(unique_shown)})")
        print(f"  Dropped frames: {dropped} (consumer slower than producer)")
        print(
            f"  E2E latency   : P50={e2e_p50:.1f}ms  P95={e2e_p95:.1f}ms  "
            f"(n={len(e2e)}, incl. display sampling)"
        )
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
    finally:
        cam.release()
        frame_buffer.clear()


def phase_ai_pipeline(device_id: int, seconds: float, no_write: bool = False) -> Dict:
    """Phase B — Camera → full AI pipeline. Measures recognition FPS and
    attempts live recognition + attendance.

    Args:
        no_write: When True, disable all database/disk side effects
            (unknown-face snapshots + recognition-log writes) so running
            the harness never pollutes the production database.
    """
    print("\n" + "=" * 70)
    print("  PHASE B — Camera → RecognitionPipeline → Attendance")
    print("=" * 70)

    # Load models BEFORE opening the camera so a model-load failure never
    # leaks the camera handle. Warm-up frames are processed outside the
    # measurement window to exclude lazy-load time.
    print("  Loading shared AI models (YOLO11, InsightFace, FAISS, AMFR)...")
    service = RecognitionService()
    if no_write:
        # Read-only mode: suppress every DB/disk write path in the pipeline
        # so a validation run has zero side effects on production data:
        # unknown-face snapshots, recognition logs, attendance, audit logs.
        service._handle_unknown_face = lambda *a, **k: None  # type: ignore[method-assign]
        service._log_recognition = lambda *a, **k: None  # type: ignore[method-assign]
        service._maybe_mark_attendance = lambda *a, **k: False  # type: ignore[method-assign]
        # AuditService.log is called at module level inside the pipeline,
        # so patch it on the imported module (this process only).
        import services.recognition_service as _rs

        _rs.AuditService.log = staticmethod(lambda *a, **k: None)
        print("  [--no-write] All DB/disk writes disabled (read-only validation)")
    print(f"  Enrolled      : {service.enrollment.count()} embedding(s)")

    cam = _open_cam(device_id)
    try:
        print(f"  Camera        : {cam.info()['resolution']}")
        frame_buffer.clear()
        results_buffer.clear()

        frame_skip = getattr(cfg, "FRAME_SKIP", 2)
        stop = threading.Event()
        ai_latencies: List[float] = []
        results_seen: List[Dict] = []
        errors: List[str] = []
        frame_count = 0
        ai_frames = 0

        def pipeline_loop():
            nonlocal frame_count, ai_frames
            try:
                while not stop.is_set():
                    ret, frame = cam.read()
                    if not ret or frame is None:
                        time.sleep(0.05)
                        continue
                    frame_count += 1
                    if frame_count % frame_skip != 0:
                        continue
                    t0 = time.perf_counter()
                    small = cv2.resize(frame, AI_PROCESS_SIZE, interpolation=cv2.INTER_LINEAR)
                    _, results = service.process_frame_detailed(small)
                    ai_latencies.append((time.perf_counter() - t0) * 1000)
                    ai_frames += 1
                    results_buffer.put(results)
                    if results:
                        results_seen.extend(results)
            except Exception as e:
                errors.append(str(e))

        # Pre-warm: run a few frames so model lazy-loads finish before timing
        for _ in range(4):
            ret, frame = cam.read()
            if ret and frame is not None:
                small = cv2.resize(frame, AI_PROCESS_SIZE, interpolation=cv2.INTER_LINEAR)
                try:
                    service.process_frame_detailed(small)
                except Exception:
                    pass

        t = threading.Thread(target=pipeline_loop, daemon=True)
        t.start()
        wall_start = time.perf_counter()
        time.sleep(seconds)
        stop.set()
        t.join(timeout=5.0)
        wall = time.perf_counter() - wall_start

        rec_fps = ai_frames / wall
        ai_p50 = pct(ai_latencies, 50)
        ai_p95 = pct(ai_latencies, 95)

        print(f"  Recognition FPS: {rec_fps:.1f} (AI frames/sec)")
        print(f"  AI latency     : P50={ai_p50:.1f}ms  P95={ai_p95:.1f}ms  (n={len(ai_latencies)})")
        print(f"  AI frames done : {ai_frames} / {frame_count} captured (skip={frame_skip})")

        decisions: Dict[str, int] = {}
        names = set()
        for r in results_seen:
            d = r.get("amfr_decision", "NONE")
            decisions[d] = decisions.get(d, 0) + 1
            nm = r.get("emp_name") or r.get("name", "")
            if nm:
                names.add(nm)
        print(f"  Decisions     : {decisions or 'no faces detected in window'}")
        print(f"  Names seen    : {sorted(names) or 'none'}")
        if errors:
            print(f"  Errors        : {errors[:3]}")

        return {
            "recognition_fps": round(rec_fps, 1),
            "ai_p50_ms": round(ai_p50, 1),
            "ai_p95_ms": round(ai_p95, 1),
            "decisions": decisions,
            "names_seen": sorted(names),
            "frames": frame_count,
            "ai_frames": ai_frames,
        }
    finally:
        cam.release()
        frame_buffer.clear()
        results_buffer.clear()


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-camera validation harness")
    parser.add_argument("--seconds", type=float, default=8.0, help="Seconds per phase (default 8)")
    parser.add_argument("--device", type=int, default=0, help="Camera device index (default 0)")
    parser.add_argument("--phase-a-only", action="store_true", help="Only run raw camera (no AI) phase")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Disable DB/disk writes during the AI phase (read-only validation, no production side effects)",
    )
    args = parser.parse_args()

    print("Real-Camera Validation — Face Recognition AI")
    print(f"  Camera device: #{args.device}  |  Phase duration: {args.seconds}s")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    a = phase_raw_camera(args.device, args.seconds)
    b: Dict = {}
    if not args.phase_a_only:
        b = phase_ai_pipeline(args.device, args.seconds, no_write=args.no_write)

    print("\n" + "=" * 70)
    print("  VALIDATION SUMMARY")
    print("=" * 70)
    print(f"  Capture FPS      : {a.get('capture_fps', 0)}")
    print(f"  Display FPS      : {a.get('display_fps', 0)}")
    print(f"  Dropped frames   : {a.get('dropped', 0)}")
    print(f"  E2E latency P50  : {a.get('e2e_p50_ms', 0)} ms")
    print(f"  E2E latency P95  : {a.get('e2e_p95_ms', 0)} ms")
    if b:
        print(f"  Recognition FPS  : {b.get('recognition_fps', 0)}")
        print(f"  AI latency P50   : {b.get('ai_p50_ms', 0)} ms")
        print(f"  AI latency P95   : {b.get('ai_p95_ms', 0)} ms")
        print(f"  Decisions        : {b.get('decisions', {})}")
        print(f"  Names seen       : {b.get('names_seen', [])}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
