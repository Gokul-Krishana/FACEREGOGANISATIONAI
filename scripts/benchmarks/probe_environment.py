"""Probe the real-camera validation environment.

Checks:
  1. OpenCV availability
  2. Available PC/USB cameras (device indices + working frames)
  3. Enrolled faces in FAISS (embeddings count, unique persons)
  4. Database type and today's attendance count
  5. YOLO model presence
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2

print("=" * 60)
print("  Environment Probe — Real Camera Validation")
print("=" * 60)
print(f"  OpenCV      : {cv2.__version__}")
print()

# ── Cameras ──────────────────────────────────────────────────
print("[1] Cameras")
found = []
for idx in range(5):
    try:
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            ok, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            backend = cap.getBackendName()
            found.append({"idx": idx, "frame": ok, "res": (w, h), "fps": fps, "backend": backend})
            print(f"    Camera #{idx}: {'FRAME OK' if ok else 'opened, no frame'} "
                  f"{w}x{h} @ {fps:.0f}fps ({backend})")
            cap.release()
        else:
            print(f"    Camera #{idx}: not found")
    except Exception as e:
        print(f"    Camera #{idx}: error {e}")
if not found:
    print("    !! NO CAMERAS DETECTED")

# ── Enrollment ───────────────────────────────────────────────
print()
print("[2] FAISS Enrollment")
try:
    from app.enrollment import FaceEnrollment
    enr = FaceEnrollment()
    total = enr.count()
    print(f"    embeddings      : {total}")
    try:
        print(f"    unique persons  : {enr.unique_count()}")
    except Exception:
        pass
    try:
        persons = enr.all_persons()
        print(f"    persons         : {persons[:10]}{' ...' if len(persons) > 10 else ''}")
    except Exception as e:
        print(f"    persons         : n/a ({e})")
except Exception as e:
    print(f"    ERROR: {e}")

# ── Database ─────────────────────────────────────────────────
print()
print("[3] Database")
try:
    from database.database import DB_TYPE, DATABASE_URL
    print(f"    type            : {DB_TYPE}")
    from services.attendance_service import AttendanceService
    stats = AttendanceService.get_statistics()
    print(f"    today records   : {stats.get('today_count', 'n/a')}")
    print(f"    unique today    : {stats.get('unique_today', 'n/a')}")
    print(f"    total records   : {stats.get('total_records', 'n/a')}")
except Exception as e:
    print(f"    ERROR: {e}")

# ── Models ───────────────────────────────────────────────────
print()
print("[4] Models")
try:
    import config.config as cfg
    yolo = Path(cfg.YOLO_MODEL_PATH)
    if yolo.exists():
        print(f"    YOLO model      : EXISTS ({yolo.stat().st_size/1e6:.1f} MB)")
    else:
        print(f"    YOLO model      : MISSING ({cfg.YOLO_MODEL_PATH})")
except Exception as e:
    print(f"    ERROR: {e}")

print()
print("=" * 60)
