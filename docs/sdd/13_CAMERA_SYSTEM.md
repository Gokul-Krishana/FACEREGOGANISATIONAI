# Section 13 — Camera System

## 13.1 Architecture Overview

```
        CameraSource (ABC)  ← camera/base.py
            ▲        ▲        ▲        ▲        ▲
   ┌────────┘        │        │        │        └───────────────┐
   │                 │        │        │                        │
WebcamSource    USBAnySource AndroidWiFi iPhoneWiFi        IPCameraSource
(camera/webcam.py) (webcam.py)  │      (phone.py)            (phone.py)
                   └────────────┼───────────────┐
                           AndroidUSB       iPhoneUSB
                            (phone.py)       (phone.py)

   create_camera(source_type, **kwargs)   ← camera/selector.py (FACTORY)
        │
        ▼
   LiveRecognitionPipeline (dashboard 04_Live.py)
   ├─ capture thread      → frame_buffer (latest frame)
   ├─ recognition worker  → AMFR pipeline → results_buffer
   └─ latency sampler     → LatencyLogger
```

## 13.2 Component-by-Component

### Camera Manager / Factory (`camera/selector.py`)
`CAMERA_REGISTRY` maps slugs → classes:

| Slug | Class | Transport |
|------|-------|-----------|
| `webcam` | `WebcamSource` | DirectShow → MSMF → Default |
| `usb_auto` | `USBAnySource` | auto-scan indices 0–9 |
| `android_usb` | `AndroidUSBSource` | DroidCam USB (Wi-Fi fallback) |
| `android_wifi` | `AndroidWiFiSource` | IP Webcam HTTP MJPEG |
| `iphone_usb` | `iPhoneUSBSource` | EpocCam virtual DirectShow |
| `iphone_wifi` | `iPhoneWiFiSource` | EpocCam RTSP/HTTP |
| `ip_camera` | `IPCameraSource` | generic RTSP/HTTP/MJPEG |

Plus CLI selector (`select_camera_cli`), Streamlit selector
(`select_camera_ui`), and probing helper (`get_available_cameras`).

### Camera Owner (`dashboard/camera_owner.py`)
A **thread-safe singleton** enforcing single camera ownership:
- State machine: `FREE` → `ACQUIRED` → `FREE` (with `RELEASING` transition).
- `acquire(camera, pipeline)` fails if not FREE.
- `release()` — teardown runs **outside** the state lock so a slow
  `pipeline.stop()` (up to ~3 s join) never blocks concurrent acquire checks.
- Survives Streamlit reruns (pipeline stored in `st.session_state`).

### Frame Buffer (`dashboard/frame_buffer.py`)
`FrameBuffer(maxlen=1)` — **latest-frame-only**:
- `put()` drops any unread frame; never blocks; assigns frame_id + timestamp.
- `get()` / `get_with_meta()` / `try_get()` non-blocking.
- `close()` rejects new frames (clean STOP).
`ResultsBuffer` — same semantics for recognition results (list of dicts).

### Capture Thread (`LiveRecognitionPipeline._capture_loop`)
- Reads camera at native rate; publishes latest raw frame to `frame_buffer`.
- Maintains EMA capture FPS; tracks status LIVE/DISCONNECTED.
- **Reconnect logic:** if the loop exits, attempts up to 5 reconnects
  (2 s delay, reopen + reconfigure) before `DISCONNECTED`.

### AI Worker (`LiveRecognitionPipeline._recognition_worker`)
- Runs **independently** of capture — display never blocks on AI.
- Downscales to 320×240 (`AI_PROCESS_SIZE`), runs the full AMFR pipeline,
  scales bboxes back to display resolution.
- **Adaptive cadence:** normal 0.10 s interval; when every active track is a
  fresh verified (ACCEPTED) identity, interval relaxes to 0.60 s
  (`_verified_interval`) — the recognition cache optimization.
- Publishes to `results_buffer`; tracks AI FPS + pipeline latency.
- Inference errors are **counted, not fatal** — the feed never freezes.

### Display Thread (Streamlit UI loop)
- `has_frame()` then `get()` from frame buffer; overlays drawn at display
  time from the latest results (video stays fluid at capture rate).
- Status bar shows capture FPS, AI FPS, latency, people count, worker errors.

### Recognition Cache
- `_verified_at: Dict[track_id, last_accept_time]` — drives adaptive cadence.
- `_identity_ttl` (`IDENTITY_TTL`, default 3 s) — stale entries pruned so a
  departed person reverts to normal cadence.
- `EmployeeService` name→id cache in CLI `LiveDetection`.

### Multi-Camera
- Schema supports a `cameras` table (CRUD via API) and per-camera pipeline
  instances sharing models (`with_shared_models`).
- Dashboard Live page runs **one active pipeline** at a time (CameraOwner);
  multi-camera operation is achieved by running multiple pipeline instances
  (supported by the API/camera table) — the dashboard UI is single-camera.

### Camera Switching & Reconnect
- Switching: STOP (release via CameraOwner) → START (fresh pipeline + camera).
- Reconnect: auto in `_capture_loop` (5 attempts) with status badges
  CONNECTING/RECONNECTING/DISCONNECTED.

## 13.3 Camera Cap & Performance

| Setting | Value | Why |
|---------|-------|-----|
| Resolution | 640×480 (capture) | sharp display |
| AI downscale | 320×240 | 4× faster inference |
| FPS cap | 15 (via `CAP_PROP_FPS`) | less USB bandwidth |
| Backend fallback | DirectShow → MSMF → Default | Windows compatibility |

## 13.4 Phone Camera Auto-Discovery (`camera/discovery.py`)

- Detects the local `/24` subnet by connecting a UDP socket to 8.8.8.8.
- Probes IPs 1..254 in parallel (50 workers) on ports **8080** (IP Webcam /
  EpocCam) and **4747** (DroidCam).
- Identifies services by HTTP response signatures (title/Server/body text).
- Returns deduplicated `DiscoveredCamera(source_type, display_name, stream_url, ip, port)`.
- Full scan ~8–10 s; exposed in Live page "Scan Cameras".

## 13.5 Synthetic Camera (`camera/fake.py`)

`FakeCameraSource` generates gradient + moving-disc frames at a target FPS
with optional jitter — used by `fake_camera_validation.py` and tests to
validate the camera→buffer→display pipeline with no hardware.

---

*References: `camera/*`, `dashboard/camera_owner.py`, `dashboard/frame_buffer.py`,
`dashboard/latency_logger.py`, `dashboard/pages/04_Live.py`,
`tests/test_camera_owner.py`, `tests/test_frame_buffer.py`*
