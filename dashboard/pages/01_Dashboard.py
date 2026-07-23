"""
Dashboard — Overview with Real Metrics & Quick Actions
=========================================================

Displays:
- Summary cards (Employees, Today's Attendance, Unknown Faces, System Status)
- Recent Activity (last 10 recognition events)
- Camera Status
- Quick Actions
"""

from __future__ import annotations

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


st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")


# ── Helper Functions ────────────────────────────────────────────
@st.cache_data(ttl=10)
def get_dashboard_stats():
    """Get all dashboard statistics in one query batch."""
    with get_session() as session:
        # Employee stats
        total_employees = EmployeeRepo.count(session)
        employees_with_faiss = session.query(EmployeeRepo.__table__.c.faiss_id).filter(
            EmployeeRepo.__table__.c.faiss_id.isnot(None)
        ).count() if hasattr(EmployeeRepo, '__table__') else 0
        
        # Attendance stats
        today_stats = AttendanceService.get_statistics()
        
        # Unknown face stats
        unknown_stats = UnknownFaceRepo.get_statistics(session)
        
        # Recent recognition logs
        recent_logs = RecognitionLogRepo.get_recent(session, limit=10)
        
        # Camera status
        cameras = CameraRepo.get_active(session)
    
    return {
        "total_employees": total_employees,
        "today_count": today_stats.get("today_count", 0),
        "unique_today": today_stats.get("unique_today", 0),
        "unknown_today": unknown_stats["today"],
        "unknown_pending": unknown_stats["pending_review"],
        "unknown_converted": unknown_stats["converted"],
        "recent_logs": recent_logs,
        "cameras": cameras,
    }


@st.cache_data(ttl=30)
def get_recent_activity(limit: int = 10):
    """Get recent recognition activity for the activity feed."""
    with get_session() as session:
        logs = RecognitionLogRepo.get_recent(session, limit=limit)
        activity = []
        for log in logs:
            emp_name = log.employee.name if log.employee else "Unknown"
            emp_id = log.employee.employee_id if log.employee else "—"
            activity.append({
                "time": log.timestamp.strftime("%I:%M:%S %p"),
                "type": "✅ Known" if log.is_known else "🔴 Unknown",
                "name": emp_name,
                "id": emp_id,
                "confidence": f"{log.confidence:.1%}" if log.confidence else "—",
            })
        return activity
    return []


# ── Page Header ────────────────────────────────────────────────
st.title("📊 Dashboard")
st.markdown("### System Overview & Real-time Status")

# ── Load Stats ─────────────────────────────────────────────────
stats = get_dashboard_stats()

# ── Summary Cards ──────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "👥 Total Employees",
        stats["total_employees"],
        help="Total registered employees in the system"
    )

with col2:
    st.metric(
        "📋 Today's Attendance",
        stats["today_count"],
        delta=f"{stats['unique_today']} unique",
        help="Total attendance marks today"
    )

with col3:
    st.metric(
        "🔴 Unknown Faces",
        stats["unknown_today"],
        delta=f"{stats['unknown_pending']} pending review",
        delta_color="inverse",
        help="Unknown faces detected today"
    )

with col4:
    st.metric(
        "🟢 System Status",
        "Online",
        help="All services operational"
    )

st.markdown("---")

# ── Main Content: Two Column Layout ────────────────────────────
left_col, right_col = st.columns([2, 1], gap="large")

# ─── LEFT: Recent Activity ────────────────────────────────────
with left_col:
    st.markdown("### 🕐 Recent Recognition Activity")
    
    activity = get_recent_activity(15)
    
    if activity:
        df_activity = pd.DataFrame(activity)
        st.dataframe(
            df_activity,
            use_container_width=True,
            hide_index=True,
            column_config={
                "time": st.column_config.TextColumn("Time", width="small"),
                "type": st.column_config.TextColumn("Type", width="small"),
                "name": st.column_config.TextColumn("Name", width="medium"),
                "id": st.column_config.TextColumn("Emp ID", width="small"),
                "confidence": st.column_config.TextColumn("Confidence", width="small"),
            },
        )
    else:
        st.info("No recognition activity yet. Start the camera on the Live or Attendance page.")

# ─── RIGHT: Camera Status & Quick Actions ─────────────────────
with right_col:
    st.markdown("### 📷 Camera Status")
    
    cameras = stats["cameras"]
    if cameras:
        for cam in cameras:
            status = "🟢 Active" if cam.is_active else "🔴 Inactive"
            st.markdown(f"""
            **{cam.name}** ({status})  
            Index: {cam.camera_index} | Location: {cam.location or 'Not set'}
            """)
    else:
        st.warning("No cameras configured. Add cameras in Settings or database.")
    
    st.divider()
    
    st.markdown("### ⚡ Quick Actions")
    
    qcol1, qcol2 = st.columns(2)
    with qcol1:
        if st.button("📸 Enroll Employee", use_container_width=True):
            st.switch_page("pages/03_Enroll.py")
    with qcol2:
        if st.button("👥 Manage Employees", use_container_width=True):
            st.switch_page("pages/02_Employees.py")
    
    qcol3, qcol4 = st.columns(2)
    with qcol3:
        if st.button("🔴 Review Unknowns", use_container_width=True):
            st.switch_page("pages/06_Unknown.py")
    with qcol4:
        if st.button("📋 View Attendance", use_container_width=True):
            st.switch_page("pages/05_Attendance.py")
    
    qcol5, qcol6 = st.columns(2)
    with qcol5:
        if st.button("📹 Live Camera", use_container_width=True):
            st.switch_page("pages/04_Live.py")
    with qcol6:
        if st.button("📈 Analytics", use_container_width=True):
            st.switch_page("pages/07_Analytics.py")

# ── System Configuration ──────────────────────────────────────
with st.expander("⚙️ System Configuration"):
    config_col1, config_col2 = st.columns(2)
    
    with config_col1:
        st.markdown("**Recognition Settings**")
        st.code(f"""
YOLO Confidence: {cfg.YOLO_CONFIDENCE}
Recognition Threshold: {cfg.RECOGNITION_THRESHOLD} (L2)
Frame Skip: {cfg.FRAME_SKIP}
Cooldown: {cfg.COOLDOWN_SECONDS}s
        """)
    
    with config_col2:
        st.markdown("**Storage Paths**")
        st.code(f"""
Models: {cfg.MODELS_DIR}
Embeddings: {cfg.EMBEDDINGS_DIR}
Attendance: {cfg.ATTENDANCE_DIR}
Unknown Faces: {cfg.UNKNOWN_FACES_DIR}
Logs: {cfg.LOGS_DIR}
        """)

# ── Pipeline Flow Diagram ─────────────────────────────────────
with st.expander("🔄 Recognition Pipeline"):
    st.markdown("""
    ```
    ┌─────────────┐
    │   Webcam    │
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │  YOLO11     │  ← Person Detection (conf ≥ {})
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │ RetinaFace  │  ← Face Detection & Alignment
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │  ArcFace    │  ← 512-D Embedding
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │   FAISS     │  ← Nearest Neighbor Search
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │  SQLite     │  ← Attendance + Recognition Log
    └─────────────┘
    """.format(cfg.YOLO_CONFIDENCE))