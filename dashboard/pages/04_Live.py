"""
Live Recognition Feed — Dual Camera Mode (AMFR-Enabled)
=========================================================

Supports **two simultaneous phone cameras** with full AMFR pipeline:

    🅰️ Camera 1 (Android)                     🅱️ Camera 2 (iPhone)
    ┌──────────────────────────────┐     ┌──────────────────────────────┐
    │ 📷 Live Feed                 │     │ 📷 Live Feed                 │
    │ Name: Gokul                  │     │ Name: Unknown                │
    │ Student ID: EMP001           │     │ Quality: 34.2%               │
    │ Confidence: 96.3%            │     │ Risk: 12.1%                  │
    │ Face Quality: 87.5%          │     │ Decision: LOW_CONFIDENCE     │
    │ Liveness: 94.1% [LIVE]       │     │                              │
    │ AMFR Score: 0.87             │     │                              │
    │ Decision: ACCEPT             │     │                              │
    │ Track ID: T000000-abc123     │     │                              │
    │ ✅ Attendance Marked         │     │                              │
    └──────────────────────────────┘     └──────────────────────────────┘

Pipeline (AMFR-enabled, per camera):
    Camera Frame → YOLO11 → RetinaFace → FaceQuality → Liveness
    → ArcFace → FAISS → AMFR (risk score + decision) → Attendance → PostgreSQL

Heavy models (YOLO, InsightFace, FAISS, Liveness CNN) are **shared**
via ``RecognitionService`` to minimise memory and loading time.
Recognition runs in background threads; the Streamlit UI reads the latest
results non-blocking.
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

# ── Ensure project root is on path ──────────────────────────────
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg
from app.amfr_engine import AMFRDecision
from services.recognition_service import RecognitionService
from camera.base import CameraSource
from camera.selector import create_camera
from camera.discovery import scan_network, DiscoveredCamera
from services.attendance_service import AttendanceService

# ── Page Config ────────────────────────────────────────────────
st.set_page_config(page_title="Live Recognition", page_icon="📹", layout="wide")


# ═══════════════════════════════════════════════════════════════
#  Shared Model Resources — loaded once, shared across cameras
# ═══════════════════════════════════════════════════════════════

@dataclass
class SharedModelResources:
    """Container for heavy deep-learning models loaded once and shared.

    Creates a **single** ``RecognitionService`` that holds the expensive
    YOLO, InsightFace, FAISS, and AMFR objects.  Each ``CameraPipeline``
    calls ``RecognitionService.with_shared_models()`` to get its own
    service instance with independent per-camera state but shared models.
    """

    service: RecognitionService

    @staticmethod
    def load() -> SharedModelResources:
        """Load (or retrieve cached) recognition models once.

        On first call the entire AI pipeline is loaded from disk;
        subsequent calls return the same cached singleton.  Camera
        pipelines use ``with_shared_models()`` to create independent
        copies that share only the expensive AI models.
        """
        if not hasattr(SharedModelResources, "_cache"):
            print("[ModelCache] Loading shared AI models (YOLO, InsightFace, FAISS, AMFR)...")
            service = RecognitionService()
            SharedModelResources._cache = SharedModelResources(service=service)
            print(f"[ModelCache] Models loaded — {service.enrollment.count()} enrolled faces")
        return SharedModelResources._cache


# ═══════════════════════════════════════════════════════════════
#  Per‑Camera Pipeline — isolated mutable state, shared read-only models
# ═══════════════════════════════════════════════════════════════

class CameraPipeline:
    """Recognition pipeline for a **single** camera feed.

    Delegates to the ``RecognitionService`` which runs the full AMFR
    pipeline: YOLO → RetinaFace → FaceQuality → Liveness → ArcFace
    → FAISS → AMFR → Attendance logging.

    Shares the heavy AI objects via ``SharedModelResources`` but keeps
    its own mutable state (frame counter, session tracking, FPS, etc.).

    Usage:

        pipeline = CameraPipeline()
        annotated, results = pipeline.process(frame)
    """

    def __init__(self, resources: Optional[SharedModelResources] = None):
        self._res = resources or SharedModelResources.load()
        # Create a per-pipeline service with shared models for thread safety
        self._service = RecognitionService.with_shared_models(self._res.service)

        # Mutable per-camera state (each pipeline has its own)
        self.frame_skip = cfg.FRAME_SKIP
        self._frame_count = 0
        self._last_recognised: List[Dict] = []
        self._marked_this_session: set = set()
        self._fps = 0.0
        self._prev_time = time.time()
        self._lock = threading.Lock()
        self._last_unknown_save = 0.0
        self._unknown_save_cooldown = 3.0
        self._saved_unknown_this_frame = False

        # Camera health tracking
        self._health_check_interval = 10.0  # seconds
        self._last_health_check = 0.0
        self._camera_health = {"status": "UNKNOWN", "fps": 0}

    def process(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict]]:
        """Run the full AMFR pipeline on one frame via RecognitionService.

        The heavy AI runs inside ``RecognitionService.process_frame_detailed()``
        which handles: YOLO → RetinaFace → FaceQuality → Liveness →
        ArcFace → FAISS → AMFR → Attendance logging.

        Returns:
            (annotated_frame, results_list_with_amfr_fields)
        """
        with self._lock:
            self._frame_count += 1

            # FPS
            now = time.time()
            self._fps = 0.9 * self._fps + 0.1 / (now - self._prev_time + 1e-6)
            self._prev_time = now

            # Camera health check (periodic)
            if now - self._last_health_check > self._health_check_interval:
                self._update_camera_health()
                self._last_health_check = now

            # Delegate to RecognitionService for the full AMFR pipeline
            annotated, results = self._service.process_frame_detailed(frame)

            # Track which names we've marked for session reset tracking
            for r in results:
                if r.get("is_known") and r.get("name"):
                    self._marked_this_session.add(r["name"])

            self._last_recognised = results
            return annotated, results

    def _update_camera_health(self) -> None:
        """Check camera health (FPS trend, frame drops)."""
        fps_ok = self._fps > 2.0
        self._camera_health = {
            "status": "HEALTHY" if fps_ok else "WARNING",
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
        }
        if self._fps < 1.0:
            self._camera_health["status"] = "CRITICAL"

    def status(self) -> Dict:
        """Return a snapshot including AMFR engine state."""
        svc_status = self._service.status()
        return {
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
            "enrolled": svc_status.get("enrolled", 0),
            "session_marked": len(self._marked_this_session),
            "amfr": svc_status.get("amfr", {}),
            "camera_health": self._camera_health,
            "attendance_stats": svc_status.get("attendance", {}),
        }

    def reset_session(self) -> None:
        """Reset attendance markers and AMFR engine for a new session."""
        self._marked_this_session.clear()
        self._service.reset_tracking()

    @property
    def service(self) -> RecognitionService:
        return self._service


# ═══════════════════════════════════════════════════════════════
#  Phone Camera Feed — wraps CameraSource + CameraPipeline
# ═══════════════════════════════════════════════════════════════

class PhoneCameraFeed:
    """Single phone camera feed: connects, captures, processes frames.

    Each feed has its own ``CameraPipeline`` so frame counters and
    session tracking are independent per camera.  The heavy models
    (YOLO, InsightFace, FAISS) are **shared** via ``SharedModelResources``.

    Usage in Streamlit::

        feed = PhoneCameraFeed(source_type="android_wifi", url="http://192.168.1.100:8080/video")
        if feed.connect():
            frame = feed.capture_frame()   # returns annotated BGR frame
    """

    def __init__(self, source_type: str, url: str = "", device_id: int = 0,
                 label: str = "Camera", pipeline: Optional[CameraPipeline] = None):
        self.source_type = source_type
        self.url = url
        self.device_id = device_id
        self.label = label
        self.pipeline = pipeline or CameraPipeline()
        self._cam: Optional[CameraSource] = None
        self._running = False
        self.last_results: List[Dict] = []

    def connect(self) -> bool:
        """Open the phone camera connection."""
        kwargs: Dict = {}
        if self.source_type in ("android_wifi", "iphone_wifi"):
            kwargs["url"] = self.url or "http://192.168.1.100:8080/video"
        elif self.source_type == "usb_auto":
            kwargs["device_id"] = self.device_id  # prefer_index
        elif self.source_type == "android_usb":
            kwargs["device_id"] = self.device_id
            kwargs["url"] = self.url or "192.168.1.100:4747"
        elif self.source_type == "iphone_usb":
            kwargs["device_id"] = self.device_id

        self._cam = create_camera(self.source_type, **kwargs)
        if self._cam is None:
            return False
        if not self._cam.open():
            return False
        self._cam.set_resolution(640, 480)
        self._running = True
        return True

    def release(self) -> None:
        self._running = False
        if self._cam is not None:
            self._cam.release()
            self._cam = None

    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture one frame and run it through the pipeline.

        Returns annotated BGR frame, or ``None`` on failure.
        """
        if self._cam is None or not self._running:
            return None
        ret, frame = self._cam.read()
        if not ret or frame is None:
            return None
        annotated, results = self.pipeline.process(frame)
        self.last_results = results
        return annotated

    @property
    def is_connected(self) -> bool:
        return self._cam is not None and self._cam.is_opened()

    @property
    def name(self) -> str:
        return self._cam.name if self._cam else f"{self.label} (disconnected)"


