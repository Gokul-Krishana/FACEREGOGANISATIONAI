# Section 2 — System Architecture

## 2.1 Architecture at a Glance (simple explanation)

Think of the system as a **conveyor belt with quality inspectors**:

1. **Camera** takes pictures continuously.
2. **Detector** finds where people are (YOLO11).
3. **Tracker** gives each person an ID so the same person isn't counted twice.
4. **Face finder + quality check** zooms in on faces and checks they're usable (not blurry/dark).
5. **Liveness check** makes sure it's a real person, not a photo or screen.
6. **Face "fingerprint"** (ArcFace embedding) is compared against the database (FAISS).
7. **Decision engine (AMFR)** combines everything into one risk score.
8. **Attendance** is marked for accepted identities.
9. **Database** stores everything; **Dashboard** displays it; **Reports** analyze it.

## 2.2 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                  │
│  ┌─────────────────────┐        ┌───────────────────────────────────┐  │
│  │  Streamlit Dashboard │        │  External Integrators (REST/WS)  │  │
│  │  (10 pages, 8501)    │        │  curl / scripts / mobile app     │  │
│  └──────────┬───────────┘        └────────────────┬──────────────────┘  │
│             │                                     │                     │
└─────────────┼─────────────────────────────────────┼─────────────────────┘
              │ HTTP/WebSocket                      │ HTTPS (FastAPI)
              ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                     FASTAPI  (api/main.py)                        │  │
│  │   Auth (JWT/MFA/OIDC) • RBAC • CRUD • Jobs • Bulk • Analytics     │  │
│  │   Rate limiting • Security headers • Audit • Prometheus metrics   │  │
│  └───────────────┬───────────────────────────────┬───────────────────┘  │
│                  │                               │                      │
│  ┌───────────────▼───────────────────────────────▼───────────────────┐  │
│  │                     SERVICE LAYER (services/)                     │  │
│  │   RecognitionService  AttendanceService  EmployeeService          │  │
│  │   UnknownFaceService  AuditService  BruteForceProtection          │  │
│  │   MFAService  OIDCService                                         │  │
│  └───────────────┬───────────────────────────────┬───────────────────┘  │
│                  │                               │                      │
│  ┌───────────────▼───────────────────────────────▼───────────────────┐  │
│  │                     AI PIPELINE (app/ + camera/)                   │  │
│  │   CameraSource ─► YOLO11 ─► Tracker ─► RetinaFace ─► Quality       │  │
│  │   ─► Liveness (5-factor) ─► ArcFace ─► FAISS ─► AMFR Engine        │  │
│  └───────────────┬───────────────────────────────┬───────────────────┘  │
│                  │                               │                      │
└──────────────────┼───────────────────────────────┼─────────────────────┘
                   │                               │
┌──────────────────▼─────────────┐   ┌─────────────▼─────────────────────┐
│        DATA LAYER               │   │         INFRASTRUCTURE             │
│  ┌───────────────────────────┐  │   │  Redis (cache, cooldown, state)    │
│  │ SQLite (dev) / PostgreSQL │  │   │  FAISS index (embeddings/)         │
│  │ (prod) via SQLAlchemy +   │  │   │  File storage (unknown_faces/,     │
│  │ Alembic migrations        │  │   │  uploads/, attendance CSV, logs/)  │
│  └───────────────────────────┘  │   └────────────────────────────────────┘
└──────────────────────────────────┘
```

## 2.3 The 8-Stage Pipeline (the core of the system)

```
Camera
  │  (frame @ up to 15 FPS)
  ▼
1. DETECTION — YOLO11n finds people       (app/face_detector.py)
  │  (person bounding boxes)
  ▼
2. TRACKING — IoU tracker assigns IDs      (app/tracking.py)
  │  (track_id per person)
  ▼
3. FACE DETECTION — RetinaFace finds faces + 5 landmarks (app/recognizer.py)
  │  (face bbox, landmarks, det_score)
  ▼
4. FACE QUALITY — blur/brightness/pose/size (app/face_quality.py)
  │  (0-1 quality score)
  ▼
5. LIVENESS — 5 factors: LBP texture, blink, motion, screen, deep CNN (app/liveness_detector.py + app/deep_liveness.py)
  │  (0-1 liveness score)
  ▼
6. EMBEDDING — ArcFace 512-D vector        (app/recognizer.py)
  │  (L2-normalized embedding)
  ▼
7. SEARCH — FAISS nearest neighbor         (app/enrollment.py)
  │  (name + distance + confidence)
  ▼
8. DECISION — AMFR engine combines all     (app/amfr_engine.py)
  │  (risk score → ACCEPT / BORDERLINE / LOW_CONFIDENCE / REJECT_SPOOF)
  ▼
ATTENDANCE — attendance.py + AttendanceService → DB
  ▼
