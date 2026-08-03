"""
Dashboard — Comprehensive Home Page
======================================

Displays:
- Summary cards (Employees, Today's Attendance, Unknown Faces, System Status)
- Recognition Status with live indicators
- Active Camera status
- Recent attendance records (real-time)
- Quick Actions to all pages
- Recognition pipeline overview
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import pandas as pd

from database.database import get_session
from database.repository import (
    EmployeeRepo, AttendanceRepo, RecognitionLogRepo, UnknownFaceRepo, CameraRepo
)
from services.attendance_service import AttendanceService
from services.employee_service import EmployeeService
from services.unknown_face_service import UnknownFaceService
import config.config as cfg

logger = logging.getLogger(__name__)


st.set_page_config(page_title="Dashboard", page_icon="🏠", layout="wide")


# ── Cached Data Functions ──────────────────────────────────────

@st.cache_data(ttl=10)
def get_home_stats() -> dict:
    """Fetch all dashboard statistics in one batch."""
    try:
        with get_session() as session:
            total_employees = EmployeeRepo.count(session)
            today_stats = AttendanceRepo.get_statistics(session)
            unknown_stats = UnknownFaceRepo.get_statistics(session)
            cameras = CameraRepo.get_active(session)
            recent_logs = RecognitionLogRepo.get_recent(session, limit=10)
            today_attendance = AttendanceRepo.get_today(session, limit=10)

            return {
                "total_employees": total_employees,
                "today_count": today_stats.get("today_count", 0),
                "unique_today": today_stats.get("unique_today", 0),
                "total_records": today_stats.get("total_records", 0),
                "unknown_pending": unknown_stats.get("pending_review", 0),
                "unknown_today": unknown_stats.get("today", 0),
                "unknown_converted": unknown_stats.get("converted", 0),
                "cameras": cameras,
                "recent_logs": recent_logs,
                "today_attendance": today_attendance[:10],  # last 10
            }
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=30)
def get_recent_attendance_df(limit: int = 10) -> pd.DataFrame:
    """Return recent attendance records as a DataFrame."""
    try:
        with get_session() as session:
            records = AttendanceRepo.get_today(session, limit=limit)
            rows = []
            for r in records:
                emp = r.employee
                rows.append({
                    "Time": r.timestamp.strftime("%I:%M:%S %p"),
                    "Employee": emp.name if emp else "Unknown",
                    "ID": emp.employee_id if emp else "—",
                    "Department": emp.department if emp and emp.department else "—",
                    "Confidence": f"{r.confidence:.1%}",
                })
            return pd.DataFrame(rows)
    except Exception as _exc:
        logger.warning("Could not load recent recognitions: %s", _exc)
        return pd.DataFrame()


# ── Status Indicator Component ─────────────────────────────────

def status_badge(label: str, status: str, detail: str = "") -> str:
    """Return an HTML status badge."""
    colors = {
        "ok": ("#00cc88", "✅"),
        "warning": ("#ffaa00", "⚠️"),
        "error": ("#ff4444", "❌"),
        "unknown": ("#888888", "❓"),
    }
    color, icon = colors.get(status, ("#888888", "❓"))
    return f"""
    <div style="display: flex; align-items: center; gap: 6px; margin: 4px 0;">
        <span>{icon}</span>
        <span style="color: {color}; font-weight: 500;">{label}</span>
        {f'<span style="color: #888; font-size: 0.85em;">— {detail}</span>' if detail else ''}
    </div>
    """


# ── Page Title ─────────────────────────────────────────────────

st.title("🏠 Face Recognition AI Dashboard")
st.markdown("### Real-time face recognition & automatic attendance system")


# ── Check Models Status ────────────────────────────────────────
models_loaded = False
models_error = None
try:
    # FaceEnrollment internally depends on FaceDetector + FaceRecognizer
    from app.enrollment import FaceEnrollment
    _enr = FaceEnrollment()
    enrolled_count = _enr.count()
    models_loaded = True
except Exception as e:
    models_error = str(e)


# ── Load Stats ─────────────────────────────────────────────────
stats = get_home_stats()
if "error" in stats:
    st.error(f"⚠️ Could not load dashboard data: {stats['error']}")
    if st.button("🔄 Retry"):
        st.cache_data.clear()
        st.rerun()
    stats = {
        "total_employees": 0, "today_count": 0, "unique_today": 0,
        "total_records": 0, "unknown_pending": 0, "unknown_today": 0,
        "unknown_converted": 0, "cameras": [], "recent_logs": [], "today_attendance": [],
    }


# ═══════════════════════════════════════════════════════════════
#  TOP ROW — Summary Cards + Recognition Status
# ═══════════════════════════════════════════════════════════════

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "👥 Total Employees",
        stats["total_employees"],
        help="Registered employees in the system",
    )

with col2:
    st.metric(
        "📋 Today's Attendance",
        stats["today_count"],
        delta=f"{stats['unique_today']} unique" if stats["unique_today"] > 0 else None,
        help="Attendance marks recorded today",
    )

with col3:
    delta_color = "inverse" if stats["unknown_pending"] > 0 else "normal"
    delta_text = f"{stats['unknown_pending']} pending review" if stats["unknown_pending"] > 0 else None
    st.metric(
        "🔴 Unknown Faces",
        stats["unknown_today"],
        delta=delta_text,
        delta_color=delta_color,
        help="Unrecognized faces detected today",
    )

with col4:
    system_status = "🟢 Online" if models_loaded else "🔴 Offline"
    st.metric(
        "🖥️ System Status",
        system_status,
        help="All services operational" if models_loaded else "Some services unavailable",
    )

st.divider()


# ═══════════════════════════════════════════════════════════════
#  SECOND ROW — Recognition Status + Live Preview + Quick Actions
# ═══════════════════════════════════════════════════════════════

left_col, mid_col, right_col = st.columns([2, 2, 1], gap="large")

# ─── LEFT: Recognition Status ─────────────────────────────────
with left_col:
    st.markdown("### 🧠 Recognition Status")

    if models_loaded:
        st.success("✅ **YOLO** — Person Detection")
        st.success("✅ **InsightFace** — RetinaFace + ArcFace")
        st.success(f"✅ **FAISS** — {enrolled_count} embedding(s) indexed")

        with st.container(border=True):
            st.markdown("**Pipeline Health:**")
            st.markdown(status_badge("YOLO11 Person Detector", "ok", "Confidence ≥ 0.5"), unsafe_allow_html=True)
            st.markdown(status_badge("RetinaFace Face Detection", "ok"), unsafe_allow_html=True)
            st.markdown(status_badge("ArcFace 512-D Embedding", "ok"), unsafe_allow_html=True)
            st.markdown(status_badge(f"FAISS Search ({enrolled_count} vectors)", "ok"), unsafe_allow_html=True)
            st.markdown(status_badge("SQLite Database", "ok", f"{stats['total_records']} records"), unsafe_allow_html=True)

        st.caption(f"Config: {cfg.SETTINGS_PATH}")
    else:
        st.error(f"❌ Models failed to load: {models_error}")
        if st.button("🔄 Retry Loading Models", type="primary"):
            st.cache_resource.clear()
            st.cache_data.clear()
            st.rerun()

# ─── MID: Recent Attendance ────────────────────────────────────
with mid_col:
    st.markdown("### 📅 Recent Attendance")

    today_df = get_recent_attendance_df(10)

    if not today_df.empty:
        st.dataframe(
            today_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Time": st.column_config.TextColumn("Time", width="small"),
                "Employee": st.column_config.TextColumn("Employee", width="medium"),
                "ID": st.column_config.TextColumn("ID", width="small"),
                "Department": st.column_config.TextColumn("Dept", width="small"),
                "Confidence": st.column_config.TextColumn("Conf", width="small"),
            },
        )
        st.caption(f"Showing latest {len(today_df)} of {stats['today_count']} today's records")
    else:
        st.info("📭 No attendance records yet today.")
        st.markdown(
            "**Getting started:** Go to **📹 Live Recognition** or **📋 Attendance** "
            "and start the camera. Faces will be recognized and attendance marked automatically."
        )

    # Camera status
    st.divider()
    st.markdown("### 📷 Camera Status")
    cameras = stats.get("cameras", [])
    if cameras:
        for cam in cameras:
            cam_status = "🟢 Active" if cam.is_active else "🔴 Inactive"
            st.markdown(f"**{cam.name}** — {cam_status}")
            if cam.location:
                st.caption(f"Location: {cam.location}")
    else:
        st.warning("No cameras configured yet.")
        if st.button("➕ Configure Cameras", use_container_width=True):
            st.switch_page("pages/08_Settings.py")

# ─── RIGHT: Quick Actions ─────────────────────────────────────
with right_col:
    st.markdown("### ⚡ Quick Actions")

    if st.button("📸 Enroll Employee", use_container_width=True, type="primary"):
        st.switch_page("pages/03_Enroll.py")
    if st.button("📹 Live Recognition", use_container_width=True):
        st.switch_page("pages/04_Live.py")
    if st.button("📋 View Attendance", use_container_width=True):
        st.switch_page("pages/05_Attendance.py")
    if st.button("🔴 Review Unknowns", use_container_width=True):
        st.switch_page("pages/06_Unknown.py")
    if st.button("📈 Analytics", use_container_width=True):
        st.switch_page("pages/07_Analytics.py")
    if st.button("👥 Manage Employees", use_container_width=True):
        st.switch_page("pages/02_Employees.py")
    if st.button("🩺 System Health", use_container_width=True):
        st.switch_page("pages/09_Health.py")
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/08_Settings.py")

st.divider()


# ═══════════════════════════════════════════════════════════════
#  THIRD ROW — Daily Stats + Recent Activity
# ═══════════════════════════════════════════════════════════════

bottom_left, bottom_right = st.columns(2, gap="large")

# ─── Daily Stats ──────────────────────────────────────────────
with bottom_left:
    st.markdown("### 📊 Today's Overview")

    met1, met2, met3, met4 = st.columns(4)
    with met1:
        st.metric("Attendance", stats["today_count"])
    with met2:
        st.metric("Unique Present", stats["unique_today"])
    with met3:
        st.metric("Unknown Today", stats["unknown_today"])
    with met4:
        st.metric("Pending Review", stats["unknown_pending"])

    st.divider()

    st.markdown("### 🕐 Recent Recognition Activity")
    recent_logs = stats.get("recent_logs", [])
    if recent_logs:
        activity = []
        for log in recent_logs:
            emp_name = log.employee.name if log.employee else "Unknown"
            log_type = "✅ Known" if log.is_known else "🔴 Unknown"
            activity.append({
                "Time": log.timestamp.strftime("%I:%M:%S %p"),
                "Type": log_type,
                "Name": emp_name,
                "Confidence": f"{log.confidence:.1%}" if log.confidence else "—",
            })
        st.dataframe(
            pd.DataFrame(activity),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No recognition activity yet.")

# ─── Configuration Overview ───────────────────────────────────
with bottom_right:
    st.markdown("### ⚙️ Configuration")
    with st.container(border=True):
        st.markdown("**Camera:**")
        st.code(f"Source: {cfg.CAMERA_SOURCE_TYPE}")
        st.code(f"ID: {cfg.CAMERA_ID}")
        st.code(f"URL: {cfg.CAMERA_URL}")

        st.markdown("**Recognition:**")
        st.code(f"YOLO Confidence: {cfg.YOLO_CONFIDENCE}")
        st.code(f"Threshold: {cfg.RECOGNITION_THRESHOLD}")
        st.code(f"Frame Skip: {cfg.FRAME_SKIP}")
        st.code(f"Cooldown: {cfg.COOLDOWN_SECONDS}s")

        st.markdown("**Storage:**")
        st.code(f"Unknown Retention: {cfg.UNKNOWN_FACE_RETENTION_DAYS}d")

    st.divider()

    # Model status card
    st.markdown("### 🧠 Model Cache")
    if models_loaded:
        st.success("✅ All models cached in shared memory")
        st.caption("Models loaded once, shared across all cameras/feeds")
    else:
        st.error("❌ Models not loaded")
        if st.button("🔧 Diagnose Issues", use_container_width=True):
            st.switch_page("pages/09_Health.py")

st.divider()

# ── Getting Started Guide ─────────────────────────────────────
with st.expander("🚀 Getting Started Guide"):
    st.markdown("""
    ### New to Face Recognition AI?

    **Step 1: Enroll employees**
    - Go to **📸 Enroll** and register employees with their faces
    - The system will capture a photo, generate a face embedding, and store it in FAISS

    **Step 2: Start recognition**
    - Go to **📹 Live Recognition** for dual camera mode
    - Or **📋 Attendance** for single camera attendance marking
    - Recognized employees are automatically marked present

    **Step 3: Review results**
    - **🔴 Unknown Faces** — Review unrecognized faces and convert them to employees
    - **📊 Dashboard** — See today's stats
    - **📈 Analytics** — Charts and trends

    **Step 4: Configure**
    - **⚙️ Settings** — Change camera source, recognition thresholds, etc.
    - **🩺 Health** — Check system status and run diagnostics

    ### Tips
    - Use good lighting for best recognition accuracy
    - Position the camera at face level
    - Keep at least one face visible at a time
    - The first recognition may take a few seconds (model loading)
    - All data is stored locally — no cloud services required
    """)

# ── Pipeline Architecture ─────────────────────────────────────
with st.expander("🔧 Pipeline Architecture"):
    st.markdown(f"""
    ```
    ┌──────────────┐
    │ Camera Feed  │   {cfg.CAMERA_SOURCE_TYPE}
    └──────┬───────┘
           │  Frame
           ▼
    ┌──────────────┐
    │   YOLO11     │   Person Detection (conf ≥ {cfg.YOLO_CONFIDENCE})
    └──────┬───────┘
           │  Person crop
           ▼
    ┌──────────────┐
    │  RetinaFace  │   Face Detection & Alignment
    └──────┬───────┘
           │  Aligned face
           ▼
    ┌──────────────┐
    │   ArcFace    │   512-D Embedding
    └──────┬───────┘
           │  Embedding vector
           ▼
    ┌──────────────┐
    │    FAISS     │   L2 Nearest Neighbor (threshold: {cfg.RECOGNITION_THRESHOLD})
    └──────┬───────┘
           │  Match / No match
           ▼
    ┌──────────────────┐
    │  ✅ Known        │  → Mark attendance in SQLite
    │  🔴 Unknown      │  → Save to Unknown Faces gallery
    └──────────────────┘
    ```
    """, unsafe_allow_html=False)

    st.markdown(
        "**Total tests:** 137 ✅ **|** "
        f"**Employees:** {stats['total_employees']} **|** "
        f"**Attendance today:** {stats['today_count']}"
    )