# ═══════════════════════════════════════════════════════════════
#  Threaded Camera Feed — runs capture + pipeline in background
# ═══════════════════════════════════════════════════════════════

class ThreadedCameraFeed:
    """Wraps a ``PhoneCameraFeed`` in a background daemon thread.

    The thread continuously captures frames and runs them through the
    recognition pipeline, storing the **latest** annotated frame and
    results.  The main UI thread reads the latest snapshot without
    blocking, so one slow camera never stalls the other.

    Usage::

        feed = PhoneCameraFeed(...)
        feed.connect()
        threaded = ThreadedCameraFeed(feed)
        threaded.start()

        while True:
            frame, results = threaded.latest()
            if frame is not None:
                display(frame)
            time.sleep(0.03)

        threaded.stop()
    """

    def __init__(self, feed: PhoneCameraFeed):
        self._feed = feed
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Latest snapshot (thread-safe via _lock)
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_results: List[Dict] = []
        self._fps: float = 0.0
        self._last_update: float = 0.0

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> None:
        """Start the background capture thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"CamThread-{self._feed.label}",
            daemon=True,
        )
        self._thread.start()
        print(f"[ThreadedFeed] Started thread for {self._feed.name}")

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                print(f"[ThreadedFeed] Thread did not join in time for {self._feed.name}")
        self._thread = None
        self._feed.release()
        print(f"[ThreadedFeed] Stopped thread for {self._feed.name}")

    # ── Background loop ──────────────────────────────────────

    def _capture_loop(self) -> None:
        """Continuously capture and process frames.

        Runs in a daemon thread; stores the latest annotated frame
        and results which the main UI picks up on each rerun.
        """
        while self._running:
            frame = self._feed.capture_frame()
            with self._lock:
                if frame is not None:
                    self._latest_frame = frame
                    self._latest_results = list(self._feed.last_results)
                    self._fps = self._feed.pipeline.status()["fps"]
                    self._last_update = time.time()
                # If frame is None (e.g. temporary glitch), keep the last good frame

            # Small sleep to prevent busy-waiting at 100% CPU
            # Frame capture internally blocks on camera read, so this
            # only adds a tiny pause between capture attempts
            time.sleep(0.005)

    # ── Main-thread accessors ─────────────────────────────────

    def latest(self) -> Tuple[Optional[np.ndarray], List[Dict]]:
        """Get the latest frame and results (non-blocking).

        Returns:
            ``(annotated_bgr_frame, results_list)``.
            Frame is ``None`` if no frame has been captured yet.
        """
        with self._lock:
            return self._latest_frame, list(self._latest_results)

    @property
    def is_connected(self) -> bool:
        return self._feed.is_connected

    @property
    def name(self) -> str:
        return self._feed.name

    @property
    def pipeline(self) -> CameraPipeline:
        return self._feed.pipeline

    @property
    def is_alive(self) -> bool:
        """Whether the background thread is currently running."""
        return self._thread is not None and self._thread.is_alive()


# ═══════════════════════════════════════════════════════════════
#  Camera Configuration Helpers
# ═══════════════════════════════════════════════════════════════

CAMERA_SOURCE_OPTIONS = {
    "🔌 USB Auto (Plug & Play)": "usb_auto",
    "📱 Android (Wi-Fi)": "android_wifi",
    "📱 Android (USB)": "android_usb",
    "📱 iPhone (Wi-Fi)": "iphone_wifi",
    "📱 iPhone (USB)": "iphone_usb",
}


def _is_phone_camera(source_type: str) -> bool:
    return source_type in {"usb_auto", "android_usb", "android_wifi", "iphone_usb", "iphone_wifi"}


def _render_camera_config(prefix: str, label: str, default_source: str, default_url: str, default_id: int):
    """Render a single camera's configuration widget block in the sidebar.

    Uses unique ``key`` prefixed with *prefix* to avoid widget ID collisions
    between the two cameras.  Includes a **widget version** suffix (from session
    state, e.g. ``cam1_url_v2``) so that auto-filled URLs are displayed correctly
    even after Streamlit has persisted a previous widget value.

    Returns the chosen ``(source_type, url, device_id)``.
    """
    # Widget version — incremented when auto-fill sets the URL, forcing fresh widgets
    widget_ver = st.session_state.get(f"{prefix}_widget_ver", 0)

    current_label = "📱 Android (Wi-Fi)"
    for lbl, slug in CAMERA_SOURCE_OPTIONS.items():
        if slug == default_source:
            current_label = lbl
            break

    selected_label = st.selectbox(
        f"{label} — Source",
        options=list(CAMERA_SOURCE_OPTIONS.keys()),
        index=list(CAMERA_SOURCE_OPTIONS.keys()).index(current_label),
        key=f"{prefix}_src_v{widget_ver}",
        help=f"Select the camera type for {label}",
    )
    source_type = CAMERA_SOURCE_OPTIONS[selected_label]

    url = default_url
    if source_type in ("android_wifi", "iphone_wifi"):
        url = st.text_input(
            f"{label} — URL / IP",
            value=default_url,
            key=f"{prefix}_url_v{widget_ver}",
            help="Enter the stream URL from the camera app",
        )

    device_id = default_id
    if source_type in ("usb_auto", "android_usb", "iphone_usb"):
        default_dev = {"usb_auto": -1, "android_usb": 1, "iphone_usb": 2}.get(source_type, 0)
        hint = {
            "usb_auto": "-1 = auto-scan all indices; 0-10 = prefer a specific device",
            "android_usb": "Camera device index for DroidCam (typically 1)",
            "iphone_usb": "Camera device index for EpocCam (typically 2)",
        }.get(source_type, "")
        device_id = st.number_input(
            f"{label} — Device Index",
            min_value=-1, max_value=10,
            value=default_dev,
            step=1,
            key=f"{prefix}_devid_v{widget_ver}",
            help=hint,
        )

    return source_type, url, int(device_id)


def _render_camera_column(feed: Optional[ThreadedCameraFeed], col, emoji: str, label: str):
    """Render a single camera column with full AMFR per-person info cards.

    Shows for each detected person:
        - Name
        - Student / Employee ID
        - Confidence %
        - Face Quality %
        - Liveness score/status
        - AMFR score (risk_score)
        - AMFR decision
        - Track ID
        - Attendance status
    """
    with col:
        st.markdown(f"### {emoji} {label}")

        if feed is None or not feed.is_connected:
            st.info(f"⬜ {label} — not connected")
            if feed is not None and not feed.is_connected:
                st.caption("Connection lost — click **Start Dual Cameras** to reconnect")
            return

        # Show live feed (non-blocking read from background thread)
        frame_placeholder = st.empty()
        annotated, results = feed.latest()
        if annotated is not None:
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(rgb, channels="RGB", use_container_width=True)

            # Camera health indicator
            health = feed.pipeline.status().get("camera_health", {})
            hstatus = health.get("status", "UNKNOWN")
            hfps = health.get("fps", 0)
            if hstatus == "HEALTHY":
                st.success(f"🟢 {feed.name} — FPS: {hfps:.1f}")
            elif hstatus == "WARNING":
                st.warning(f"🟡 {feed.name} — FPS: {hfps:.1f} (low)")
            elif hstatus == "CRITICAL":
                st.error(f"🔴 {feed.name} — FPS: {hfps:.1f} (critical)")
            else:
                st.info(f"⚪ {feed.name} — connecting...")
        else:
            st.warning(f"🟡 Waiting for first frame... ({feed.name})")

        # Show per-detection AMFR info cards
        if results:
            st.markdown("**Detections:**")
            for r in results:
                name = r.get("name", "?")
                decision = r.get("amfr_decision", "")
                is_known = r.get("is_known", False)
                track_id = r.get("track_id", "—")
                emp_id = r.get("emp_id", "—")
                risk_score = r.get("risk_score", 0.0)
                quality_score = r.get("quality_score", 0.0)
                liveness_score = r.get("liveness_score", 0.5)
                arcface_dist = r.get("arcface_distance", 999.0)

                # ── Decide color and badge ────────────────────
                if decision == AMFRDecision.ACCEPT.value:
                    badge = "🟢"
                    with st.container(border=True):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**{badge} {name}**")
                            if emp_id and emp_id != "—":
                                st.caption(f"ID: {emp_id}")
                        with col2:
                            st.markdown(f"<span style='color:green'>ACCEPT</span>", unsafe_allow_html=True)

                        cols = st.columns(3)
                        with cols[0]:
                            st.metric("Confidence", f"{risk_score:.1%}")
                            st.metric("Face Quality", f"{quality_score:.1%}")
                        with cols[1]:
                            live_status = "🟢 LIVE" if liveness_score > 0.5 else "⚠️"
                            st.metric("Liveness", f"{liveness_score:.1%}")
                            st.markdown(f"**{live_status}**")
                        with cols[2]:
                            st.metric("AMFR Score", f"{risk_score:.3f}")
                            st.caption(f"Track: {track_id[:12] if track_id != '—' else '—'}")
                        st.success("✅ Attendance Marked")

                elif decision == AMFRDecision.BORDERLINE.value:
                    with st.container(border=True):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**🟡 {name}?**")
                        with col2:
                            st.markdown("<span style='color:orange'>BORDERLINE</span>", unsafe_allow_html=True)

                        cols = st.columns(3)
                        with cols[0]:
                            st.metric("Confidence", f"{risk_score:.1%}")
                            st.metric("Face Quality", f"{quality_score:.1%}")
                        with cols[1]:
                            st.metric("Liveness", f"{liveness_score:.1%}")
                        with cols[2]:
                            st.metric("AMFR Score", f"{risk_score:.3f}")
                            st.caption(f"Track: {track_id[:12] if track_id != '—' else '—'}")
                        st.info("⏳ Collecting more frames...")

                elif decision == AMFRDecision.REJECT_SPOOF.value:
                    with st.container(border=True):
                        st.markdown(f"**🔴 SPOOF DETECTED**")
                        cols = st.columns(2)
                        with cols[0]:
                            st.metric("Liveness", f"{liveness_score:.1%}")
                        with cols[1]:
                            st.metric("Face Quality", f"{quality_score:.1%}")
                        st.error("🚨 Security Alert Logged")

                elif decision == AMFRDecision.LOW_CONFIDENCE.value or name == "No Face":
                    with st.container(border=True):
                        if name == "No Face":
                            st.markdown(f"**⚠️ {name}**")
                        else:
                            st.markdown(f"**⚪ {name}**")
                            st.caption(f"Risk: {risk_score:.1%}, Quality: {quality_score:.1%}")
                        st.info("📸 Unknown — saved to gallery")

                else:  # PENDING or unknown
                    with st.container(border=True):
                        st.markdown(f"**⚪ {name}**")
                        st.caption(f"Decision: {decision}, Risk: {risk_score:.1%}")
        else:
            st.caption("No detections yet")


@st.cache_data(ttl=3)
def _get_today_attendance_df() -> pd.DataFrame:
    """Return today's attendance as a DataFrame for the live dashboard."""
    records = AttendanceService.get_today(limit=200)
    rows = []
    for record in records:
        rows.append(AttendanceService.to_dict(record))
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["id", "employee_id", "employee_name", "timestamp", "confidence", "camera_id"])
    return df.sort_values("timestamp", ascending=False)


