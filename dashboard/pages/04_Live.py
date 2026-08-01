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
from typing import Dict, List, Optional

import cv2
import numpy as np
import pandas as pd
import streamlit as st

# Performance: downscale large frames before AI pipeline for speed
# Display stays at original resolution; AI processes at this size
AI_PROCESS_SIZE = (320, 240)  # Downscale to this for YOLO/ArcFace inference

# Cadence (seconds) for the E2E frame-latency sampler. Matches the display
# rerun loop (time.sleep(0.05) + st.rerun()) so latency is measured at the
# same rate a human sees frames.
LATENCY_SAMPLE_CADENCE = 0.05

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
from dashboard.camera_owner import CameraOwner
from dashboard.frame_buffer import frame_buffer, results_buffer
from dashboard.latency_logger import LatencyLogger

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
        self._fps: float = 0.0
        self._ai_fps: float = 0.0
        self._pipeline_latency: float = 0.0
        self._status: str = "STOPPED"
        self._people_count: int = 0
        self._frame_count: int = 0
        self._error: Optional[str] = None
        self._reconnect_attempts: int = 0

        # E2E frame-latency logging (Camera → FrameBuffer → display)
        self._latency_logger = LatencyLogger()
        self._latency_thread: Optional[threading.Thread] = None

        # Recognition worker — runs AI independently of the capture thread so
        # the displayed video always shows the most recent RAW frame while
        # inference happens at its own cadence.
        self._worker_thread: Optional[threading.Thread] = None
        self._worker_interval: float = 0.10        # normal cadence (~10 AI runs/s max)
        self._verified_interval: float = 0.60      # verified-only scenes → run less often
        self._verified_at: Dict[str, float] = {}    # track_id → last ACCEPT wall-clock
        self._identity_ttl: float = 3.0
        self._last_worker_run: float = 0.0
        self._worker_errors: int = 0   # persistent inference failures (observability)

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

        # Fresh latency stats per session, sampled at the display cadence.
        self._latency_logger.reset()
        self._latency_thread = threading.Thread(
            target=self._latency_loop,
            name="LatencySampler",
            daemon=True,
        )
        self._latency_thread.start()

        # The recognition worker fully controls inference cadence, so disable
        # the service's internal frame-skip (every worker call runs the full
        # pipeline; the worker decides WHEN to run it).
        self._service.frame_skip = 1
        self._verified_at.clear()
        self._last_worker_run = 0.0
        self._worker_errors = 0
        self._worker_thread = threading.Thread(
            target=self._recognition_worker,
            name="RecognitionWorker",
            daemon=True,
        )
        self._worker_thread.start()
        return True

    def stop(self) -> None:
        """Stop recognition and release camera."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
        if self._latency_thread and self._latency_thread.is_alive():
            self._latency_thread.join(timeout=1.0)
        self._worker_thread = None
        self._latency_thread = None
        self._verified_at.clear()
        if self._cam:
            try:
                self._cam.release()
            except Exception:
                pass
            self._cam = None
        self._status = "STOPPED"
        self._reconnect_attempts = 0
        
        # Clear global buffers
        frame_buffer.clear()
        results_buffer.clear()

    # ── Background capture loop ──────────────────────────────

    def _capture_loop(self) -> None:
        """Capture frames and publish the latest RAW frame to the buffer.

        Capture is decoupled from AI inference: this thread only reads the
        camera and keeps the shared ``frame_buffer`` fresh at capture rate,
        so the displayed video is always the most recent frame. Inference
        runs in ``_recognition_worker`` at its own cadence and never blocks
        the video feed. Old frames are dropped (latest-frame-only buffer),
        so there is never a backlog.
        """
        last_frame_time = time.time()
        fps_alpha = 0.9
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

                # Update capture FPS
                dt = now - last_frame_time
                if dt > 0:
                    instant_fps = 1.0 / dt
                    with self._lock:
                        self._fps = fps_alpha * self._fps + (1 - fps_alpha) * instant_fps
                last_frame_time = now

                # Publish the latest RAW frame (drops any older unread frame)
                frame_buffer.put(frame)

                with self._lock:
                    self._frame_count += 1
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

    # ── Recognition worker (independent of capture) ───────────

    def _recognition_worker(self) -> None:
        """Run the AMFR pipeline on the latest frame at a controlled cadence.

        - Pulls the latest RAW frame from the shared buffer (never queues).
        - Runs the full pipeline on a 320×240 downscale.
        - Scales result bboxes back to display resolution.
        - Caches ACCEPTED identities per track_id; while every active track
          is verified and fresh, the worker idles longer (``_verified_interval``)
          instead of re-running the expensive pipeline on every frame.
        - Publishes results to ``results_buffer`` for the display loop.
        """
        last_ai_time = time.time()
        fps_alpha = 0.9

        while self._running:
            now = time.time()
            elapsed = now - self._last_worker_run

            # Adaptive cadence: verified-only scenes skip the full pipeline
            interval = self._verified_interval if self._only_verified_tracks() else self._worker_interval
            if elapsed < interval:
                time.sleep(0.02)
                continue

            frame = frame_buffer.get()
            if frame is None:
                time.sleep(0.02)
                continue

            self._last_worker_run = time.time()
            pipeline_start = time.time()
            try:
                small_frame = cv2.resize(frame, AI_PROCESS_SIZE, interpolation=cv2.INTER_LINEAR)
                _, results = self._service.process_frame_detailed(small_frame)
                pipeline_latency = (time.time() - pipeline_start) * 1000  # ms

                # Scale bbox coordinates back to the raw (display) frame size
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

                # Track verified identities per track_id (drives adaptive cadence)
                now_ts = time.time()
                for r in results:
                    tid = r.get("track_id")
                    if tid and r.get("amfr_decision") == AMFRDecision.ACCEPT.value:
                        self._verified_at[tid] = now_ts
                # Prune stale entries so a departed person reverts to normal cadence
                stale = [t for t, ts in self._verified_at.items() if now_ts - ts > self._identity_ttl]
                for t in stale:
                    self._verified_at.pop(t, None)

                # Publish latest results (latest-only buffer — never a queue)
                results_buffer.put(results)

                # AI FPS + latency
                ai_now = time.time()
                ai_dt = ai_now - last_ai_time
                if ai_dt > 0:
                    instant_ai_fps = 1.0 / ai_dt
                    with self._lock:
                        self._ai_fps = fps_alpha * self._ai_fps + (1 - fps_alpha) * instant_ai_fps
                last_ai_time = ai_now

                with self._lock:
                    self._people_count = len(results)
                    self._pipeline_latency = pipeline_latency

            except Exception as e:
                # Inference errors are counted, not surfaced as a camera status
                # change — the capture loop owns LIVE/ERROR/DISCONNECTED state.
                # A transient inference failure must never freeze the feed.
                with self._lock:
                    self._error = str(e)
                    self._worker_errors += 1
                time.sleep(0.5)

    def _only_verified_tracks(self) -> bool:
        """True when every active track is a fresh, verified (ACCEPTED) identity.

        When true, the worker uses the slower ``_verified_interval`` cadence
        instead of running the full pipeline every ``_worker_interval`` — the
        key track-based recognition caching optimisation.
        """
        if not self._verified_at:
            return False
        latest = results_buffer.get() or []
        if not latest:
            return False
        now = time.time()
        for r in latest:
            tid = r.get("track_id")
            if not tid or tid not in self._verified_at:
                return False
            if now - self._verified_at[tid] > self._identity_ttl:
                return False
        return True

    # ── Latency sampling ─────────────────────────────────────

    def _latency_loop(self) -> None:
        """Sample E2E frame latency at the display cadence while running.

        Reads the shared frame buffer via ``frame_buffer.get_with_meta()``
        and records ``now - put_timestamp`` — the age of the latest frame
        in the buffer at read time (capture → display). The capture loop
        puts at capture rate (independent of AI inference), so this is a
        faithful E2E proxy consistent with the benchmark methodology. Runs
        as its own daemon thread so the cadence stays regular.

        Only records while ``LIVE``: during DISCONNECTED/RECONNECTING the
        capture loop stops putting frames, so the buffer would hold a stale
        frame and ``now - ts`` would grow unboundedly, polluting the stats.
        """
        while self._running:
            time.sleep(LATENCY_SAMPLE_CADENCE)
            if self._status != "LIVE":
                continue
            _, _, ts = frame_buffer.get_with_meta()
            if ts is not None:
                self._latency_logger.record((time.time() - ts) * 1000.0)

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
            department = r.get("department", "")
            risk_score = r.get("risk_score", 0.0)
            liveness_score = r.get("liveness_score", 0.0)
            is_known = r.get("is_known", False)
            attended = r.get("attendance_marked", False)

            # Display name: prefer database name, fall back to FAISS name
            display_name = emp_name if emp_name and emp_name != "Unknown" else name

            # Confidence + liveness summary line for known/accept boxes
            detail_line = ""
            if risk_score:
                detail_line = f"\u2022 {risk_score:.0%} conf"
                if liveness_score:
                    detail_line += f" \u2022 live {liveness_score:.0%}"

            # Determine visual treatment based on AMFR decision
            if decision == AMFRDecision.ACCEPT.value:
                color = (50, 200, 50)       # Green
                status_text = "ALREADY PRESENT" if attended else "PRESENT"
                label = f"\u2713 {display_name}"
                sublines = [status_text]
                if emp_id is not None:
                    sublines.insert(0, f"ID: {name}")
                if department:
                    sublines.insert(0, f"{department}")
                if detail_line:
                    sublines.append(detail_line)

            elif decision == AMFRDecision.REJECT_SPOOF.value:
                color = (50, 50, 200)       # Red
                label = "\u26a0 SPOOF DETECTED"
                sublines = ["Attendance Rejected"]

            elif decision == AMFRDecision.BORDERLINE.value:
                color = (50, 180, 200)      # Yellow (BGR)
                label = f"{display_name}?"
                sublines = ["COLLECTING FRAMES..."]
                if department:
                    sublines.insert(0, f"{department}")

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
                if department:
                    sublines.insert(0, f"{department}")
                if detail_line:
                    sublines.append(detail_line)

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
    def worker_errors(self) -> int:
        with self._lock:
            return self._worker_errors

    @property
    def resolution(self) -> str:
        if self._cam and self._cam.is_opened():
            try:
                w, h = self._cam.get_resolution()
                return f"{w}x{h}"
            except Exception:
                pass
        return "N/A"

    # ── Latency accessors ────────────────────────────────────

    def latency_stats(self) -> Dict:
        """Rolling E2E frame-latency stats (count/p50_ms/p95_ms/avg_ms/last_ms)."""
        return self._latency_logger.stats()


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
    """Start the camera and recognition pipeline with CameraOwner."""
    camera_owner = CameraOwner()

    # Stop any existing pipeline first and release stale ownership.
    # This guarantees START→STOP→START always works even if a previous
    # run left the CameraOwner in an ACQUIRED state.
    _stop_recognition(quiet=True)

    # Now check if we can acquire the camera
    if not camera_owner.can_acquire():
        st.error("Camera is already in use. Please stop the current session first.")
        return

    # Refresh camera cache
    st.session_state.pc_cameras_cache = scan_local_cameras()

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
            # Acquire camera ownership
            if camera_owner.acquire(pipeline._cam, pipeline):
                st.session_state.pipeline = pipeline
                st.session_state.camera_manager_active = True
                st.success("\u2705 Camera started — recognition running")
            else:
                st.error("Failed to acquire camera ownership")
                pipeline.stop()
        else:
            st.error(f"\u274c Failed to start: {pipeline.error}")

    st.rerun()


def _stop_recognition(quiet: bool = False) -> None:
    """Stop the camera and recognition pipeline.

    Args:
        quiet: If True, skip the "Camera stopped" info message. Used when
            stopping as part of a START (to release stale ownership).
    """
    camera_owner = CameraOwner()
    owned = camera_owner.pipeline
    session_pipeline = st.session_state.pipeline

    # Stop + release the owned pipeline/camera via the owner (avoids
    # double-stopping the same pipeline). Teardown happens outside the
    # owner's state lock, so this is safe even during a START cycle.
    camera_owner.release()

    # Defensive fallback: stop a session pipeline the owner does NOT hold
    # (unusual/stale state). Skipped when the owner already stopped it.
    if session_pipeline is not None and session_pipeline is not owned:
        session_pipeline.stop()

    st.session_state.pipeline = None
    st.session_state.camera_manager_active = False
    if not quiet:
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
if "camera_manager_active" not in st.session_state:
    st.session_state.camera_manager_active = False


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
    # Latest RAW frame + latest recognition results. Overlays are drawn at
    # DISPLAY time (on the most recent frame) so the video stays fluid at
    # capture rate while recognition overlays refresh at the AI cadence.
    raw_frame = frame_buffer.get()
    results = results_buffer.get()
    
    if results is None:
        results = []
    frame = pipeline._draw_overlays(raw_frame, results) if raw_frame is not None else None
    last_result = results[0] if results else None

    # Display FPS — measured at the rerun cadence (capture + recognition FPS
    # are shown separately in the status bar).
    _now = time.time()
    _prev = st.session_state.get("_live_display_ts", _now)
    st.session_state["_live_display_ts"] = _now
    _display_fps = 1.0 / (_now - _prev) if _now > _prev else 0.0

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
        st.markdown(f"**Display FPS:** {_display_fps:.1f}")
        st.markdown(f"**AI FPS:** {pipeline.ai_fps:.1f}")
        st.markdown(f"**People:** {pipeline.people_count}")

        _e2e = pipeline.latency_stats()
        if _e2e.get("count", 0):
            st.markdown(f"**E2E Latency:** {_e2e['p50_ms']:.1f} / {_e2e['p95_ms']:.1f} ms (P50/P95)")
        else:
            st.markdown("**E2E Latency:** measuring…")

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
        st.markdown(f"**AI FPS:** {pipeline.ai_fps:.1f}")
    with status_cols[3]:
        _e2e = pipeline.latency_stats()
        if _e2e.get("count", 0):
            st.markdown(f"**E2E:** {_e2e['p50_ms']:.1f}/{_e2e['p95_ms']:.1f} ms")
        else:
            st.markdown("**E2E:** — ms")

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
        st.markdown(f"**AI FPS:** {pipeline.ai_fps:.1f}")
        st.markdown(f"**Resolution:** {pipeline.resolution}")
        st.markdown(f"**People detected:** {pipeline.people_count}")
        st.markdown(f"**Frames processed:** {pipeline.frame_count}")
        if pipeline.worker_errors:
            st.warning(f"\u26a0\ufe0f Worker errors (transient): {pipeline.worker_errors}")
        try:
            import psutil
            st.markdown(f"**CPU:** {psutil.cpu_percent(interval=None):.0f}% · "
                        f"**RAM:** {psutil.virtual_memory().percent:.0f}%")
        except Exception:
            pass  # psutil optional — skip CPU/RAM monitoring if unavailable
        _e2e = pipeline.latency_stats()
        if _e2e.get("count", 0):
            st.markdown(f"**E2E Latency (P50/P95):** {_e2e['p50_ms']:.1f} / "
                        f"{_e2e['p95_ms']:.1f} ms ({_e2e['count']:.0f} samples)")
        else:
            st.markdown("**E2E Latency (P50/P95):** measuring…")
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
