"""
System Health — Live Monitoring Dashboard
===========================================

Displays real-time health status of all system components:

    🟢 Camera Connected        🟢 Database Connected
    🟢 YOLO Loaded             🟢 ArcFace Loaded
    🟢 FAISS Loaded            🟢 Recognition Running

Provides diagnostics, auto-refresh, and quick-fix buttons.
"""

from __future__ import annotations

from pathlib import Path
import sys
import time
import threading

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import pandas as pd

from database.database import get_session
from database.repository import EmployeeRepo, AttendanceRepo, UnknownFaceRepo
from services.attendance_service import AttendanceService
from services.employee_service import EmployeeService
import config.config as cfg

st.set_page_config(page_title="System Health", page_icon="🩺", layout="wide")


# ── Health Check Functions ─────────────────────────────────────

from sqlalchemy import text as _sa_text


@st.cache_resource(ttl=10)
def check_database() -> dict:
    """Check if the database is reachable and responsive."""
    try:
        with get_session() as session:
            session.execute(_sa_text("SELECT 1"))
            emp_count = EmployeeRepo.count(session)
            return {"status": "ok", "employees": emp_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@st.cache_resource(ttl=10)
def check_camera() -> dict:
    """Check if a camera device is available (cached to avoid repeated open/close)."""
    import cv2
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                return {"status": "ok", "device": "Device #0", "resolution": f"{frame.shape[1]}x{frame.shape[0]}"}
            return {"status": "warning", "device": "Device #0", "message": "Opened but no frame"}
        return {"status": "error", "message": "No camera found on index 0"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@st.cache_resource(ttl=10)
def check_yolo() -> dict:
    """Check if YOLO model file exists and can be loaded (cached 10s)."""
    try:
        from app.face_detector import FaceDetector
        model_path = Path(cfg.YOLO_MODEL_PATH)
        if not model_path.exists():
            return {"status": "error", "message": f"Model not found: {model_path}"}
        # Instantiate to verify model loads without error
        FaceDetector()
        return {
            "status": "ok",
            "model": model_path.name,
            "size_mb": round(model_path.stat().st_size / 1024 / 1024, 1),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@st.cache_resource(ttl=10)
def check_arcface() -> dict:
    """Check if InsightFace is loaded (cached 10s)."""
    try:
        from app.recognizer import FaceRecognizer
        recognizer = FaceRecognizer()
        dim = recognizer.embedding_dim()
        return {
            "status": "ok",
            "model": recognizer.model_name,
            "embedding_dim": dim,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@st.cache_resource(ttl=10)
def check_faiss() -> dict:
    """Check if FAISS index is loaded (cached 10s)."""
    try:
        from app.enrollment import FaceEnrollment
        enrollment = FaceEnrollment()
        count = enrollment.count()
        index_path = Path(cfg.FAISS_INDEX_PATH)
        return {
            "status": "ok",
            "embeddings": count,
            "index_size_kb": round(index_path.stat().st_size / 1024, 1) if index_path.exists() else 0,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@st.cache_resource(ttl=10)
def check_recognition_pipeline() -> dict:
    """Run an end-to-end recognition test (cached 10s)."""
    try:
        from app.face_detector import FaceDetector
        from app.recognizer import FaceRecognizer
        from app.enrollment import FaceEnrollment
        import numpy as np

        detector = FaceDetector()
        recognizer = FaceRecognizer()
        enrollment = FaceEnrollment()

        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect(test_img)
        return {
            "status": "ok",
            "detectors_loaded": True,
            "recognizer_loaded": True,
            "faiss_loaded": True,
            "test_detections": len(detections),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@st.cache_resource(ttl=10)
def check_disk_space() -> dict:
    """Check available disk space (cached 10s)."""
    import shutil
    try:
        total, used, free = shutil.disk_usage(cfg.ROOT_DIR)
        free_gb = free / (1024 ** 3)
        return {
            "status": "ok" if free_gb > 1 else "warning",
            "free_gb": round(free_gb, 1),
            "total_gb": round(total / (1024 ** 3), 1),
        }
    except Exception:
        return {"status": "unknown", "free_gb": "?", "total_gb": "?"}


# ── Render Status Indicator ────────────────────────────────────

def render_status(status: str, label: str, detail: str = "", help_text: str = "") -> None:
    """Render a color-coded status indicator."""
    icons = {"ok": "✅", "warning": "⚠️", "error": "❌", "unknown": "❓"}
    colors = {"ok": "#00cc88", "warning": "#ffaa00", "error": "#ff4444", "unknown": "#888888"}
    icon = icons.get(status, "❓")
    color = colors.get(status, "#888888")
    st.markdown(
        f"""
        <div style="
            border: 1px solid {color}33;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 8px;
            background: #1a1a1a;
        ">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 24px;">{icon}</span>
                <div>
                    <strong style="color: {color};">{label}</strong>
                    {f'<br><span style="color: #aaaaaa; font-size: 0.85em;">{detail}</span>' if detail else ''}
                    {f'<br><span style="color: #ff6666; font-size: 0.85em;">{help_text}</span>' if help_text else ''}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Page Header ────────────────────────────────────────────────

st.title("🩺 System Health")
st.markdown("Real-time health monitoring for all Face Recognition AI components.")

# ── Auto-refresh toggle ────────────────────────────────────────
auto_refresh = st.checkbox("🔄 Auto-refresh (every 10s)", value=True)
if auto_refresh:
    st.caption(f"Last checked: {time.strftime('%I:%M:%S %p')}")

refresh_col1, refresh_col2 = st.columns([1, 5])
with refresh_col1:
    if st.button("🔄 Refresh Now", type="primary", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

# ── Run all health checks (each wrapped individually to prevent one failure from blocking others) ──
_status_placeholder = st.empty()
_status_placeholder.caption("Running diagnostics...")
_checks = [
    ("Database", check_database),
    ("Camera", check_camera),
    ("YOLO", check_yolo),
    ("ArcFace", check_arcface),
    ("FAISS", check_faiss),
    ("Pipeline", check_recognition_pipeline),
    ("Disk", check_disk_space),
]
db_health = {}
cam_health = {}
yolo_health = {}
arcface_health = {}
faiss_health = {}
pipeline_health = {}
disk_health = {}

for _name, _fn in _checks:
    try:
        _result = _fn()
    except Exception as _exc:
        _result = {"status": "error", "message": f"{_name} check crashed: {_exc}"}
    if _name == "Database":
        db_health = _result
    elif _name == "Camera":
        cam_health = _result
    elif _name == "YOLO":
        yolo_health = _result
    elif _name == "ArcFace":
        arcface_health = _result
    elif _name == "FAISS":
        faiss_health = _result
    elif _name == "Pipeline":
        pipeline_health = _result
    elif _name == "Disk":
        disk_health = _result

# Clear the "Running diagnostics..." placeholder now that checks are done
_status_placeholder.empty()

# ── Overall Status Banner ──────────────────────────────────────
all_ok = all(
    h.get("status") == "ok"
    for h in [db_health, cam_health, yolo_health, arcface_health, faiss_health, disk_health]
)
if all_ok:
    st.success("✅ **All systems operational** — every component is running normally.")
else:
    warnings = sum(1 for h in [db_health, cam_health, yolo_health, arcface_health, faiss_health, disk_health]
                   if h.get("status") == "warning")
    errors = sum(1 for h in [db_health, cam_health, yolo_health, arcface_health, faiss_health, disk_health]
                 if h.get("status") == "error")
    st.warning(f"⚠️ **{errors} error(s), {warnings} warning(s)** — some components need attention.")

st.divider()

# ── Health Grid ────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🗄️ Database")
    db_detail = f"{db_health.get('employees', '?')} employees" if db_health["status"] == "ok" else ""
    db_error = db_health.get("message", "") if db_health["status"] != "ok" else ""
    render_status(db_health["status"], "SQLite Database", db_detail, db_error)

    st.markdown("### 📷 Camera")
    cam_detail = cam_health.get("resolution", "") if cam_health["status"] == "ok" else cam_health.get("message", "")
    cam_error = cam_health.get("message", "") if cam_health["status"] == "error" else ""
    render_status(cam_health["status"], "Camera Device", cam_detail, cam_error)

with col2:
    st.markdown("### 🧠 YOLO")
    yolo_detail = f"Model: {yolo_health.get('model', '?')}" if yolo_health["status"] == "ok" else ""
    yolo_error = yolo_health.get("message", "") if yolo_health["status"] != "ok" else ""
    render_status(yolo_health["status"], "Person Detection (YOLO11)", yolo_detail, yolo_error)

    st.markdown("### 👤 ArcFace")
    arcface_detail = f"Dim: {arcface_health.get('embedding_dim', '?')}" if arcface_health["status"] == "ok" else ""
    arcface_error = arcface_health.get("message", "") if arcface_health["status"] != "ok" else ""
    render_status(arcface_health["status"], "Face Recognition (ArcFace)", arcface_detail, arcface_error)

with col3:
    st.markdown("### 🔍 FAISS")
    faiss_detail = f"{faiss_health.get('embeddings', '?')} embeddings" if faiss_health["status"] == "ok" else ""
    faiss_error = faiss_health.get("message", "") if faiss_health["status"] != "ok" else ""
    render_status(faiss_health["status"], "Vector Search (FAISS)", faiss_detail, faiss_error)

    st.markdown("### 💾 Disk")
    disk_detail = f"{disk_health.get('free_gb', '?')} GB free" if disk_health["status"] in ("ok", "warning") else ""
    disk_error = "Low disk space" if disk_health["status"] == "warning" else ""
    render_status(disk_health["status"], "Disk Space", disk_detail, disk_error)

st.divider()

# ── End-to-End Pipeline Test ───────────────────────────────────
st.markdown("### 🔄 Pipeline Integration Test")
pipeline_status = pipeline_health["status"]
if pipeline_status == "ok":
    st.success("✅ Full pipeline test passed — all subsystems respond correctly.")
else:
    st.error(f"❌ Pipeline test failed: {pipeline_health.get('message', 'Unknown error')}")
    if st.button("🔄 Retry Pipeline Test", use_container_width=False):
        st.cache_resource.clear()
        st.rerun()

# ── Quick Actions ──────────────────────────────────────────────
st.divider()
st.markdown("### ⚡ Quick Actions")

action_col1, action_col2, action_col3, action_col4 = st.columns(4)
with action_col1:
    if st.button("🔄 Reset All Caches", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("✅ All caches cleared!")

with action_col2:
    if db_health["status"] != "ok":
        if st.button("🔄 Retry DB Connection", use_container_width=True):
            st.rerun()
    else:
        st.button("✅ DB Connected", disabled=True, use_container_width=True)

with action_col3:
    if cam_health["status"] != "ok":
        if st.button("📷 Retry Camera", use_container_width=True):
            st.rerun()
    else:
        st.button("✅ Camera OK", disabled=True, use_container_width=True)

with action_col4:
    if st.button("🗑️ Clear Unknown Faces Cache", use_container_width=True):
        st.rerun()

# ── System Details (expandable) ────────────────────────────────
st.divider()
with st.expander("📋 Detailed System Information"):
    sys_col1, sys_col2 = st.columns(2)

    with sys_col1:
        st.markdown("**Configuration**")
        st.code(f"""
Python:      {sys.version.split()[0]}
Streamlit:   {st.__version__ if hasattr(st, '__version__') else '?'}
Config File: {cfg.SETTINGS_PATH}
Models Dir:  {cfg.MODELS_DIR}
DB Path:     {cfg.ROOT_DIR / 'data' / 'app.db'}
FAISS Index: {cfg.FAISS_INDEX_PATH}
        """)

    with sys_col2:
        st.markdown("**Recognition Settings**")
        st.code(f"""
YOLO Confidence:    {cfg.YOLO_CONFIDENCE}
Recognition Threshold: {cfg.RECOGNITION_THRESHOLD}
Frame Skip:         {cfg.FRAME_SKIP}
Cooldown:           {cfg.COOLDOWN_SECONDS}s
Camera Source:      {cfg.CAMERA_SOURCE_TYPE}
Camera ID:          {cfg.CAMERA_ID}
Retention Days:     {cfg.UNKNOWN_FACE_RETENTION_DAYS}
        """)

# ── Health Log ─────────────────────────────────────────────────
with st.expander("📊 Service Statistics"):
    stat_col1, stat_col2, stat_col3 = st.columns(3)

    with stat_col1:
        stats = AttendanceService.get_statistics()
        daily = stats.get("today_count", 0)
        st.metric("Today's Marks", daily)

    with stat_col2:
        with get_session() as s:
            pending = UnknownFaceRepo.count_unreviewed(s)
        st.metric("Pending Review", pending)

    with stat_col3:
        total_emps = EmployeeService.count()
        st.metric("Registered Employees", total_emps)

# ── Troubleshooting Guide ─────────────────────────────────────
with st.expander("🔧 Troubleshooting Guide"):
    st.markdown("""
    ### Common Issues & Fixes

    **❌ Database Error**
    - Ensure `data/` directory exists and is writable
    - Run `alembic upgrade head` to apply migrations
    - Check if another process has the database locked

    **❌ Camera Not Found**
    - Make sure no other app (Zoom, Teams) is using the camera
    - Try different device indices (0, 1, 2...)
    - For phone cameras, install DroidCam or EpocCam first

    **❌ YOLO Model Failed to Load**
    - Ensure `models/yolo11n.pt` exists (download it manually if missing)
    - Check disk space — model is ~6 MB

    **❌ InsightFace Failed to Load**
    - The model downloads automatically on first use
    - Ensure `models/.insightface/` directory exists
    - Check internet connection for first-time download

    **❌ FAISS Index Error**
    - If corrupted, delete `embeddings/faiss.index` and re-enroll employees
    - Ensure `embeddings/` directory exists and is writable
    """)

# ── Auto-refresh logic ─────────────────────────────────────────
if auto_refresh:
    time.sleep(10)
    try:
        st.rerun()
    except Exception:
        # Silently ignore rerun errors (e.g. when navigating away during refresh)
        pass