# ═══════════════════════════════════════════════════════════════
#  Page — UI
# ═══════════════════════════════════════════════════════════════

st.title("📹 Dual Camera Live Recognition")
st.markdown(
    "Run **two phone cameras simultaneously** — "
    "e.g. an Android camera on the left and an iPhone camera on the right."
)

st.markdown("""
| Camera | Connection | App Required |
|---|---|---|
| 🔌 **USB Auto (Plug & Play)** | Auto-detect any USB camera | **None!** (Android 14+ USB Webcam / any UVC cam) |
| 📱 **Android (Wi-Fi)** | HTTP MJPEG stream | [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) |
| 📱 **Android (USB)** | DroidCam virtual device | [DroidCam](https://www.dev47apps.com/) |
| 📱 **iPhone (Wi-Fi)** | RTSP / HTTP stream | [EpocCam](https://www.elgato.com/us/en/s/epoccam) |
| 📱 **iPhone (USB)** | DirectShow virtual camera | [EpocCam](https://www.elgato.com/us/en/s/epoccam) |
""")

# ── Session state initialisation ──────────────────────────────
if "dual_active" not in st.session_state:
    st.session_state.dual_active = False

# Camera 1 config (default: Android Wi-Fi)
if "cam1_source" not in st.session_state:
    st.session_state.cam1_source = "android_wifi"
