"""
Attendance — Live Camera + Auto-Marking Attendance
====================================================

This page combines live recognition with the attendance table.
Pipeline: Camera → YOLO11 → RetinaFace → ArcFace → FAISS → SQLite Attendance

Supports **two camera modes**:
- 💻 **Browser Webcam** — via ``streamlit_webrtc`` (works in browser)
- 📱 **Phone / IP Camera** — server-side capture via CameraSource abstraction

Phone camera sources:
- Android (USB via DroidCam / Wi-Fi via IP Webcam)
- iPhone (USB via EpocCam / Wi-Fi via EpocCam)
- Any IP / RTSP camera
- USB Auto (Plug & Play)
"""

from __future__ import annotations

import logging
import time
import threading
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import pandas as pd
import cv2
import numpy as np

# streamlit_webrtc is an OPTIONAL dependency. It is imported below inside a
# try/except so the page still loads (and shows a helpful message) when the
# package is not installed.

from services.attendance_service import AttendanceService
from services.employee_service import EmployeeService
from database.database import get_session
from database.repository import AttendanceRepo, EmployeeRepo
from app.live_detection import LiveDetection
from app.face_detector import FaceDetector
from app.recognizer import FaceRecognizer
from app.enrollment import FaceEnrollment
from camera.base import CameraSource
from camera.selector import create_camera, CAMERA_CHOICES

import config.config as cfg

logger = logging.getLogger(__name__)

# streamlit_webrtc is an OPTIONAL dependency — the page must still load
# (and show a helpful message) when it is not installed.
try:
    from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, RTCConfiguration
    _WEBRTC_AVAILABLE = True
except ImportError:  # pragma: no cover
    webrtc_streamer = None  # type: ignore[assignment]
    VideoTransformerBase = object
    RTCConfiguration = None  # type: ignore[assignment]
    _WEBRTC_AVAILABLE = False


# ── Video Transformer for Real-time Recognition ─────────────────
class AttendanceVideoTransformer(VideoTransformerBase):
    """Streamlit-webrtc video transformer for live attendance."""
    
    def __init__(self):
        self.pipeline = LiveDetection()
    
    def transform(self, frame):
        """Process frame through recognition pipeline."""
        img = frame.to_ndarray(format="bgr24")
        annotated = self.pipeline.process_frame(img)
        return annotated


# ── Phone Camera Feed (server-side capture, same pattern as Live page) ──
class PhoneAttendanceFeed:
    """Server-side phone camera feed with background thread for attendance."""

    def __init__(self, source_type: str, url: str = "", device_id: int = 0):
        self.source_type = source_type
        self.url = url
        self.device_id = device_id
        self._cam: Optional[CameraSource] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._pipeline = LiveDetection()

    def connect(self) -> bool:
        """Open the camera connection."""
        kwargs: Dict = {}
        if self.source_type in ("android_wifi", "iphone_wifi", "ip_camera"):
            kwargs["url"] = self.url or "http://192.168.1.100:8080/video"
        elif self.source_type in ("webcam", "android_usb", "iphone_usb"):
            kwargs["device_id"] = self.device_id
        elif self.source_type == "usb_auto":
            kwargs["device_id"] = self.device_id

        self._cam = create_camera(self.source_type, **kwargs)
        if self._cam is None:
            return False
        if not self._cam.open():
            return False
        self._cam.set_resolution(640, 480)
        return True

    def start(self) -> None:
        """Start the background capture thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="AttPhoneCam",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        if self._cam is not None:
            self._cam.release()
            self._cam = None

    def _capture_loop(self) -> None:
        """Continuously capture and process frames in background."""
        while self._running:
            if self._cam is None:
                break
            ret, frame = self._cam.read()
            if ret and frame is not None:
                annotated = self._pipeline.process_frame(frame)
                with self._lock:
                    self._latest_frame = annotated
            time.sleep(0.03)  # ~30 FPS

    def latest(self) -> Optional[np.ndarray]:
        """Get the latest annotated frame (non-blocking)."""
        with self._lock:
            return self._latest_frame

    @property
    def is_connected(self) -> bool:
        return self._cam is not None and self._cam.is_opened()

    @property
    def pipeline(self) -> LiveDetection:
        return self._pipeline


# ── Page Config ─────────────────────────────────────────────────
st.set_page_config(page_title="Attendance", page_icon="📋", layout="wide")

# ── Session State Initialization ────────────────────────────────
if "selected_date" not in st.session_state:
    st.session_state["selected_date"] = date.today()
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = True
if "att_cam_mode" not in st.session_state:
    st.session_state["att_cam_mode"] = "webcam"  # "webcam" or "phone"


# ── Helper Functions ────────────────────────────────────────────
@st.cache_data(ttl=5)
def get_attendance_data(target_date: date, limit: int = 200, skip: int = 0):
    """Get attendance records for a specific date."""
    try:
        with get_session() as session:
            records = AttendanceRepo.get_by_date(session, target_date, limit=limit, skip=skip)
            data = []
            for r in records:
                emp = r.employee
                data.append({
                    "ID": emp.employee_id if emp else f"ID:{r.employee_id}",
                    "Name": emp.name if emp else "Unknown",
                    "Department": emp.department if emp and emp.department else "—",
                    "Time": r.timestamp.strftime("%I:%M:%S %p"),
                    "Confidence": f"{r.confidence:.1%}",
                })
            return data
    except Exception as _exc:
        logger.warning("Could not load attendance records: %s", _exc)
        return []


@st.cache_data(ttl=5)
def get_today_stats():
    """Get today's attendance statistics."""
    try:
        return AttendanceService.get_statistics()
    except Exception as _exc:
        logger.warning("Could not load attendance stats: %s", _exc)
        return {}


