"""
Live Camera Manager — API-side camera sessions
==============================================

One authoritative owner per camera for the FastAPI process, mirroring the
architecture proven on the Streamlit Live page:

    camera -> capture thread -> latest-frame buffer (capacity 1)
           -> independent AI worker (RecognitionService, 320x240)
           -> recognition events -> WebSocket manager
           -> MJPEG generator (annotated or raw latest frame)

Invariants:

- Exactly one session per key; starting an already-running key is a no-op.
- The capture thread NEVER waits on AI; the display (MJPEG) NEVER waits
  on inference — consumers always get the newest frame.
- Frames carry timestamps/sequence numbers; overlays expire when their
  track disappears or their results go stale.
- STOP -> START is safe: every start builds fresh threads and camera
  handles; stop joins threads and releases the camera even on errors.

Usage::

    from services.live_camera_manager import live_camera_manager

    live_camera_manager.start("local-0", source_type="webcam", device_id=0)
    for chunk in live_camera_manager.mjpeg("local-0", annotate=True):
        ...
    live_camera_manager.stop("local-0")
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

from camera.base import CameraSource
from camera.selector import create_camera
from utils.logging_setup import get_logger

logger = get_logger(__name__)

AI_PROCESS_SIZE = (320, 240)
RESULTS_TTL = 2.0  # seconds before stale overlays are dropped


class LatestFrameBuffer:
    """Thread-safe single-slot frame buffer (newest wins, never queues)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._ts: Optional[float] = None
        self._seq = 0
        self._dropped = 0

    def put(self, frame: np.ndarray) -> None:
        with self._lock:
            if self._frame is not None:
                self._dropped += 1
            self._frame = frame
            self._ts = time.time()
            self._seq += 1

    def get(self) -> Tuple[Optional[np.ndarray], Optional[float], int]:
        with self._lock:
            return self._frame, self._ts, self._seq

    @property
    def dropped(self) -> int:
        with self._lock:
            return self._dropped