if "cam1_url" not in st.session_state:
    st.session_state.cam1_url = "http://192.168.1.100:8080/video"
if "cam1_id" not in st.session_state:
    st.session_state.cam1_id = 0

# Camera 2 config (default: iPhone Wi-Fi)
if "cam2_source" not in st.session_state:
    st.session_state.cam2_source = "iphone_wifi"
if "cam2_url" not in st.session_state:
    st.session_state.cam2_url = "http://192.168.1.101:8080/video"
if "cam2_id" not in st.session_state:
    st.session_state.cam2_id = 0


# ── Sidebar — Camera Configuration ────────────────────────────
with st.sidebar:
    st.markdown("### 🎥 Dual Camera Setup")
    st.caption("Configure each camera independently")

    if st.session_state.dual_active:
        st.warning("🔄 Stop cameras before changing config")
    else:
        with st.expander("📱 Camera 1 (Android)", expanded=True):
            cam1_src, cam1_url, cam1_id = _render_camera_config(
                prefix="cam1",
                label="Camera 1",
                default_source=st.session_state.cam1_source,
                default_url=st.session_state.cam1_url,
                default_id=st.session_state.cam1_id,
            )
            st.session_state.cam1_source = cam1_src
            st.session_state.cam1_url = cam1_url
            st.session_state.cam1_id = cam1_id

        with st.expander("📱 Camera 2 (iPhone)", expanded=True):
            cam2_src, cam2_url, cam2_id = _render_camera_config(
                prefix="cam2",
                label="Camera 2",
                default_source=st.session_state.cam2_source,
                default_url=st.session_state.cam2_url,
                default_id=st.session_state.cam2_id,
            )
            st.session_state.cam2_source = cam2_src
            st.session_state.cam2_url = cam2_url
            st.session_state.cam2_id = cam2_id

    st.divider()

    # Start / Stop buttons
    col1, col2 = st.columns(2)
    with col1:
        start_btn = st.button(
            "▶️ Start Dual Cameras", type="primary", use_container_width=True,
            disabled=st.session_state.dual_active,
        )
    with col2:
        stop_btn = st.button(
            "⏹️ Stop", use_container_width=True,
            disabled=not st.session_state.dual_active,
        )

    if start_btn:
        # Stop any stale threads and clear feeds
        for key in ("tfeed1", "tfeed2"):
            if key in st.session_state:
                st.session_state[key].stop()
                st.session_state.pop(key, None)
        for key in ("cam_pipeline", "cam_pipeline2"):
            st.session_state.pop(key, None)
        st.session_state.dual_active = True
        st.rerun()

    if stop_btn:
        st.session_state.dual_active = False
        for key in ("tfeed1", "tfeed2", "cam_pipeline", "cam_pipeline2"):
            if key in st.session_state:
                obj = st.session_state[key]
                if hasattr(obj, 'stop'):
                    obj.stop()
                st.session_state.pop(key, None)
        st.rerun()

    st.divider()

    # Reset session tracking
    if st.button("🔄 Reset Session Markers", use_container_width=True):
        if "cam_pipeline" in st.session_state:
            st.session_state.cam_pipeline.reset_session()
        st.success("Session markers cleared — all faces can be re-marked")

    st.divider()

    # ── Auto-Discovery Section ──────────────────────────────
    st.markdown("### 🔍 Auto-Discovery")
    st.caption("Scan your network for phone cameras")

    scan_col1, scan_col2 = st.columns([3, 1])
    with scan_col1:
        scan_clicked = st.button(
            "🔍 Scan Network",
            type="secondary",
            use_container_width=True,
            disabled=st.session_state.dual_active or st.session_state.get("scanning", False),
        )
    with scan_col2:
        if st.session_state.get("scanning", False):
            st.caption("Scanning...")

    discovered_devices: List[DiscoveredCamera] = st.session_state.get("discovered_devices", [])

    if scan_clicked:
        st.session_state.scanning = True
        with st.spinner("🔍 Scanning local network (takes ~10s)..."):
            try:
                devices = scan_network(timeout=1.5)
                st.session_state.discovered_devices = devices
            except Exception as scan_err:
                st.error(f"Scan failed: {scan_err}")
                st.session_state.discovered_devices = []
        st.session_state.scanning = False
        st.rerun()

    if discovered_devices:
        st.success(f"Found {len(discovered_devices)} device(s)")
        for dev in discovered_devices:
            icon = "📱" if "IP Webcam" in dev.display_name or "DroidCam" in dev.display_name else "📱"
            with st.container(border=True):
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(f"**{icon} {dev.display_name}**")
                    st.caption(f"{dev.stream_url}")
                with cols[1]:
                    # Auto-fill buttons for each camera
                    if not st.session_state.dual_active:
                        if st.button("Cam 1", key=f"use1_{dev.ip}_{dev.port}", use_container_width=True):
                            st.session_state.cam1_source = dev.source_type
                            st.session_state.cam1_url = dev.stream_url
                            # Bump widget version so Streamlit shows the auto-filled URL
                            st.session_state.cam1_widget_ver = st.session_state.get("cam1_widget_ver", 0) + 1
                            st.rerun()
                        if st.button("Cam 2", key=f"use2_{dev.ip}_{dev.port}", use_container_width=True):
                            st.session_state.cam2_source = dev.source_type
                            st.session_state.cam2_url = dev.stream_url
                            # Bump widget version so Streamlit shows the auto-filled URL
                            st.session_state.cam2_widget_ver = st.session_state.get("cam2_widget_ver", 0) + 1
                            st.rerun()
    elif not st.session_state.get("scanning", False) and "discovered_devices" in st.session_state:
        st.info("No phone cameras found. Make sure your phone is on the same Wi-Fi and the camera app is running.")

    st.divider()

    # Pre-load models indicator
    st.markdown("### 🧠 Model Status (AMFR)")
    try:
        res = SharedModelResources.load()
        st.success(f"✅ RecognitionService loaded (YOLO + InsightFace + FAISS + AMFR)")
        enrolled = res.service.enrollment.count()
        st.caption(f"{enrolled} enrolled faces | AMFR active")
    except Exception as e:
        st.error(f"❌ Model load failed: {e}")