def format_date(d: date) -> str:
    return d.strftime("%d %b %Y")


# ── Page Header ─────────────────────────────────────────────────
st.title("📋 Attendance")
st.markdown("Live camera recognition with automatic attendance marking")

# ── Camera Mode Selector ──────────────────────────────────────
cam_mode = st.radio(
    "Camera mode",
    options=["💻 Browser Webcam", "📱 Phone / IP Camera"],
    index=0 if st.session_state.att_cam_mode == "webcam" else 1,
    horizontal=True,
    key="att_cam_mode_radio",
    help="Browser webcam uses your laptop camera. Phone/IP camera connects via network or USB.",
)
if cam_mode == "💻 Browser Webcam":
    st.session_state.att_cam_mode = "webcam"
elif cam_mode == "📱 Phone / IP Camera":
    st.session_state.att_cam_mode = "phone"

# ── Phone / IP Camera Configuration (shown when phone mode selected) ──
if st.session_state.att_cam_mode == "phone":
    with st.expander("📱 Camera Configuration", expanded=True):
        # Build camera source dropdown
        cam_opts = {}
        for slug, label, desc in CAMERA_CHOICES:
            cam_opts[label] = slug

        current_label = "📱 Android (Wi-Fi)"
        for lbl, slug in cam_opts.items():
            if slug == st.session_state.get("phone_src", "android_wifi"):
                current_label = lbl
                break

        sel_label = st.selectbox(
            "Camera Source",
            options=list(cam_opts.keys()),
            index=list(cam_opts.keys()).index(current_label),
            key="phone_src_sel",
        )
        phone_src = cam_opts[sel_label]
        st.session_state.phone_src = phone_src

        # Extra fields for URL / device ID
        phone_url = st.session_state.get("phone_url", "")
        phone_id = st.session_state.get("phone_id")  # None on first visit — triggers source-specific defaults

        if phone_src in ("android_wifi", "iphone_wifi", "ip_camera"):
            default_urls = {
                "android_wifi": "http://192.168.1.100:8080/video",
                "iphone_wifi": "http://192.168.1.101:8080/video",
                "ip_camera": "http://192.168.1.200:8080/video",
            }
            phone_url = st.text_input(
                "Camera URL",
                value=phone_url or default_urls.get(phone_src, ""),
                key="phone_url_input",
                help="Stream URL from the camera app",
            )
        elif phone_src in ("webcam", "android_usb", "iphone_usb"):
            default_ids = {"webcam": 0, "android_usb": 1, "iphone_usb": 2}
            current_id = phone_id if phone_id is not None else default_ids.get(phone_src, 0)
            phone_id = st.number_input(
                "Device Index",
                min_value=0, max_value=10,
                value=current_id,
                step=1,
                key="phone_id_input",
            )
        elif phone_src == "usb_auto":
            current_id = phone_id if phone_id is not None else -1
            phone_id = st.number_input(
                "Preferred Device Index (-1 = auto)",
                min_value=-1, max_value=10, value=current_id, step=1,
                key="phone_id_auto",
            )

        st.session_state.phone_url = phone_url
        st.session_state.phone_id = int(phone_id) if phone_id is not None else 0

        # Connect / Disconnect buttons
        conn_col1, conn_col2 = st.columns(2)
        with conn_col1:
            if st.button("🔌 Connect Camera", type="primary", use_container_width=True):
                # Stop any existing feed
                if "att_phone_feed" in st.session_state:
                    st.session_state.att_phone_feed.stop()
                    del st.session_state.att_phone_feed

                feed = PhoneAttendanceFeed(
                    source_type=phone_src,
                    url=phone_url,
                    device_id=int(phone_id),
                )
                with st.spinner("Connecting to phone camera..."):
                    if feed.connect():
                        feed.start()
                        st.session_state.att_phone_feed = feed
                        st.success("✅ Connected!")
                        st.rerun()
                    else:
                        st.error("❌ Could not connect to camera. Check URL/device.")
        with conn_col2:
            if st.button("⏹️ Disconnect", use_container_width=True):
                if "att_phone_feed" in st.session_state:
                    st.session_state.att_phone_feed.stop()
                    del st.session_state.att_phone_feed
                st.rerun()