class CameraSession:
    """A single camera + recognition pipeline running in background threads."""

    def __init__(
        self,
        key: str,
        source_type: str,
        camera_kwargs: dict,
        service,  # RecognitionService (shared models)
        event_sink: Optional[Callable[[dict], None]] = None,
    ) -> None:
        self.key = key
        self.source_type = source_type
        self.camera_kwargs = camera_kwargs
        self._service = service
        self._event_sink = event_sink
        self._cam: Optional[CameraSource] = None
        self._running = False
        self._lock = threading.Lock()

        self.buffer = LatestFrameBuffer()
        self._results: List[dict] = []
        self._results_ts: float = 0.0
        self._results_lock = threading.Lock()

        self.status = "STOPPED"
        self.error: Optional[str] = None
        self.capture_fps = 0.0
        self.ai_fps = 0.0
        self.last_latency_ms = 0.0
        self.frame_count = 0
        self._threads: List[threading.Thread] = []
        self._last_event_at: Dict[str, float] = {}

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> bool:
        if self._running:
            return True
        try:
            self._cam = create_camera(self.source_type, **self.camera_kwargs)
            if self._cam is None or not self._cam.open():
                self.error = "Could not open camera - check connection/index"
                self.status = "ERROR"
                self._cam = None
                return False
            self._cam.set_resolution(640, 480)
        except Exception as exc:
            self.error = str(exc)
            self.status = "ERROR"
            self._cam = None
            return False

        self._running = True
        self.error = None
        self.status = "CONNECTING"
        self._threads = [
            threading.Thread(target=self._capture_loop, name=f"cap-{self.key}", daemon=True),
            threading.Thread(target=self._ai_loop, name=f"ai-{self.key}", daemon=True),
        ]
        for t in self._threads:
            t.start()
        return True

    def stop(self) -> None:
        self._running = False
        for t in self._threads:
            if t.is_alive():
                t.join(timeout=3.0)
        self._threads = []
        if self._cam is not None:
            try:
                self._cam.release()
            except Exception:
                pass
            self._cam = None
        self.status = "STOPPED"
        with self._results_lock:
            self._results = []
        self._last_event_at.clear()

    @property
    def running(self) -> bool:
        return self._running

    # ── Background capture ───────────────────────────────────

    def _capture_loop(self) -> None:
        last_t = time.time()
        alpha = 0.9
        consecutive_failures = 0
        reconnect_backoff = 1.0

        while self._running:
            # Reconnect if camera was closed or disconnected (CCTV/RTSP stream loss)
            cam_is_open = False
            if self._cam is not None:
                if hasattr(self._cam, "is_opened"):
                    cam_is_open = self._cam.is_opened()
                else:
                    cam_is_open = not getattr(self._cam, "released", False)

            if self._cam is None or not cam_is_open:
                with self._lock:
                    self.status = "RECONNECTING"
                time.sleep(reconnect_backoff)
                reconnect_backoff = min(reconnect_backoff * 1.5, 10.0)
                try:
                    if self._cam is not None:
                        try:
                            self._cam.release()
                        except Exception:
                            pass
                    self._cam = create_camera(self.source_type, **self.camera_kwargs)
                    if self._cam and self._cam.open():
                        self.error = None
                        with self._lock:
                            self.status = "LIVE"
                        reconnect_backoff = 1.0
                        consecutive_failures = 0
                    else:
                        continue
                except Exception as exc:
                    with self._lock:
                        self.error = f"Reconnection error: {exc}"
                    continue

            try:
                ok, frame = self._cam.read()
                if not ok or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures > 20:  # ~1.0s of continuous failed reads
                        with self._lock:
                            self.status = "RECONNECTING"
                            self.error = "Camera stream lost or stalled; reconnecting..."
                        try:
                            self._cam.release()
                        except Exception:
                            pass
                        self._cam = None
                        time.sleep(0.5)
                        continue
                    if self.status == "LIVE":
                        self.status = "DISCONNECTED"
                    time.sleep(0.05)
                    continue

                consecutive_failures = 0
                now = time.time()
                dt = now - last_t
                last_t = now
                if dt > 0:
                    with self._lock:
                        self.capture_fps = alpha * self.capture_fps + (1 - alpha) * (1.0 / dt)
                self.buffer.put(frame)
                with self._lock:
                    self.frame_count += 1
                    self.status = "LIVE"
                    self.error = None
            except Exception as exc:
                with self._lock:
                    self.error = str(exc)
                    self.status = "ERROR"
                time.sleep(0.5)

    # ── Independent AI worker ────────────────────────────────

    def _ai_loop(self) -> None:
        last_run = 0.0
        last_ai_t = time.time()
        alpha = 0.9
        while self._running:
            now = time.time()
            if now - last_run < 0.10:  # ~10 AI runs/s max
                time.sleep(0.02)
                continue
            frame, _, _ = self.buffer.get()
            if frame is None:
                time.sleep(0.02)
                continue
            last_run = time.time()
            t0 = time.time()
            try:
                small = cv2.resize(frame, AI_PROCESS_SIZE, interpolation=cv2.INTER_LINEAR)
                _, results = self._service.process_frame_detailed(small)
            except Exception as exc:
                logger.warning("AI worker error on %s: %s", self.key, exc)
                with self._lock:
                    self.error = str(exc)
                time.sleep(0.5)
                continue

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

            latency = (time.time() - t0) * 1000.0
            with self._results_lock:
                self._results = results
                self._results_ts = time.time()
            ai_now = time.time()
            dt = ai_now - last_ai_t
            last_ai_t = ai_now
            if dt > 0:
                with self._lock:
                    self.ai_fps = alpha * self.ai_fps + (1 - alpha) * (1.0 / dt)
                    self.last_latency_ms = latency

            self._publish_events(results, latency)

    def _publish_events(self, results: List[dict], latency_ms: float) -> None:
        """Throttled recognition events to the WebSocket layer."""
        if self._event_sink is None:
            return
        now = time.time()
        for r in results:
            track = r.get("track_id") or r.get("name") or "unknown"
            decision = r.get("amfr_decision")
            # Only meaningful decisions are broadcast, at most 1/s per track
            if decision not in ("ACCEPT", "REJECT_SPOOF"):
                continue
            if now - self._last_event_at.get(str(track), 0.0) < 1.0:
                continue
            self._last_event_at[str(track)] = now
            try:
                self._event_sink(
                    {
                        "type": "recognition",
                        "camera_key": self.key,
                        "track_id": track,
                        "student_name": r.get("emp_name") or r.get("name"),
                        "amfr_decision": decision,
                        "confidence": r.get("risk_score", r.get("confidence")),
                        "liveness_score": r.get("liveness_score"),
                        "quality_score": r.get("quality_score"),
                        "attendance_marked": bool(r.get("attendance_marked")),
                        "latency_ms": round(latency_ms, 1),
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                )
            except Exception:
                logger.debug("event publish failed for %s", self.key, exc_info=True)

    # ── Snapshot access ──────────────────────────────────────

    def latest_results(self) -> List[dict]:
        with self._results_lock:
            if time.time() - self._results_ts > RESULTS_TTL:
                return []
            return list(self._results)

    def status_payload(self) -> dict:
        with self._lock:
            _, ts, seq = self.buffer.get()
            frame_age_ms = round((time.time() - ts) * 1000.0, 1) if ts else 0.0
            return {
                "key": self.key,
                "source_type": self.source_type,
                "camera_kwargs": self.camera_kwargs,
                "status": self.status,
                "error": self.error,
                "capture_fps": round(self.capture_fps, 1),
                "ai_fps": round(self.ai_fps, 1),
                "last_latency_ms": round(self.last_latency_ms, 1),
                "frame_count": self.frame_count,
                "frame_seq": seq,
                "frame_age_ms": frame_age_ms,
                "dropped_frames": self.buffer.dropped,
            }

    def annotated_frame(self) -> Optional[np.ndarray]:
        """Latest raw frame with recognition overlays (if any, and fresh)."""
        frame, _, _ = self.buffer.get()
        if frame is None:
            return None
        results = self.latest_results()
        if not results:
            return frame
        out = frame.copy()
        for r in results:
            bbox = r.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = bbox[:4]
            decision = r.get("amfr_decision", "")
            color = {
                "ACCEPT": (60, 200, 60),
                "REJECT_SPOOF": (40, 40, 230),
            }.get(decision, (200, 180, 40))
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            name = r.get("emp_name") or r.get("name") or "UNKNOWN"
            label = f"{name} {decision}" if decision else str(name)
            cv2.putText(out, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        return out


class LiveCameraManager:
    """Process-wide registry of camera sessions (one owner per key)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, CameraSession] = {}
        self._sessions_lock = threading.Lock()
        self.event_sink: Optional[Callable[[dict], None]] = None
        self._service = None  # lazy shared RecognitionService

    def _get_service(self):
        if self._service is None:
            from services.recognition_service import RecognitionService

            self._service = RecognitionService()
        return self._service

    def start(
        self, key: str, source_type: str = "webcam", camera_kwargs: Optional[dict] = None
    ) -> CameraSession:
        with self._sessions_lock:
            existing = self._sessions.get(key)
            if existing is not None and existing.running:
                return existing
            session = CameraSession(
                key=key,
                source_type=source_type,
                camera_kwargs=camera_kwargs or {},
                service=self._get_service(),
                event_sink=self.event_sink,
            )
            self._sessions[key] = session
        ok = session.start()
        if not ok:
            logger.warning("Failed to start camera session %s: %s", key, session.error)
        return session

    def stop(self, key: str) -> bool:
        with self._sessions_lock:
            session = self._sessions.pop(key, None)
        if session is None:
            return False
        session.stop()
        return True

    def stop_all(self) -> None:
        with self._sessions_lock:
            keys = list(self._sessions.keys())
        for key in keys:
            self.stop(key)

    def get(self, key: str) -> Optional[CameraSession]:
        with self._sessions_lock:
            return self._sessions.get(key)

    def list_sessions(self) -> List[dict]:
        with self._sessions_lock:
            sessions = list(self._sessions.values())
        return [s.status_payload() for s in sessions]

    def mjpeg(self, key: str, fps: int = 15, annotate: bool = True):
        """Generator producing multipart/x-mixed-replace MJPEG chunks."""
        interval = 1.0 / max(1, min(fps, 30))
        while True:
            session = self.get(key)
            if session is None:
                time.sleep(0.2)
                continue
            frame = session.annotated_frame() if annotate else session.buffer.get()[0]
            if frame is None:
                time.sleep(0.05)
                continue
            ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                time.sleep(0.05)
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
            time.sleep(interval)


live_camera_manager = LiveCameraManager()
