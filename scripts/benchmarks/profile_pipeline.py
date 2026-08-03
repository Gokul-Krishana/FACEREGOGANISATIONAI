"""Pipeline Stage Profiler — instruments every AI stage for latency measurement."""

import sys
import time
import statistics
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2  # noqa: E402
import config.config as cfg  # noqa: E402
from camera.selector import create_camera  # noqa: E402
from services.recognition_service import RecognitionService  # noqa: E402

AI_PROCESS_SIZE = (320, 240)
SECONDS = 20


def pct(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] * (1 - (k - int(k))) + s[hi] * (k - int(k))


def fmt(name, vals):
    if not vals:
        return f"  {name:20s}: no data"
    return (
        f"  {name:20s}: avg={statistics.mean(vals):7.1f}ms  P50={pct(vals, 50):7.1f}ms  "
        f"P95={pct(vals, 95):7.1f}ms  P99={pct(vals, 99):7.1f}ms  max={max(vals):7.1f}ms  n={len(vals)}"
    )


def main():
    print("Loading AI models...")
    t0 = time.perf_counter()
    service = RecognitionService()
    model_load_time = (time.perf_counter() - t0) * 1000
    print(f"  Model load: {model_load_time:.0f}ms")
    print(f"  Enrolled: {service.enrollment.count()} faces")

    # GPU check
    try:
        import torch

        cuda = torch.cuda.is_available()
        print(f"  CUDA available: {cuda}")
        if cuda:
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
    except Exception:
        cuda = False
    try:
        import psutil

        print(f"  CPU: {psutil.cpu_percent(interval=0.5):.0f}%")
        print(f"  RAM: {psutil.virtual_memory().percent:.0f}%")
    except Exception:
        pass

    cam = create_camera("webcam", device_id=0)
    if not cam or not cam.open():
        print("ERROR: Cannot open camera")
        return
    cam.set_resolution(640, 480)
    try:
        cam.set(cv2.CAP_PROP_FPS, 15)
    except Exception:
        pass

    # Warmup
    print("\nWarmup (5 frames)...")
    for _ in range(5):
        ret, frame = cam.read()
        if ret and frame is not None:
            small = cv2.resize(frame, AI_PROCESS_SIZE)
            service.process_frame_detailed(small)

    # Monkey-patch to instrument sub-stages
    # We'll measure: capture, resize, full_AI, overlay
    times = {
        "capture": [],
        "resize": [],
        "full_ai": [],
        "yolo_detect": [],
        "face_detect": [],
        "embedding": [],
        "faiss_search": [],
        "amfr_decide": [],
        "attendance_check": [],
        "overlay": [],
    }

    # Wrap detector methods
    orig_detect = service.detector.detect
    _orig_crop = service.detector.crop_person
    orig_detect_face = service.recognizer.detect_face
    orig_embed = service.recognizer.extract_embedding
    orig_search = service.enrollment.search
    _orig_amfr = service.amfr._evaluate_person

    def timed_detect(frame, **kw):
        t = time.perf_counter()
        result = orig_detect(frame, **kw)
        times["yolo_detect"].append((time.perf_counter() - t) * 1000)
        return result

    def timed_detect_face(crop):
        t = time.perf_counter()
        result = orig_detect_face(crop)
        times["face_detect"].append((time.perf_counter() - t) * 1000)
        return result

    def timed_embed(crop):
        t = time.perf_counter()
        result = orig_embed(crop)
        times["embedding"].append((time.perf_counter() - t) * 1000)
        return result

    def timed_search(emb, **kw):
        t = time.perf_counter()
        result = orig_search(emb, **kw)
        times["faiss_search"].append((time.perf_counter() - t) * 1000)
        return result

    service.detector.detect = timed_detect
    service.recognizer.detect_face = timed_detect_face
    service.recognizer.extract_embedding = timed_embed
    service.enrollment.search = timed_search

    # Capture FPS tracking
    cap_fps_list = []
    cap_counter = 0
    cap_start = time.perf_counter()

    print(f"\nProfiling {SECONDS} seconds of live pipeline...\n")

    wall_start = time.perf_counter()
    frame_count = 0
    skip = getattr(cfg, "FRAME_SKIP", 2)

    while time.perf_counter() - wall_start < SECONDS:
        # Capture
        tc = time.perf_counter()
        ret, frame = cam.read()
        tc2 = time.perf_counter()
        if not ret or frame is None:
            time.sleep(0.01)
            continue
        times["capture"].append((tc2 - tc) * 1000)
        cap_counter += 1
        frame_count += 1

        # Resize
        tr = time.perf_counter()
        small = cv2.resize(frame, AI_PROCESS_SIZE, interpolation=cv2.INTER_LINEAR)
        times["resize"].append((time.perf_counter() - tr) * 1000)

        # Full AI pipeline (only on non-skipped frames)
        if frame_count % skip == 0:
            t_ai = time.perf_counter()
            annotated, results = service.process_frame_detailed(small)
            times["full_ai"].append((time.perf_counter() - t_ai) * 1000)

            # Overlay
            t_ov = time.perf_counter()
            service._draw_overlay(frame, results)
            times["overlay"].append((time.perf_counter() - t_ov) * 1000)
        else:
            # Skipped frame — still draw last results
            t_ov = time.perf_counter()
            service._draw_overlay(frame, service._last_recognised)
            times["overlay"].append((time.perf_counter() - t_ov) * 1000)

        # Capture FPS
        cap_elapsed = time.perf_counter() - cap_start
        if cap_elapsed >= 1.0:
            cap_fps_list.append(cap_counter / cap_elapsed)
            cap_counter = 0
            cap_start = time.perf_counter()

    cam.release()
    wall = time.perf_counter() - wall_start

    # Results
    print("=" * 72)
    print("  PIPELINE STAGE PROFILING RESULTS")
    print("=" * 72)
    print(
        f"  Duration: {wall:.1f}s | Frames captured: {frame_count} | AI frames: {len(times['full_ai'])} | Skip: {skip}"
    )
    print(f"  Capture FPS: {statistics.mean(cap_fps_list):.1f}" if cap_fps_list else "  Capture FPS: N/A")
    print()
    print("  Stage Latencies (ms):")
    print(fmt("Capture", times["capture"]))
    print(fmt("Resize", times["resize"]))
    print(fmt("YOLO Detect", times["yolo_detect"]))
    print(fmt("Face Detect", times["face_detect"]))
    print(fmt("ArcFace Embed", times["embedding"]))
    print(fmt("FAISS Search", times["faiss_search"]))
    print(fmt("Full AI Total", times["full_ai"]))
    print(fmt("Overlay Render", times["overlay"]))
    print()

    # AI FPS
    if times["full_ai"]:
        ai_fps = 1000.0 / statistics.mean(times["full_ai"])
        print(f"  AI Recognition FPS: {ai_fps:.1f}")
        print(f"  AI frames/sec (incl skip): {len(times['full_ai']) / wall:.1f}")
    print()

    # Bottleneck identification
    print("  BOTTLENECK ANALYSIS:")
    if times["full_ai"]:
        ai_avg = statistics.mean(times["full_ai"])
        cap_avg = statistics.mean(times["capture"]) if times["capture"] else 0
        total_per_frame = cap_avg + ai_avg / skip
        print(f"    Capture time:     {cap_avg:.1f}ms ({cap_avg / total_per_frame * 100:.0f}%)")
        print(f"    AI time (avg):    {ai_avg:.1f}ms")
        print(f"    AI time/frame:    {ai_avg / skip:.1f}ms (with frame_skip={skip})")
        print(f"    Total/frame:      {total_per_frame:.1f}ms → {1000 / total_per_frame:.1f} effective FPS")
        print()
        # Identify biggest sub-stage
        sub_stages = [
            ("YOLO", times["yolo_detect"]),
            ("Face Detect", times["face_detect"]),
            ("ArcFace", times["embedding"]),
            ("FAISS", times["faiss_search"]),
        ]
        if any(v for _, v in sub_stages):
            print("    Sub-stage breakdown (AI pipeline):")
            for name, vals in sub_stages:
                if vals:
                    avg = statistics.mean(vals)
                    print(f"      {name:15s}: {avg:7.1f}ms  ({avg / ai_avg * 100:4.1f}% of AI)")

    print()
    print("  SYSTEM RESOURCES:")
    try:
        import psutil

        print(f"    CPU: {psutil.cpu_percent():.0f}%")
        vmem = psutil.virtual_memory()
        print(f"    RAM: {vmem.percent:.0f}% ({vmem.used / 1e9:.1f}GB / {vmem.total / 1e9:.1f}GB)")
    except Exception:
        pass
    try:
        import torch

        if torch.cuda.is_available():
            print(f"    GPU: {torch.cuda.get_device_name(0)}")
            print(f"    VRAM: {torch.cuda.memory_allocated() / 1e9:.2f}GB allocated")
        else:
            print("    GPU: Not available (CPU-only mode)")
    except Exception:
        pass
    print("=" * 72)


if __name__ == "__main__":
    main()