# ── Main Area — Side-by-Side Camera Feeds ─────────────────────
if st.session_state.dual_active:
    # Ensure shared models are loaded
    SharedModelResources.load()

    # ── Create or retrieve threaded camera feeds ──────────
    tfeed1_key, tfeed2_key = "tfeed1", "tfeed2"
    need_rerun = False

    # Camera 1 — connect (if needed) → wrap in thread → start
    if tfeed1_key not in st.session_state or not st.session_state[tfeed1_key].is_connected:
        with st.spinner("Connecting Camera 1...", _cache=False):
            pipeline1 = CameraPipeline()
            st.session_state["cam_pipeline"] = pipeline1
            raw1 = PhoneCameraFeed(
                source_type=st.session_state.cam1_source,
                url=st.session_state.cam1_url,
                device_id=st.session_state.cam1_id,
                label="Camera 1",
                pipeline=pipeline1,
            )
            if raw1.connect():
                threaded = ThreadedCameraFeed(raw1)
                threaded.start()
                st.session_state[tfeed1_key] = threaded
                need_rerun = True

    # Camera 2 — same pattern (runs in parallel since connect is sequential but fast)
    if tfeed2_key not in st.session_state or not st.session_state[tfeed2_key].is_connected:
        with st.spinner("Connecting Camera 2...", _cache=False):
            pipeline2 = CameraPipeline()
            st.session_state["cam_pipeline2"] = pipeline2
            raw2 = PhoneCameraFeed(
                source_type=st.session_state.cam2_source,
                url=st.session_state.cam2_url,
                device_id=st.session_state.cam2_id,
                label="Camera 2",
                pipeline=pipeline2,
            )
            if raw2.connect():
                threaded = ThreadedCameraFeed(raw2)
                threaded.start()
                st.session_state[tfeed2_key] = threaded
                need_rerun = True

    if need_rerun:
        st.rerun()

    tfeed1: ThreadedCameraFeed = st.session_state.get(tfeed1_key)
    tfeed2: ThreadedCameraFeed = st.session_state.get(tfeed2_key)

    # Ensure background threads are running (they persist across reruns)
    if tfeed1 and tfeed1.is_connected and not tfeed1.is_alive:
        tfeed1.start()
    if tfeed2 and tfeed2.is_connected and not tfeed2.is_alive:
        tfeed2.start()

    # ── Side-by-side columns (non-blocking reads from threads) ─
    col_left, col_right = st.columns(2)

    _render_camera_column(tfeed1, col_left, "🅰️", "Camera 1 — Android")
    _render_camera_column(tfeed2, col_right, "🅱️", "Camera 2 — iPhone")

    # ── Combined stats row ───────────────────────────────────
    st.divider()
    st.markdown("### 📊 Combined Status")

    s1 = tfeed1.pipeline.status() if tfeed1 is not None and tfeed1.is_connected else {}
    s2 = tfeed2.pipeline.status() if tfeed2 is not None and tfeed2.is_connected else {}

    # AMFR stats from camera 1 (shared engine)
    amfr_state = s1.get("amfr", {}) or s2.get("amfr", {})
    camera1_health = s1.get("camera_health", {})
    camera2_health = s2.get("camera_health", {})

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        fps1 = s1.get("fps", 0)
        fps2 = s2.get("fps", 0)
        st.metric("FPS (Cam1 / Cam2)", f"{fps1:.1f} / {fps2:.1f}")
        c1h = camera1_health.get("status", "—")
        c2h = camera2_health.get("status", "—")
        st.caption(f"Health: {c1h} / {c2h}")
    with m2:
        e = s1.get("enrolled", 0) or s2.get("enrolled", 0)
        st.metric("Enrolled Faces", e)
        at = amfr_state.get("active_tracks", 0)
        st.caption(f"AMFR tracks: {at}")
    with m3:
        mk1 = s1.get("session_marked", 0)
        mk2 = s2.get("session_marked", 0)
        st.metric("Marked Today", f"{mk1} + {mk2}")
        spf = amfr_state.get("spoof_detected", 0)
        st.caption(f"Spoof alerts: {spf}")
    with m4:
        fc1 = s1.get("frame_count", 0)
        fc2 = s2.get("frame_count", 0)
        st.metric("Frames Processed", f"{fc1} + {fc2}")
        am = amfr_state.get("attendance_marked", 0)
        st.caption(f"AMFR accepted: {am}")

    # ── Auto-refresh ─────────────────────────────────────────
    # Background threads keep capturing and processing independently
    time.sleep(0.06)  # ~16 FPS refresh rate for UI updates
    st.divider()
    st.markdown("### 📅 Today’s Attendance")
    today_df = _get_today_attendance_df()

    top_left, top_right = st.columns([3, 1])
    with top_left:
        st.caption("Records are saved in SQLite and can be downloaded as CSV.")
    with top_right:
        csv_data = (
            today_df.to_csv(index=False)
            if not today_df.empty
            else "id,employee_id,employee_name,timestamp,confidence,camera_id\n"
        )
        st.download_button(
            "📥 Download CSV",
            data=csv_data,
            file_name=f"attendance_{time.strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if today_df.empty:
        st.info("No attendance records yet. Stand in front of the camera until your face is recognized.")
    else:
        display_df = today_df.rename(
            columns={
                "employee_id": "Emp ID",
                "employee_name": "Name",
                "timestamp": "Time",
                "confidence": "Confidence",
                "camera_id": "Camera",
            }
        )[["Emp ID", "Name", "Time", "Confidence", "Camera"]]
        display_df["Confidence"] = display_df["Confidence"].map(
            lambda x: f"{float(x):.1%}" if pd.notna(x) else "—"
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.rerun()

else:
    # ── Inactive — show camera config summary ─────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### 🅰️ Camera 1 (Android)")
        src_map = {
            "usb_auto": "🔌 USB Auto (Plug & Play)",
            "android_wifi": "📱 Android (Wi-Fi)",
            "android_usb": "📱 Android (USB)",
            "iphone_wifi": "📱 iPhone (Wi-Fi)",
            "iphone_usb": "📱 iPhone (USB)",
        }
        st.info(
            f"**Source:** {src_map.get(st.session_state.cam1_source, '?')}\n\n"
            f"**URL / Device:** {st.session_state.cam1_url or st.session_state.cam1_id}"
        )

    with col_right:
        st.markdown("### 🅱️ Camera 2 (iPhone)")
        st.info(
            f"**Source:** {src_map.get(st.session_state.cam2_source, '?')}\n\n"
            f"**URL / Device:** {st.session_state.cam2_url or st.session_state.cam2_id}"
        )

    st.info("👈 Configure both cameras in the sidebar, then click **▶️ Start Dual Cameras**")
    st.divider()

    # Model status with AMFR components
    st.markdown("### 🧠 Recognition Model Status (AMFR)")
    try:
        res = SharedModelResources.load()
        col1, col2, col3, col4 = st.columns(4)
        col1.success(f"✅ **YOLO11** — Person detection")
        col2.success(f"✅ **InsightFace** — RetinaFace + ArcFace")
        col3.success(f"✅ **FAISS** — {res.service.enrollment.count()} embeddings")
        col4.success(f"✅ **AMFR** — {res.service.amfr.status().get('active_tracks', 0)} tracks")
    except Exception as e:
        st.error(f"❌ Model loading failed: {e}")


# ── How it Works ──────────────────────────────────────────────
st.divider()
with st.expander(    "ℹ️ How Dual Camera + AMFR Works"):
    st.markdown("""
    **Architecture (AMFR-Enabled):**

    ```
    Camera 1 (Android)     Camera 2 (iPhone)
         │                       │
         ▼                       ▼
    ┌──────────────────┐  ┌──────────────────┐
    │  Pipeline 1       │  │  Pipeline 2       │
    │ (own state)       │  │ (own state)       │
    │ FPS, counters     │  │ FPS, counters     │
    └──────┬───────────┘  └──────┬───────────┘
           │                     │
           └─── Shared RecognitionService ───┘
           YOLO → RetinaFace → FaceQuality →
           Liveness → ArcFace → FAISS → AMFR
           (loaded once in memory)
    ```

    **Full AMFR Pipeline (per person):**

    ```
    YOLO person detection
      ↓
    RetinaFace (face detection + landmarks)
      ↓
    FACE QUALITY (blur, brightness, size, pose, contrast)
      ↓
    LIVENESS DETECTION (texture LBP, blink EAR, motion, screen edges, CNN)
      ↓
    ArcFace embedding (512-D normalized)
      ↓
    FAISS similarity search (L2 distance)
      ↓
    AMFR ENGINE (risk score + decision)
      ↓
    ACCEPT | BORDERLINE | LOW_CONFIDENCE | REJECT_SPOOF
      ↓
    Attendance (PostgreSQL) / Unknown Gallery / Security Log
    ```

    **Decision Rules:**
    - **ACCEPT** (risk ≥ 70%) → Mark PRESENT in attendance
    - **BORDERLINE** (risk ≥ 40%) → Collect more frames
    - **LOW_CONFIDENCE** → Display UNKNOWN, save to gallery
    - **REJECT_SPOOF** (liveness < 15%) → Reject, log security alert

    **Benefits:**
    - Heavy models (YOLO, InsightFace, FAISS, Liveness CNN) loaded **once**
    - Each camera has its own FPS, tracking, and attendance markers
    - Independent — one camera can fail without affecting the other
    - Per-track liveness detectors keep blink/motion state independent

    **Per-Camera Colors:**
    - 🟢 **Green** — ACCEPT: Known live person, attendance marked
    - 🟡 **Yellow** — BORDERLINE: Uncertain, collecting frames
    - 🔴 **Red** — SPOOF: Rejected, security alert logged
    - ⚪ **Grey** — LOW_CONFIDENCE: Unknown person saved
    - 🟠 **Orange** — No Face detected in bounding box

    **Performance:**
    - Recognition runs in background threads; UI never blocks on AI
    - FPS and camera health displayed per camera
    - Frame skip configurable via recognition.frame_skip in settings</pre>
    """)
