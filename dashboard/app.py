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

import streamlit as st  # noqa: E402

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

# ── Main Navigation ─────────────────────────────────────────
st.sidebar.page_link("pages/01_Dashboard.py", label="🏠  Dashboard", icon="🏠")
st.sidebar.page_link("pages/02_Employees.py", label="👥  Employees", icon="👥")
st.sidebar.page_link("pages/03_Enroll.py", label="📸  Enroll", icon="📸")
st.sidebar.page_link("pages/04_Live.py", label="📹  Live Recognition", icon="📹")
st.sidebar.page_link("pages/05_Attendance.py", label="📋  Attendance", icon="📋")
st.sidebar.page_link("pages/06_Unknown.py", label="🔴  Unknown Faces", icon="🔴")
st.sidebar.page_link("pages/07_Analytics.py", label="📈  Analytics", icon="📈")
st.sidebar.page_link("pages/08_Settings.py", label="⚙️  Settings", icon="⚙️")
st.sidebar.page_link("pages/09_Health.py", label="🩺  System Health", icon="🩺")
st.sidebar.page_link("pages/10_About.py", label="ℹ️  About", icon="ℹ️")

st.sidebar.divider()

# ── Auto-initialization ─────────────────────────────────────
try:
    from database.database import init_db

    init_db()
except Exception as e:
    st.sidebar.error(f"DB init failed: {e}")

# ── Auto-cleanup → Silently handle errors ───────────────────
try:
    from services.unknown_face_service import UnknownFaceService

    deleted = UnknownFaceService.auto_cleanup()
    if deleted:
        st.sidebar.info(f"🧹 Auto-cleaned {deleted} old unknown faces")
except Exception:
    pass  # Cleanup is best-effort

# ── Sidebar Footer ──────────────────────────────────────────
st.sidebar.divider()
st.sidebar.caption("**Face Recognition AI v1.0**")

# Try to show enrolled count
try:
    from app.enrollment import FaceEnrollment

    _enr = FaceEnrollment()
    st.sidebar.caption(f"🧠 {_enr.count()} embeddings in FAISS")
except Exception:
    pass

import config.config as cfg  # noqa: E402

st.sidebar.caption(f"⚙️ Threshold: {cfg.RECOGNITION_THRESHOLD}")
st.sidebar.caption(f"📷 Source: {cfg.CAMERA_SOURCE_TYPE}")

# ── Redirect to the first page ─────────────────────────────
# The main content area is empty — the dashboard page handles everything
st.switch_page("pages/01_Dashboard.py")