# ── Top Row: Live Camera + Today's Attendance ───────────────────
col_camera, col_attendance = st.columns([2, 1], gap="large")

# ─── LEFT: Live Camera ──────────────────────────────────────────
with col_camera:
    st.markdown("### 📹 Live Camera")
    
    # Camera controls
    cam_col1, cam_col2, cam_col3 = st.columns([2, 1, 1])
    with cam_col1:
        camera_active_label = "📱 Phone Camera" if st.session_state.att_cam_mode == "phone" else "💻 Browser Webcam"
        camera_active = st.checkbox(f"Start {camera_active_label}", value=True, key="att_cam_active")
    with cam_col2:
        if st.button("🔄 Reset Session", use_container_width=True):
            st.cache_data.clear()
            if "att_phone_feed" in st.session_state:
                st.session_state.att_phone_feed.pipeline._marked_this_session.clear()
            st.rerun()
    with cam_col3:
        st.session_state["auto_refresh"] = st.checkbox(
            "Auto-refresh", value=st.session_state.get("auto_refresh", True)
        )
    
    if camera_active:
        if st.session_state.att_cam_mode == "phone":
            # ── Phone / IP Camera mode (server-side capture) ──
            feed = st.session_state.get("att_phone_feed")
            if feed is not None and feed.is_connected:
                frame = feed.latest()
                if frame is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    st.image(rgb, channels="RGB", use_container_width=True)
                    # Show pipeline stats
                    st.success(f"🟢 {feed.pipeline.enrollment.count()} enrolled | "
                               f"{len(feed.pipeline._marked_this_session)} marked today")
                else:
                    st.warning("🟡 Waiting for first frame...")
            else:
                st.info("📱 Configure and connect a phone/IP camera above, then enable the checkbox.")
        else:
            # ── Browser Webcam mode (WebRTC) ──
            if not _WEBRTC_AVAILABLE:
                st.error(
                    "⚠️ `streamlit-webrtc` is not installed — Browser Webcam mode is "
                    "unavailable. Install it with `pip install streamlit-webrtc`, or "
                    "use the Phone / IP Camera mode instead."
                )
            else:
                RTC_CONFIG = RTCConfiguration({
                    "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                })

                webrtc_ctx = webrtc_streamer(
                    key="attendance-camera",
                    video_transformer_factory=AttendanceVideoTransformer,
                    rtc_configuration=RTC_CONFIG,
                    media_stream_constraints={"video": True, "audio": False},
                    async_processing=True,
                )

                # Status indicator
                if webrtc_ctx.state.playing:
                    st.success("🟢 Camera Active — Recognition Running")
                else:
                    st.warning("🟡 Camera Starting...")
    else:
        st.info("Camera stopped. Check the checkbox to begin.")

# ─── RIGHT: Today's Attendance Summary ──────────────────────────
with col_attendance:
    st.markdown("### 📅 Today's Attendance")
    
    stats = get_today_stats()
    today_data = get_attendance_data(date.today())
    
    # Summary cards
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        st.metric("Total Marks", stats.get("today_count", 0))
    with mcol2:
        st.metric("Unique Present", stats.get("unique_today", 0))
    
    mcol3, mcol4 = st.columns(2)
    with mcol3:
        st.metric("All Time Records", stats.get("total_records", 0))
    with mcol4:
        st.metric("Employees Ever Marked", stats.get("unique_employees", 0))
    
    st.divider()
    
    # Today's attendance table
    if today_data:
        df_today = pd.DataFrame(today_data)
        st.dataframe(
            df_today,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.TextColumn("Emp ID", width="small"),
                "Name": st.column_config.TextColumn("Name", width="medium"),
                "Department": st.column_config.TextColumn("Dept", width="medium"),
                "Time": st.column_config.TextColumn("Time", width="small"),
                "Confidence": st.column_config.TextColumn("Conf", width="small"),
            },
        )
    else:
        st.info("No attendance records for today yet. Stand in front of the camera!")

# ─── Date Selector & Historical Records ─────────────────────────
st.divider()
st.markdown("### 📊 Historical Attendance Records")

# Date picker row
dcol1, dcol2, dcol3, dcol4 = st.columns([2, 2, 1, 1])
with dcol1:
    selected_date = st.date_input(
        "Select Date",
        value=st.session_state["selected_date"],
        max_value=date.today(),
    )
    if selected_date != st.session_state["selected_date"]:
        st.session_state["selected_date"] = selected_date
        st.rerun()

with dcol2:
    st.write(f"**Showing:** {format_date(selected_date)}")

with dcol3:
    if st.button("📥 Export CSV", use_container_width=True):
        hist_data = get_attendance_data(selected_date)
        if hist_data:
            df = pd.DataFrame(hist_data)
            csv = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv,
                file_name=f"attendance_{selected_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.warning("No data to export")

# ── Professional formats: PDF / Excel for the selected date ──
_export_pdf = st.button("📕 Export PDF", key="att_export_pdf")
_export_xlsx = st.button("📗 Export Excel", key="att_export_xlsx")
if _export_pdf or _export_xlsx:
    hist_rows = get_attendance_data(selected_date)
    if not hist_rows:
        st.warning("No data to export")
    else:
        try:
            from services.report_service import ReportService, ReportUnavailableError
            rows = [
                {
                    "ID": r.get("ID", ""),
                    "Name": r.get("Name", ""),
                    "Department": r.get("Department", ""),
                    "Time": r.get("Time", ""),
                    "Confidence": r.get("Confidence", ""),
                }
                for r in hist_rows
            ]
            title = f"Attendance Register — {format_date(selected_date)}"
            if _export_pdf:
                pdf = ReportService._pdf_table(
                    title, ["ID", "Name", "Department", "Time", "Confidence"], rows,
                    subtitle=f"{len(rows)} record(s) · Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                )
                st.download_button(
                    "Download PDF", pdf,
                    file_name=f"attendance_{selected_date.strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                )
            else:
                xlsx = ReportService._excel_table(
                    title, ["ID", "Name", "Department", "Time", "Confidence"],
                    rows, sheet_name="Attendance",
                )
                st.download_button(
                    "Download Excel", xlsx,
                    file_name=f"attendance_{selected_date.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        except ReportUnavailableError as _exc:
            st.error(f"⚠️ {_exc}")

with dcol4:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Historical data table
hist_data = get_attendance_data(selected_date)
if hist_data:
    df_hist = pd.DataFrame(hist_data)
    df_hist.insert(0, "Date", format_date(selected_date))
    
    st.dataframe(
        df_hist,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Date": st.column_config.TextColumn("Date", width="small"),
            "ID": st.column_config.TextColumn("Emp ID", width="small"),
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Department": st.column_config.TextColumn("Dept", width="medium"),
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Confidence": st.column_config.TextColumn("Conf", width="small"),
        },
    )
    
    # Summary stats for selected date
    unique_emps = df_hist["Name"].nunique()
    total_marks = len(df_hist)
    avg_conf = df_hist["Confidence"].apply(lambda x: float(x.rstrip('%')) / 100).mean()
    
    scol1, scol2, scol3 = st.columns(3)
    with scol1:
        st.metric("Total Marks", total_marks)
    with scol2:
        st.metric("Unique Employees", unique_emps)
    with scol3:
        st.metric("Avg Confidence", f"{avg_conf:.1%}")
else:
    st.info(f"No attendance records for {format_date(selected_date)}")

# ─── Pipeline Status & Debug ────────────────────────────────────
with st.expander("🔧 Pipeline Status & Debug"):
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        st.markdown("**Configuration**")
        st.code(f"""
YOLO Confidence: {cfg.YOLO_CONFIDENCE}
Recognition Threshold: {cfg.RECOGNITION_THRESHOLD}
Frame Skip: {cfg.FRAME_SKIP}
Cooldown: {cfg.COOLDOWN_SECONDS}s
Camera ID: {cfg.CAMERA_ID}
        """)
    
    with col_s2:
        st.markdown("**System Status**")
        with get_session() as session:
            total_emps = EmployeeRepo.count(session)
            pending_unknown = AttendanceRepo.get_statistics(session).get("today_count", 0)
        st.write(f"Total Employees: {total_emps}")
        st.write(f"Today's Attendance: {pending_unknown}")
        st.write("Pipeline: YOLO11 → RetinaFace → ArcFace → FAISS")
        st.write("Output: SQLite + CSV")

# ─── Auto-refresh ───────────────────────────────────────────────
if st.session_state.get("auto_refresh", True) and camera_active:
    # Rerun every 5 seconds to update attendance table
    time.sleep(5)
    st.rerun()
