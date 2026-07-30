"""
Live Recognition — Simplified Operator UI
==========================================

Complete real-world flow:

    PC CAMERA → LIVE VIDEO → YOLO11 → TRACKING → RETINAFACE → FACE QUALITY
    → LIVENESS → ARCFACE 512-D → FAISS → AMFR → IDENTITY → ATTENDANCE
    → POSTGRESQL → STREAMLIT LIVE UPDATE

Normal operator experience:

    Open Live Recognition
    → Select PC Camera (default)
    → Click START
    → Student stands in front of camera
    → Student recognized
    → Attendance marked automatically
    → PRESENT displayed

Architecture:
    Camera → CameraSource → LiveRecognitionPipeline → RecognitionService → AMFR → Attendance

All heavy models (YOLO, InsightFace, FAISS, AMFR) loaded once via SharedModelResources.
Recognition runs in a background thread; the UI reads latest results non-blocking.

Supports:
    - PC Camera (built-in webcam) — DEFAULT
    - USB Camera (auto-detect)
    - Android Phone (Wi-Fi / USB)
    - iPhone (Wi-Fi / USB)
    - IP / RTSP Camera
"""

from __future__ import annotations

import sys
import time
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
import streamlit as st

# Performance: downscale large frames before AI pipeline for speed
# Display stays at original resolution; AI processes at this size
AI_PROCESS_SIZE = (320, 240)  # Downscale to this for YOLO/ArcFace inference

# ── Ensure project root is on path ──────────────────────────────
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg
from app.amfr_engine import AMFRDecision
from services.recognition_service import RecognitionService
from camera.base import CameraSource
from camera.selector import create_camera
from camera.discovery import scan_network
from services.attendance_service import AttendanceService

# ── Page Config ────────────────────────────────────────────────
st.set_page_config(page_title="Live Recognition", page_icon="📹", layout="wide")


# ═══════════════════════════════════════════════════════════════
#  Shared Model Resources — loaded once, shared across pipelines
# ═══════════════════════════════════════════════════════════════

@dataclass
class SharedModelResources:
    """Container for heavy deep-learning models loaded once and shared."""

    service: RecognitionService

    @staticmethod
    def load() -> SharedModelResources:
        """Load (or retrieve cached) recognition models once."""
        if not hasattr(SharedModelResources, "_cache"):
            print("[ModelCache] Loading shared AI models (YOLO, InsightFace, FAISS, AMFR)...")
            service = RecognitionService()
            SharedModelResources._cache = SharedModelResources(service=service)
            print(f"[ModelCache] Models loaded — {service.enrollment.count()} enrolled faces")
        return SharedModelResources._cache


# ═══════════════════════════════════════════════════════════════
#  Camera Pipeline — runs AMFR pipeline in background thread
# ═══════════════════════════════════════════════════════════════