DASHBOARD + REPORTS — Streamlit pages + API analytics
```

## 2.4 Module-by-Module Explanation

### 2.4.1 Camera Layer (`camera/`)
- `base.py` — abstract `CameraSource` interface (open/read/release/info).
- `webcam.py` — `WebcamSource` (DirectShow→MSMF fallback) and `USBAnySource` (auto-detect).
- `phone.py` — `AndroidWiFiSource`, `AndroidUSBSource`, `iPhoneWiFiSource`, `iPhoneUSBSource`, `IPCameraSource`.
- `selector.py` — `create_camera()` **factory** mapping slugs → classes; CLI + Streamlit selectors.
- `discovery.py` — scans the `/24` subnet for IP Webcam / DroidCam / EpocCam.
- `fake.py` — synthetic camera for hardware-free testing/benchmarks.

**Design note:** `WebcamSource`/`USBAnySource` are the *sole* owners of
`cv2.VideoCapture` — no other module opens raw camera devices.

### 2.4.2 Detection Layer (`app/face_detector.py`)
Wraps Ultralytics YOLO11 (`yolo11n.pt`, COCO). Returns only `person`
detections (COCO class 0) with bboxes ≥ confidence threshold.

### 2.4.3 Tracking Layer (`app/tracking.py`)
Custom **greedy IoU multi-object tracker**. `TrackState` accumulates per-
person score history (arcface distances, liveness, quality, decisions) and
computes `identity_stability`. Used by AMFR for temporal smoothing.

### 2.4.4 Face Detection & Embedding Layer (`app/recognizer.py`)
Wraps InsightFace `FaceAnalysis` (`buffalo_l` pack) — RetinaFace detection
+ ArcFace embedding. Exposes `detect_face()`, `extract_embedding()`,
`get_landmarks()`, `compute_similarity()`.

### 2.4.5 Quality Layer (`app/face_quality.py`)
`FaceQualityAssessment.assess()` — 6 metrics (blur, brightness, contrast,
face size, det score, pose) → weighted `overall` 0–1 score + `failure_reasons`.

### 2.4.6 Liveness Layer (`app/liveness_detector.py` + `app/deep_liveness.py`)
- `LivenessDetector` — software factors (texture LBP, blink EAR, motion,
  screen edges) with per-track state.
- `DeepLivenessDetector` — MiniFASNet ONNX (80×80 input, 3-class softmax)
  or a built-in numpy fallback CNN. Combined with weights:
  texture 0.15, blink 0.20, motion 0.15, screen 0.10, deep 0.40.

### 2.4.7 Search Layer (`app/enrollment.py`)
`FaceEnrollment` — FAISS index (flat/HNSW/IVF), metadata JSON, enroll/search/
remove-by-name/rename/clear/status. L2 distance → confidence mapping `1/(1+d²)`.

### 2.4.8 Decision Layer (`app/amfr_engine.py`)
`AMFREngine` — per-track liveness instances, quality + liveness + arcface
weighted risk score (0.45/0.35/0.20), hard liveness gate for spoof rejection.
`AMFRDecision`: ACCEPT, BORDERLINE, LOW_CONFIDENCE, REJECT_SPOOF, PENDING.

### 2.4.9 Attendance Layer
- `app/attendance.py` — CSV per-day logging (`AttendanceTracker`).
- `services/attendance_service.py` — DB + CSV dual write, dedupe per day.
- `api/attendance_service.py` — timetable-aware logic (class in session, grace period, enrollment checks).

### 2.4.10 Database Layer (`database/`)
- `database.py` — engine, sessionmaker, `init_db()` (Alembic → create_all fallback).
- `models.py` — 20 tables + 2 association tables (college schema).
- `repository.py` — repository pattern (Repo classes + `PageResult` pagination).

### 2.4.11 Service Layer (`services/`)
Business logic façade over repositories; used by both dashboard and API so
neither touches AI modules or repositories directly.

### 2.4.12 API Layer (`api/`)
FastAPI app (v2.0.0): auth (JWT, refresh rotation, MFA, OIDC), RBAC deps,
CRUD (students, employees, cameras, attendance), unknown faces, analytics,
WebSocket event stream, job queue, bulk operations, health/metrics.

### 2.4.13 Dashboard Layer (`dashboard/`)
Streamlit app: `app.py` (sidebar nav) + 10 pages. Live page runs
`LiveRecognitionPipeline` with `SharedModelResources` (models loaded once),
`CameraOwner` singleton, `FrameBuffer` (latest-frame-only), `LatencyLogger`.

## 2.5 Key Architectural Decisions (from source)

| Decision | Implementation | Benefit |
|----------|----------------|---------|
| Shared models | `SharedModelResources.load()` caches `RecognitionService`; `with_shared_models()` reuses YOLO/InsightFace/FAISS/AMFR | ~2 GB memory saved |
| Isolated state | Per-pipeline frame counters, FPS, session tracking | Multi-camera independence |
| Background threads | Capture loop + recognition worker + latency sampler (daemon) | UI never blocks |
| Downscaled AI | AI runs on 320×240, display at 640×480 (bboxes rescaled) | ~4× faster inference |
| Latest-frame buffer | `FrameBuffer(maxlen=1)` drops stale frames | No queue buildup on Streamlit reruns |
| Offline first | All models local; no cloud APIs | Privacy + cost |
| Single camera owner | `camera/webcam.py` owns `cv2.VideoCapture`; `CameraOwner` singleton enforces one active pipeline | No resource conflicts |

## 2.6 Runtime Process Topology

```
Process 1: streamlit run dashboard/app.py      (port 8501)
   └─ Live page: LiveRecognitionPipeline
        ├─ Thread: capture loop      → frame_buffer
        ├─ Thread: recognition worker → AMFR pipeline → results_buffer
        └─ Thread: latency sampler   → LatencyLogger

Process 2: uvicorn api.main:app               (port 8000)
   ├─ Job queue workers (asyncio, 3 workers)
   └─ WebSocket manager (event stream)

Process 3 (optional): Redis (cache/state) + PostgreSQL (prod DB)
```

---

*References: [`README.md`](../../README.md), [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md), `app/live_detection.py`, `dashboard/pages/04_Live.py`*
