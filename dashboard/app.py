"""
Face Recognition AI — Streamlit Dashboard
==========================================

Main entry point. Run with::

    streamlit run dashboard/app.py

Pages:
    - Dashboard (overview)
    - Employees (CRUD)
    - Enroll (webcam enrollment)
    - Live (live recognition feed)
    - Attendance (records)
    - Unknown Faces (gallery + management)
    - Analytics (charts)
    - Settings (configuration)
"""

from __future__ import annotations

from pathlib import Path
import sys

# ── Ensure project root is on path ────────────────────────────
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Face Recognition AI",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ──────────────────────────────────────────────────
st.sidebar.markdown(
    """
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="font-size: 1.8rem;">🟢</h1>
        <h3 style="margin: 0;">Face Recognition AI</h3>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.page_link("pages/01_Dashboard.py", label="📊  Dashboard", icon="📊")
st.sidebar.page_link("pages/02_Employees.py", label="👥  Employees", icon="👥")
st.sidebar.page_link("pages/03_Enroll.py", label="📸  Enroll", icon="📸")
st.sidebar.page_link("pages/04_Live.py", label="📹  Live Recognition", icon="📹")
st.sidebar.page_link("pages/05_Attendance.py", label="📋  Attendance", icon="📋")
st.sidebar.page_link("pages/06_Unknown.py", label="🔴  Unknown Faces", icon="🔴")
st.sidebar.page_link("pages/07_Analytics.py", label="📈  Analytics", icon="📈")
st.sidebar.page_link("pages/08_Settings.py", label="⚙️  Settings", icon="⚙️")

st.sidebar.divider()

# Run auto-cleanup on startup
from database.database import init_db
init_db()

from services.unknown_face_service import UnknownFaceService
import config.config as cfg

try:
    deleted = UnknownFaceService.auto_cleanup()
    if deleted:
        st.sidebar.info(f"Auto-cleaned {deleted} old unknown faces")
except Exception:
    pass

st.sidebar.caption(f"Recognition threshold: {cfg.RECOGNITION_THRESHOLD}")
st.sidebar.caption(f"Enrolled: ? — Unknown retention: {cfg.UNKNOWN_FACE_RETENTION_DAYS}d")

# ── Main content ─────────────────────────────────────────────
st.title("🟢 Face Recognition AI")
st.markdown("### Real-time face recognition & attendance system")

from database.database import get_session
from database.repository import EmployeeRepo, UnknownFaceRepo, AttendanceRepo
from services.attendance_service import AttendanceService

col1, col2, col3, col4 = st.columns(4)

with col1:
    with get_session() as s:
        emp_count = EmployeeRepo.count(s)
    st.metric("Total Employees", emp_count)

with col2:
    stats = AttendanceService.get_statistics()
    st.metric("Today's Attendance", stats.get("today_count", 0))

with col3:
    with get_session() as s:
        unknown_count = UnknownFaceRepo.count_unreviewed(s)
    st.metric("Unknown Faces", unknown_count)

with col4:
    st.metric("System Status", "🟢 Online")

st.markdown("---")
st.markdown(
    """
    ### Quick Actions
    - **Enroll** a new employee via the sidebar
    - **Review** unknown faces in the gallery
    - **Check** today's attendance records
    - **Configure** recognition settings
    """
)