class LiveRecognitionPipeline:
    """Manages a single camera + recognition pipeline in a background thread."""

    def __init__(self, source_type: str, **kwargs):
        self.source_type = source_type
        self.camera_kwargs = kwargs
        self._cam: Optional[CameraSource] = None
        self._resource = SharedModelResources.load()
        self._service = RecognitionService.with_shared_models(self._resource.service)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Latest results (thread-safe)
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_results: List[Dict] = []
        self._fps: float = 0.0
        self._ai_fps: float = 0.0
        self._pipeline_latency: float = 0.0
        self._status: str = "STOPPED"
        self._people_count: int = 0
        self._frame_count: int = 0
        self._error: Optional[str] = None
        self._reconnect_attempts: int = 0

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> bool:
        """Open camera and start background recognition thread."""
        try:
            self._cam = create_camera(self.source_type, **self.camera_kwargs)
            if self._cam is None:
                self._error = f"Could not create camera source: {self.source_type}"
                self._status = "ERROR"
                return False

            if not self._cam.open():
                self._error = "Could not open camera — check connection"
                self._status = "ERROR"
                self._cam = None
                return False

            self._cam.set_resolution(640, 480)
            # Cap camera FPS at 15 to reduce USB bandwidth
            try:
                self._cam.set(cv2.CAP_PROP_FPS, 15)
            except Exception:
                pass
        except Exception as e:
            self._error = f"Camera error: {e}"
            self._status = "ERROR"
            return False

        self._running = True
        self._status = "CONNECTING"
        self._reconnect_attempts = 0
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="LiveRecognition",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop recognition and release camera."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._cam:
            try:
                self._cam.release()
            except Exception:
                pass
            self._cam = None
        self._status = "STOPPED"
        self._reconnect_attempts = 0
        with self._lock:
            self._latest_frame = None
            self._latest_results = []

    # ── Background capture loop ──────────────────────────────

    def _capture_loop(self) -> None:
        """Continuously capture frames and run AMFR pipeline."""
        frame_skip = getattr(cfg, 'FRAME_SKIP', 2)
        frame_count = 0
        last_frame_time = time.time()
        last_process_time = 0.0
        fps_alpha = 0.9
        ai_frame_count = 0
        last_ai_time = time.time()
        max_reconnects = 5

        while self._running and self._cam is not None:
            try:
                ret, frame = self._cam.read()
                now = time.time()

                if not ret or frame is None:
                    # Camera temporarily unavailable
                    if self._status == "LIVE":
                        self._status = "DISCONNECTED"
                    time.sleep(0.05)
                    continue

                # Update FPS
                dt = now - last_frame_time
                if dt > 0:
                    instant_fps = 1.0 / dt
                    with self._lock:
                        self._fps = fps_alpha * self._fps + (1 - fps_alpha) * instant_fps
                last_frame_time = now

                frame_count += 1

                # Performance: run AI on downscaled frame (320x240) but display at full res (640x480)
                # This keeps YOLO/ArcFace fast while the video stays sharp.
                # _draw_overlays handles its own copy internally — no need to copy here.
                results = []  # initialize for edge case where first frame is a non-skip frame
                pipeline_start = time.time()
                if frame_count % frame_skip == 0:
                    small_frame = cv2.resize(frame, AI_PROCESS_SIZE, interpolation=cv2.INTER_LINEAR)
                    _, results = self._service.process_frame_detailed(small_frame)
                    pipeline_end = time.time()
                    
                    # Scale bbox coordinates back to original 640x480 frame size
                    scale_x = frame.shape[1] / AI_PROCESS_SIZE[0]
                    scale_y = frame.shape[0] / AI_PROCESS_SIZE[1]
                    for r in results:
                        bbox = r.get("bbox")
                        if bbox and len(bbox) >= 4:
                            r["bbox"] = (
                                int(bbox[0] * scale_x),
                                int(bbox[1] * scale_y),
                                int(bbox[2] * scale_x),
                                int(bbox[3] * scale_y),
                            )
                    
                    # Update AI FPS
                    ai_now = time.time()
                    ai_dt = ai_now - last_ai_time
                    if ai_dt > 0:
                        instant_ai_fps = 1.0 / ai_dt
                        with self._lock:
                            self._ai_fps = fps_alpha * self._ai_fps + (1 - fps_alpha) * instant_ai_fps
                    last_ai_time = ai_now
                    ai_frame_count += 1
                    pipeline_latency = (pipeline_end - pipeline_start) * 1000  # ms
                else:
                    pipeline_latency = 0.0

                # Draw overlays on original full-resolution frame (_draw_overlays copies internally)
                annotated = self._draw_overlays(frame, results)

                with self._lock:
                    self._latest_frame = annotated
                    self._latest_results = results

                with self._lock:
                    self._latest_frame = annotated
                    self._latest_results = results
                    self._people_count = len(results)
                    self._frame_count = frame_count
                    self._pipeline_latency = pipeline_latency
                    self._status = "LIVE"
                    self._reconnect_attempts = 0

            except Exception as e:
                with self._lock:
                    self._error = str(e)
                    self._status = "ERROR"
                time.sleep(0.5)

        # Camera disconnected — attempt reconnection
        while self._running and self._cam and self._reconnect_attempts < max_reconnects:
            self._status = "RECONNECTING"
            time.sleep(2.0)
            try:
                if not self._cam.is_opened():
                    self._cam.open()
                    self._cam.set_resolution(640, 480)
                    try:
                        self._cam.set(cv2.CAP_PROP_FPS, 15)
                    except Exception:
                        pass
                    if self._cam.is_opened():
                        self._status = "LIVE"
                        self._frame_count = 0
                        self._reconnect_attempts = 0
                        continue
                else:
                    self._status = "LIVE"
                    self._reconnect_attempts = 0
                    continue
            except Exception:
                self._reconnect_attempts += 1

        if self._reconnect_attempts >= max_reconnects:
            self._status = "DISCONNECTED"

    # ── Overlay drawing — clean, minimal labels ─────────────

    def _draw_overlays(self, frame: np.ndarray, results: List[Dict]) -> np.ndarray:
        """Draw minimal recognition overlays on the frame.

        ACCEPT       → Green box + "✓ NAME" + "ID: EMP001" + "PRESENT"
        ALREADY ACCEPT→ Green box + "✓ NAME" + "ID: EMP001" + "ALREADY PRESENT"
        SPOOF        → Red box   + "⚠ SPOOF" + "Rejected"
        BORDERLINE   → Yellow box + "NAME?" + "COLLECTING FRAMES..."
        UNKNOWN      → Grey box  + "? UNKNOWN" + "Not Enrolled"
        """
        if frame is None:
            return frame
        frame = frame.copy()  # Never mutate original

        for r in results:
            bbox = r.get("bbox")
            if bbox is None or len(bbox) < 4:
                continue

            x1, y1, x2, y2 = map(int, bbox[:4])
            decision = r.get("amfr_decision", "")
            name = r.get("name", "?")
            emp_name = r.get("emp_name", "")
            emp_id = r.get("emp_id")
            is_known = r.get("is_known", False)
            attended = r.get("attendance_marked", False)

            # Display name: prefer database name, fall back to FAISS name
            display_name = emp_name if emp_name and emp_name != "Unknown" else name

            # Determine visual treatment based on AMFR decision
            if decision == AMFRDecision.ACCEPT.value:
                color = (50, 200, 50)       # Green
                status_text = "ALREADY PRESENT" if attended else "PRESENT"
                label = f"\u2713 {display_name}"
                sublines = [status_text]
                if emp_id is not None:
                    sublines.insert(0, f"ID: {name}")

            elif decision == AMFRDecision.REJECT_SPOOF.value:
                color = (50, 50, 200)       # Red
                label = "\u26a0 SPOOF DETECTED"
                sublines = ["Attendance Rejected"]

            elif decision == AMFRDecision.BORDERLINE.value:
                color = (50, 180, 200)      # Yellow (BGR)
                label = f"{display_name}?"
                sublines = ["COLLECTING FRAMES..."]

            elif is_known:
                color = (50, 200, 50)       # Green
                if attended:
                    label = f"\u2713 {display_name}"
                    sublines = ["ALREADY PRESENT"]
                else:
                    label = f"\u25cf {display_name}"
                    sublines = ["KNOWN"]
                if emp_id is not None:
                    sublines.insert(0, f"ID: {name}")

            else:
                color = (150, 150, 150)     # Grey
                label = "\uff1f UNKNOWN"
                sublines = ["Not Enrolled"]

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Draw label background + text
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            label_bg_y1 = max(y1 - 32, 0)
            cv2.rectangle(frame, (x1, label_bg_y1), (x1 + tw + 10, y1), color, -1)
            cv2.putText(frame, label, (x1 + 5, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

            # Draw sublines below the box
            for i, sub in enumerate(sublines):
                sy = y2 + 20 + (i * 18)
                cv2.putText(frame, sub, (x1, sy),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        return frame

    # ── Thread-safe accessors ─────────────────────────────────

    def latest(self) -> Tuple[Optional[np.ndarray], List[Dict]]:
        """Get the latest frame and results (non-blocking)."""
        with self._lock:
            return self._latest_frame, list(self._latest_results)

    @property
    def fps(self) -> float:
        with self._lock:
            return self._fps

    @property
    def ai_fps(self) -> float:
        with self._lock:
            return self._ai_fps

    @property
    def pipeline_latency(self) -> float:
        with self._lock:
            return self._pipeline_latency

    @property
    def people_count(self) -> int:
        with self._lock:
            return self._people_count

    @property
    def status(self) -> str:
        return self._status

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def frame_count(self) -> int:
        with self._lock:
            return self._frame_count

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def resolution(self) -> str:
        if self._cam and self._cam.is_opened():
            try:
                w, h = self._cam.get_resolution()
                return f"{w}x{h}"
            except Exception:
                pass
        return "N/A"


# ═══════════════════════════════════════════════════════════════
#  Camera Discovery — probe local PC/USB cameras
# ═══════════════════════════════════════════════════════════════

def scan_local_cameras(max_devices: int = 5) -> List[Dict]:
    """Detect available local PC/USB cameras by probing indices 0-4."""
    available = []
    for idx in range(max_devices):
        try:
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                # Try reading a test frame
                ret, _ = cap.read()
                backend = cap.getBackendName()
                available.append({
                    "index": idx,
                    "label": f"Camera {idx} ({backend})",
                    "type": "webcam",
                    "has_frame": ret,
                })
                cap.release()
        except Exception:
            pass
    return available


# ═══════════════════════════════════════════════════════════════
#  Attendance Helpers
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3)  # Refresh every 3 seconds
def _get_today_attendance_df() -> pd.DataFrame:
    """Return today's attendance as a DataFrame."""
    records = AttendanceService.get_today(limit=200)
    rows = []
    for record in records:
        d = AttendanceService.to_dict(record)
        rows.append({
            "time": d.get("timestamp", "")[11:16] if d.get("timestamp") else "",
            "name": d.get("employee_name", ""),
            "id": d.get("employee_id", ""),
            "status": "Present",
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["time", "name", "id", "status"])
    return df


# ═══════════════════════════════════════════════════════════════
#  Camera Type Definitions
# ═══════════════════════════════════════════════════════════════

CAMERA_OPTIONS = {
    "\U0001f4bb PC Camera": "webcam",
    "\U0001f50c USB Camera": "usb_auto",
    "\U0001f4f1 Android Phone": "android_wifi",
    "\U0001f4f1 iPhone": "iphone_wifi",
    "\U0001f310 IP / RTSP Camera": "ip_camera",
}

PHONE_CONNECTION_OPTIONS = {
    "Wi-Fi": "wifi",
    "USB": "usb",
}


def _render_camera_config(source_type: str) -> dict:
    """Render only the relevant configuration fields for the selected camera type."""
    config = {}

    if source_type == "webcam":
        # Check cached discovery results
        pc_cameras = st.session_state.get("pc_cameras_cache", [])
        if len(pc_cameras) > 1:
            labels = [c["label"] for c in pc_cameras]
            chosen = st.selectbox(
                "Which camera?",
                options=labels,
                index=0,
                key="webcam_select",
                disabled=st.session_state.pipeline is not None and st.session_state.pipeline.is_running,
            )
            idx = pc_cameras[labels.index(chosen)]["index"]
            config["device_id"] = idx
        elif len(pc_cameras) == 1:
            config["device_id"] = pc_cameras[0]["index"]
            st.caption(f"Using {pc_cameras[0]['label']}")
        else:
            config["device_id"] = 0
            st.caption("No camera detected — will try default")

    elif source_type == "usb_auto":
        st.caption("Auto-detects USB camera on connect")

    elif source_type == "android_wifi":
        connection = st.selectbox(
            "Connection",
            options=list(PHONE_CONNECTION_OPTIONS.keys()),
            index=0,
            key="android_conn",
        )
        conn_type = PHONE_CONNECTION_OPTIONS[connection]
        if conn_type == "wifi":
            config["source_type"] = "android_wifi"
            config["url"] = st.text_input(
                "Camera URL",
                value="http://192.168.1.100:8080/video",
                key="android_url",
                help="URL shown in IP Webcam app",
            )
        else:
            config["source_type"] = "android_usb"
            config["device_id"] = st.number_input(
                "Device Index", 0, 10, 1, key="android_dev",
                help="Device index for DroidCam (typically 1)",
            )
        if st.button("\U0001f517 Test Connection", key="android_test", use_container_width=True):
            _test_camera_connection(config)

    elif source_type == "iphone_wifi":
        connection = st.selectbox(
            "Connection",
            options=list(PHONE_CONNECTION_OPTIONS.keys()),
            index=0,
            key="iphone_conn",
        )
        conn_type = PHONE_CONNECTION_OPTIONS[connection]
        if conn_type == "wifi":
            config["source_type"] = "iphone_wifi"
            config["url"] = st.text_input(
                "Camera URL",
                value="http://192.168.1.101:8080/video",
                key="iphone_url",
                help="URL from EpocCam app",
            )
        else:
            config["source_type"] = "iphone_usb"
            config["device_id"] = st.number_input(
                "Device Index", 0, 10, 2, key="iphone_dev",
                help="Device index for EpocCam (typically 2)",
            )
        if st.button("\U0001f517 Test Connection", key="iphone_test", use_container_width=True):
            _test_camera_connection(config)

    elif source_type == "ip_camera":
        config["source_type"] = "ip_camera"
        config["url"] = st.text_input(
            "Camera URL",
            value="rtsp://192.168.1.200:554/stream1",
            key="ip_url",
            help="RTSP or HTTP stream URL",
        )
        col1, col2 = st.columns(2)
        with col1:
            config["username"] = st.text_input("Username (optional)", key="ip_user")
        with col2:
            config["password"] = st.text_input("Password (optional)", type="password", key="ip_pass")
        if st.button("\U0001f517 Test Connection", key="ip_test", use_container_width=True):
            _test_camera_connection(config)

    return config


def _test_camera_connection(config: dict) -> None:
    """Test a camera connection and show result."""
    source_type = config.get("source_type", "webcam")
    kwargs = {}
    for key in ("url", "device_id", "username", "password"):
        if key in config:
            kwargs[key] = config[key]

    with st.spinner("Testing connection..."):
        try:
            cam = create_camera(source_type, **kwargs)
            if cam and cam.open():
                res = cam.get_resolution()
                st.success(f"\u2705 Connected! Resolution: {res[0]}\u00d7{res[1]}")
                cam.release()
            else:
                st.error("\u274c Could not connect. Check URL/device and try again.")
        except Exception as e:
            st.error(f"\u274c Connection failed: {e}")


# ═══════════════════════════════════════════════════════════════
#  Recognition Start/Stop Functions
# ═══════════════════════════════════════════════════════════════

def _start_recognition() -> None:
    """Start the camera and recognition pipeline."""
    # Refresh camera cache
    st.session_state.pc_cameras_cache = scan_local_cameras()

    # Stop any existing pipeline first
    _stop_recognition()

    source_type = st.session_state.get("camera_type", "webcam")
    config = st.session_state.get("camera_config", {})

    # Use sub-type from config if set (phone USB mode overrides top-level type)
    effective_source = config.get("source_type", source_type)

    # Build kwargs for create_camera
    kwargs = {}
    if effective_source in ("webcam",):
        kwargs["device_id"] = config.get("device_id", 0)
    elif effective_source == "usb_auto":
        kwargs["device_id"] = -1
    elif effective_source in ("android_wifi", "iphone_wifi", "ip_camera"):
        kwargs["url"] = config.get("url", "")
        if "username" in config:
            kwargs["username"] = config["username"]
        if "password" in config:
            kwargs["password"] = config["password"]
    elif effective_source in ("android_usb", "iphone_usb"):
        kwargs["device_id"] = config.get("device_id", 0)

    pipeline = LiveRecognitionPipeline(source_type=effective_source, **kwargs)

    with st.spinner("Starting camera..."):
        if pipeline.start():
            st.session_state.pipeline = pipeline
            st.success("\u2705 Camera started — recognition running")
        else:
            st.error(f"\u274c Failed to start: {pipeline.error}")

    st.rerun()


def _stop_recognition() -> None:
    """Stop the camera and recognition pipeline."""
    if st.session_state.pipeline:
        st.session_state.pipeline.stop()
        st.session_state.pipeline = None
        st.info("\u23f9\ufe0f Camera stopped")


# ═══════════════════════════════════════════════════════════════
#  MAIN PAGE UI
# ═══════════════════════════════════════════════════════════════

# ── Session state initialization ──────────────────────────────
if "pipeline" not in st.session_state:
    st.session_state.pipeline = None
if "camera_type" not in st.session_state:
    st.session_state.camera_type = "webcam"
if "camera_config" not in st.session_state:
    st.session_state.camera_config = {}
if "pc_cameras_cache" not in st.session_state:
    st.session_state.pc_cameras_cache = scan_local_cameras()
if "camera_settings_expanded" not in st.session_state:
    st.session_state.camera_settings_expanded = False


# ═══════════════════════════════════════════════════════════════
#  TITLE
# ═══════════════════════════════════════════════════════════════

st.markdown(
    "<h1 style='margin-bottom:0'>"
    "\U0001f4f9 Live Recognition"
    "</h1>",
    unsafe_allow_html=True,
)

pipeline = st.session_state.pipeline
is_running = pipeline is not None and pipeline.is_running

# ═══════════════════════════════════════════════════════════════
#  CONTROL BAR
# ═══════════════════════════════════════════════════════════════

st.markdown("---")

# ── Row 1: Camera select + buttons ──────────────────────────
row1 = st.columns([2.5, 1.5, 1, 1, 1.5])

with row1[0]:
    selected_camera_label = st.selectbox(
        "Camera",
        options=list(CAMERA_OPTIONS.keys()),
        index=0,  # PC Camera is DEFAULT
        key="camera_select",
        disabled=is_running,
    )
    selected_source = CAMERA_OPTIONS[selected_camera_label]
    st.session_state.camera_type = selected_source

    # Render camera-type-specific config below the selector
    config = _render_camera_config(selected_source)
    st.session_state.camera_config = config

with row1[1]:
    st.markdown("##### &nbsp;")
    if st.button(
        "\U0001f50d Scan Cameras",
        use_container_width=True,
        disabled=is_running,
    ):
        with st.spinner("Scanning..."):
            local = scan_local_cameras()
            st.session_state.pc_cameras_cache = local
            try:
                network = scan_network(timeout=1.0)
                st.session_state["scan_results"] = {"local": local, "network": network}
            except Exception:
                st.session_state["scan_results"] = {"local": local, "network": []}
            st.rerun()

    # Show discovery results
    if "scan_results" in st.session_state:
        sr = st.session_state["scan_results"]
        local = sr.get("local", [])
        network = sr.get("network", [])
        if local:
            for c in local:
                st.caption(f"\u2713 {c['label']}")
        if network:
            for d in network:
                st.caption(f"\u2713 {d.display_name}")

with row1[2]:
    st.markdown("##### &nbsp;")
    if st.button(
        "\u25b6 START",
        type="primary",
        use_container_width=True,
        disabled=is_running,
    ):
        _start_recognition()

with row1[3]:
    st.markdown("##### &nbsp;")
    if st.button(
        "\u23f9 STOP",
        use_container_width=True,
        disabled=not is_running,
    ):
        _stop_recognition()

with row1[4]:
    st.markdown("##### Status")
    if is_running:
        ps = pipeline.status
        if ps == "LIVE":
            st.markdown(":green[**\u25cf LIVE**]")
        elif ps == "CONNECTING":
            st.markdown(":orange[**\u25cb CONNECTING**]")
        elif ps == "RECONNECTING":
            st.markdown(":orange[**\u25cb RECONNECTING...**]")
            st.caption("Attempting to reconnect...")
        elif ps in ("ERROR", "DISCONNECTED"):
            st.markdown(":red[**\u25cf DISCONNECTED**]")
        else:
            st.markdown(f":gray[**\u25cf {ps}**]")
    else:
        st.markdown(":green[**\u25cf READY**]")


st.markdown("---")

# ═══════════════════════════════════════════════════════════════
#  MAIN VIDEO AREA
# ═══════════════════════════════════════════════════════════════

if is_running:
    frame, results = pipeline.latest()
    last_result = results[0] if results else None

    # Main layout: video + sidebar
    video_col, info_col = st.columns([3, 1])

    with video_col:
        if frame is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            st.image(rgb_frame, channels="RGB", use_container_width=True)
        else:
            # Dark placeholder
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            placeholder[:] = (25, 25, 25)
            cv2.putText(
                placeholder, "Waiting for camera...",
                (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 180), 2,
            )
            st.image(placeholder, channels="BGR", use_container_width=True)

    with info_col:
        # Camera info summary
        camera_label_display = selected_camera_label
        st.markdown(f"**Camera:** {camera_label_display}")
        st.markdown(f"**FPS:** {pipeline.fps:.1f}")
        st.markdown(f"**People:** {pipeline.people_count}")

        if pipeline.error:
            st.error(f"Error: {pipeline.error}")

        # ── Last Recognition ──────────────────────────────────
        if last_result:
            st.markdown("---")
            st.markdown("**Last Recognition**")
            decision = last_result.get("amfr_decision", "")
            name = last_result.get("emp_name") or last_result.get("name", "?")

            if decision == AMFRDecision.ACCEPT.value:
                st.markdown(f"\u2705 **{name}**")
                emp_id_str = last_result.get("name", "")
                if emp_id_str:
                    st.caption(f"ID: {emp_id_str}")
                st.success("PRESENT")
            elif decision == AMFRDecision.REJECT_SPOOF.value:
                st.markdown(f"\U0001f6ab **SPOOF DETECTED**")
                st.error("Attendance Rejected")
            elif decision == AMFRDecision.BORDERLINE.value:
                st.markdown(f"\u23f3 **{name}?**")
                st.info("Collecting more frames...")
            else:
                st.markdown(f"\u2753 **{name}**")
                st.info("Not Enrolled")

    # ── Camera Status Bar ─────────────────────────────────────
    status_cols = st.columns(4)
    with status_cols[0]:
        st.markdown(f":green[**{camera_label_display}**]")
    with status_cols[1]:
        st.markdown(f"**FPS:** {pipeline.fps:.1f}")
    with status_cols[2]:
        st.markdown(f"**People:** {pipeline.people_count}")
    with status_cols[3]:
        st.markdown(f"**Latency:** {pipeline.pipeline_latency:.0f} ms")

    # ── Today's Attendance ────────────────────────────────────
    st.markdown("---")
    st.markdown("### \U0001f4cb Today's Attendance")
    today_df = _get_today_attendance_df()
    if today_df.empty:
        st.info("No attendance records yet. Stand in front of the camera to be recognized.")
    else:
        st.dataframe(
            today_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "time": "Time",
                "name": "Name",
                "id": "ID",
                "status": "Status",
            },
        )

    # ── Expandable Sections ──────────────────────────────────

    # Recognition Details
    with st.expander("\U0001f52c Recognition Details"):
        if results:
            for i, r in enumerate(results):
                display_name = (r.get("emp_name") or r.get("name", "?"))
                if r.get("amfr_decision") == AMFRDecision.ACCEPT.value:
                    check = "\u2705 "
                elif r.get("amfr_decision") == AMFRDecision.REJECT_SPOOF.value:
                    check = "\U0001f6ab "
                else:
                    check = "\u2753 "

                st.markdown(f"**Person {i + 1}:** {check}{display_name}")
                cols = st.columns(4)
                with cols[0]:
                    conf = r.get("risk_score", r.get("confidence", 0))
                    st.metric("AMFR Confidence", f"{float(conf):.1%}" if conf else "\u2014")
                with cols[1]:
                    qual = r.get("quality_score", 0)
                    st.metric("Face Quality", f"{float(qual):.1%}" if qual else "\u2014")
                with cols[2]:
                    live = r.get("liveness_score", 0)
                    liveness_label = "LIVE" if float(live) > cfg.LIVENESS_MIN_SCORE else f"{float(live):.1%}"
                    st.metric("Liveness", liveness_label)
                with cols[3]:
                    if r.get("amfr_decision") == AMFRDecision.ACCEPT.value:
                        st.metric("Attendance", "\u2705 PRESENT")
                    elif r.get("amfr_decision") == AMFRDecision.REJECT_SPOOF.value:
                        st.metric("Attendance", "\U0001f6ab REJECTED")
                    elif r.get("attendance_marked"):
                        st.metric("Attendance", "\u2705 PRESENT")
                    else:
                        st.metric("Attendance", "\u2014")

                st.caption(
                    f"AMFR Score: {r.get('risk_score', 0):.3f} | "
                    f"Decision: {r.get('amfr_decision', '\u2014')} | "
                    f"Track: {r.get('track_id', '\u2014')[:10] if r.get('track_id') else '\u2014'}"
                )
                st.divider()
        else:
            st.info("No recognition results yet")

    # Camera Details
    with st.expander("\U0001f4f7 Camera Details"):
        st.markdown(f"**Source:** {camera_label_display}")
        st.markdown(f"**Type:** {selected_source}")
        st.markdown(f"**FPS:** {pipeline.fps:.1f}")
        st.markdown(f"**Resolution:** {pipeline.resolution}")
        st.markdown(f"**People detected:** {pipeline.people_count}")
        st.markdown(f"**Frames processed:** {pipeline.frame_count}")
        st.markdown(f"**Status:** {pipeline.status}")
        if pipeline.error:
            st.error(f"Error: {pipeline.error}")

    # Advanced Settings
    with st.expander("\u2699\ufe0f Advanced Settings"):
        st.markdown("**Recognition Thresholds**")
        st.markdown(f"- FAISS distance threshold: {cfg.RECOGNITION_THRESHOLD}")
        st.markdown(f"- Face quality min: {cfg.FACE_QUALITY_MIN_SCORE}")
        st.markdown(f"- Liveness min: {cfg.LIVENESS_MIN_SCORE}")
        st.markdown(f"- AMFR high confidence: {cfg.AMFR_HIGH_CONFIDENCE_THRESHOLD}")
        st.markdown(f"- AMFR borderline: {cfg.AMFR_BORDERLINE_THRESHOLD}")
        st.markdown(f"- Frame skip: {getattr(cfg, 'FRAME_SKIP', 2)}")
        st.markdown(f"- Cooldown: {cfg.COOLDOWN_SECONDS}s")
        st.markdown(f"- FAISS: {cfg.FAISS_INDEX_TYPE} M={cfg.FAISS_HNSW_M}, {cfg.FAISS_HNSW_EF_SEARCH} efSearch")

        st.markdown("**Model Status**")
        try:
            res = SharedModelResources.load()
            enrolled = res.service.enrollment.count()
            unique = res.service.enrollment.unique_count()
            st.success(f"\u2705 YOLO11 + InsightFace + FAISS ({enrolled} emb, {unique} persons) + AMFR")
        except Exception as e:
            st.error(f"\u274c Model error: {e}")

    # Auto-refresh for live feed
    time.sleep(0.05)
    st.rerun()

else:
    # ══════════════════════════════════════════════════════════
    #  INACTIVE STATE — show placeholder and system info
    # ══════════════════════════════════════════════════════════

    video_col, info_col = st.columns([3, 1])

    with video_col:
        # Dark placeholder
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        placeholder[:] = (18, 18, 18)
        cv2.putText(
            placeholder, "Camera Stopped",
            (180, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (140, 140, 140), 2,
        )
        cv2.putText(
            placeholder, "Select camera and press START",
            (140, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1,
        )
        st.image(placeholder, channels="BGR", use_container_width=True)

    with info_col:
        st.markdown("**Camera:** \u2014")
        st.markdown("**FPS:** \u2014")
        st.markdown("**People:** \u2014")
        st.info("\U0001f448\ufe0f Configure camera on the left, then click START")

    # Show scan results
    if "scan_results" in st.session_state:
        sr = st.session_state["scan_results"]
        local = sr.get("local", [])
        network = sr.get("network", [])
        if local or network:
            st.markdown("---")
            st.markdown("### \U0001f4e1 Discovered Devices")
            if local:
                st.markdown("**Local Cameras**")
                for c in local:
                    st.markdown(f"\u2705 {c['label']}")
            if network:
                st.markdown("**Network Cameras**")
                for d in network:
                    st.markdown(f"\U0001f4f1 {d.display_name} \u2014 `{d.stream_url}`")

    # System health status
    st.markdown("---")
    st.markdown("### \U0001f9e0 System Status")
    try:
        res = SharedModelResources.load()
        model_cols = st.columns(4)
        model_cols[0].success(f"\u2705 **YOLO11** \u2014 Detection")
        model_cols[1].success(f"\u2705 **InsightFace** \u2014 Recognition")
        model_cols[2].success(f"\u2705 **FAISS** \u2014 {res.service.enrollment.count()} emb.")
        model_cols[3].success(f"\u2705 **AMFR** \u2014 Active")

        # Database status
        from database.database import DB_TYPE, DATABASE_URL
        masked_url = DATABASE_URL
        if "sqlite" in masked_url:
            masked_url = "SQLite (development)"
        elif "postgresql" in masked_url:
            from urllib.parse import urlparse
            parsed = urlparse(DATABASE_URL)
            masked_url = f"PostgreSQL @ {parsed.hostname}:{parsed.port}/{parsed.path.split('/')[-1]}"
        st.info(f"**Database:** {masked_url}")
    except Exception as e:
        st.error(f"\u274c System error: {e}")
