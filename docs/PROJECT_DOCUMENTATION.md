# FaceRecognitionAI — Complete Software Design Document (Master)

> Single-file edition of the 30-section Software Design Document (SDD).
> Per-section files live in `docs/sdd/`. Generated directly from the
> repository source code — every statement is grounded in the actual
> implementation.

## Table of Contents

| # | Section | File |
|---|---------|------|
| 1 | PROJECT OVERVIEW | [docs/sdd/01_PROJECT_OVERVIEW.md](docs/sdd/01_PROJECT_OVERVIEW.md) |
| 2 | SYSTEM ARCHITECTURE | [docs/sdd/02_SYSTEM_ARCHITECTURE.md](docs/sdd/02_SYSTEM_ARCHITECTURE.md) |
| 3 | FOLDER STRUCTURE | [docs/sdd/03_FOLDER_STRUCTURE.md](docs/sdd/03_FOLDER_STRUCTURE.md) |
| 4 | FILE EXPLANATION | [docs/sdd/04_FILE_EXPLANATION.md](docs/sdd/04_FILE_EXPLANATION.md) |
| 5 | AI PIPELINE | [docs/sdd/05_AI_PIPELINE.md](docs/sdd/05_AI_PIPELINE.md) |
| 6 | MACHINE LEARNING MODELS | [docs/sdd/06_MACHINE_LEARNING_MODELS.md](docs/sdd/06_MACHINE_LEARNING_MODELS.md) |
| 7 | DATABASE | [docs/sdd/07_DATABASE.md](docs/sdd/07_DATABASE.md) |
| 8 | DATABASE SCHEMA | [docs/sdd/08_DATABASE_SCHEMA.md](docs/sdd/08_DATABASE_SCHEMA.md) |
| 9 | API DOCUMENTATION | [docs/sdd/09_API_DOCUMENTATION.md](docs/sdd/09_API_DOCUMENTATION.md) |
| 10 | STREAMLIT DASHBOARD | [docs/sdd/10_STREAMLIT_DASHBOARD.md](docs/sdd/10_STREAMLIT_DASHBOARD.md) |
| 11 | SECURITY | [docs/sdd/11_SECURITY.md](docs/sdd/11_SECURITY.md) |
| 12 | ATTENDANCE SYSTEM | [docs/sdd/12_ATTENDANCE_SYSTEM.md](docs/sdd/12_ATTENDANCE_SYSTEM.md) |
| 13 | CAMERA SYSTEM | [docs/sdd/13_CAMERA_SYSTEM.md](docs/sdd/13_CAMERA_SYSTEM.md) |
| 14 | PERFORMANCE | [docs/sdd/14_PERFORMANCE.md](docs/sdd/14_PERFORMANCE.md) |
| 15 | PACKAGES | [docs/sdd/15_PACKAGES.md](docs/sdd/15_PACKAGES.md) |
| 16 | CONFIGURATION | [docs/sdd/16_CONFIGURATION.md](docs/sdd/16_CONFIGURATION.md) |
| 17 | DEPLOYMENT | [docs/sdd/17_DEPLOYMENT.md](docs/sdd/17_DEPLOYMENT.md) |
| 18 | TESTING | [docs/sdd/18_TESTING.md](docs/sdd/18_TESTING.md) |
| 19 | BENCHMARKS | [docs/sdd/19_BENCHMARKS.md](docs/sdd/19_BENCHMARKS.md) |
| 20 | COMPLETE WORKFLOW | [docs/sdd/20_COMPLETE_WORKFLOW.md](docs/sdd/20_COMPLETE_WORKFLOW.md) |
| 21 | DATA FLOW | [docs/sdd/21_DATA_FLOW.md](docs/sdd/21_DATA_FLOW.md) |
| 22 | CLASS DIAGRAM | [docs/sdd/22_CLASS_DIAGRAM.md](docs/sdd/22_CLASS_DIAGRAM.md) |
| 23 | MODULE DIAGRAM | [docs/sdd/23_MODULE_DIAGRAM.md](docs/sdd/23_MODULE_DIAGRAM.md) |
| 24 | TECH STACK | [docs/sdd/24_TECH_STACK.md](docs/sdd/24_TECH_STACK.md) |
| 25 | WHY TECHNOLOGY | [docs/sdd/25_WHY_TECHNOLOGY.md](docs/sdd/25_WHY_TECHNOLOGY.md) |
| 26 | DESIGN PATTERNS | [docs/sdd/26_DESIGN_PATTERNS.md](docs/sdd/26_DESIGN_PATTERNS.md) |
| 27 | PROJECT FLOW | [docs/sdd/27_PROJECT_FLOW.md](docs/sdd/27_PROJECT_FLOW.md) |
| 28 | CODE QUALITY | [docs/sdd/28_CODE_QUALITY.md](docs/sdd/28_CODE_QUALITY.md) |
| 29 | PRODUCTION READINESS | [docs/sdd/29_PRODUCTION_READINESS.md](docs/sdd/29_PRODUCTION_READINESS.md) |
| 30 | FINAL SUMMARY | [docs/sdd/30_FINAL_SUMMARY.md](docs/sdd/30_FINAL_SUMMARY.md) |

---

<!-- Section: 01_PROJECT_OVERVIEW.md -->
# Section 1 — Project Overview

**FaceRecognitionAI — Real-Time Face Recognition & Automatic Attendance System**

---

## 1.1 Project Name

**FaceRecognitionAI** (also referred to as *Face Recognition AI*). A real-time
face recognition and automatic attendance management system designed for
college-scale deployment.

## 1.2 Project Goal

The goal of FaceRecognitionAI is to build a **fully offline, real-time face
recognition system** that automatically detects people in a camera feed,
verifies their identity using a multi-factor AI pipeline, and records their
attendance without any human intervention. It must be accurate enough to
prevent spoofing (photos, screens, masks) and scalable enough for a college
environment with hundreds of students and multiple cameras.

## 1.3 Problem Statement

Colleges and organizations rely on manual attendance (sign-in sheets, roll
calls, ID card swipes) which is:

- **Time-consuming** — a lecturer spends 5–10 minutes per class calling names.
- **Error-prone** — proxy attendance ("buddy signing"), missed marks, illegible handwriting.
- **Non-scalable** — manual processes break down with 100+ students.
- **Hard to audit** — paper records are easily lost or altered.

## 1.4 Existing Problems (in conventional solutions)

| Approach | Problems |
|----------|----------|
| Paper sign-in sheets | Proxy attendance, lost records, no analytics |
| RFID / ID-card swipe | Cards can be shared/stolen; requires hardware issuance |
| Fingerprint biometrics | Hygiene concerns, skin condition failures, expensive hardware |
| Cloud face-recognition APIs | Privacy risk (faces sent to third parties), recurring cost, **requires internet** — a hard blocker in many colleges |
| Basic webcam face detection | No anti-spoofing — a printed photo defeats it |

## 1.5 Proposed Solution

A **self-hosted, offline-first, multi-factor face recognition system**:

- Runs **entirely locally** — no cloud API calls after initial model download.
- Uses a **deep AI pipeline**: YOLO11 (person detection) → RetinaFace (face
  detection) → Face Quality → Liveness (5-factor anti-spoofing) → ArcFace
  (512-D embedding) → FAISS (vector search) → **AMFR** (Adaptive Multi-Factor
  Recognition decision engine).
- Includes a **Streamlit dashboard** (10 pages) for enrollment, live
  recognition, attendance, analytics, settings, and health monitoring.
- Exposes a **secure FastAPI REST layer** (JWT, RBAC, MFA, OIDC, rate
  limiting, audit logs) for enterprise integration.
- Supports **7 camera types** (webcam, USB auto, Android USB/Wi-Fi, iPhone
  USB/Wi-Fi, IP/RTSP) plus network auto-discovery.

## 1.6 Objectives

1. Automate attendance capture with **no manual roll call**.
2. Achieve **high recognition accuracy** (multi-factor scoring, not a single similarity threshold).
3. **Defeat presentation attacks** (printed photos, screen replays, video loops) via layered liveness.
4. Operate **100% offline** for privacy and cost.
5. Provide **real-time feedback** (FPS, overlays, live status) in the UI.
6. Provide **enterprise-grade security** for the web layer (auth, RBAC, audit).
7. Be **deployable by a college** on commodity Windows/Linux hardware or Docker.
8. Be **testable and verifiable** (490 automated tests, benchmark scripts).

## 1.7 Scope

### In scope
- Real-time person detection and face recognition from live camera feeds.
- Multi-factor liveness/anti-spoofing and an adaptive decision engine (AMFR).
- Face enrollment (single + bulk) with FAISS vector storage.
- Automatic and manual attendance marking, per-day and per-date queries.
- Unknown-face capture, review, and conversion-to-employee workflow.
- Streamlit dashboard: 10 pages covering the full operator lifecycle.
- Secure REST API: auth (local + OIDC + MFA), CRUD for students/employees/
  cameras/attendance, jobs, bulk operations, analytics, health, metrics.
- SQLite (dev) and PostgreSQL (prod) persistence with Alembic migrations.
- Docker / docker-compose deployment; GitHub Actions CI/CD.
- Backup & restore, seed, dedupe, and migration scripts.

### Out of scope / explicitly missing (verified from source)
- **FAISS deletion is not natively supported** — `FaceEnrollment.remove()`
  raises `NotImplementedError`; `remove_by_name()` works by rebuilding the
  index (O(N)), and raw embeddings are not stored independently (a production
  `.npy` store is recommended in the code comments).
- **The tracker is IoU-based, not a full MOT (ByteTrack) implementation** —
  the documentation name "ByteTrack" describes the *role* (multi-object
  tracking); the shipped code is a custom greedy IoU matcher (see §5.3).
- **Job queue handlers are placeholders** (`_batch_enroll_handler`,
  `_rebuild_index_handler`, `_cleanup_unknown_handler`) that simulate work.
- **Redis is optional** — every Redis path degrades gracefully when Redis is down.
- **On-site pilot validation** (real-person attendance, spoof artifacts,
  multi-classroom load) is not yet proven — see `FINAL_ACCEPTANCE_REPORT.md`
  and `docs/PILOT_DEPLOYMENT_PLAN.md`.

## 1.8 Features

| Feature | Description |
|---------|-------------|
| 🧠 Full AI Pipeline | YOLO11 → RetinaFace → Quality → Liveness → ArcFace → FAISS → AMFR |
| 🛡️ 5-Factor Liveness | Texture (LBP), blink (EAR), motion, screen-edge, deep CNN (MiniFASNet) |
| ⚖️ AMFR Decision Engine | Weighted risk score → ACCEPT / BORDERLINE / LOW_CONFIDENCE / REJECT_SPOOF |
| 📸 Multi-Camera Support | 7 source types + network auto-discovery (IP Webcam, DroidCam, EpocCam) |
| 🗄️ Vector Database | FAISS with flat / HNSW / IVF index types (tuned parameters) |
| 📊 Streamlit Dashboard | 10 pages: overview, employees, enroll, live, attendance, unknown, analytics, settings, health, about |
| 🔐 Secure REST API | 46 endpoints, JWT + refresh rotation, RBAC (7 roles), MFA (TOTP), OIDC |
| 📝 Audit Trail | Every action logged to `audit_logs` with actor, IP, severity |
| 🚫 Brute Force Protection | Per-username lockout (5 attempts / 30 min), per-IP rate limiting |
| 🧹 Unknown Face Lifecycle | Auto-save → review → convert to employee / ignore / delete; retention cleanup |
| 📈 Analytics | Daily/hourly attendance, top employees, accuracy, department distribution, confidence histogram |
| 🧪 Tested | 490 automated tests, benchmark + validation scripts |
| 🐳 Containerised | Multi-stage Dockerfile + docker-compose (PostgreSQL + Redis + app) |

## 1.9 Benefits

- **For the college:** accurate, tamper-resistant attendance; full audit trail; dashboards for lecturers and administrators; zero per-recognition cost.
- **For students:** no queues, no cards — walk in, get marked automatically.
- **For IT/admin:** single offline deployment; YAML-based configuration; health monitoring; scripted backup/restore; no cloud dependency.
- **For privacy:** face data never leaves the premises.

## 1.10 Real-World Applications

- 🏫 **Colleges/Universities** — automatic lecture/exam attendance.
- 🏢 **Corporate** — employee check-in and access logging.
- 🏭 **Manufacturing** — shift tracking and secure-area access.
- 🏥 **Healthcare** — staff attendance and visitor logging.
- 🚪 **Access control** — door-gate integration via the recognition event stream.
- 🏟️ **Events** — attendee presence verification.

## 1.11 Future Scope (identified from code TODOs + gap analysis)

1. **Native FAISS deletion** — store raw embeddings as `.npy` files so the
   index can be rebuilt faithfully (explicitly called out in `app/enrollment.py`).
2. **Real ByteTrack / SORT tracker** — replace the greedy IoU matcher for
   stronger multi-object tracking under occlusion.
3. **Real background jobs** — replace placeholder handlers with actual
   batch-enroll / index-rebuild / cleanup work (or swap to Celery + Redis).
4. **Multi-classroom deployment** — per-room cameras, timetables, and
   classroom-aware attendance (schema already supports it).
5. **ONNX export of YOLO/ArcFace** — further CPU inference speedups.
6. **Mobile attendance app** for students to view own records.
7. **GPU acceleration** for higher FPS with multiple simultaneous cameras.
8. **Data export / BI integration** — attendance data already has a CSV
   export path; BI dashboards could consume the REST API directly.

---

*References: [`README.md`](../../README.md), [`FINAL_ACCEPTANCE_REPORT.md`](../../FINAL_ACCEPTANCE_REPORT.md), [`docs/GAP_ANALYSIS_COLLEGE_SCALE.md`](../GAP_ANALYSIS_COLLEGE_SCALE.md), [`docs/PILOT_DEPLOYMENT_PLAN.md`](../PILOT_DEPLOYMENT_PLAN.md)*

---

<!-- Section: 02_SYSTEM_ARCHITECTURE.md -->
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

---

<!-- Section: 03_FOLDER_STRUCTURE.md -->
# Section 3 — Complete Folder Structure

## 3.1 Full Repository Tree (verified from source)

```
FaceRecognitionAI/
│
├── main.py                     # CLI entry point (live / image / enroll / test / debug)
├── requirements.txt            # Python dependencies
├── pytest.ini                  # pytest configuration
├── alembic.ini                 # Alembic migration config
├── Dockerfile                  # Multi-stage container build
├── docker-compose.yml          # App + PostgreSQL + Redis orchestration
├── run.bat / run.sh            # Convenience launchers
├── clear_cache.py              # Cache-clearing utility
├── README.md                   # Project readme
├── LICENSE                     # MIT license
│
├── app/                        # ⭐ Core AI pipeline (see 3.1.1)
│   ├── amfr_engine.py          #   AMFR decision engine
│   ├── face_detector.py        #   YOLO11 person detection
│   ├── face_quality.py         #   Face quality assessment
│   ├── liveness_detector.py    #   4 software liveness factors
│   ├── deep_liveness.py        #   MiniFASNet CNN anti-spoofing
│   ├── recognizer.py           #   RetinaFace + ArcFace
│   ├── enrollment.py           #   FAISS index management
│   ├── tracking.py             #   IoU multi-object tracker
│   ├── attendance.py           #   CSV attendance logging
│   └── live_detection.py       #   CLI pipeline orchestrator
│
├── recognition/                # Face alignment utilities
│   └── alignment.py            #   Landmark-based face alignment + CLAHE
│
├── camera/                     # Camera abstraction layer (see 3.1.2)
│   ├── base.py                 #   CameraSource ABC
│   ├── webcam.py               #   Webcam + USB auto-detect
│   ├── phone.py                #   Android/iPhone + IP cameras
│   ├── selector.py             #   Factory + CLI/Streamlit selectors
│   ├── discovery.py            #   Network camera discovery
│   └── fake.py                 #   Synthetic camera for testing
│
├── dashboard/                  # Streamlit UI (see 3.1.3)
│   ├── app.py                  #   Entry point + sidebar nav
│   ├── frame_buffer.py         #   Thread-safe latest-frame buffer
│   ├── camera_owner.py         #   Singleton camera ownership
│   ├── latency_logger.py       #   E2E latency statistics
│   └── pages/
│       ├── 01_Dashboard.py     #   Overview + stats
│       ├── 02_Employees.py     #   Employee CRUD
│       ├── 03_Enroll.py        #   Face enrollment
│       ├── 04_Live.py          #   Live recognition pipeline
│       ├── 05_Attendance.py    #   Attendance records + live camera
│       ├── 06_Unknown.py       #   Unknown face gallery
│       ├── 07_Analytics.py     #   Plotly charts
│       ├── 08_Settings.py      #   Config editor
│       ├── 09_Health.py        #   System health
│       └── 10_About.py         #   About & stack
│
├── services/                   # Business logic layer (see 3.1.4)
│   ├── recognition_service.py  #   Pipeline orchestrator (dashboard/API entry)
│   ├── attendance_service.py   #   Attendance marking + queries
│   ├── employee_service.py     #   Employee CRUD + FAISS sync
│   ├── unknown_face_service.py #   Unknown face lifecycle
│   ├── audit_service.py        #   Audit trail
│   ├── brute_force_protection.py
│   ├── mfa_service.py          #   TOTP MFA
│   └── oidc_service.py         #   SSO integration
│
├── api/                        # FastAPI REST layer (see 3.1.5)
│   ├── main.py                 #   App + all endpoints
│   ├── attendance_service.py   #   Timetable-aware attendance
│   ├── audit_service.py        #   API audit logging
│   ├── bulk_operations.py      #   CSV imports/exports
│   ├── job_queue.py            #   Async background jobs
│   ├── redis_client.py         #   Redis state helpers
│   └── websocket_manager.py    #   Real-time event stream
│
├── database/                   # ORM + repository (see 3.1.6)
│   ├── database.py             #   Engine, session, init_db
│   ├── models.py               #   All ORM models
│   └── repository.py           #   Repository pattern CRUD
│
├── config/                     # Configuration
│   ├── config.py               #   Central config (YAML + defaults + logging)
│   └── settings.yaml           #   User-editable settings
│
├── utils/                      # Utilities
│   ├── image.py                #   Image I/O helpers
│   └── upload_security.py      #   Upload validation (magic bytes)
│
├── scripts/                    # Admin & benchmark scripts (see 3.1.7)
│   ├── seed_admin.py           #   First admin + RBAC bootstrap
│   ├── backup.py               #   PostgreSQL + FAISS backup
│   ├── restore.py              #   Restore from backup
│   ├── bulk_enroll.py          #   Bulk face enrollment
│   ├── dedupe_employees.py     #   Duplicate cleanup
│   ├── migrate_faiss_hnsw.py   #   FAISS index migration
│   └── benchmarks/             #   Performance/validation scripts
│       ├── faiss_benchmark.py      #   FAISS speed tests
│       ├── tune_hnsw.py            #   HNSW parameter tuning
│       ├── tune_ivf.py             #   IVF parameter tuning
│       ├── benchmark_real_embeddings.py
│       ├── camera_validation.py    #   Camera latency/FPS
│       ├── fake_camera_validation.py
│       ├── scalability_benchmark.py
│       ├── profile_pipeline.py     #   Per-stage profiling
│       ├── probe_environment.py
│       └── validate_amfr.py        #   AMFR decision validation
│
├── alembic/                    # Schema migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 1bf6aa4e001c_initial_schema.py
│       ├── 2a7c9e4f1b3d_add_failed_login_attempts_table.py
│       └── 9c4d2f6a7b11_add_scalability_indexes.py
│
├── tests/                      # 20 pytest modules (see 3.1.8)
│
├── tools/                      # Diagnostics
│   ├── validate_startup.py     #   Startup health check
│   └── diagnose_cameras.py     #   Camera troubleshooting
│
├── models/                     # AI model weights
│   ├── yolo11n.pt              #   YOLO person detector
│   ├── .insightface/           #   InsightFace buffalo_l pack
│   └── liveness/               #   MiniFASNet ONNX model
│
├── embeddings/                 # FAISS vector database
│   ├── faiss.index
│   └── metadata.json
│
├── attendance/                 # Per-day CSV attendance logs
├── unknown_faces/              # Unknown face snapshots
├── uploads/                    # Enrollment image uploads (API)
├── outputs/                    # CLI processed images
├── dataset/                    # Test images
├── logs/                       # Rotating application logs
├── data/                       # SQLite database (dev)
├── backups/                    # Backup snapshots
│
└── docs/                       # Existing documentation
    ├── ARCHITECTURE.md, DEPLOYMENT.md, TROUBLESHOOTING.md
    ├── USER_MANUAL.md, ADMIN_MANUAL.md, API_DOCUMENTATION.md
    ├── DATABASE_SCHEMA.md, SECURITY_REPORT.md, PERFORMANCE_REPORT.md
    ├── BACKUP_RESTORE_GUIDE.md, PILOT_DEPLOYMENT_PLAN.md
    ├── GAP_ANALYSIS_COLLEGE_SCALE.md
    └── sdd/                    # ★ This Software Design Document
```

## 3.2 Folder-by-Folder Rationale

### 3.2.1 `app/` — Core AI Pipeline ⭐
**Why it exists:** Contains every AI component. Kept separate from
presentation/API so models can be loaded once and shared. Each module is
independently testable (there are matching `tests/test_*.py` files).
**Dependencies:** `config/`, `camera/` (via live_detection), `database/`,
`services/` (for DB logging).

### 3.2.2 `camera/` — Camera Abstraction
**Why it exists:** The pipeline must not care *where* frames come from.
The `CameraSource` ABC + factory makes adding a new camera type a one-file
change. This is also the only layer allowed to touch `cv2.VideoCapture`.

### 3.2.3 `dashboard/` — Streamlit UI
**Why it exists:** Provides the operator interface. `frame_buffer.py` and
`camera_owner.py` are the canonical shared infrastructure that survive
Streamlit reruns — critical because Streamlit reruns the script top-to-bottom
on every interaction.

### 3.2.4 `services/` — Business Logic Layer
**Why it exists:** The dashboard and API both need attendance/employee/
recognition operations. Services centralize that logic, wrap repositories,
add audit logging, and keep the FAISS index in sync with the DB
(e.g. rename/delete propagation).

### 3.2.5 `api/` — FastAPI REST Layer
**Why it exists:** Enterprise integration: programmatic access to students,
employees, cameras, attendance, analytics, jobs, and real-time events.
Contains its own security stack (JWT, RBAC, rate limiting, headers).

### 3.2.6 `database/` — ORM + Repository
**Why it exists:** Centralizes schema (models), connection/session
management, and all SQL queries (repository). The repository pattern keeps
business logic free of SQLAlchemy noise and makes testing with mocks easy.

### 3.2.7 `scripts/` — Admin & Benchmarks
**Why it exists:** One-off/ops tasks that shouldn't live in the app:
seeding, backup/restore, dedupe, migrations, bulk enrollment, and
performance benchmarking/tuning.

### 3.2.8 `tests/` — Automated Tests
**Why it exists:** 490 tests protect the system. Each module has a matching
test file. Integration tests require PostgreSQL + Redis (they skip when
unavailable).

### 3.2.9 `alembic/` — Migrations
**Why it exists:** Schema changes must be versioned and repeatable across
dev/prod. Three migrations exist: initial schema index, failed-login table,
and scalability indexes.

### 3.2.10 Data directories (`embeddings/`, `attendance/`, `unknown_faces/`,
`logs/`, `data/`, `uploads/`, `outputs/`, `backups/`)
**Why they exist:** Persistent state that must not be in git. Paths are
created automatically by `config/config.py` at import time.

---

*References: `config/config.py`, `README.md`, repository tree*

---

<!-- Section: 04_FILE_EXPLANATION.md -->
# Section 4 — Complete File Explanation

Every important file in the repository, explained with: purpose,
responsibilities, classes, functions, inputs, outputs, dependencies, flow,
complexity, and interactions.

---

## 4.1 Entry Points

### `main.py` — CLI Entry Point
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Command-line interface for live recognition, single-image processing, enrollment, pipeline testing, and diagnostics |
| **Classes** | None (module-level functions) |
| **Functions** | `cmd_webcam()`, `cmd_image()`, `cmd_enroll()`, `cmd_test()`, `cmd_debug()`, `main()` |
| **Inputs** | CLI args: `--camera-id`, `--source-type`, `--camera-url`, `--image`, `--enroll`, `--test`, `--debug` |
| **Outputs** | Annotated video window, annotated images in `outputs/`, console logs |
| **Dependencies** | `config.config`, `app.live_detection.LiveDetection`, `cv2`, `numpy` |
| **Flow** | Parse args → route to command → each command builds a `LiveDetection` pipeline and runs it |
| **Complexity** | O(n) frames; simple orchestration |
| **Interactions** | Wraps the entire `app/` pipeline; uses `camera.selector.create_camera()` via `LiveDetection.open_camera()` |

### `dashboard/app.py` — Streamlit Entry Point
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Bootstrap the Streamlit dashboard, sidebar navigation, DB init, auto-cleanup |
| **Dependencies** | `database.database.init_db`, `services.unknown_face_service.UnknownFaceService.auto_cleanup`, `app.enrollment.FaceEnrollment`, `config.config`, `streamlit` |
| **Flow** | `st.set_page_config` → sidebar links to 10 pages → `init_db()` → `auto_cleanup()` → footer stats → `st.switch_page("pages/01_Dashboard.py")` |

### `run.bat` / `run.sh` / `clear_cache.py`
- `run.bat`/`run.sh` — convenience launchers (install deps, run dashboard or API).
- `clear_cache.py` — clears FAISS metadata/index caches (ops utility).

---

## 4.2 Core AI Pipeline (`app/`)

### `app/face_detector.py` — YOLO Person Detector
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Detect people in a frame using YOLO11 (person class only) |
| **Class** | `FaceDetector` |
| **Functions** | `detect(frame, conf_threshold)`, `crop_person(frame, bbox, padding)`, `get_largest_detection(detections)` |
| **Inputs** | BGR frame (H×W×3), optional confidence threshold |
| **Outputs** | List of `{"bbox": (x1,y1,x2,y2), "confidence": float, "class_id": 0}` |
| **Dependencies** | `ultralytics.YOLO`, `config.config`, `cv2`, `numpy` |
| **Flow** | `model(frame)` → filter `cls==0` → convert boxes to ints |
| **Complexity** | Model inference is the dominant cost; per-frame O(1) detections |
| **Interactions** | First stage of every pipeline; crops feed `recognizer.detect_face()` |

### `app/recognizer.py` — RetinaFace + ArcFace
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Face detection with 5-point landmarks (RetinaFace) and 512-D embedding (ArcFace) |
| **Class** | `FaceRecognizer` |
| **Functions** | `extract_embedding()`, `detect_face()`, `get_landmarks()`, `compute_similarity()`, `embedding_dim()` |
| **Inputs** | BGR image (person crop or face) |
| **Outputs** | 512-D L2-normalized float32 embedding, or face dict `{"bbox","landmarks","embedding","det_score"}` |
| **Dependencies** | `insightface.FaceAnalysis` (`buffalo_l`), `config.config` |
| **Flow** | `app.get(img)` → take first face → normalize embedding to unit norm |
| **Complexity** | One CNN pass per person; det_size 640×640 |
| **Interactions** | Consumed by enrollment, AMFR, enrollment page, bulk enroll |

### `app/enrollment.py` — FAISS Vector Store
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Persistent face-embedding store with nearest-neighbor search |
| **Class** | `FaceEnrollment` |
| **Functions** | `enroll()`, `search()`, `remove()` (NotImplemented), `remove_by_name()`, `rename()`, `clear()`, `all_persons()`, `count()`, `unique_count()`, `_save()`, `_create_index()`, `status()` |
| **Inputs** | Names + 512-D embeddings; queries + thresholds |
| **Outputs** | Match list `{"name","confidence","distance"}`; status dict |
| **Dependencies** | `faiss`, `numpy`, `config.config` |
| **Flow** | Load index+metadata at init; search via `index.search`; confidence = `1/(1+d²)` |
| **Complexity** | Search O(log n) HNSW, O(n) flat; delete/rename rebuild O(n) |
| **Interactions** | Used by recognizer pipeline, services (employee rename/delete sync), scripts |

### `app/face_quality.py` — Quality Assessment
| Attribute | Detail |
|-----------|--------|
| **Class** | `FaceQualityAssessment` |
| **Functions** | `assess()`, `_assess_blur()`, `_assess_brightness()`, `_assess_contrast()`, `_assess_face_size()`, `_assess_det_score()`, `_assess_pose()` |
| **Metrics** | Laplacian variance (blur), mean brightness, stddev contrast, face size ratio, det score, landmark-based pose |
| **Outputs** | `{"overall": 0-1, "passed": bool, "metrics": {...}, "failure_reasons": [...]}` |
| **Complexity** | O(face_area) pixel ops; ~sub-ms |
| **Interactions** | Called by `AMFREngine._evaluate_person()` |

### `app/liveness_detector.py` — Multi-Factor Liveness
| Attribute | Detail |
|-----------|--------|
| **Class** | `LivenessDetector`, `LivenessResult` |
| **Functions** | `analyze_frame()`, `reset()`, `register_blink()`, `_analyze_texture()` (LBP), `_compute_approximate_ear()`, `_update_blink_state()`, `_analyze_motion()`, `_detect_screen_edges()`, `_fail_result()` |
| **Inputs** | Face crop + optional 5-point landmarks |
| **Outputs** | `LivenessResult` with per-factor scores (texture/blink/motion/screen/dl) + `is_live` |
| **Weights** | With DL: 0.15/0.20/0.15/0.10/0.40; without DL: 0.25/0.35/0.25/0.15 |
| **Dependencies** | `cv2`, `numpy`, `app.deep_liveness` (optional), `config.config` |
| **Complexity** | LBP downsampled to 48×48 (~0.1 ms); deep factor ~5 ms |
| **Interactions** | Instantiated **per track** by AMFR engine (isolated blink/motion state) |

### `app/deep_liveness.py` — CNN Anti-Spoofing
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Deep-learning liveness (MiniFASNet ONNX) with a numpy fallback CNN |
| **Class** | `DeepLivenessDetector`, `DeepLivenessResult` |
| **Functions** | `predict()`, `_load_model()`, `_download_model()`, `_predict_onnx()`, `_preprocess()`, `_align_face()`, `_predict_fallback()`, `_estimate_uniformity()`, `reload()` |
| **Model** | `MiniFASNetV2.onnx` (80×80 input, 3-class softmax), downloaded from yakhyo/face-anti-spoofing releases |
| **Fallback** | 3-channel histogram + FFT spectral + gradient + color-correlation features, ~0.5 ms |
| **Outputs** | `DeepLivenessResult` (dl_score, is_live, inference_time_ms, model_available) |
| **Complexity** | ONNX ~5 ms; fallback ~0.5 ms |
| **Interactions** | Singleton via `get_deep_liveness_detector()`; used by `LivenessDetector` |

### `app/tracking.py` — IoU Multi-Object Tracker
| Attribute | Detail |
|-----------|--------|
| **Class** | `TrackState` (dataclass), `MultiFrameTracker` |
| **Functions** | `update()`, `reset()`, `_compute_iou_matrix()`, `_iou()`, `_greedy_assign()`, `_create_track()`, `_update_track()`, `_apply_detection()`, `_prune_lost_tracks()` |
| **Inputs** | Detection dicts (bbox + scores), frame shape |
| **Outputs** | Active `TrackState` list with accumulated scores, identity, stability |
| **Complexity** | IoU matrix O(tracks×detections); greedy assignment O(n²) worst case |
| **Interactions** | Updated twice per frame by AMFR (identity feedback loop) |

### `app/amfr_engine.py` — Adaptive Multi-Factor Recognition
| Attribute | Detail |
|-----------|--------|
| **Class** | `AMFREngine`, `AMFRDecision` (enum) |
| **Functions** | `process_frame()`, `reset()`, `status()`, `_get_liveness_detector()`, `_evaluate_person()`, `_decide()` |
| **Inputs** | Frame, detections, embeddings, FAISS results, face data |
| **Outputs** | Augmented detections: `name`, `confidence`, `amfr_decision`, `risk_score`, `amfr_details` |
| **Decision logic** | Liveness gate (hard reject) → quality gate → arcface score → weighted risk = 0.45·arcface + 0.35·liveness + 0.20·quality → thresholds (0.70 ACCEPT, 0.40 BORDERLINE) |
| **Complexity** | Per-person: quality + liveness + tracking; moderate |
| **Interactions** | Core of `RecognitionService` and `LiveDetection` |

### `app/attendance.py` — CSV Attendance Logger
| Attribute | Detail |
|-----------|--------|
| **Class** | `AttendanceTracker` |
| **Functions** | `mark()`, `today()`, `by_date()`, `all_records()`, `statistics()` |
| **Outputs** | Per-day CSV files (`attendance/YYYY-MM-DD.csv`) |
| **Flow** | `mark()` dedupes per name per day |
| **Interactions** | Used by `AttendanceService` (dual-write) and CLI `LiveDetection` |

### `app/live_detection.py` — CLI Pipeline Orchestrator
| Attribute | Detail |
|-----------|--------|
| **Class** | `LiveDetection` |
| **Functions** | `process_frame()`, `open_camera()`, `run()`, `process_image()`, `process_video()`, `status()`, `_draw_overlay()`, `_draw_info_card()`, `_log_attendance_db()`, `_save_unknown_face()`, `_interactive_enroll()`, `_debug_faiss()` |
| **Flow** | YOLO → RetinaFace → ArcFace → FAISS → AMFR → attendance + unknown handling |
| **Interactions** | Instantiated by `main.py` CLI and the Attendance page's WebRTC transformer |

---

## 4.3 Recognition & Camera (`recognition/`, `camera/`)

### `recognition/alignment.py`
| Attribute | Detail |
|-----------|--------|
| **Functions** | `align_face()`, `align_face_from_bbox()`, `normalize_intensity()` |
| **Purpose** | Similarity-transform face alignment to canonical landmarks (224×224), CLAHE normalization |
| **Interactions** | Available to any consumer; the live pipeline embeds alignment inside InsightFace/detector pre-processing |

### `camera/base.py`
`CameraSource` (ABC): `name`, `source_type`, `open()`, `release()`, `read()`,
`is_opened()`, `set_resolution()`, `get_resolution()`, `info()`. `CameraError` exception.

### `camera/webcam.py`
| Class | Detail |
|-------|--------|
| `WebcamSource` | OpenCV webcam with DirectShow→MSMF→Default backend fallback |
| `USBAnySource` | Auto-scans indices 0..9, prefers a given index, uses first working camera |
| `list_webcams()` / `list_all_cameras()` | Index probing helpers |

### `camera/phone.py`
| Class | Transport |
|-------|-----------|
| `AndroidWiFiSource` | IP Webcam HTTP MJPEG (`http://ip:8080/video`), connectivity pre-check with `requests` |
| `AndroidUSBSource` | DroidCam USB (DirectShow) with Wi-Fi fallback |
| `iPhoneWiFiSource` | EpocCam RTSP/HTTP |
| `iPhoneUSBSource` | EpocCam/DroidCam virtual DirectShow camera (default index 2) |
| `IPCameraSource` | Generic RTSP/HTTP/MJPEG |

### `camera/selector.py`
`CAMERA_REGISTRY` slug→class map; `create_camera(source_type, **kwargs)`
factory; `select_camera_cli()`; `select_camera_ui(st)`; `get_available_cameras()`.

### `camera/discovery.py`
`scan_network(timeout, max_workers)` — probes 1..254 in the /24 subnet on
ports 8080/4747, matches HTTP signatures (IP Webcam / DroidCam / EpocCam),
returns deduplicated `DiscoveredCamera` list.

### `camera/fake.py`
`FakeCameraSource` — synthetic gradient frames at target FPS with optional
jitter; used by benchmarks and hardware-free tests.

---

## 4.4 Service Layer (`services/`)

### `services/recognition_service.py` — Pipeline Orchestrator ⭐
| Attribute | Detail |
|-----------|--------|
| **Purpose** | The single entry point the dashboard/API use for frame processing |
| **Functions** | `process_frame()`, `process_frame_detailed()`, `with_shared_models()`, `reset_tracking()`, `status()`, `_maybe_mark_attendance()`, `_log_recognition()`, `_handle_unknown_face()`, `_draw_overlay()` |
| **Flow** | YOLO → RetinaFace → ArcFace → FAISS → AMFR → attendance/unknown/spoof actions → DB logging |
| **Key detail** | `with_shared_models()` shares models across pipelines but keeps per-pipeline state |
| **Interactions** | Consumes `FaceDetector`, `FaceRecognizer`, `FaceEnrollment`, `AMFREngine`; writes via `AttendanceService`, `RecognitionLogRepo`, `UnknownFaceRepo`, `AuditService` |

### `services/attendance_service.py`
`mark()` (DB+CSV dual write, dedupe per day, audit), `get_today()`,
`get_by_date()`, `get_by_employee()`, `get_statistics()`, `to_dict()`.

### `services/employee_service.py`
`create()`, `get_by_employee_id()`, `get_by_id()`, `get_by_name()`, `update()`
(renames FAISS label on name change), `get_all()`, `search()`, `delete()`
(removes FAISS embedding), `remove_faiss_embedding()`, `count()`, `to_dict()`.

### `services/unknown_face_service.py`
`get_statistics()`, `get_all()`, `get_filtered()`, `get_by_id()`,
`mark_reviewed()`, `delete()`, `update_notes()`, `convert_to_employee()`
(full workflow: load image → ArcFace embedding → FAISS → DB → mark converted),
`delete_all()`, `auto_cleanup()`.

### `services/audit_service.py`
`log(action, description, operator, employee_id)`, `get_recent()`, `get_by_action()`.

### `services/brute_force_protection.py`
`is_locked_out()`, `record_failed_attempt()`, `record_successful_login()`,
`get_lockout_info()`, `cleanup_old_attempts()`. Constants: 5 attempts /
30 min lockout / 20 IP requests per minute / 7-day cleanup.

### `services/mfa_service.py`
TOTP via `pyotp`: `generate_secret()`, `verify_totp()`, `generate_backup_codes()`
(SHA-256 hashed), `verify_backup_code()`, `enroll_user()`, `disable_mfa()`,
`verify_and_update()`, `requires_mfa()` (super-admin and admin roles always MFA).

### `services/oidc_service.py`
Provider-agnostic OIDC (discovery endpoint, code exchange, user sync):
`OIDCUserInfo` dataclass, `get_login_url()`, `handle_callback()`, `sync_user()`.

---

## 4.5 API Layer (`api/`)

### `api/main.py` — FastAPI App (46 endpoints)
| Attribute | Detail |
|-----------|--------|
| **Middleware** | SlowAPI rate limiter, CORS, TrustedHost, security headers, request-ID, body-size limit |
| **Security** | `HTTPBearer`, JWT decode, `require_permission()` (RBAC), `require_role()`, bcrypt via passlib |
| **Endpoints** | Auth (login/logout/me/change-password/revoke-all/mfa/oidc/refresh), health/metrics, enroll/upload, students CRUD, employees CRUD, cameras CRUD, attendance, unknown-faces, analytics, events/stream (WS), jobs, bulk, health/ready/live, system/status |
| **Dependencies** | FastAPI, slowapi, jose, passlib, sqlalchemy, pydantic, prometheus_client |

### `api/redis_client.py`
`RedisClient` — student last-seen, attendance dedupe keys, camera status,
recognition cooldown, track identity cache, generic cache_get/set/delete.
Singleton via `get_redis()`.

### `api/job_queue.py`
In-process asyncio job queue (`JobQueue`, `Job`, `JobStatus`). Handlers:
`batch_enroll`, `rebuild_index`, `cleanup_unknown` (currently simulated).

### `api/websocket_manager.py`
`WebSocketManager` — per-camera event streams, role-based filtering, heartbeat
(15 s), event buffering (last 100), `broadcast_event()`, `send_personal()`.

### `api/bulk_operations.py`
`BulkOperations` — `import_students_from_csv()`, `import_employees_from_csv()`,
`bulk_update_camera_status()`, `export_attendance_csv()`; `BulkResult` dataclass.

### `api/attendance_service.py`
Timetable-aware: `is_class_in_session()`, `is_within_time_window()`,
`is_student_enrolled()`, `get_today_attendance()`, `create_attendance()`,
`get_attendance_summary()`.

### `api/audit_service.py`
`log_event()`, `log_recognition_event()`, `log_security_alert()`,
`get_audit_logs()`, `export_logs()`.

---

## 4.6 Database Layer (`database/`)

### `database/database.py`
`DB_TYPE` env switch (sqlite default / postgres via `DATABASE_URL`), engine,
`SessionLocal`, `get_session()` context manager, `init_db()` (Alembic →
create_all fallback → stamp), `run_migrations()`, `reset_db()`.

### `database/models.py`
20 tables + 2 association tables (see §8 for full schema). Key enums:
`RoleName` (7 roles), `ActionType`, `AuditAction`.

### `database/repository.py`
`PageResult` dataclass; repos: `StudentRepo`, `EmployeeRepo`, `AttendanceRepo`,
`RecognitionLogRepo`, `UnknownFaceRepo`, `CameraRepo`, `AuditLogRepo`.
All take a Session; callers control transactions.

---

## 4.7 Config, Utils, Scripts, Tools

### `config/config.py`
Loads `settings.yaml` with defaults; exposes typed constants
(`YOLO_CONFIDENCE`, `RECOGNITION_THRESHOLD`, AMFR weights, FAISS params,
paths, logging config). `save_settings()` preserves YAML comments via
ruamel round-trip. Creates required directories at import.

### `utils/upload_security.py`
`validate_image_upload()` — magic-bytes format detection (JPEG/PNG/GIF/WebP),
size limit, Pillow verification, dimension checks, server-side filename
(`enroll_<ts>_<uuid>.<ext>`). `UploadSecurityError`, `sanitize_filename()`.

### `utils/image.py`
`read_image()`, `save_image()`, `resize_to_height()`, `draw_rounded_rect()`.

### `scripts/seed_admin.py`
Seeds 7 roles, permissions (11 resources × 5 actions + extras), assigns all to
SUPER_ADMIN, subset to COLLEGE_ADMIN, creates admin user. Idempotent.

### `scripts/backup.py` / `scripts/restore.py`
Backup: pg_dump (plain SQL) + FAISS index + metadata + manifest.json with
SHA-256 hashes. Restore: integrity verify → terminate connections → drop →
create → restore DB → restore FAISS artifacts.

### `scripts/bulk_enroll.py`
Real mode (scan photo dir) or synthetic mode (generate N random L2-normalized
512-D embeddings in batches). `--db` creates employee records; `--dry-run`
validates without saving.

### `scripts/dedupe_employees.py`
Groups employees by normalized name, picks survivor (valid FAISS id, else
earliest), re-points attendance/recognition rows, deletes duplicates.
`--clean-stale` removes employees whose faiss_id is gone (guarded against
empty metadata).

### `scripts/migrate_faiss_hnsw.py`
Extracts vectors via `reconstruct_n`, rebuilds with current config, re-adds
in batches, verifies with a search test.

### `tools/validate_startup.py`
Import checks, env checks, model presence, DB init — prints a health report.

### `tools/diagnose_cameras.py`
Camera diagnostics: lists devices, tests capture, reports issues.

---

## 4.8 Test Files (`tests/`)

| File | Covers |
|------|--------|
| `test_enrollment.py` | FAISS enroll/search/remove/rename/clear |
| `test_attendance_service.py` | Marking, dedupe, queries |
| `test_employee_service.py` | CRUD + FAISS sync |
| `test_repair.py` | Camera selection + config UI repairs |
| `test_repository.py` / `test_repository_pagination.py` | Repository CRUD + pagination |
| `test_face_quality.py` | Quality metrics |
| `test_deep_liveness.py` | ONNX + fallback paths (forced fallback via monkeypatch) |
| `test_liveness_detector.py` | Multi-factor liveness |
| `test_tracking.py` | IoU tracker |
| `test_upload_security.py` | Upload validation |
| `test_brute_force_protection.py` | Lockout + rate limiting |
| `test_ip_camera.py` / `test_phone_cameras.py` | Camera sources |
| `test_camera_owner.py` | Singleton ownership |
| `test_frame_buffer.py` / `test_latency_logger.py` | Buffers/stats |
| `test_audit_service.py` | Audit trail |
| `test_integration.py` | PostgreSQL + Redis (skips when unavailable) |

---

*References: all files listed; `tests/`, `scripts/`, `tools/` directories*

---

<!-- Section: 05_AI_PIPELINE.md -->
# Section 5 — Complete AI Pipeline

## 5.1 Pipeline Overview

The recognition pipeline is a **sequential cascade of specialist models and
checks**. Each stage is deliberately placed so that cheap operations run
first and expensive ones run only when needed:

```
Camera frame (640×480)
   │
   ▼
① YOLO11 person detection          (app/face_detector.py)
   │  person bboxes only (COCO class 0)
   ▼
② Tracking (IoU matching)          (app/tracking.py)
   │  track_id per person; identity/temporal smoothing
   ▼
③ RetinaFace face detection        (app/recognizer.py)
   │  face bbox + 5 landmarks + det_score
   ▼
④ Face Quality assessment          (app/face_quality.py)
   │  0–1 quality score
   ▼
⑤ Liveness — 5 factors             (app/liveness_detector.py + app/deep_liveness.py)
   │  texture / blink / motion / screen / deep CNN
   ▼
⑥ ArcFace embedding (512-D)        (app/recognizer.py)
   │  L2-normalized vector
   ▼
⑦ FAISS nearest-neighbor search    (app/enrollment.py)
   │  name + L2 distance + confidence
   ▼
⑧ AMFR decision engine             (app/amfr_engine.py)
   │  risk score → ACCEPT / BORDERLINE / LOW_CONFIDENCE / REJECT_SPOOF
   ▼
⑨ Attendance + DB logging          (attendance.py, services/, repositories)
```

> **Note on ByteTrack:** the README and pipeline diagrams describe this stage
> as "ByteTrack" (its role in the cascade), but the shipped code implements a
> **custom greedy IoU multi-object tracker** (`app/tracking.py`), not the
> ByteTrack library. §5.3 documents what the code actually does.

## 5.2 Stage-by-Stage Detail

### Stage ① — YOLO11 Person Detection
- **Why used:** A dedicated person detector is the cheapest reliable way to
  localize people in a full frame; it also rejects non-face regions and lets
  the system skip the entire pipeline when nobody is present (early exit).
- **Why chosen:** Ultralytics YOLO11n is a small (~6 MB) COCO-trained model
  with excellent speed/accuracy on CPU, a mature Python API, and ONNX export
  support.
- **Alternatives:** YOLOv8/YOLOv5 (older), MediaPipe Pose (person
  landmarks), HOG+SVM (classic, slower to tune), MobileNet-SSD.
- **Advantages:** Single-pass detection, strong COCO benchmark, active
  ecosystem.
- **Disadvantages:** Detects *people*, not *faces* — needs the RetinaFace
  stage; COCO-trained (not face-specific).
- **Input:** BGR frame.
- **Output:** `[{"bbox": (x1,y1,x2,y2), "confidence", "class_id": 0}]`.
- **Implementation notes:** `FaceDetector.detect()` filters to class 0 and
  applies `cfg.YOLO_CONFIDENCE` (default 0.5/0.6). `crop_person()` adds 15%
  padding. Early exit: if no detections, the rest of the pipeline is skipped
  (~200 ms saved per empty frame).

### Stage ② — Tracking (custom IoU tracker)
- **Why used:** A single recognition on one frame is noisy. Tracking
  accumulates evidence over time (identity stability, score averages) so the
  AMFR decision is temporal, not instantaneous, and attendance is not marked
  twice for the same person walking across the room.
- **Why chosen (implementation):** a greedy IoU matcher is simple, fast, and
  dependency-free; it suits indoor camera scenes with modest occlusion.
- **Alternatives:** ByteTrack (SORT-based, SOTA), DeepSORT (appearance
  re-ID), Norfair, Kalman-filter trackers.
- **Advantages:** Zero extra dependencies; O(tracks×detections) IoU matrix;
  easy to reason about.
- **Disadvantages:** No motion prediction or appearance re-ID → identity
  switches under heavy occlusion; "ByteTrack" naming in docs overstates the
  shipped capability.
- **Input:** detection dicts with `bbox` (+ optional scores).
- **Output:** `TrackState` objects with `track_id`, `total_frames`,
  `consistent_frames`, `identity`, `identity_confidence`,
  `identity_stability`, score accumulators, `spoof_frame_count`,
  `attendance_marked`.
- **Implementation notes:** Two `update()` calls per frame in AMFR — first
  with bbox-only detections (assigns track IDs), then with enriched results
  (feeds identity back for smoothing). Tracks disappear after
  `max_disappeared=30` frames.

### Stage ③ — RetinaFace Face Detection
- **Why used:** Converts a person bbox into a precise face bbox + 5 facial
  landmarks — needed for alignment, quality, liveness (blink), and cropping.
- **Why chosen:** Bundled inside InsightFace's `buffalo_l` pack, so it shares
  the runtime with ArcFace (one load, one dependency).
- **Alternatives:** MTCNN, YuNet (OpenCV Zoo), SCRFD, DSFD.
- **Advantages:** Accurate 5-point landmarks; tuned for ArcFace pipelines.
- **Disadvantages:** Heavier than YOLO; CPU-only in this project
  (`CPUExecutionProvider`).
- **Input:** person crop.
- **Output:** `{"bbox", "landmarks" (5×2), "embedding", "det_score"}` or
  `None` when no face.
- **Implementation notes:** `detect_face()` normalizes the embedding too;
  `get_landmarks()` is a separate helper.

### Stage ④ — Face Quality Assessment
- **Why used:** Poor faces (blurry, dark, tiny, extreme angle) produce
  unreliable embeddings and false reject/accept. Quality gates the whole
  decision.
- **Why chosen:** 6 interpretable CV metrics — no extra model download.
- **Alternatives:** SER-FIQ, FaceQnet (learned quality estimators).
- **Advantages:** Fast, explainable, zero deps.
- **Disadvantages:** Heuristic — less calibrated than learned models.
- **Input:** face crop, det_score, face bbox, frame shape, landmarks.
- **Output:** `overall` 0–1, `passed`, `metrics`, `failure_reasons`.
- **Threshold:** `FACE_QUALITY_MIN_SCORE = 0.35`; weights:
  blur 0.30, brightness 0.15, contrast 0.10, size 0.15, det 0.20, pose 0.10.

### Stage ⑤ — Liveness (5 factors)
- **Why used:** Defeat presentation attacks (printed photo, phone screen,
  replayed video) that defeat 2D face recognition.
- **Factors:**
  1. **Texture (LBP):** real skin has high-variance LBP histograms; prints/screens are uniform.
  2. **Blink (EAR):** eye-aspect-ratio state machine detects natural blinks.
  3. **Motion:** frame-differencing/optical-flow magnitude (liveness needs natural motion).
  4. **Screen edges:** Canny edge density near borders flags phone/tablet bezels.
  5. **Deep CNN:** MiniFASNet ONNX (80×80, 3-class softmax) or numpy fallback.
- **Why chosen:** layered defense-in-depth; the deep model catches what
  software heuristics miss; weights: 0.15/0.20/0.15/0.10/0.40 (deep dominant
  when available).
- **Alternatives:** single CNN only, remote photoplethysmography (rPPG),
  challenge-response (user gestures).
- **Advantages:** No user cooperation; real-time; works offline.
- **Disadvantages:** Software factors are heuristic; deep model needs a
  download; spoofs can evolve (training-data staleness).
- **Input:** face crop + landmarks (per-track detector instance).
- **Output:** `LivenessResult` with per-factor scores + `is_live`.

### Stage ⑥ — ArcFace Embedding
- **Why used:** Produces a compact, discriminative, L2-normalized 512-D
  representation whose cosine similarity approximates identity distance.
- **Why chosen:** Industry-standard face embedding (1:N recognition leader on
  LFW/MegaFace), bundled in `buffalo_l`.
- **Alternatives:** FaceNet, CosFace, SphereFace, Dlib ResNet.
- **Advantages:** High accuracy, large margin loss, robust to pose/lighting
  after alignment.
- **Disadvantages:** Embedding dim fixed; needs ~200 MB model pack.
- **Input:** person crop.
- **Output:** 512-D float32 unit-norm vector (or None).

### Stage ⑦ — FAISS Search
- **Why used:** Brute-force pairwise comparison of 512-D vectors is O(N) per
  query; FAISS gives sub-linear ANN search with tunable recall.
- **Why chosen:** Facebook AI's high-performance vector library; CPU support;
  multiple index types; serialization.
- **Alternatives:** Milvus, Qdrant, hnswlib, pgvector, Chroma.
- **Advantages:** Battle-tested, fast, in-process (offline).
- **Disadvantages:** Not a database (no native delete → index rebuild); no
  transactions; approximate indices trade recall.
- **Input:** query embedding, k=1, threshold.
- **Output:** `[{"name", "confidence", "distance"}]`; confidence = `1/(1+d²)`.
- **Index types:** `flat` (exact), `hnsw` (default; M=32, efC=200, efS=128),
  `ivf` (nlist=200, nprobe=256).

### Stage ⑧ — AMFR Decision Engine
- **Why used:** A single similarity score is a weak signal. AMFR fuses
  **ArcFace similarity + liveness + quality** into a weighted risk score and
  applies gates so spoofs are hard-rejected and marginal matches are
  deferred (BORDERLINE) instead of guessed.
- **Weights:** arcface 0.45, liveness 0.35, quality 0.20.
- **Gates:** liveness gate (spoof → REJECT_SPOOF), quality gate (soft).
- **Thresholds:** ≥0.70 ACCEPT; ≥0.40 BORDERLINE; low → LOW_CONFIDENCE.
- **Input:** detection, embedding, FAISS results, face data, track_id.
- **Output:** augmented detection: `name`, `confidence`, `amfr_decision`,
  `risk_score`, `amfr_details`, `trigger_security_alert`.

### Stage ⑨ — Attendance + Logging
- ACCEPT → `AttendanceService.mark()` (DB + CSV, per-day dedupe, audit) +
  `RecognitionLogRepo.create()`.
- BORDERLINE → log recognition (known, not marked), keep collecting frames.
- REJECT_SPOOF → log `is_spoof=True` + `AuditService.log("SPOOF_ATTEMPT")`.
- LOW_CONFIDENCE → save unknown face (cooldown 3 s) + `UnknownFaceRepo.create()`.

## 5.3 Tracking Deep-Dive (what the code actually does)

`MultiFrameTracker.update(detections, frame_shape)`:
1. If no detections → mark all tracks disappeared.
2. If no tracks → create tracks for all detections.
3. Else compute **IoU matrix** between track bboxes and detection bboxes.
4. **Greedy assignment**: repeatedly pick the highest-IoU pair until < 0.01.
5. Update matched tracks (`_update_track`), increment disappear counts for
   unmatched tracks, prune tracks gone > 30 frames, create new tracks for
   unmatched detections.

`TrackState` accumulates `arcface_distances`, `liveness_scores`,
`quality_scores`, `amfr_decisions` and exposes averages + `identity_stability`
(= consistent_frames / total_frames). The AMFR engine feeds identity back in
the second `update()` call, enabling temporal smoothing of names and scores.

## 5.4 AMFR Decision Table (visual)

| Decision | Condition | Visual | Action |
|----------|-----------|--------|--------|
| ✅ ACCEPT | risk ≥ 0.70, live, quality ok | 🟢 Green + name + PRESENT | Attendance marked |
| ⚠️ BORDERLINE | 0.40 ≤ risk < 0.70 (or arcface>0.3 & quality>0.4) | 🟡 Yellow + "COLLECTING FRAMES" | More frames |
| ❓ LOW_CONFIDENCE | risk < 0.40, no arcface match | ⚫ Grey + UNKNOWN | Unknown snapshot |
| 🚫 REJECT_SPOOF | liveness < 0.15 or not live | 🔴 Red + SPOOF | Reject + alert + audit |

---

*References: `app/amfr_engine.py`, `app/live_detection.py`,
`services/recognition_service.py`, `dashboard/pages/04_Live.py`, `README.md`*

---

<!-- Section: 06_MACHINE_LEARNING_MODELS.md -->
# Section 6 — Machine Learning Models

This section documents every AI model used, with architecture, training
data, working principle, output, accuracy, and limitations — verified
against the source code.

---

## 6.1 YOLO11 (Ultralytics) — Person Detection

| Attribute | Detail |
|-----------|--------|
| **File** | `models/yolo11n.pt` (auto-downloaded on first use) |
| **Used in** | `app/face_detector.py` |
| **Task** | Person localization (COCO class 0) |

**Architecture:** YOLO11 ("You Only Look Once") is a single-stage CNN
object detector. It divides the image into a grid and predicts bounding
boxes + class probabilities in one forward pass. The `n` (nano) variant is
the smallest: roughly 2.6M parameters, ~6 MB weights.

**Training dataset:** COCO (Common Objects in Context) — 118K training
images, 80 classes. The "person" class is the only one used here.

**Working principle:** Anchor-free detection with a backbone (CSPNet-style),
neck (PAN-FPN), and head producing box + class + confidence outputs. NMS
(Non-Maximum Suppression) removes duplicate boxes.

**Output:** person bounding boxes `(x1,y1,x2,y2)` + confidence.

**Accuracy:** Excellent on COCO person detection (~50+ mAP@0.5 for nano);
real-world accuracy depends on camera angle and distance.

**Limitations:**
- Detects whole people, not faces (needs RetinaFace stage).
- COCO-trained — no fine-tuning for classroom scenes.
- Runs on CPU here (`Ultralytics` default device is CPU in this codebase).
- Single-frame detection — no motion modelling.

---

## 6.2 RetinaFace — Face Detection + Landmarks

| Attribute | Detail |
|-----------|--------|
| **File** | Inside InsightFace `buffalo_l` pack (`~/.insightface` / `models/.insightface`) |
| **Used in** | `app/recognizer.py` |
| **Task** | Face detection + 5-point landmark regression |

**Architecture:** RetinaFace is a single-stage face detector built on a
ResNet/ResNeXt backbone with a feature pyramid (FPN) and context modules.
It predicts: face boxes, 5 facial landmarks, and a detection score. The
version in `buffalo_l` also performs face alignment internally.

**Training dataset:** WIDER FACE (32K images, 394K faces) plus extra
landmark annotations.

**Working principle:** Dense anchors over the feature pyramid; regression
head refines boxes/landmarks; NMS merges duplicates. `FaceAnalysis.prepare()`
uses det_size=(640,640).

**Output:** `face.bbox`, `face.landmark` (5×2), `face.det_score`,
`face.embedding` (used for ArcFace in this pipeline).

**Accuracy:** Very high recall on frontal and profile faces; landmarks are
stable enough for blink detection and alignment.

**Limitations:**
- CPU execution only (`CPUExecutionProvider`, `ctx_id=-1`).
- First face only is returned per call (`faces[0]`).
- Small/occluded faces can be missed.

---

## 6.3 ArcFace — Face Embedding

| Attribute | Detail |
|-----------|--------|
| **File** | Inside InsightFace `buffalo_l` pack |
| **Used in** | `app/recognizer.py` (embedding extraction) |
| **Task** | Map a face to a discriminative 512-D embedding |

**Architecture:** A ResNet-100 backbone (for buffalo_l) trained with the
**ArcFace (Additive Angular Margin)** loss: embeddings are pushed to a
hypersphere where the angle between vectors encodes identity distance.

**Training dataset:** WebFace42M / MS1MV3-scale face datasets (buffalo_l is
trained on large web face corpora).

**Working principle:** Face → CNN → 512-D feature vector → L2 normalization
(unit norm). Cosine similarity between two embeddings approximates the
probability they are the same person. In this codebase embeddings are
L2-normalized so **FAISS L2 distance ≈ cosine distance**.

**Output:** 512-D float32 unit-norm embedding (`EMBEDDING_DIM = 512`).

**Accuracy:** buffalo_l achieves state-of-the-art accuracy on LFW (99%+),
MegaFace, and IJB benchmarks.

**Limitations:**
- Requires a reasonably frontal, well-lit face (alignment helps).
- Fixed dimension (512).
- ~200 MB model pack download on first use.

---

## 6.4 MiniFASNet — Deep Liveness CNN

| Attribute | Detail |
|-----------|--------|
| **File** | `models/liveness/MiniFASNetV2.onnx` (~4 MB, auto-downloaded from `yakhyo/face-anti-spoofing` releases) |
| **Used in** | `app/deep_liveness.py` |
| **Task** | Binary-ish anti-spoofing (live vs presentation attack) |

**Architecture:** MiniFASNet is a lightweight CNN (~1.6M params) from the
Silent-Face-Anti-Spoofing project. It takes a small face crop and emits
class logits. The ONNX export used here expects **80×80 RGB** input and
produces **3 class logits** `[spoof, fake, live]` (postprocessed with
softmax; index 2 = live).

**Training dataset:** The SFAS (Silent-Face-Anti-Spoofing) training set of
real and attack faces (printed photos, screens, etc.).

**Working principle:** Standard CNN feature extraction + classification.
The repository also ships a **fallback**: if ONNX Runtime or the model file
is unavailable, a numpy-only classifier runs using color histograms, FFT
frequency distribution, gradient statistics, and channel correlation
(~0.5 ms/call).

**Output:** `DeepLivenessResult(dl_score 0–1, is_live, inference_time_ms)`.
Threshold: `DEEP_LIVENESS_THRESHOLD = 0.50`.

**Accuracy:** Strong against print/screen attacks on its training
distribution; the fallback is heuristic.

**Limitations:**
- Model source moved upstream (the original repo removed the ONNX export —
  this project now uses the maintained yakhyo export; noted in code comments).
- 80×80 input is low resolution.
- Spoofing techniques evolve; periodic model refresh is recommended.
- ONNX inference ~5 ms per face (CPU).

---

## 6.5 FAISS — Vector Search Index (not a model, but an AI-infrastructure component)

| Attribute | Detail |
|-----------|--------|
| **File** | `embeddings/faiss.index` + `embeddings/metadata.json` |
| **Used in** | `app/enrollment.py` |
| **Task** | Approximate/exact nearest-neighbor search over 512-D embeddings |

**Architecture:** Three supported index types (config in `settings.yaml`):
- `flat` — `IndexFlatL2`, exact brute-force (best recall, slow at scale).
- `hnsw` — `IndexHNSWFlat`, hierarchical navigable small-world graph
  (default; M=32, efConstruction=200, efSearch=128).
- `ivf` — `IndexIVFFlat`, inverted-file with Voronoi cells
  (nlist=200, nprobe=256).

**Working principle:** `index.add()` builds the index; `index.search(query,
k)` returns distances + indices. HNSW/Flat/IVF support `reconstruct()`,
which is used for delete/rename rebuilds. HNSW search parameters are not
persisted by `faiss.write_index`, so they are restored at load time.

**Output:** top-k `(distances, indices)`.

**Accuracy/recall:** Flat = 100% recall; HNSW/IVF approximate (tuned by
benchmarks in `scripts/benchmarks/`).

**Limitations:**
- **No native delete** — `remove()` raises `NotImplementedError`;
  `remove_by_name()`/`rename()` rebuild the index in O(N).
- Raw embeddings are not stored independently (recommended future: `.npy`).

---

## 6.6 The Tracker (not a neural model, but an algorithm)

**Implementation:** `app/tracking.py` — greedy IoU matcher (documented in
§5.3). No Kalman filter, no appearance re-ID. It is described as
"ByteTrack" in README diagrams, but the shipped code is the custom IoU
tracker.

---

## 6.7 Model Accuracy Summary

| Model | Metric | Expected Range (CPU, this project) |
|-------|--------|------------------------------------|
| YOLO11n | Person detection conf | > 0.5 (threshold `YOLO_CONFIDENCE`) |
| RetinaFace | det_score | typically 0.9–1.0 on clear faces |
| ArcFace | Embedding cosine/L2 | L2 < threshold (1.0 default) for same person |
| FAISS confidence | `1/(1+d²)` | > 0.7 for confident matches |
| MiniFASNet | dl_score | ≥ 0.5 live; < 0.15 spoof-hard-reject |
| AMFR risk | weighted composite | ≥ 0.70 ACCEPT; ≥ 0.40 BORDERLINE |

---

*References: `requirements.txt` (torch, ultralytics, insightface, faiss-cpu,
onnxruntime), `app/*`, `config/config.py`*

---

<!-- Section: 07_DATABASE.md -->
# Section 7 — Database

## 7.1 Simple Language Explanation

The system stores three kinds of data:

1. **Relational data** (people, attendance, cameras, users, roles, audit
   logs) → SQLite in development, PostgreSQL in production.
2. **Face vectors** (512-D embeddings) → FAISS index files (see §6.5).
3. **Temporary/runtime state** (cooldowns, camera status, OIDC state) →
   Redis (optional, degrades gracefully).

SQLAlchemy ORM maps Python classes to tables; Alembic versions schema
changes; the Repository pattern wraps all queries.

## 7.2 Database Engines

### SQLite (development / default)
- **Connection URL:** `sqlite:///data/face_recognition.db`
- **Set via:** `DB_TYPE=sqlite` (default) in `database/database.py`.
- **Advantages:** zero-config, single file, perfect for dev and small pilots.
- **Disadvantages:** single-writer, limited concurrency — not for campus-scale
  concurrent writes.

### PostgreSQL (production)
- **Connection URL:** from `DATABASE_URL` env var (`DB_TYPE=postgres`).
- **Advantages:** concurrency, ACID, indexes, JSON columns, maturity.
- **Used by:** production college deployment; `docker-compose.yml` provides
  `postgres:16-alpine` with healthcheck.
- **Backup/restore:** `scripts/backup.py` / `scripts/restore.py` (pg_dump).

### Redis (optional cache/state)
- **Connection URL:** `REDIS_URL` (default `redis://localhost:6379/0`).
- **Used for:** student last-seen, attendance dedupe markers, camera status,
  recognition cooldowns, track identity cache, OIDC CSRF state.
- **Key design property:** *every* Redis call in `api/redis_client.py` is
  wrapped so failure degrades gracefully — tests skip when Redis is absent.

## 7.3 ORM — SQLAlchemy 2.0

- **Declarative base:** `database/models.py` defines `Base(DeclarativeBase)`.
- **Session:** `SessionLocal = sessionmaker(...)`; `get_session()` context
  manager yields a Session; callers commit/rollback.
- **Types used:** Integer, String, Text, Boolean, Float, DateTime, JSON,
  Enum (via SAEnum where needed), ForeignKey, Index, Table (associations).
- **Timestamps:** `_utcnow()` helper returns naive UTC.

## 7.4 Migration — Alembic

- **Config:** `alembic.ini`; environment: `alembic/env.py`.
- **Versions** (in `alembic/versions/`):
  1. `1bf6aa4e001c` — initial schema (index on `unknown_faces.timestamp`).
  2. `2a7c9e4f1b3d` — `failed_login_attempts` table + composite indexes.
  3. `9c4d2f6a7b11` — scalability indexes (students, attendance, recognition_log, unknown_faces, audit_logs).
- **Auto-init:** `init_db()` runs `alembic upgrade head` if `alembic.ini`
  exists; falls back to `Base.metadata.create_all()` and stamps the DB.

## 7.5 Repository Pattern

`database/repository.py` defines per-entity repositories, each a class of
static methods taking a `Session`:

| Repository | Entity | Key operations |
|------------|--------|----------------|
| `StudentRepo` | students | create, get, search (name/id prefix), count |
| `EmployeeRepo` | employees | create, get_by_*, search (paginated), update (whitelisted), delete, count |
| `AttendanceRepo` | attendance | create, get_by_date/today/employee, is_marked_today, statistics |
| `RecognitionLogRepo` | recognition_log | create (with liveness/spoof/track), get_recent, get_by_date |
| `UnknownFaceRepo` | unknown_faces | create, get_all/filtered, stats, mark_reviewed/converted, notes, delete/all, delete_older_than |
| `CameraRepo` | cameras | create, get_all/active/by_id/by_index |
| `AuditLogRepo` | audit_logs | create, get_recent, get_by_action |

**Pagination:** `PageResult(items, total, skip, limit)` with `has_more`
property; `_paginate()` helper counts + slices. Search uses **prefix
patterns** (`name%`) so indexes can be used.

**Why the pattern:** keeps SQL out of business logic, makes services thin,
enables unit testing with a session mock, and gives a consistent CRUD API.

## 7.6 Why Each Table Exists (summary — full schema in §8)

| Group | Tables | Purpose |
|-------|--------|---------|
| RBAC | users, roles, permissions, user_roles, role_permissions | Authentication + authorization |
| Auth extras | failed_login_attempts, refresh_tokens | Brute-force protection; token rotation |
| College structure | institutions, departments, courses, sections, classrooms, timetables | Model the college so attendance is timetable-aware |
| People | students, staff, employees | People records (students + staff + legacy employees) |
| Enrollment | enrollments | Student ↔ section membership |
| Cameras | cameras | Multi-camera config with credentials refs |
| Attendance | attendance | Timetable-aware attendance records |
| Recognition | recognition_log | Every recognition event (analytics) |
| Unknown faces | unknown_faces | Snapshots + review workflow |
| Audit | audit_logs | Compliance/security trail |

## 7.7 Data Consistency Between Stores

- **Employee rename/delete** propagates to **FAISS** via
  `EmployeeService.update()`/`delete()` → `enrollment.rename()` /
  `remove_by_name()`.
- **Attendance** is dual-written to the DB (via repository) and to **CSV**
  (via `AttendanceTracker`) for backward compatibility.
- **Unknown face conversion** creates an Employee record first, then adds the
  embedding to FAISS (rolls back the employee if FAISS fails).

---

*References: `database/*`, `alembic/*`, `api/redis_client.py`, `scripts/backup.py`,
`docker-compose.yml`, `docs/DATABASE_SCHEMA.md`*

---

<!-- Section: 08_DATABASE_SCHEMA.md -->
# Section 8 — Complete Database Schema

All tables below are defined in `database/models.py` and verified against
the Alembic migrations. Types are SQLAlchemy column types.

## 8.1 ER Diagram (Mermaid)

```mermaid
erDiagram
    institutions ||--o{ departments : has
    institutions ||--o{ classrooms : has
    departments ||--o{ courses : has
    departments ||--o{ students : has
    departments ||--o{ staff : has
    courses ||--o{ sections : has
    sections ||--o{ timetables : has
    classrooms ||--o{ timetables : holds
    sections ||--o{ enrollments : registers
    students ||--o{ enrollments : enrolled_in
    staff ||--o{ timetables : teaches
    students ||--o{ attendance : records
    staff ||--o{ attendance : teaches
    sections ||--o{ attendance : for
    courses ||--o{ attendance : for
    classrooms ||--o{ attendance : in
    cameras ||--o{ attendance : captured_by
    cameras ||--o{ recognition_log : logged_by
    cameras ||--o{ unknown_faces : captured_by
    employees ||--o{ attendance : records
    employees ||--o{ audit_logs : acted_on
    employees ||--o{ recognition_log : recognized
    students ||--o{ recognition_log : recognized
    users ||--o{ user_roles : has
    roles ||--o{ user_roles : assigned_to
    roles ||--o{ role_permissions : grants
    permissions ||--o{ role_permissions : granted_to
    users ||--o{ refresh_tokens : owns
    users ||--o{ unknown_faces : reviewed
    users ||--o{ attendance : marked_by
```

## 8.2 Table-by-Table Reference

### 8.2.1 RBAC & Users

#### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | autoincrement |
| username | String(100) UNIQUE | |
| email | String(255) UNIQUE | |
| password_hash | String(255) | bcrypt |
| oidc_sub | String(255) UNIQUE NULL | OIDC subject |
| oidc_provider | String(50) NULL | azure/keycloak/google |
| auth_method | String(20) | local / oidc / both |
| is_mfa_enabled | Boolean | |
| mfa_totp_secret | String(64) NULL | Base32 |
| mfa_backup_codes | JSON NULL | SHA-256 hashes |
| mfa_last_verified | DateTime NULL | |
| is_active | Boolean | |
| last_login_at | DateTime NULL | |
| created_at / updated_at | DateTime | `_utcnow` defaults |

Relationships: `roles` (M:N via `user_roles`).

#### `roles`
`id` PK, `name` String(50) UNIQUE, `description` Text.
Enum `RoleName`: SUPER_ADMIN, COLLEGE_ADMIN, HOD, FACULTY, SECURITY, STUDENT, STAFF.
Relationships: `permissions` (M:N), `users` (M:N).

#### `permissions`
`id` PK, `resource` String(100), `action` String(50), `description` Text.
Unique index `(resource, action)`.
`ActionType`: READ, CREATE, UPDATE, DELETE, EXECUTE.

#### `user_roles` (association)
`user_id` FK→users.id, `role_id` FK→roles.id (composite PK).

#### `role_permissions` (association)
`role_id` FK→roles.id, `permission_id` FK→permissions.id (composite PK).

### 8.2.2 Auth Extras

#### `failed_login_attempts`
`id` PK, `username` String(100) indexed, `ip_address` String(45) indexed,
`user_agent` String(500), `attempted_at` DateTime indexed, `success` Boolean.
Indexes: `(username, attempted_at)`, `(ip_address, attempted_at)`.

#### `refresh_tokens`
`id` PK, `user_id` FK→users.id, `token_hash` String(128) UNIQUE,
`expires_at` DateTime, `created_at`, `revoked_at` NULL, `replaced_by`
String(128) NULL (rotation chain), `device_info` String(255),
`ip_address` String(45). Index: `(user_id, revoked_at)`.
Properties: `is_revoked`, `is_expired`.

### 8.2.3 College Structure

#### `institutions`
`id` PK, `name` String(255), `code` String(20) UNIQUE, `address` Text,
`phone` String(20), `email` String(255), `is_active` Boolean.
Relationships: `departments`.

#### `departments`
`id` PK, `institution_id` FK→institutions.id, `name` String(255),
`code` String(20), `head_id` FK→staff.id (named `fk_departments_head_id`,
use_alter) NULL, `is_active`. Unique `(institution_id, code)`.
Relationships: institution, head, courses, students, staff_members.

#### `courses`
`id` PK, `department_id` FK→departments.id, `code` String(50),
`name` String(255), `credits` Integer default 3, `description` Text,
`is_active`. Unique `(department_id, code)`.

#### `sections`
`id` PK, `course_id` FK→courses.id, `section_name` String(50),
`semester` String(20), `year` Integer, `max_capacity` Integer NULL.
Index `(course_id, semester, year)`.

#### `classrooms`
`id` PK, `institution_id` FK, `building` String(100), `room_number`
String(20), `capacity` Integer NULL, `floor` String(20), `is_active`.
Unique `(building, room_number)`. Relationships: cameras, attendance_records.

#### `timetables`
`id` PK, `section_id` FK→sections.id, `classroom_id` FK→classrooms.id,
`day_of_week` Integer (0=Mon..6=Sun), `start_time` String(8), `end_time`
String(8), `instructor_id` FK→staff.id NULL.
Indexes: `(section_id, day_of_week)`, `(classroom_id, day_of_week, start_time)`.

### 8.2.4 People

#### `students`
`id` PK, `student_id` String(20) UNIQUE, `name` String(100), `email`
String(255), `phone` String(20), `department_id` FK→departments.id NULL,
`enrollment_year` / `graduation_year` Integer NULL, `is_active`,
`created_at`.
Indexes: `student_id` (unique), `name`, `(department_id, is_active)`.

#### `staff`
`id` PK, `employee_id` String(20) UNIQUE, `name` String(100), `email`,
`phone`, `department_id` FK NULL, `position` String(100), `is_active`,
`created_at`. Index: `employee_id` (unique).

#### `employees` (legacy, backward-compatible)
`id` PK, `employee_id` String(20) UNIQUE, `name` String(100),
`department` String(100) NULL, `photo_path` String(500) NULL,
`faiss_id` Integer NULL, `created_at`/`updated_at`.
Relationships: attendance_records, audit_logs, recognition_logs.

### 8.2.5 Enrollment

#### `enrollments`
`id` PK, `student_id` FK→students.id, `section_id` FK→sections.id,
`enrollment_date` DateTime default now, `status` String(20) default ACTIVE.
Unique `(student_id, section_id)`.

### 8.2.6 Cameras

#### `cameras`
`id` PK, `name` String(100), `camera_index` Integer NULL,
`camera_id` String(50) UNIQUE, `stream_url` String(500) NULL,
`credential_ref` String(255) NULL (secrets-manager reference),
`location` String(200), `building` String(100), `room` String(50),
`classroom_id` FK→classrooms.id NULL, `is_active` Boolean, `status`
String(20) default OFFLINE, `last_seen` DateTime NULL, `fps` Integer,
`resolution` String(20), `created_at`/`updated_at`.
Indexes: `camera_id` (unique), `status`.

### 8.2.7 Attendance

#### `attendance`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| student_id | FK→students.id NULL | primary person |
| employee_id | FK→employees.id NULL | legacy path |
| section_id / course_id / classroom_id / instructor_id | FK NULL | timetable context |
| camera_id | FK→cameras.id NULL | capture source |
| timestamp | DateTime NOT NULL indexed | |
| recognized_at | DateTime NULL | |
| confidence | Float NOT NULL default 1.0 | |
| method | String(50) default FACE_RECOGNITION | |
| status | String(20) default PRESENT | PRESENT/ABSENT/LATE/EXCUSED |
| marked_by_user_id | FK→users.id NULL | manual override |
| marked_manually | Boolean default False | |
| manual_notes | Text NULL | |

Indexes: `timestamp`, `(student_id, timestamp)`, `(student_id, section_id)`,
`(course_id, timestamp)`, `(camera_id, timestamp)`.

### 8.2.8 Recognition & Unknown Faces

#### `recognition_log`
`id` PK, `employee_id`/`student_id` FK NULL, `is_known` Boolean NOT NULL,
`confidence` Float, `liveness_confidence` Float, `is_spoof` Boolean,
`track_id` String(50), `timestamp` DateTime indexed, `camera_id` FK,
`classroom_id` FK, `section_id` FK, `face_snapshot_path` String(500),
`embedding_path` String(500), `frame_number` Integer,
`processing_time_ms` Float.
Indexes: `timestamp`, `is_known`, `employee_id`, `student_id`,
`(camera_id, timestamp)`.

#### `unknown_faces`
`id` PK, `image_path` String(500) NOT NULL, `embedding_path`/`thumbnail_path`
String(500) NULL, `camera_id` FK, `classroom_id` FK, `timestamp` indexed,
`confidence` Float, `liveness_score` Float, `track_id` String(50),
`is_spoof` Boolean, `reviewed` Boolean, `reviewed_by` FK→users.id,
`reviewed_at` DateTime, `converted_to_employee` Boolean, `notes` Text,
`retention_expires_at` DateTime, `face_metadata` JSON.
Indexes: `timestamp`, `reviewed`, `retention_expires_at`,
`(camera_id, timestamp)`, `(camera_id, reviewed)`.

### 8.2.9 Audit

#### `audit_logs`
`id` PK, `action` String(50) (AuditAction enum), `actor` String(100)
(synonym `operator`), `actor_type` String(20) default USER,
`actor_id` FK→employees.id NULL (synonym `employee_id`), `timestamp`
DateTime indexed, `resource_type` String(50), `resource_id` Integer,
`description` Text, `ip_address` String(45), `user_agent` String(500),
`request_id` String(100), `details` JSON, `severity` String(20) default INFO.
Indexes: `timestamp`, `actor`, `action`, `severity`, `(actor, timestamp)`.

`AuditAction` enum: USER_LOGIN, USER_LOGOUT, ATTENDANCE_MARKED/MODIFIED/
DELETED, STUDENT_ENROLLED/UPDATED/DELETED, EMPLOYEE_ENROLLED/UPDATED,
CAMERA_ADDED/REMOVED/STATUS_CHANGED, UNKNOWN_FACE_REVIEWED/DELETED,
PERMISSION_GRANTED/REVOKED, ROLE_ASSIGNED/REMOVED, SYSTEM_CONFIG_CHANGED,
DATA_EXPORTED/DELETED, SECURITY_ALERT, PASSWORD_CHANGED/
PASSWORD_CHANGE_FAILED, RECOGNITION_EVENT, ATTENDANCE_SYNC.

## 8.3 Relationships Summary (FK map)

| FK | From | To |
|----|------|----|
| departments.institution_id | departments | institutions |
| departments.head_id | departments | staff (use_alter) |
| courses.department_id | courses | departments |
| sections.course_id | sections | courses |
| timetables.section_id / classroom_id / instructor_id | timetables | sections / classrooms / staff |
| students.department_id | students | departments |
| staff.department_id | staff | departments |
| enrollments.student_id / section_id | enrollments | students / sections |
| cameras.classroom_id | cameras | classrooms |
| attendance.* | attendance | students / employees / sections / courses / classrooms / staff / cameras / users |
| recognition_log.* | recognition_log | employees / students / cameras / classrooms / sections |
| unknown_faces.* | unknown_faces | cameras / classrooms / users |
| refresh_tokens.user_id | refresh_tokens | users |
| audit_logs.actor_id | audit_logs | employees |
| user_roles / role_permissions | associations | users↔roles / roles↔permissions |

## 8.4 Index Strategy (why)

- **Attendance** — heavy date-range + student queries → `timestamp`,
  `(student_id, timestamp)`, `(camera_id, timestamp)`.
- **Recognition log / unknown faces** — analytics and gallery queries →
  timestamp + camera composites.
- **RBAC** — permission checks join users→roles→permissions; unique
  `(resource, action)` prevents duplicates.
- **Auth** — failed-login lockout queries use `(username, attempted_at)`.

## 8.5 Migrations Applied

| Migration | Change |
|-----------|--------|
| 1bf6aa4e001c | initial schema (unknown_faces.timestamp index) |
| 2a7c9e4f1b3d | failed_login_attempts + composite indexes |
| 9c4d2f6a7b11 | scalability indexes (8 new) |

---

*References: `database/models.py`, `alembic/versions/*`, `docs/DATABASE_SCHEMA.md`*

---

<!-- Section: 09_API_DOCUMENTATION.md -->
# Section 9 — API Documentation

**Base URL:** `http://<host>:8000` (FastAPI, version 2.0.0)
**Interactive docs:** `/docs` and `/redoc` (disabled in production).

## 9.1 Authentication & Authorization Model

- **Bearer JWT** access tokens (HS256, `SECRET_KEY`, default 30 min expiry).
- **Refresh tokens** — opaque, stored hashed (SHA-256) in `refresh_tokens`,
  rotating on use; reuse of a revoked token revokes all of the user's tokens.
- **RBAC:** `require_permission(resource, action)` checks the user's
  role→permission mapping; `require_role(*roles)` checks membership.
- **MFA:** privileged roles require TOTP (see §11.6). Login returns
  `requires_mfa=true` + a short-lived `mfa_token`; client then calls
  `/auth/mfa/verify`.
- **Rate limiting:** slowapi keyed by client IP (defaults: login 10/min,
  general API 100/min, etc.).
- **Common error shape:** `{"error": "<detail>", "code": <http_status>}`.
- **Every response carries `X-Request-ID`.**

## 9.2 Standard Error Codes

| Code | Meaning |
|------|---------|
| 400 | Validation error / bad request (e.g. upload security, not enrolled in section) |
| 401 | Missing/invalid/expired token; wrong credentials; MFA failed |
| 403 | Insufficient permissions / disabled account / CSRF (OIDC state) |
| 404 | Resource not found |
| 409 | Duplicate (e.g. employee_id already exists) |
| 413 | Request body too large (>10 MB default) |
| 429 | Rate limited or account locked |
| 500 | Internal server error (generic message, no stack traces) |
| 501 | Feature not configured (e.g. OIDC not configured) |

## 9.3 Endpoint Reference

### 9.3.1 Auth

| Method | Path | Auth | Rate | Description |
|--------|------|------|------|-------------|
| POST | `/auth/login` | public | 10/min | Login; returns tokens or MFA challenge |
| POST | `/auth/logout` | user | 20/min | Audit logout |
| GET | `/auth/me` | user | 30/min | Current user profile + roles |
| POST | `/auth/change-password` | user | 5/min | Verify current + set new; revokes all refresh tokens |
| POST | `/auth/revoke-all-sessions` | user | 3/min | Revoke all refresh tokens |
| POST | `/auth/refresh` | public+token | 20/min | Rotate refresh token → new access+refresh |
| POST | `/auth/mfa/enroll` | mfa:UPDATE | 5/min | Generate TOTP secret + backup codes |
| POST | `/auth/mfa/verify` | mfa-token | 10/min | Verify TOTP/backup → full tokens |
| GET | `/auth/mfa/status` | user | — | MFA status + backup codes remaining |
| POST | `/auth/mfa/disable` | mfa:UPDATE | 5/min | Disable MFA |
| GET | `/auth/oidc/login` | public | 10/min | SSO auth URL + state |
| GET | `/auth/oidc/callback` | public | 10/min | SSO callback → tokens |

**Login request:**
```json
{ "username": "admin", "password": "AutoR!0t!ze*9!" }
```
**Login response (no MFA):**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "refresh_token": "<opaque>",
  "requires_mfa": false,
  "mfa_token": null
}
```
**Login response (MFA required):** `requires_mfa: true`, `mfa_token: "<2-min jwt>"`.

**JWT claims:** `sub` (user id), `username`, `roles`, `exp`, `iat`,
optionally `mfa_pending`, `mfa`, `oidc`.

### 9.3.2 Health & Monitoring

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | public | status/version/timestamp/database/redis |
| GET | `/health/live` | public | liveness probe |
| GET | `/health/ready` | public | readiness probe |
| GET | `/metrics` | public | Prometheus metrics (text format) |
| GET | `/system/status` | user | full system status snapshot |

### 9.3.3 Enrollment

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/enroll/upload` | enrollment:CREATE | Upload enrollment photo (magic-bytes validated, 5 MB max) → `{filename, size_bytes, message}` |

### 9.3.4 Students

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/students` | students:CREATE | Create student (201) |
| GET | `/students` | students:READ | Paginated list; `q`, `department_id`, `is_active`, `skip`, `limit` |
| GET | `/students/{id}` | students:READ | Get one |

`StudentCreate`: `{student_id, name, email?, department_id?}` (student_id pattern `^[a-zA-Z0-9\-]+$`).

### 9.3.5 Employees

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/employees` | employees:CREATE | Create (409 on duplicate) |
| GET | `/employees` | employees:READ | Paginated + `q` search |
| GET | `/employees/{id}` | employees:READ | Get one |
| PUT | `/employees/{id}` | employees:UPDATE | Partial update (name/department/photo_path) |
| DELETE | `/employees/{id}` | employees:DELETE | Delete + FAISS embedding removal (204) |

### 9.3.6 Cameras

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/cameras` | COLLEGE_ADMIN/SUPER_ADMIN | Create camera |
| GET | `/cameras` | cameras:READ | Paginated + `q`/`is_active`/`status` filters |
| GET | `/cameras/{id}` | cameras:READ | Get one |
| PATCH | `/cameras/{id}/status` | COLLEGE_ADMIN/SUPER_ADMIN | Set active/offline |

### 9.3.7 Attendance

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/attendance` | attendance:CREATE | Mark attendance (validates student + enrollment) |
| GET | `/attendance` | attendance:READ | Filtered by student/section/course/date range, paginated |

`AttendanceCreate`: `{student_id, section_id?, course_id?, classroom_id?, camera_id?, confidence [0-1], method, status}`.

### 9.3.8 Unknown Faces

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/unknown-faces` | unknown_faces:READ | Paginated + date/camera/reviewed filters |
| POST | `/unknown-faces/{id}/review` | unknown_faces:UPDATE | Mark reviewed |

### 9.3.9 Analytics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/analytics/attendance-summary` | analytics:READ | Aggregated attendance stats |
| GET | `/analytics/camera-status` | analytics:READ | Per-camera status |

### 9.3.10 Real-Time Events

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/events/stream` | user (WS) | WebSocket recognition event stream; supports `camera_id` filter; role-filtered for students |

### 9.3.11 Jobs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/jobs` | jobs:CREATE | Enqueue `batch_enroll` / `rebuild_index` / `cleanup_unknown` → `{job_id, status, job_type}` |
| GET | `/jobs` | jobs:READ | List (status filter, limit) |
| GET | `/jobs/{id}` | jobs:READ | Job status + progress |
| POST | `/jobs/{id}/cancel` | jobs:UPDATE | Cancel job |

### 9.3.12 Bulk Operations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/bulk/students/import` | students:CREATE | CSV student import → `BulkResult` |
| POST | `/bulk/employees/import` | employees:CREATE | CSV employee import |
| POST | `/bulk/cameras/status` | cameras:UPDATE | Bulk enable/disable |
| GET | `/bulk/attendance/export` | attendance:READ | CSV export (date/section filters) |

**BulkResult:** `{total, success, failed, skipped, errors[≤20], created_ids, elapsed_ms}`.

## 9.4 Security Headers (every response)

`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy: camera=(), microphone=(), geolocation=()`,
`Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; ...`,
optional `Strict-Transport-Security` (when `ENABLE_HSTS=1`).

## 9.5 Production Secret-Key Guard

On startup, if `ENVIRONMENT=production`, the app **raises** unless
`SECRET_KEY` is set and ≥ 32 characters (fails loudly, no silent default).

---

*References: `api/main.py`, `api/bulk_operations.py`, `api/job_queue.py`,
`api/websocket_manager.py`, `docs/API_DOCUMENTATION.md`*

---

<!-- Section: 10_STREAMLIT_DASHBOARD.md -->
# Section 10 — Streamlit Dashboard

**Run:** `streamlit run dashboard/app.py` → http://localhost:8501
**Layout:** wide, expanded sidebar. Sidebar contains navigation links, DB
init status, auto-cleanup status, FAISS embedding count, recognition
threshold, and camera source.

## 10.1 Page-by-Page Explanation

### Page 01 — Dashboard (🏠 Overview)
| Element | Description |
|---------|-------------|
| **Summary cards** | Total Employees, Today's Attendance (+unique delta), Unknown Faces (pending review), System Status |
| **Recognition Status** | YOLO/InsightFace/FAISS load badges + pipeline health badges + config path |
| **Recent Attendance** | Table (time/employee/id/dept/confidence) — `st.cache_data(ttl=10)` |
| **Camera Status** | Active cameras from DB |
| **Quick Actions** | Buttons that `st.switch_page()` to every page |
| **Today's Overview** | Attendance / Unique Present / Unknown Today / Pending Review metrics |
| **Recent Recognition Activity** | RecognitionLog table |
| **Configuration** | Live values of `cfg.*` settings |
| **Getting Started + Pipeline Architecture** | Expanders with guide and ASCII pipeline diagram |

**Workflow:** Landing page for operators — glance at today's numbers, jump to
Live/Enroll/Attendance.

### Page 02 — Employees (👥 CRUD)
| Element | Description |
|---------|-------------|
| **Stats** | Total, Departments, FAISS-Enrolled, Active |
| **Search** | Text input → `EmployeeService.search()` (name/id/dept prefix) |
| **Table** | ID, Name, Department, FAISS ID, Today ✅, Enrolled date |
| **Edit expander** | Select employee → form (name/dept) → `EmployeeService.update()` (also renames FAISS label) |
| **Delete expander** | Select → type ID to confirm → `EmployeeService.delete()` (removes FAISS embedding) |
| **Add form** | Employee ID + Name + Department → `EmployeeService.create()` (duplicates → error) |
| **Attendance history** | Per-employee records (first 10 employees) |

### Page 03 — Enroll (📸 Face Enrollment)
| Element | Description |
|---------|-------------|
| **Camera source** | Selectbox of all `CAMERA_CHOICES` + URL/device fields per type |
| **Employee details form** | ID (required), Name (required), Department |
| **Capture** | Webcam → `st.camera_input` (browser); Phone/IP → `CameraSource` snapshot (10 warm-up frames) |
| **Preview/Confirm** | Image preview, "Confirm & Enroll" / "Recapture" |
| **Processing** | `FaceRecognizer.extract_embedding` → duplicate check → `FaceEnrollment.enroll` → `EmployeeService.create` (rolls back FAISS on DB failure) |

**Workflow:** form → capture → confirm → embedding → FAISS + DB → success →
"Enroll Another" or "View Employees".

### Page 04 — Live (📹 Live Recognition) ⭐
The most complex page. See §10.2 for architecture and §13 for camera system.

| Element | Description |
|---------|-------------|
| **Camera select** | PC/USB/Android/iPhone/IP with per-type config (`_render_camera_config`) |
| **Scan Cameras** | `scan_local_cameras()` + `scan_network()` discovery results |
| **START/STOP** | `_start_recognition()` / `_stop_recognition()` via `CameraOwner` |
| **Status badge** | LIVE / CONNECTING / RECONNECTING / DISCONNECTED / READY |
| **Video area** | Latest frame + overlays from `results_buffer` (drawn at display time) |
| **Sidebar live stats** | Capture FPS, AI FPS, pipeline latency, people count, worker errors, E2E latency p50/p95 |
| **Today's attendance** | Cached table (3 s TTL) |

### Page 05 — Attendance (📋 Records + Live Camera)
| Element | Description |
|---------|-------------|
| **Camera mode** | Browser Webcam (WebRTC, needs `streamlit-webrtc`) or Phone/IP Camera (`PhoneAttendanceFeed` background thread) |
| **Live camera** | WebRTC transformer `AttendanceVideoTransformer` (uses `LiveDetection`), or phone feed preview |
| **Today's summary** | Total Marks, Unique Present, All-Time Records, Employees Ever Marked |
| **Historical records** | Date picker, Export CSV, Refresh; per-date table + stats (unique, avg confidence) |
| **Pipeline debug** | Expander with config + status |
| **Auto-refresh** | Every 5 s when camera active |

### Page 06 — Unknown (🔴 Gallery + Review)
| Element | Description |
|---------|-------------|
| **Stats** | Today, This Week, Pending Review, Converted |
| **Bulk actions** | Delete All (with count), warning |
| **Filters** | Date range, Status (All/Not Reviewed/Reviewed/Converted), Max results |
| **Face cards** | Image, time, camera, confidence, status badge (Converted/Ignored/Unreviewed); actions: Register Employee, Ignore, Delete, Notes |

**Workflow:** unknown face captured by pipeline → admin reviews → convert to
employee (via `UnknownFaceService.convert_to_employee`) or ignore/delete.

### Page 07 — Analytics (📈 Charts)
Charts (Plotly):
1. Daily Attendance (bar, last 30 days)
2. Hourly Attendance (bar)
3. Top Employees (horizontal bar)
4. Recognition Accuracy (known vs unknown pie)
5. Department Distribution (pie)
6. Recognition Confidence Distribution (histogram)

### Page 08 — Settings (⚙️ Config Editor)
Full configuration editor over `settings.yaml` via `cfg.save_settings()`
(comment-preserving), plus camera diagnostics. **Verify:** camera source,
recognition thresholds, AMFR weights, deep liveness, unknown-face retention,
logging.

### Page 09 — Health (🩺 System Health)
Live component monitoring + quick-fix buttons (model reload, DB check,
camera diagnostic). Pairs with `tools/validate_startup.py`.

### Page 10 — About (ℹ️)
Version info, technology stack, credits.

## 10.2 Live Page Internals (the heart of the UI)

### `SharedModelResources` (dataclass)
- `load()` caches a `RecognitionService` as a class attribute `_cache`.
- All heavy models (YOLO, InsightFace, FAISS, AMFR) load **once**.
- New pipelines use `RecognitionService.with_shared_models(shared.service)`
  → independent per-camera state, shared models.

### `LiveRecognitionPipeline`
- **start()** — `create_camera(source_type, **kwargs)` → open → set 640×480,
  FPS cap 15 → start 3 daemon threads:
  1. `_capture_loop` — reads camera, puts **latest raw frame** into
     `frame_buffer` at capture rate; handles reconnect (up to 5 attempts).
  2. `_recognition_worker` — pulls latest frame, downscales to 320×240,
     runs `process_frame_detailed()`, scales bboxes back, caches verified
     track IDs for **adaptive cadence** (0.10 s normal → 0.60 s when all
     tracks verified & fresh), publishes to `results_buffer`.
  3. `_latency_loop` — records E2E frame age (now − put timestamp) into
     `LatencyLogger` every 0.05 s while LIVE.
- **stop()** — joins threads (3 s timeout), releases camera, clears buffers.
- **Overlays** — `_draw_overlays()`: green ✓NAME+PRESENT (ACCEPT), red
  ⚠SPOOF (REJECT), yellow NAME? COLLECTING FRAMES (BORDERLINE), grey
  ?UNKNOWN (LOW_CONFIDENCE); sublines for ID/department/confidence/liveness.

### Thread-safe buffers
- `frame_buffer` (FrameBuffer, maxlen=1) — latest raw frame, drops stale.
- `results_buffer` (ResultsBuffer, maxlen=1) — latest recognition results.
- Both in `dashboard/frame_buffer.py`, shared module-level singletons.

### `CameraOwner` (singleton)
Guarantees **one camera owner at a time**; `acquire()/release()` manage
state FREE → ACQUIRED → FREE; teardown happens outside the state lock so
slow `pipeline.stop()` never blocks concurrent checks. Survives Streamlit
reruns via `st.session_state.pipeline`.

## 10.3 Widget & Interaction Summary

| Widget | Pages | Purpose |
|--------|-------|---------|
| `st.metric` | 1,2,5,6 | KPI cards |
| `st.dataframe` | 1,2,5,6 | Tabular data |
| `st.selectbox` | 2,3,4,5,8 | Source/entity selection |
| `st.text_input` / `st.number_input` | 2,3,4,5,8 | Form fields |
| `st.form` | 2,3 | Submission + validation |
| `st.camera_input` | 3 | Browser webcam capture |
| `st.image` | 4,5,6 | Video frames / photos |
| `st.button` / `st.download_button` | 1,4,5,6 | Actions / CSV export |
| `st.expander` | 1,2,5,6,8 | Progressive disclosure |
| `st.rerun` / `st.switch_page` | 1,3,4,5,8 | Navigation & refresh |
| `st.cache_data` / `st.cache_resource` | 1,4,5,7 | Caching (SQL/DF/models) |
| `st.session_state` | 3,4,5,8 | Survive reruns |

## 10.4 Dashboard Data Sources

| Page | Services/Repos used |
|------|---------------------|
| Dashboard | EmployeeRepo, AttendanceRepo, RecognitionLogRepo, UnknownFaceRepo, CameraRepo, FaceEnrollment |
| Employees | EmployeeService, AttendanceRepo |
| Enroll | FaceRecognizer, FaceEnrollment, EmployeeService |
| Live | RecognitionService, AttendanceService, CameraOwner, buffers |
| Attendance | AttendanceService, EmployeeRepo, LiveDetection, CameraSource |
| Unknown | UnknownFaceService, CameraRepo |
| Analytics | AttendanceRepo, RecognitionLogRepo, UnknownFaceRepo, EmployeeRepo |

---

*References: `dashboard/app.py`, `dashboard/pages/*`, `dashboard/frame_buffer.py`,
`dashboard/camera_owner.py`, `dashboard/latency_logger.py`, `docs/USER_MANUAL.md`*

---

<!-- Section: 11_SECURITY.md -->
# Section 11 — Security

## 11.1 Security Model Overview

The system has **two security surfaces**:
1. **Physical/biometric** — liveness anti-spoofing on the camera pipeline.
2. **Cyber** — the FastAPI web layer (auth, RBAC, MFA, OIDC, rate limiting,
   upload security, audit).

All cyber-security features are implemented in `api/main.py`,
`services/*`, `utils/upload_security.py`; biometric security lives in
`app/liveness_detector.py` + `app/deep_liveness.py`.

## 11.2 JWT (JSON Web Tokens)

| Aspect | Detail |
|--------|--------|
| Library | `python-jose` (`jose`), HS256 |
| Secret | `SECRET_KEY` env (default dev-only `dev-secret-change-in-production`; **production startup fails loudly if unset/short**) |
| Access token | 30 min default (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| Claims | `sub` (user id), `username`, `roles`, `exp`, `iat` |
| Validation | `get_current_user()` decodes, loads user, checks `is_active` |
| Refresh tokens | Opaque 48-char `secrets.token_urlsafe`, **SHA-256 hash stored** in `refresh_tokens`; 30-day expiry; **rotation** (old revoked, `replaced_by` chain); **reuse detection** revokes all tokens |
| Logout/session revoke | `/auth/revoke-all-sessions`, password change revokes all |

## 11.3 RBAC (Role-Based Access Control)

- **7 roles** (`RoleName`): SUPER_ADMIN, COLLEGE_ADMIN, HOD, FACULTY, SECURITY, STUDENT, STAFF.
- **Permissions:** 11 resources (students, employees, cameras, attendance,
  analytics, enrollment, mfa, users, unknown_faces, jobs, audit_logs) × 5
  actions (READ/CREATE/UPDATE/DELETE/EXECUTE) + institution/department/
  course/section/classroom READ extras.
- **Mapping:** `role_permissions` + `user_roles` association tables.
- **Enforcement:** FastAPI dependencies `require_permission(resource, action)`
  and `require_role(*roles)`.
- **Seeding:** `scripts/seed_admin.py` assigns **all** permissions to
  SUPER_ADMIN, a management subset to COLLEGE_ADMIN.
- **MFA policy:** SUPER_ADMIN always requires MFA; COLLEGE_ADMIN, HOD,
  SECURITY also require MFA (`MFAService.requires_mfa`).

## 11.4 Password Security

- **Hashing:** bcrypt via `passlib.CryptContext(schemes=["bcrypt"])`.
- **Policy** (configurable env): min 12 chars, uppercase + lowercase +
  digit + special required; common weak-password blocklist.
- **Change flow:** verify current → enforce policy → hash → revoke all
  refresh tokens → audit.
- **Seed default** (`ADMIN_PASSWORD=AutoR!0t!ze*9!`) — change in production.

## 11.5 Brute Force Protection

`services/brute_force_protection.py` (uses `failed_login_attempts` table):

| Policy | Value |
|--------|-------|
| Max failed attempts per username | 5 |
| Lockout duration | 30 minutes |
| IP rate limit | 20 attempts/minute |
| Attempts cleanup | older than 7 days |
| Success resets | successful login recorded; lockout counts only failures after last success |
| Warning | ≥3 failures → "N attempts remaining" message |
| HTTP status on lock | 429 Too Many Requests |

## 11.6 MFA (Multi-Factor Authentication)

| Aspect | Detail |
|--------|--------|
| Type | TOTP (time-based one-time password) via `pyotp` |
| Enrollment | `/auth/mfa/enroll` → base32 secret + provisioning URI (QR) + 8 backup codes |
| Backup codes | 10-char hex, **SHA-256 hashed** in DB, one-time use, constant-time compare (`hmac.compare_digest`) |
| Verify | `/auth/mfa/verify` accepts TOTP (1-window drift tolerance) or backup code; only `mfa_pending` tokens accepted (prevents bypass) |
| MFA token | 2-minute JWT with `mfa_pending: true` |
| Required for | SUPER_ADMIN, COLLEGE_ADMIN, HOD, SECURITY |

## 11.7 OIDC (SSO)

- Provider-agnostic via well-known discovery (Azure AD, Keycloak, Okta, Google).
- Env: `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`,
  `OIDC_SCOPES`, `OIDC_REDIRECT_URI`.
- Flow: `/auth/oidc/login` (state stored in Redis, 5-min TTL, one-time use)
  → provider → `/auth/oidc/callback` (state validated → code exchange →
  user sync → JWT).
- If the IdP performed MFA, `mfa_last_verified` is set (no second challenge).
- Degradation: if Redis is down, CSRF state validation is skipped with a
  warning logged.

## 11.8 Liveness (Biometric Anti-Spoofing)

- **5 factors** (see §5.2⑤): LBP texture, blink (EAR), motion, screen-edge
  detection, deep CNN (MiniFASNet ONNX 80×80).
- **AMFR gates:** liveness below `LIVENESS_SPOOF_THRESHOLD (0.15)` →
  hard REJECT_SPOOF + `SPOOF_ATTEMPT` audit log.
- **Per-track state:** each tracked person gets its own `LivenessDetector`
  so one person's blink/motion doesn't pollute another's score.
- **Fallback:** if ONNX model unavailable → numpy spectral classifier.

## 11.9 Upload Security

`utils/upload_security.py` — used by `/enroll/upload`:
- **Magic bytes** format detection (JPEG/PNG/GIF/WebP) — never trusts the
  extension.
- **Size limit** (5 MB default, `MAX_UPLOAD_SIZE_MB`).
- **Pillow verify** — rejects truncated/corrupt images.
- **Dimension limits** — 4096×4096, 8 MP max.
- **Server-side filenames** — `enroll_<ts>_<uuid>.<ext>` (path-traversal
  immune); `sanitize_filename()` strips path components + null bytes.
- **Request body cap** — 10 MB middleware (`MAX_BODY_SIZE_BYTES`).

## 11.10 Audit Logs

`AuditLog` table (see §8.2.9) records: action, actor (+type), actor_id,
timestamp, resource_type/id, description, **IP**, **user-agent**,
request_id, JSON details, severity (INFO/WARNING/ERROR/CRITICAL).
Every sensitive path calls `log_audit()` or `AuditService.log()` — login
success/failure, attendance, enrollment, config changes, spoof attempts,
session revocation.

## 11.11 Rate Limiting

- **slowapi** `Limiter(key_func=get_remote_address)` + `SlowAPIMiddleware`.
- Per-endpoint limits: login 10/min, logout 20/min, me 30/min,
  change-password 5/min, enroll-upload 5/min, general API 100/min
  (`API_RATE_LIMIT`), jobs 20/min, bulk 30/min.
- `/health`, `/metrics` exempt.

## 11.12 Security Headers

Applied by response middleware: `X-Content-Type-Options`, `X-Frame-Options:
DENY`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy` (blocks
camera/mic/geo in the API), `Content-Security-Policy`, optional HSTS
(`ENABLE_HSTS=1`). Additional middleware: CORS (configurable origins),
TrustedHost (Host-header protection, `*` only in dev), X-Request-ID tracing.

## 11.13 Other Security Practices

- **Safe errors:** global handlers return generic messages — no stack
  traces or internals leaked; 500s log server-side with `exc_info`.
- **Docs disabled in production** (`docs_url=None`).
- **Redis bound to localhost** in docker-compose (127.0.0.1) and PostgreSQL
  bound to 127.0.0.1; both have healthchecks.
- **Refresh tokens in POST body** (not query params) so they never appear
  in access logs.
- **Production secret-key validation** at startup (fail-fast).
- **Idempotent seed** — safe to re-run.

## 11.14 Known Gaps / Notes

- `TrustedHostMiddleware` with `allowed_hosts=["*"]` in dev only; set
  explicit hosts in production.
- OIDC state validation degrades when Redis is unavailable (logged).
- Uploads are validated but stored on local disk — production should use an
  immutable store + signed URLs (see §29).
- HSTS is opt-in (`ENABLE_HSTS=1`) — enable after HTTPS is configured.

---

*References: `api/main.py`, `services/*`, `utils/upload_security.py`,
`docs/SECURITY_REPORT.md`, `scripts/seed_admin.py`*

---

<!-- Section: 12_ATTENDANCE_SYSTEM.md -->
# Section 12 — Attendance System

## 12.1 Simple Explanation

A person walks in front of the camera. The system recognizes their face,
checks they haven't already been marked today, and records their attendance
with a timestamp and confidence score — in **both** the database and a
per-day CSV file. The dashboard then shows today's attendance, and analytics
produce reports.

## 12.2 Complete Workflow

```
Student/Employee enters camera view
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  Recognition pipeline (YOLO → RetinaFace → Quality →    │
│  Liveness → ArcFace → FAISS)                             │
└─────────────────────────────────────────────────────────┘
        │
        ▼
AMFR decision engine
   ├─ ACCEPT ─────────────► ─┐
   ├─ BORDERLINE ──────────►  │ (collect more frames)
   ├─ LOW_CONFIDENCE ─────►  │ (save unknown face)
   └─ REJECT_SPOOF ────────►  │ (alert + audit, NO attendance)
                             ▼
                    ┌─────────────────────┐
                    │ _maybe_mark_attendance│  (RecognitionService /
                    │  / AttendanceService  │   LiveDetection)
                    └─────────────────────┘
        │ checks
        ▼
  1. Session cooldown?  (COOLDOWN_SECONDS=60, per name)
  2. Already marked today in DB?  (AttendanceRepo.is_marked_today)
        │
        ▼  (both clear)
┌─────────────────────────────────────────────────────────┐
│  WRITE                                                │
│  • DB: attendance row (employee_id, confidence,        │
│        timestamp, method=FACE_RECOGNITION,             │
│        status=PRESENT, camera_id)                      │
│  • CSV: attendance/YYYY-MM-DD.csv                      │
│  • Audit: AuditService.log("MARK_ATTENDANCE", ...)     │
│  • RecognitionLog row (is_known=True, liveness,        │
│        quality, track_id)                              │
└─────────────────────────────────────────────────────────┘
        │
        ▼
Dashboard: Live page shows "✓ NAME · PRESENT"
Attendance page: today's table updates (5 s auto-refresh)
Analytics: daily/hourly charts update
```

## 12.3 Dual-Write Design (why both DB and CSV?)

| Store | Purpose | Who reads it |
|-------|---------|--------------|
| SQLite/PostgreSQL `attendance` | Structured queries, analytics, API | Dashboard, API, analytics |
| `attendance/YYYY-MM-DD.csv` | Backward compatibility with the original CLI (`app/attendance.py`) | CLI mode, manual inspection, simple exports |

`AttendanceService.mark()` writes both; `LiveDetection._log_attendance_db()`
writes the DB side for the CLI pipeline. The CSV logger can be deprecated
once the terminal app is fully replaced (noted in the service docstring).

## 12.4 Deduplication (preventing double-marking)

Three layers prevent duplicates:
1. **Session cache** — `_marked_this_session` set (per pipeline/session).
2. **Cooldown** — per-name timestamp; only re-marks after
   `COOLDOWN_SECONDS` (default 60 s) AND a session reset.
3. **Database** — `AttendanceRepo.is_marked_today()` checks for an existing
   row for the employee today before inserting.

Result: exactly **one attendance record per person per day** (per employee).

## 12.5 Data Model Fields

| Field | Source | Notes |
|-------|--------|-------|
| employee_id / student_id | recognition lookup | employee path is active |
| section_id / course_id / classroom_id | API manual mark (timetable-aware) | optional |
| camera_id | pipeline | which camera captured |
| timestamp | `_utcnow()` | when marked |
| confidence | AMFR risk score | 0–1 |
| method | `FACE_RECOGNITION` (or manual) | |
| status | `PRESENT` (or ABSENT/LATE/EXCUSED via API) | |
| marked_manually / marked_by_user_id / manual_notes | API manual override | audit trail for corrections |

## 12.6 Attendance Queries & Reports

| Query | Implementation |
|-------|----------------|
| Today's records | `AttendanceRepo.get_today()` / `AttendanceService.get_today()` |
| By date | `get_by_date(date)` |
| By employee | `get_by_employee(id)` (history) |
| Statistics | `get_statistics()` → today_count, unique_today, total_records, unique_employees |
| Dashboard cards | Dashboard page via `get_home_stats()` (10 s cache) |
| Charts | Analytics page: daily/hourly bars, top employees, confidence histogram |
| CSV export | Attendance page download button; `api/bulk_operations.py export_attendance_csv()` |
| API | GET `/attendance` (filters + pagination); POST `/attendance` (manual) |

## 12.7 Timetable-Aware Attendance (API layer)

`api/attendance_service.py` adds college semantics for manual marks:
- `is_class_in_session()` — checks weekday + time against `timetables`
  with a 10-minute grace period.
- `is_student_enrolled()` — student must be an ACTIVE enrollment in the section.
- `create_attendance()` — derives course/classroom/section when possible and
  rejects non-enrolled students.

> **Note:** the live camera pipeline marks attendance by *employee* (legacy
> path). Student/timetable-aware marking is available via the API and is the
> intended college path per the schema.

## 12.8 Reset & Session Semantics

- **Reset Session Markers** (Live page) → `reset_tracking()` clears the
  session set + cooldowns + AMFR tracker state → people can be re-marked.
- **Per-day reset** is automatic (dedupe checks today's date).
- **CLI:** pressing `R` clears `_marked_this_session`.

## 12.9 Failure Handling

- If DB write fails (e.g. DB down), the pipeline logs a warning and
  **does not crash** — CSV may still record the event.
- `_log_attendance_db()` silently returns when no employee record exists
  (unknown person → unknown-face path instead).
- Recognition logs are best-effort (`logger.warning` on failure).

---

*References: `app/attendance.py`, `services/attendance_service.py`,
`services/recognition_service.py`, `api/attendance_service.py`,
`database/repository.py`, `dashboard/pages/05_Attendance.py`*

---

<!-- Section: 13_CAMERA_SYSTEM.md -->
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

---

<!-- Section: 14_PERFORMANCE.md -->
# Section 14 — Performance

## 14.1 Performance Strategy

The system is designed for **real-time CPU inference on commodity hardware**.
Every stage is optimized to reduce wasted work while keeping the display fluid.

## 14.2 Threading Model

| Thread | Owner | Work | Lifecycle |
|--------|-------|------|-----------|
| Capture loop | `LiveRecognitionPipeline` | reads camera → `frame_buffer.put()` | daemon; stopped via join(3s) |
| Recognition worker | `LiveRecognitionPipeline` | AMFR pipeline → `results_buffer` | daemon; adaptive cadence |
| Latency sampler | `LiveRecognitionPipeline` | E2E frame age → `LatencyLogger` | daemon; 0.05 s cadence |
| Job queue workers | `api/job_queue.py` | asyncio tasks (3 workers) | started/stopped by FastAPI lifespan |
| WebSocket heartbeat | `api/websocket_manager.py` | ping + dead-client cleanup | asyncio task, 15 s |

**Why background threads:** Streamlit reruns the script top-to-bottom; the
camera must survive reruns, so capture/AI run in daemon threads and the UI
only reads the latest frames/results (non-blocking).

## 14.3 Queues & Buffers

| Buffer | Semantics | Prevents |
|--------|-----------|----------|
| `FrameBuffer(maxlen=1)` | latest-frame-only; stale frames dropped | queue buildup on slow consumers |
| `ResultsBuffer(maxlen=1)` | latest results only | stale overlays |
| `asyncio.Queue(maxsize=100)` (job queue) | bounded job queue | unbounded memory |
| WebSocket event buffer | last 100 events | slow-client disconnect data loss |

**Key property:** writers never block on slow readers; readers never wait.

## 14.4 Frame Buffer Benefits

- Camera thread can run at full capture rate while AI is still processing
  the previous frame.
- Streamlit reruns always see the newest frame, so video never lags by an
  accumulating queue.
- `get_with_meta()` returns timestamps → precise E2E latency measurement.

## 14.5 Caching

| Cache | Where | Effect |
|-------|-------|--------|
| `SharedModelResources._cache` | 04_Live.py | YOLO/InsightFace/FAISS/AMFR loaded **once** (~2 GB RAM saved across pipelines) |
| `with_shared_models()` | recognition_service | shares models, isolates per-pipeline state |
| `_employee_cache` | LiveDetection | name→employee_id DB lookup avoided per frame |
| `_verified_at` track cache | pipeline | verified scenes run AI 6× less often (0.6 s vs 0.1 s) |
| `st.cache_data` | dashboard pages | SQL/DF results cached with TTL (3–60 s) |
| `st.cache_resource` | dashboard | long-lived resources across reruns |
| Redis (optional) | api/redis_client | attendance dedupe, camera status, cooldowns, OIDC state |

## 14.6 AI-Specific Optimizations

| Optimization | Implementation | Benefit |
|--------------|----------------|---------|
| Frame skip | `FRAME_SKIP=2` (CLI/service) | 50–75% fewer inferences |
| Downscale | AI on 320×240 (`AI_PROCESS_SIZE`) | ~4× faster YOLO/ArcFace |
| Early exit | no detections → skip FAISS/AMFR | ~200 ms saved on empty frames |
| Adaptive cadence | verified tracks → 0.6 s interval | big CPU saving when scene is stable |
| Camera FPS cap | 15 FPS via CAP_PROP_FPS | less USB bandwidth |
| LBP downscale | 48×48 for texture analysis | ~0.1 ms per call |
| HNSW index | approximate ANN (efSearch=128) | sub-linear search |
| FPS EMA | `0.9*old + 0.1*new` | stable FPS readouts |
| psutil hoisted | module-level import | no repeated import lookup in hot path |

## 14.7 GPU Usage

- **Currently CPU-only inference:** InsightFace uses
  `CPUExecutionProvider`; onnxruntime uses `CPUExecutionProvider`.
- Dockerfile supports GPU builds (`--gpus all`) — the base image includes
  GPU-capable deps, but the code paths run on CPU by default.
- GPU acceleration is future work for higher multi-camera FPS.

## 14.8 CPU Usage

- YOLO11n: ~15–40 ms/frame (CPU).
- InsightFace (RetinaFace+ArcFace) on person crop: ~20–60 ms.
- MiniFASNet ONNX: ~5 ms; fallback CNN: ~0.5 ms.
- Quality/LBP/blink/motion: sub-ms each.
- With frame-skip + downscale + adaptive cadence, total CPU is modest for a
  single camera on a modern laptop.

## 14.9 Memory Usage

- Models in RAM: YOLO11n ~6 MB weights + runtime; buffalo_l ~200 MB;
  FAISS index grows with enrollments (512-D float32 = 2 KB/vector + graph
  overhead for HNSW); fallback CNN negligible.
- Streamlit reruns are cheap because models are cached in `_cache`.
- LatencyLogger window bounded (500 samples); WS event buffer bounded (100).

## 14.10 Measured Performance (references)

The repository includes benchmark scripts and reports:
- `scripts/benchmarks/profile_pipeline.py` — per-stage profiling.
- `scripts/benchmarks/faiss_benchmark.py` — index build/query timing.
- `scripts/benchmarks/camera_validation.py` — camera latency/FPS.
- `scripts/benchmarks/fake_camera_validation.py` — hardware-free pipeline FPS/latency.
- `scripts/benchmarks/scalability_benchmark.py` — enrollment scale tests.
- `docs/PERFORMANCE_REPORT.md` — measured GPU-accelerated report.
- `scripts/benchmarks/tune_hnsw.py` / `tune_ivf.py` — index tuning
  (M=32, efC=200, efS=128; nlist=200, nprobe=256).

## 14.11 Optimization Recommendations (future)

1. ONNX-export YOLO + ArcFace for faster, more portable inference.
2. GPU execution providers when NVIDIA hardware is available.
3. Reduce re-validation frequency (raise `identity_ttl` carefully).
4. Batch FAISS searches across detections.
5. Vectorize the IoU matching loop (currently Python loops over track×detection).

---

*References: `dashboard/pages/04_Live.py`, `dashboard/frame_buffer.py`,
`config/settings.yaml`, `scripts/benchmarks/*`, `docs/PERFORMANCE_REPORT.md`*

---

<!-- Section: 15_PACKAGES.md -->
# Section 15 — Packages & Libraries

All packages below are declared in `requirements.txt`. For each: purpose,
why used, alternatives, and which module uses it.

## 15.1 Core

| Package | Purpose | Why used | Alternatives | Used in |
|---------|---------|----------|--------------|---------|
| **streamlit** ≥1.28 | Build the web dashboard | Python-native UI; rerun model fits camera loops; easy charts | Gradio, Dash, Panel, Flask+JS | `dashboard/` |
| **opencv-python** ≥4.8 | Image/video processing | Camera capture, drawing, CV metrics (Laplacian, Canny, LBP) | Pillow (limited video), scikit-image | almost everywhere |
| **numpy** ≥1.24 | Numerical arrays | Embeddings, tensors, IoU, stats | — | everywhere |
| **pandas** ≥2.0 | Tabular data | Dashboard DataFrames, analytics | polars | dashboard pages |
| **Pillow** ≥10 | Image I/O | Upload verification (magic bytes + decode) | — | `utils/upload_security.py` |

## 15.2 AI Models

| Package | Purpose | Why used | Alternatives | Used in |
|---------|---------|----------|--------------|---------|
| **torch** ≥2.0 (≠2.4.0) | Deep learning runtime | YOLO11 runs on PyTorch; 2.4.0 excluded (Windows fbgemm.dll breakage) | — | `app/face_detector.py` (transitively) |
| **ultralytics** ≥8.0 | YOLO11 | Person detection (person class) | YOLOv5, MediaPipe | `app/face_detector.py` |
| **insightface** ≥0.7.3 | RetinaFace + ArcFace | Face detection + 512-D embeddings | face_recognition (dlib), facenet | `app/recognizer.py`, enrollment, services |
| **faiss-cpu** ≥1.7 | Vector search | ANN index for embeddings | hnswlib, Milvus, pgvector | `app/enrollment.py` |
| **onnxruntime** ≥1.15 | ONNX inference | MiniFASNet liveness (~5 ms CPU) | — | `app/deep_liveness.py` |
| **psycopg2-binary** ≥2.9 | PostgreSQL driver | prod DB | asyncpg | `database/`, scripts |

## 15.3 Security & Infrastructure

| Package | Purpose | Why used | Alternatives | Used in |
|---------|---------|----------|--------------|---------|
| **fastapi** ≥0.100 | REST framework | async API, Pydantic validation, docs | Flask, Django REST | `api/` |
| **uvicorn[standard]** | ASGI server | run FastAPI | hypercorn, gunicorn (uvicorn workers) | run commands |
| **python-multipart** | form parsing | UploadFile support | — | `api/main.py` |
| **python-magic** ≥0.4.27 | MIME detection | Magic-bytes file type (declared; upload_security uses its own magic-byte dict to avoid Windows libmagic segfaults — see code comment) | filetype, pure-python magic | `utils/upload_security.py` (fallback) |
| **slowapi** ≥0.1.9 | Rate limiting | per-endpoint IP limits | limits, custom middleware | `api/main.py` |
| **secure** ≥0.3.0 | Security headers helper | (declared; headers are also set manually in middleware) | manual middleware | `api/main.py` |
| **python-dotenv** ≥1.0 | env loading | `.env` config | — | config/bootstrap |
| **httpx** ≥0.27 | async HTTP client | OIDC provider calls (discovery, token exchange) | aiohttp, requests | `services/oidc_service.py` |
| **pyotp** ≥2.9 | TOTP | MFA authenticator codes | onetimepass | `services/mfa_service.py` |
| **passlib** | password hashing | bcrypt context | argon2-cffi, bcrypt direct | `api/main.py` |
| **python-jose** | JWT | sign/verify access + MFA tokens | PyJWT | `api/main.py` |
| **bcrypt** | password hashing | direct hashing in seed script | — | `scripts/seed_admin.py` |
| **cryptography** | crypto primitives | (transitive for jose/TLS) | — | transitively |

## 15.4 Additional / Production

| Package | Purpose | Why used | Alternatives | Used in |
|---------|---------|----------|--------------|---------|
| **redis** ≥4.4 | Redis client | state/cache (graceful fallback) | fakeredis (tests) | `api/redis_client.py` |
| **hiredis** ≥2.3 | faster Redis parser | performance (optional) | — | redis client |
| **plotly** ≥5.18 | interactive charts | Analytics page | matplotlib, altair | `dashboard/pages/07_Analytics.py` |
| **prometheus-client** ≥0.19 | metrics | `/metrics` endpoint | statsd, opentelemetry | `api/main.py` |
| **ydata-profiling** ≥2.0 | data profiling | (declared; profiling reports) | pandas-profiling | optional use |
| **psutil** ≥5.9 | system metrics | CPU/RAM monitoring on Live page sidebar | — | `dashboard/pages/04_Live.py` |
| **python-json-logger** ≥2.0 | JSON structured logs | (declared; production logging) | structlog | logging config |
| **gunicorn** ≥21.2 | WSGI server | Streamlit production serving (per README) | — | deployment |
| **ruamel.yaml** | YAML round-trip | comment-preserving settings save | pyyaml (used for load) | `config/config.py` |
| **requests** | HTTP client | camera discovery + connectivity probes | httpx | `camera/discovery.py`, `camera/phone.py` |
| **streamlit-webrtc** (optional) | browser WebRTC | Attendance page browser webcam (optional dep — page degrades gracefully) | — | `dashboard/pages/05_Attendance.py` |
| **pydantic** (via fastapi) | validation | schemas, EmailStr, validators | marshmallow | `api/main.py` |
| **pytest** (dev) | testing | 490 tests | unittest, tox | `tests/` |
| **pytest-cov** (dev) | coverage | coverage reports | coverage | `tests/` |
| **alembic** | migrations | schema versioning | raw SQL, SQLAlchemy create_all | `database/database.py`, `alembic/` |
| **sqlalchemy** | ORM | models, sessions, repository | SQLObject, Tortoise | `database/` |
| **faiss** | — | see faiss-cpu | — | — |

## 15.5 Package → Module Map (quick reference)

| Package | Primary consumers |
|---------|-------------------|
| ultralytics / torch | app/face_detector.py |
| insightface | app/recognizer.py, app/enrollment.py (via recognizer) |
| faiss-cpu | app/enrollment.py |
| onnxruntime | app/deep_liveness.py |
| opencv-python | app/*, camera/*, services/recognition_service.py, dashboard pages |
| streamlit + plotly + pandas | dashboard/* |
| fastapi + slowapi + jose + passlib + pyotp + httpx | api/*, services/oidc_service.py, services/mfa_service.py |
| sqlalchemy + alembic + psycopg2-binary | database/*, alembic/* |
| redis + hiredis | api/redis_client.py |
| requests | camera/discovery.py, camera/phone.py |
| ruamel.yaml + pyyaml | config/config.py |
| Pillow | utils/upload_security.py |
| psutil | dashboard/pages/04_Live.py |
| prometheus-client | api/main.py |

## 15.6 Notable Version Pins & Notes (from requirements.txt comments)

- `torch>=2.0.0,!=2.4.0` — torch 2.4.0 is broken on Windows
  (`fbgemm.dll` WinError 126) and excluded by ultralytics on win32.
- `ydata-profiling>=2.0.0` — renamed from pandas-profiling.
- `python-magic` declared, but `utils/upload_security.py` uses a local
  magic-byte dict because libmagic segfaults on Windows.
- `streamlit-webrtc` is **optional** (not in requirements.txt) — the
  Attendance page imports it defensively.

---

*References: `requirements.txt`, module imports throughout the codebase*

---

<!-- Section: 16_CONFIGURATION.md -->
# Section 16 — Configuration

## 16.1 Configuration Layers

The system is configured through **three layers** (later wins):

1. `config/settings.yaml` — user-editable, human-readable settings.
2. `config/config.py` — Python constants with fallback defaults.
3. Environment variables — for API/DB/Redis/OIDC/security (Docker-friendly).

## 16.2 `config/settings.yaml` (full reference, verified)

```yaml
camera:
  source_type: webcam        # webcam | android_usb | android_wifi | iphone_usb | iphone_wifi
  id: 0                      # device index
  url: "http://192.168.1.100:8080/video"
  width: 480
  height: 360
  fps: 15
  auto_connect: false

recognition:
  yolo_confidence: 0.60
  recognition_threshold: 1.0    # FAISS L2 distance (1.0-1.5 same person range)
  frame_skip: 2                 # process every Nth frame
  cooldown_seconds: 60          # re-mark window
  identity_ttl: 3.0             # verified-track revalidation seconds

database:
  type: sqlite                  # sqlite | postgresql
  path: data/face_recognition.db

enrollment:
  min_face_size: 100
  capture_count: 1

faiss:
  index_type: hnsw              # flat | hnsw | ivf
  hnsw: { M: 32, ef_construction: 200, ef_search: 128 }
  ivf:  { nlist: 200, nprobe: 256 }

amfr:
  face_quality_min_score: 0.35
  liveness_min_score: 0.30
  liveness_spoof_threshold: 0.15
  high_confidence_threshold: 0.70
  borderline_threshold: 0.40
  weight_arcface: 0.45
  weight_liveness: 0.35
  weight_quality: 0.20

deep_liveness:
  enabled: true
  threshold: 0.50
  use_fallback: true
  auto_download: true

unknown_faces:
  retention_days: 30            # 0 = never delete

logging:
  level: INFO
  file: logs/app.log
  max_size_mb: 10
  backup_count: 3
```

> **Note:** `recognition_threshold` defaults to **1.0** in the current
> settings.yaml (README's table mentions 1.2 in an older revision; the
> shipped YAML is authoritative).

## 16.3 `config/config.py` Behavior

- Loads YAML at import; missing keys fall back to Python defaults
  (`_get(*keys, default=...)`).
- Exposes typed module constants used everywhere:
  - Paths: `MODELS_DIR`, `EMBEDDINGS_DIR`, `ATTENDANCE_DIR`, `LOGS_DIR`,
    `OUTPUTS_DIR`, `UNKNOWN_FACES_DIR`, `DATASET_DIR`.
  - Models: `YOLO_MODEL_PATH`, `INSIGHTFACE_MODEL=buffalo_l`,
    `EMBEDDING_DIM=512`.
  - Detection: `YOLO_CONFIDENCE`, `RECOGNITION_THRESHOLD`, `FRAME_SKIP`,
    `COOLDOWN_SECONDS`, `IDENTITY_TTL`.
  - Camera: `CAMERA_ID`, `CAMERA_SOURCE_TYPE`, `CAMERA_URL`, `CAMERA_AUTO_CONNECT`.
  - AMFR: `FACE_QUALITY_MIN_SCORE`, `LIVENESS_MIN_SCORE`,
    `LIVENESS_SPOOF_THRESHOLD`, `AMFR_HIGH_CONFIDENCE_THRESHOLD`,
    `AMFR_BORDERLINE_THRESHOLD`, weights.
  - Deep liveness: `DEEP_LIVENESS_*`.
  - FAISS: `FAISS_INDEX_TYPE`, `FAISS_HNSW_*`, `FAISS_IVF_*`.
  - `UNKNOWN_FACE_RETENTION_DAYS`.
- **`save_settings(updates)`** — writes back to YAML using **ruamel.yaml
  round-trip** so comments survive; reloads in-memory dict.
- Creates required directories at import.
- Configures logging: console + `RotatingFileHandler` (10 MB × 3 backups).

## 16.4 Environment Variables (API & infra)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_TYPE` | `sqlite` | sqlite \| postgres |
| `DATABASE_URL` | — | PostgreSQL URL (required if postgres) |
| `SECRET_KEY` | dev placeholder | JWT signing; ≥32 chars enforced in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 30 | refresh token lifetime |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CORS_ORIGINS` | `http://localhost:8501` | comma-separated allowed origins |
| `ENVIRONMENT` | `development` | production disables docs + validates secret |
| `LOG_LEVEL` | INFO | logging level |
| `MAX_UPLOAD_SIZE_MB` | 5 | enrollment upload cap |
| `MAX_BODY_SIZE_BYTES` | 10 MB | request body cap |
| `MAX_FAILED_LOGIN_ATTEMPTS` | 5 | brute-force lockout |
| `LOCKOUT_DURATION_MINUTES` | 30 | lockout window |
| `PASSWORD_MIN_LENGTH` / `PASSWORD_REQUIRE_*` | 12 / true | password policy |
| `LOGIN_RATE_LIMIT` / `API_RATE_LIMIT` / `ENROLL_RATE_LIMIT` | 10/100/5 per minute | rate limits |
| `ENABLE_HSTS` | `0` | HSTS header toggle |
| `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_SCOPES`, `OIDC_REDIRECT_URI` | — | SSO |
| `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | admin / admin@college.edu / AutoR!0t!ze*9! | seed script |

## 16.5 Docker Configuration

### `Dockerfile` (multi-stage)
- `python:3.11-slim` base; installs system deps (OpenCV runtime libs
  libgl1/libglib2.0, libmagic), Python deps.
- `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `PIP_NO_CACHE_DIR=1`.
- GPU-capable (`docker run --gpus all`); healthcheck + verify step runs
  critical module imports after build.

### `docker-compose.yml` (3 services)

| Service | Image | Notes |
|---------|-------|-------|
| `faceai-db` | `postgres:16-alpine` | env `POSTGRES_USER/PASSWORD/DB` (defaults faceai/changeme/face_recognition), bound 127.0.0.1:5432, pg_isready healthcheck |
| `faceai-redis` | `redis:7-alpine` | `--requirepass` only when `REDIS_PASSWORD` set (avoids empty-flag crash), bound 127.0.0.1:6379, redis-cli ping healthcheck |
| app | built from Dockerfile | depends on healthy db + redis |

Volumes: `postgres_data`, `redis_data`.

> **Security note:** ports bound to **127.0.0.1 only** — not publicly
> accessible.

## 16.6 `alembic.ini`

Standard Alembic config; `database.py` points at `ROOT_DIR/alembic.ini`
for `run_migrations()`.

---

*References: `config/settings.yaml`, `config/config.py`, `api/main.py`
(Settings model), `Dockerfile`, `docker-compose.yml`, `alembic.ini`,
`docs/DEPLOYMENT.md`*

---

<!-- Section: 17_DEPLOYMENT.md -->
# Section 17 — Deployment

## 17.1 Prerequisites

- **Python 3.10+** (3.11 recommended; Docker uses 3.11-slim).
- **pip**, optional **venv**.
- Windows: no extra system deps for webcam (DirectShow); OpenCV wheels
  include everything.
- Linux: `libgl1`, `libglib2.0-0` (or use Docker).
- PostgreSQL 16 (production), Redis 7 (optional, recommended).
- Models auto-download on first run: YOLO11n (~6 MB), InsightFace buffalo_l
  (~200 MB), MiniFASNet ONNX (~4 MB).

## 17.2 Development (Windows / Linux)

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head                # create schema
python scripts/seed_admin.py        # create admin + RBAC (first time)

# CLI mode
python main.py                      # live webcam
python main.py --debug              # diagnostics

# Dashboard
streamlit run dashboard/app.py      # http://localhost:8501

# API (optional)
uvicorn api.main:app --reload --port 8000   # http://localhost:8000/docs
```

**Verification:** `python tools/validate_startup.py`.

## 17.3 Production (Linux server)

| Step | Command / action |
|------|------------------|
| 1. System deps | `apt install -y libgl1 libglib2.0-0 libmagic1` |
| 2. Code + venv | clone repo, create venv, `pip install -r requirements.txt` |
| 3. Database | `DB_TYPE=postgres DATABASE_URL=postgresql://faceai:pass@localhost:5432/face_recognition` |
| 4. Migrations | `alembic upgrade head` |
| 5. Secrets | `export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")`; `ENVIRONMENT=production` |
| 6. Redis | install + `REDIS_URL=redis://localhost:6379/0` |
| 7. API service | systemd unit running `uvicorn api.main:app --host 0.0.0.0 --port 8000` (or gunicorn with uvicorn workers) |
| 8. Dashboard service | systemd unit running `streamlit run dashboard/app.py --server.port 8501` |
| 9. Reverse proxy (optional) | nginx/Caddy → TLS → HSTS (`ENABLE_HSTS=1`), trusted hosts configured |
| 10. Health checks | `/health`, `/health/ready`, `/health/live`; Prometheus `/metrics` |

**Production guardrails (fail-fast):**
- `ENVIRONMENT=production` + default/short `SECRET_KEY` → startup **raises**.
- API docs disabled in production.
- `TrustedHostMiddleware` — set explicit allowed hosts (dev uses `*`).

## 17.4 Docker Deployment

```bash
# Build image
docker build -t face-recognition-ai .

# Full stack (PostgreSQL + Redis + app)
docker-compose up -d

# GPU variant (if NVIDIA hardware)
docker run --gpus all -p 8000:8000 face-recognition-ai
```

`docker-compose.yml` provides `faceai-db` (postgres:16-alpine),
`faceai-redis` (redis:7-alpine), and the app service, with healthchecks and
localhost-only ports.

## 17.5 Deployment Checklist (see also §29.5)

1. ✅ Python/Docker installed, deps installed
2. ✅ DB migrated (`alembic upgrade head`), admin seeded
3. ✅ `SECRET_KEY` set (≥32 chars) in production
4. ✅ `ENVIRONMENT=production`
5. ✅ Redis reachable (or accept degraded mode)
6. ✅ Camera tested (`python main.py --debug` or dashboard Health page)
7. ✅ First enrollment done (Enroll page)
8. ✅ Backup configured (`scripts/backup.py` + cron)
9. ✅ Firewall: 8501/8000 only as needed; DB/Redis on 127.0.0.1
10. ✅ TLS + HSTS behind reverse proxy

## 17.6 Environment Matrix

| Concern | Development | Production |
|---------|-------------|------------|
| DB | SQLite (default) | PostgreSQL 16 |
| Redis | optional | recommended |
| Docs | `/docs` enabled | disabled |
| SECRET_KEY | default dev value | required, ≥32 chars |
| CORS | localhost:8501 | explicit origins |
| Trusted hosts | `*` | explicit list |
| HSTS | off | on after TLS |
| Logging | INFO console | JSON structured (python-json-logger available) |

## 17.7 Backup & Restore (ops)

- **Backup:** `python scripts/backup.py` — pg_dump + FAISS index + metadata
  + manifest (SHA-256 hashes) into `backups/backup_<ts>/`.
- **Restore:** `python scripts/restore.py --backup-dir backups/backup_<ts>`
  — verifies integrity → terminates connections → drop/recreate DB →
  restore SQL → restore FAISS artifacts. `--dry-run` to preview;
  `--no-db` to skip DB. **App must be stopped first** (DROP DATABASE needs
  no active connections).
- **Cron suggestion:** nightly backup + off-site copy
  (see `docs/BACKUP_RESTORE_GUIDE.md`).

---

*References: `Dockerfile`, `docker-compose.yml`, `run.sh`, `run.bat`,
`docs/DEPLOYMENT.md`, `docs/BACKUP_RESTORE_GUIDE.md`, `scripts/backup.py`,
`scripts/restore.py`, `tools/validate_startup.py`*

---

<!-- Section: 18_TESTING.md -->
# Section 18 — Testing

## 18.1 Test Suite Overview

- **Runner:** pytest (`pytest.ini` config at repo root).
- **Count:** 20 test modules; **490 tests passing with Redis+PostgreSQL**,
  484 passing + 6 skipped without Redis.
- **Command:** `python -m pytest tests/ -v`
- **Coverage:** `python -m pytest tests/ --cov=app --cov=services --cov=database`

## 18.2 Test File Reference

| Test file | Type | Covers |
|-----------|------|--------|
| `test_enrollment.py` | Unit | FAISS enroll/search/remove_by_name/rename/clear/status, thresholds |
| `test_attendance_service.py` | Unit/Service | Marking, daily dedupe, queries, stats |
| `test_employee_service.py` | Unit/Service | CRUD, name→FAISS sync on rename/delete |
| `test_repair.py` | Unit | Camera selection + config-UI repair regressions |
| `test_repository.py` | Unit | Repository CRUD (employees, attendance, unknown faces) |
| `test_repository_pagination.py` | Unit | `PageResult`, skip/limit, has_more |
| `test_face_quality.py` | Unit | All quality metrics + failure reasons |
| `test_deep_liveness.py` | Unit | ONNX preprocess shape, fallback path (monkeypatched to force fallback), thresholds |
| `test_liveness_detector.py` | Unit | 5-factor scoring, blink state, screen detection, spoof reasons |
| `test_tracking.py` | Unit | IoU matching, greedy assignment, identity stability, pruning |
| `test_upload_security.py` | Unit | Magic bytes, size limits, dimensions, safe filenames |
| `test_brute_force_protection.py` | Unit | Lockout, IP rate limit, reset on success, lockout info |
| `test_ip_camera.py` | Unit | IP camera source open/read/release |
| `test_phone_cameras.py` | Unit | Phone camera sources (Android/iPhone modes) |
| `test_camera_owner.py` | Unit | Singleton ownership, acquire/release transitions |
| `test_frame_buffer.py` | Unit | Latest-frame semantics, close, IDs/timestamps |
| `test_latency_logger.py` | Unit | Rolling stats, percentiles |
| `test_audit_service.py` | Unit | Audit logging |
| `test_integration.py` | Integration | PostgreSQL + Redis live paths (skips when unavailable) |

## 18.3 Test Types

### Unit Tests
- Target a single module with mocked/forced dependencies.
- Example: `test_deep_liveness.py` **monkeypatches** `_get_model_path` and
  `_download_model` so tests deterministically exercise the fallback path
  regardless of local model presence.

### Service Tests
- Exercise `services/*` against the real SQLite DB (in-memory or temp file)
  via `get_session()`; verify audit + FAISS side effects.

### Integration Tests
- `test_integration.py` — needs live **PostgreSQL + Redis**; gracefully
  skips when services are unavailable (this is the "6 skipped" set).
- Verified green in the acceptance run: 490 passed with services.

### Performance / Benchmark Scripts (`scripts/benchmarks/`)
Not pytest — standalone scripts:
- `faiss_benchmark.py` — index build/query latency at scale.
- `tune_hnsw.py` / `tune_ivf.py` — parameter sweeps → tuned config.
- `camera_validation.py` — camera FPS + E2E latency measurement.
- `fake_camera_validation.py` — hardware-free pipeline validation.
- `profile_pipeline.py` — per-stage timing (YOLO/RetinaFace/ArcFace/FAISS/AMFR).
- `benchmark_real_embeddings.py` — recognition with real embeddings.
- `scalability_benchmark.py` — enrollment count scaling.
- `probe_environment.py` — dependency/environment probing.
- `validate_amfr.py` — AMFR decision validation.

## 18.4 Conventions & Fixtures

- `tests/conftest.py` provides shared fixtures.
- Tests are deterministic where possible (monkeypatch model paths).
- DB-dependent tests use project SQLite path or create temp databases
  (`reset_db()` available in `database/database.py`).

## 18.5 CI/CD

`.github/workflows/`:
- `python-ci.yml` — Python lint/tests on push/PR.
- `frontend-ci.yml` — dashboard verification scripts
  (`scripts/verify_dashboard_pages.py`, `verify_attendance_page.py`,
  `verify_health_page.py`).
- `docker-build.yml` — multi-arch image build; **Trivy + Grype** container
  vulnerability scans with SARIF uploads to the GitHub Security tab;
  critical-module import verification.
- `security-scan.yml` — additional security scanning.

## 18.6 Coverage Guidance

- Aim: app/, services/, database/ covered by the unit+service suites.
- Benchmark scripts validate performance characteristics that unit tests
  can't (latency, throughput, recall at scale).
- Reports: `FINAL_VALIDATION_REPORT.md`, `FINAL_ACCEPTANCE_REPORT.md`,
  `PRODUCT_VALIDATION_REPORT.md` document historical suite results.

---

*References: `pytest.ini`, `tests/*`, `.github/workflows/*`,
`scripts/verify_*.py`, `scripts/benchmarks/*`, validation reports*

---

<!-- Section: 19_BENCHMARKS.md -->
# Section 19 — Benchmarks

## 19.1 Benchmark Suite (`scripts/benchmarks/`)

| Script | What it measures | Typical usage |
|--------|------------------|---------------|
| `faiss_benchmark.py` | FAISS index build time, search latency, recall at N vectors | `python scripts/benchmarks/faiss_benchmark.py` |
| `tune_hnsw.py` | HNSW M / efConstruction / efSearch sweeps | generates tuned params (now M=32, efC=200, efS=128 in settings.yaml) |
| `tune_ivf.py` | IVF nlist / nprobe sweeps | generates tuned params (nlist=200, nprobe=256) |
| `benchmark_real_embeddings.py` | Recognition with real ArcFace embeddings | accuracy/confidence realism check |
| `camera_validation.py` | Camera FPS, E2E latency (p50/p95), drop rate | per-camera hardware validation |
| `fake_camera_validation.py` | Pipeline FPS/latency without hardware | CI-friendly validation |
| `scalability_benchmark.py` | Enrollment scale (100 → 100K vectors) | capacity planning |
| `profile_pipeline.py` | Per-stage timing (YOLO/RetinaFace/ArcFace/FAISS/AMFR) | identifies bottlenecks |
| `probe_environment.py` | Dependency versions, GPU availability, env sanity | pre-deployment |
| `validate_amfr.py` | AMFR decision correctness (accept/borderline/reject) | threshold sanity |

## 19.2 Key Benchmarked Quantities

### FAISS
- **Index type comparison:** flat vs hnsw vs ivf — build time, query time,
  memory, recall@1.
- **Search latency:** sub-ms at thousands of vectors (HNSW); tuning scripts
  produced the shipped defaults.
- **Recall trade-off:** efSearch higher → better recall, slower query.

### AMFR
- `validate_amfr.py` verifies the decision matrix:
  - high liveness + high arcface → ACCEPT
  - marginal scores → BORDERLINE
  - low everything → LOW_CONFIDENCE
  - liveness below spoof threshold → REJECT_SPOOF

### Latency
- **E2E frame latency:** Camera → FrameBuffer → display (measured by
  `camera_validation.py` and the Live page's `LatencyLogger`):
  p50/p95/avg ms.
- **AI pipeline latency:** per-stage ms (profile_pipeline.py) and total
  frame processing time.
- **FPS:** capture FPS, AI FPS, display FPS (EMA-smoothed).

### Accuracy
- **Recognition confidence** = `1/(1+d²)` mapping from FAISS L2 distance.
- **Threshold guidance** (settings.yaml comments):
  - 0.0–0.5 → exact duplicate
  - 0.5–1.0 → same person, similar conditions
  - 1.0–1.5 → same person, different lighting/angle (default threshold 1.0)
  - 1.5–2.0 → possibly different person
  - >2.0 → almost certainly different person

### Precision / Recall (operational)
- No formal PR curves are shipped; `benchmark_real_embeddings.py` and the
  acceptance reports provide empirical accuracy observations. On-site
  precision/recall measurement is an explicit **pilot phase task**
  (see `docs/PILOT_DEPLOYMENT_PLAN.md`).

## 19.3 Where Results Live

| Artifact | Content |
|----------|---------|
| `docs/PERFORMANCE_REPORT.md` | Measured GPU-accelerated performance |
| `docs/GAP_ANALYSIS_COLLEGE_SCALE.md` | College-scale capacity analysis |
| `FINAL_ACCEPTANCE_REPORT.md` | Test + validation summary (490 green) |
| `POSTGRESQL_VALIDATION_REPORT.md` | PostgreSQL + Redis validation |
| `LIVE_SYSTEM_VALIDATION_REPORT.md` | Live pipeline verification |
| `CAMERA_STABILIZATION_REPORT.md` | Camera stability validation |

## 19.4 Running a Quick Benchmark

```bash
python scripts/benchmarks/faiss_benchmark.py
python scripts/benchmarks/fake_camera_validation.py
python scripts/benchmarks/profile_pipeline.py
python scripts/benchmarks/validate_amfr.py
python tools/validate_startup.py     # environment sanity
```

---

*References: `scripts/benchmarks/*`, `docs/PERFORMANCE_REPORT.md`,
`docs/GAP_ANALYSIS_COLLEGE_SCALE.md`, validation reports*

---

<!-- Section: 20_COMPLETE_WORKFLOW.md -->
# Section 20 — Complete Workflow

## 20.1 End-to-End Narrative (simple language)

1. An operator opens the **Live Recognition** page and clicks **START**.
2. The page creates a camera source and starts a background capture thread.
3. A person walks in front of the camera.
4. YOLO finds the person; the tracker assigns them an ID.
5. RetinaFace finds their face; quality and liveness checks run.
6. ArcFace creates their face fingerprint; FAISS finds the closest match.
7. AMFR combines everything and decides: **ACCEPT**.
8. Attendance is marked in the database and CSV; the screen shows a green
   box with the name and "PRESENT".
9. The dashboard and attendance page show the record; analytics update.

## 20.2 Sequence Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant Op as Operator (Streamlit)
    participant Live as LiveRecognitionPipeline
    participant Cam as CameraSource
    participant Buf as FrameBuffer/ResultsBuffer
    participant Pipe as RecognitionService
    participant AI as AI Models (YOLO/Retina/ArcFace/FAISS/AMFR)
    participant DB as Database + Services
    participant UI as Dashboard UI

    Op->>Live: START (camera_type, config)
    Live->>Cam: create_camera() + open()
    Cam-->>Live: ok
    Live->>Live: spawn capture thread, worker, sampler
    loop every frame
        Cam->>Buf: read() → frame_buffer.put(frame)
    end
    loop every 0.1s (adaptive)
        Buf->>Pipe: frame_buffer.get()
        Pipe->>AI: process_frame_detailed(frame 320x240)
        AI->>AI: YOLO → RetinaFace → Quality → Liveness → ArcFace
        AI->>AI: FAISS search → AMFR decision
        AI-->>Pipe: results (name, decision, risk, bbox...)
        Pipe->>DB: ACCEPT → AttendanceService.mark() + RecognitionLogRepo
        Pipe->>Buf: results_buffer.put(results)
    end
    Buf->>UI: frame_buffer.get() + results_buffer.get()
    UI->>UI: draw overlays (✓ NAME · PRESENT)
    Op->>Live: STOP
    Live->>Cam: release() via CameraOwner
    Live->>Live: join threads, clear buffers
```

## 20.3 Step-by-Step Detail

### Step 1 — Open camera
`LiveRecognitionPipeline.start()`:
- `create_camera(source_type, **kwargs)` (factory) → `open()` →
  `set_resolution(640,480)` → FPS cap 15.
- Failures produce `ERROR` status with a readable message.

### Step 2 — Capture
`_capture_loop` reads frames; `frame_buffer.put(frame)` keeps the latest.
Status → LIVE. On read failure → DISCONNECTED → reconnect (≤5 tries).

### Step 3 — Detect people (YOLO)
`FaceDetector.detect()` on the 320×240 downscale; filter person class;
early-exit if empty.

### Step 4 — Track
`AMFREngine.process_frame()` first calls `tracker.update(bbox-only)` to
assign `track_id`; per-track liveness detectors are (re)created/cleaned.

### Step 5 — Face & embedding per person
For each detection: `crop_person()` → `recognizer.detect_face()` (face +
landmarks + embedding) → `enrollment.search(embedding, k=1, threshold)`.

### Step 6 — Quality + Liveness
`_evaluate_person()` runs `FaceQualityAssessment.assess()` and
`LivenessDetector.analyze_frame()` (per track), then `_decide()` computes the
weighted risk and decision.

### Step 7 — Act on decision
- **ACCEPT** → `_maybe_mark_attendance()` (cooldown + DB dedupe) →
  `AttendanceService.mark()` (DB+CSV+audit) → `RecognitionLogRepo.create()`
  → results carry `attendance_marked`.
- **BORDERLINE** → log recognition, keep collecting.
- **REJECT_SPOOF** → log spoof + `AuditService.log("SPOOF_ATTEMPT")`.
- **LOW_CONFIDENCE** → save unknown face (3 s cooldown) + `UnknownFaceRepo`.

### Step 8 — Second tracker update
Enriched results are fed back into the tracker for identity stability,
then augmented with `track_id`, `track_frames`, `identity_stability`.

### Step 9 — Publish & display
Worker scales bboxes back to display size and publishes to
`results_buffer`. UI draws overlays + HUD (FPS, enrolled, tracks).

### Step 10 — Persistence & reports
Attendance rows appear in the Dashboard/Attendance/Analytics pages via
cached queries. API clients can query `/attendance`, `/analytics/*`,
and subscribe to `/events/stream`.

## 20.4 Attendance-Dedup Detail

```
ACCEPT for "Alice"
  → already in _marked_this_session?  → skip
  → cooldown (now - last) < 60s?      → skip
  → AttendanceRepo.is_marked_today()? → add to session cache, skip
  → else → mark (DB + CSV + audit) → session cache += Alice
```

## 20.5 Failure Modes & Recovery

| Failure | Behavior | Recovery |
|---------|----------|----------|
| Camera read error | status DISCONNECTED | auto-reconnect ≤5 tries |
| Inference exception | worker error counted; feed keeps showing last frame | continues next cycle |
| DB write error | logged warning; CSV may still record | transient |
| FAISS model load fail | fallback CNN for liveness | reload via Health page |
| Redis down | all Redis calls degrade (logged) | optional |

---

*References: `dashboard/pages/04_Live.py`, `services/recognition_service.py`,
`app/amfr_engine.py`, `app/live_detection.py`, `services/attendance_service.py`*

---

<!-- Section: 21_DATA_FLOW.md -->
# Section 21 — Complete Data Flow

## 21.1 Data Flow Diagram (Mermaid)

```mermaid
flowchart TD
    subgraph Input
        A[Camera Frame 640x480] --> B[Capture Thread]
        B -->|frame_buffer.put| FB[(FrameBuffer maxlen=1)]
    end

    subgraph AI
        FB -->|get| C[Recognition Worker]
        C -->|downscale 320x240| D[YOLO11 Person Detect]
        D -->|person bboxes| E[AMFR Engine process_frame]
        E -->|track_id| T[Tracker]
        T -->|per-track state| F[RetinaFace + ArcFace]
        F -->|512-D emb| G[FAISS search]
        G -->|name distance| H[Quality + Liveness]
        H -->|scores| I[AMFR Decide]
        I -->|decision| RB[(ResultsBuffer)]
    end

    subgraph Persistence
        I -->|ACCEPT| S[AttendanceService.mark]
        S --> DB[(SQLite/PostgreSQL)]
        S --> CSV[(attendance/date.csv)]
        S --> AL[(audit_logs)]
        I -->|LOW_CONFIDENCE| U[UnknownFaceService]
        U --> UF[(unknown_faces table)]
        U --> DIR[(unknown_faces/ images)]
        I -->|REJECT_SPOOF| AUD[Audit SPOOF_ATTEMPT]
    end

    subgraph Presentation
        RB -->|results| UI[Live Page overlays]
        FB -->|raw frame| UI
        DB -->|queries| DASH[Dashboard/Attendance/Analytics]
        DB -->|REST| API[FastAPI]
        API -->|WS events| WS[WebSocket clients]
    end

    subgraph Infra
        RED[(Redis: cooldown, camera status, OIDC state)]
        FA[(FAISS index + metadata.json)]
    end

    G <--> FA
    API -.-> RED
    DASH -.-> RED
```

## 21.2 Data Items & Their Lifecycle

| Data item | Created by | Stored in | Consumed by | Retained |
|-----------|-----------|-----------|-------------|----------|
| Camera frame | camera read | in-memory buffers only | pipeline, display | never (latest-only) |
| YOLO detections | face_detector | in-memory per frame | AMFR | per-frame |
| Track state | tracker | in-memory (`_tracks`) | AMFR smoothing | until track lost (>30 frames) |
| Face embedding | recognizer | FAISS index (enrolled), in-memory (query) | enrollment.search | enrolled: forever (file) |
| Recognition result | AMFR | recognition_log table | dashboard activity, analytics | forever |
| Attendance record | AttendanceService | attendance table + CSV | dashboard, analytics, API | forever |
| Unknown face | pipeline | unknown_faces table + image file | gallery, review | retention_days (30) |
| Audit entry | AuditService / log_audit | audit_logs table | security review | forever |
| User/token | auth endpoints | users + refresh_tokens | get_current_user | until revoke/expiry |
| OIDC state | oidc login | Redis (5 min TTL) | callback CSRF | 5 minutes |

## 21.3 Flow Paths by Feature

### Recognition → Attendance (primary)
```
frame → YOLO bbox → track_id → face + emb → FAISS → quality/liveness
     → AMFR decision → AttendanceService.mark → attendance row + CSV
     → audit + recognition_log → dashboard refresh
```

### Unknown person
```
LOW_CONFIDENCE → person crop saved (3s cooldown) → unknown_faces row
     → gallery → admin review → convert_to_employee
        → ArcFace emb → FAISS add → Employee row → converted=true
     or ignore (reviewed=true) / delete (row + file)
```

### Enrollment
```
photo → FaceRecognizer.extract_embedding → FaceEnrollment.enroll (FAISS)
     → EmployeeService.create (DB, faiss_id) → audit ENROLL
     (on DB failure → FAISS rollback remove_by_name)
```

### API client
```
login → JWT (+MFA if required) → authorized request → service/repo
     → audit + response → refresh rotation on expiry
```

### Backup
```
pg_dump (SQL) + faiss.index + metadata.json → backups/backup_ts/
     manifest.json (hashes) → restore verifies hashes → drop/create/psql
     → FAISS artifacts copied back → restart app
```

## 21.4 Streaming vs Batch Data

| Path | Type | Notes |
|------|------|-------|
| Camera → buffers → UI | streaming (frames) | latest-only, non-blocking |
| Recognition events → WebSocket | streaming (events) | buffered (100), role-filtered |
| Recognition → DB writes | event-driven writes | per ACCEPT/UNKNOWN/SPOOF |
| Attendance queries | on-demand reads | cached (TTL) in dashboard |
| Analytics charts | aggregated reads | SQL group-by |
| Bulk imports/exports | batch | CSV via BulkOperations |

## 21.5 Data Integrity Notes

- Attendance dedupe prevents duplicates (session + cooldown + DB check).
- Employee rename/delete synchronizes FAISS labels (rename) / embeddings (delete).
- Unknown-face conversion rolls back the Employee row if FAISS add fails.
- Backups include SHA-256 manifests verified on restore.
- Redis state is ephemeral by design (TTLs) — no integrity risk on loss.

---

*References: `app/*`, `services/*`, `api/*`, `database/*`, `scripts/backup.py`*

---

<!-- Section: 22_CLASS_DIAGRAM.md -->
# Section 22 — Complete Class Diagram (UML)

UML class diagrams for the major subsystems, derived from source.

## 22.1 AI Pipeline Classes

```mermaid
classDiagram
    class FaceDetector {
        +model: YOLO
        +person_class_id: int
        +detect(frame, conf_threshold) List[dict]
        +crop_person(frame, bbox, padding) np.ndarray
        +get_largest_detection(detections) dict
    }

    class FaceRecognizer {
        +app: FaceAnalysis
        +model_name: str
        +extract_embedding(face_img) np.ndarray
        +detect_face(person_crop) dict
        +get_landmarks(face_img) np.ndarray
        +compute_similarity(emb1, emb2) float
        +embedding_dim() int
    }

    class FaceEnrollment {
        +index: faiss.Index
        +metadata: List[dict]
        +dimension: int
        +enroll(name, embedding) bool
        +search(embedding, k, threshold) List[dict]
        +remove_by_name(name) bool
        +rename(old_name, new_name) bool
        +clear() None
        +all_persons() List[str]
        +count() int
        +unique_count() int
        +status() dict
        -_create_index() faiss.Index
        -_save() None
    }

    class FaceQualityAssessment {
        +weights: dict
        +assess(face_img, det_score, face_bbox, img_shape, landmarks) dict
    }

    class LivenessResult {
        +is_live: bool
        +liveness_score: float
        +texture_score: float
        +blink_score: float
        +motion_score: float
        +screen_score: float
        +dl_score: float
        +dl_time_ms: float
        +blink_detected: bool
        +reasons: List[str]
    }

    class LivenessDetector {
        -_deep_liveness: DeepLivenessDetector
        -_ear_history: Deque
        -_blink_count: int
        -_prev_gray: np.ndarray
        +analyze_frame(face_img, landmarks) LivenessResult
        +reset() None
        +register_blink() None
        +deep_liveness_available: bool
    }

    class DeepLivenessDetector {
        -_session: InferenceSession
        -_model_available: bool
        -_fallback_active: bool
        +predict(face_img, landmarks) DeepLivenessResult
        +available: bool
        +using_fallback: bool
        +reload() bool
        -_predict_onnx() DeepLivenessResult
        -_predict_fallback() DeepLivenessResult
    }

    class TrackState {
        +track_id: str
        +first_seen: float
        +last_seen: float
        +total_frames: int
        +consistent_frames: int
        +identity: str
        +identity_confidence: float
        +arcface_distances: List
        +liveness_scores: List
        +quality_scores: List
        +attendance_marked: bool
        +spoof_frame_count: int
        +avg_arcface_distance: float
        +identity_stability: float
    }

    class MultiFrameTracker {
        -_tracks: Dict[str, TrackState]
        -_disappeared: Dict[str, int]
        +update(detections, frame_shape) List[TrackState]
        +reset() None
        +get_track(track_id) TrackState
        +_iou(box_a, box_b) float
    }

    class AMFRDecision {
        <<enum>>
        ACCEPT
        BORDERLINE
        LOW_CONFIDENCE
        REJECT_SPOOF
        PENDING
    }

    class AMFREngine {
        +quality: FaceQualityAssessment
        +tracker: MultiFrameTracker
        -_liveness_instances: Dict[str, LivenessDetector]
        +process_frame(frame, detections, embeddings, faiss_results, face_data) List[dict]
        +reset() None
        +get_all_tracks() List[TrackState]
        +status() dict
        -_evaluate_person(frame, det, embedding, faiss, face, track_id) dict
        -_decide(arcface_distance, liveness_score, quality_score, is_live, faiss_confidence) tuple
    }

    class AttendanceTracker {
        +log_dir: Path
        +mark(name, confidence) bool
        +today() List[dict]
        +by_date(date) List[dict]
        +all_records() dict
        +statistics() dict
    }

    AMFREngine --> FaceQualityAssessment
    AMFREngine --> MultiFrameTracker
    AMFREngine --> LivenessDetector : per-track instances
    AMFREngine --> AMFRDecision
    LivenessDetector --> LivenessResult
    LivenessDetector --> DeepLivenessDetector
    MultiFrameTracker --> TrackState
    FaceDetector ..> FaceRecognizer : crop feeds
    FaceRecognizer ..> FaceEnrollment : embedding queries
```

## 22.2 Camera Classes

```mermaid
classDiagram
    class CameraSource {
        <<abstract>>
        +name: str
        +source_type: str
        +open() bool*
        +release() None*
        +read() (bool, np.ndarray)*
        +is_opened() bool*
        +set_resolution(w, h) None*
        +get_resolution() (int, int)*
        +info() dict*
    }

    class WebcamSource
    class USBAnySource
    class AndroidWiFiSource
    class AndroidUSBSource
    class iPhoneWiFiSource
    class iPhoneUSBSource
    class IPCameraSource
    class FakeCameraSource

    CameraSource <|-- WebcamSource
    CameraSource <|-- USBAnySource
    CameraSource <|-- AndroidWiFiSource
    CameraSource <|-- AndroidUSBSource
    CameraSource <|-- iPhoneWiFiSource
    CameraSource <|-- iPhoneUSBSource
    CameraSource <|-- IPCameraSource
    CameraSource <|-- FakeCameraSource
```

## 22.3 Service & Dashboard Classes

```mermaid
classDiagram
    class RecognitionService {
        +detector: FaceDetector
        +recognizer: FaceRecognizer
        +enrollment: FaceEnrollment
        +amfr: AMFREngine
        -_marked_this_session: set
        +process_frame(frame) np.ndarray
        +process_frame_detailed(frame) tuple
        +with_shared_models(models) RecognitionService
        +reset_tracking() None
        +status() dict
        -_maybe_mark_attendance(name, employee_id, confidence) bool
        -_log_recognition(...) None
        -_handle_unknown_face(face_img) None
    }

    class AttendanceService {
        +mark(employee_id, confidence, camera_id, operator, employee_name) bool
        +get_today() List
        +get_by_date(date) List
        +get_by_employee(id) List
        +get_statistics() dict
        +to_dict(record) dict
    }

    class EmployeeService {
        +create(...) Employee
        +get_by_name(name) Employee
        +update(employee_id, name, department) Employee
        +delete(employee_id) bool
        +remove_faiss_embedding(name, fallback) bool
        +count() int
    }

    class UnknownFaceService {
        +get_statistics() dict
        +get_filtered(...) List
        +convert_to_employee(face_id, employee_id, name, department) bool
        +delete_all() int
        +auto_cleanup(days) int
    }

    class AuditService {
        +log(action, description, operator, employee_id) None
        +get_recent(limit) list
        +get_by_action(action) list
    }

    class BruteForceProtection {
        +is_locked_out(username, ip) tuple
        +record_failed_attempt(...) None
        +record_successful_login(...) None
        +get_lockout_info(username) dict
        +cleanup_old_attempts() int
    }

    class MFAService {
        +generate_secret(email) tuple
        +verify_totp(secret, code) bool
        +generate_backup_codes() tuple
        +verify_backup_code(hashes, code) tuple
        +enroll_user(user) tuple
        +requires_mfa(user) bool
    }

    class OIDCService {
        +enabled: bool
        +get_login_url(request, state) str
        +handle_callback(code, state, expected) OIDCUserInfo
        +sync_user(user_info) User
    }

    class LiveRecognitionPipeline {
        +source_type: str
        -_cam: CameraSource
        -_service: RecognitionService
        -_threads: list
        -_verified_at: dict
        +start() bool
        +stop() None
        +fps: float
        +ai_fps: float
        +pipeline_latency: float
        +people_count: int
        +status: str
        +latency_stats() dict
        -_capture_loop() None
        -_recognition_worker() None
        -_latency_loop() None
    }

    class SharedModelResources {
        +service: RecognitionService
        +load() SharedModelResources
    }

    class CameraOwner {
        -_instance: CameraOwner
        +get() CameraOwner
        +can_acquire() bool
        +acquire(camera, pipeline) bool
        +release() None
        +is_owned() bool
        +get_status() dict
    }

    class FrameBuffer {
        +put(frame) int
        +get() np.ndarray
        +get_with_meta() tuple
        +close() None
        +has_frame() bool
    }

    class LatencyLogger {
        +record(ms) None
        +stats() dict
        +p50() float
        +p95() float
    }

    LiveRecognitionPipeline --> RecognitionService
    LiveRecognitionPipeline --> CameraSource
    LiveRecognitionPipeline --> LatencyLogger
    LiveRecognitionPipeline --> SharedModelResources
    LiveRecognitionPipeline --> FrameBuffer
    CameraOwner --> LiveRecognitionPipeline : owns
```

## 22.4 ORM Models (summary — full schema in §8)

```mermaid
classDiagram
    class User {
        +id, username, email, password_hash
        +oidc_sub, oidc_provider, auth_method
        +is_mfa_enabled, mfa_totp_secret, mfa_backup_codes
        +is_active, last_login_at, created_at, updated_at
    }
    class Role { +id, name, description }
    class Permission { +id, resource, action }
    class RefreshToken { +id, user_id, token_hash, expires_at, revoked_at }
    class Student { +id, student_id, name, department_id, is_active }
    class Staff { +id, employee_id, name, department_id }
    class Employee { +id, employee_id, name, department, faiss_id }
    class Department { +id, institution_id, name, code, head_id }
    class Course { +id, department_id, code, name, credits }
    class Section { +id, course_id, section_name, semester, year }
    class Enrollment { +id, student_id, section_id, status }
    class Timetable { +id, section_id, classroom_id, day_of_week, start_time, end_time }
    class Classroom { +id, institution_id, building, room_number }
    class Camera { +id, camera_id, stream_url, status, is_active }
    class Attendance { +id, student_id, employee_id, timestamp, confidence, status }
    class RecognitionLog { +id, is_known, confidence, is_spoof, timestamp }
    class UnknownFace { +id, image_path, reviewed, converted_to_employee }
    class AuditLog { +id, action, actor, timestamp, severity }

    User "1" --> "0..*" RefreshToken
    User "1" --> "0..*" Attendance : marked_by
    User "1" --> "0..*" UnknownFace : reviewed
    User "1" --> "0..*" Role : user_roles
    Role "1" --> "0..*" Permission : role_permissions
    Department "1" --> "0..*" Course
    Course "1" --> "0..*" Section
    Section "1" --> "0..*" Timetable
    Classroom "1" --> "0..*" Timetable
    Student "1" --> "0..*" Enrollment
    Section "1" --> "0..*" Enrollment
    Student "1" --> "0..*" Attendance
    Camera "1" --> "0..*" Attendance
    Employee "1" --> "0..*" Attendance
    Employee "1" --> "0..*" RecognitionLog
    Camera "1" --> "0..*" UnknownFace
```

---

*References: class definitions in `app/*`, `camera/*`, `services/*`,
`dashboard/*`, `database/models.py`*

---

<!-- Section: 23_MODULE_DIAGRAM.md -->
# Section 23 — Complete Module Diagram

## 23.1 Module Dependency Diagram (Mermaid)

```mermaid
flowchart TB
    subgraph UI["PRESENTATION"]
        DASH["dashboard/app.py"]
        P1["01_Dashboard"]
        P2["02_Employees"]
        P3["03_Enroll"]
        P4["04_Live"]
        P5["05_Attendance"]
        P6["06_Unknown"]
        P7["07_Analytics"]
        P8["08_Settings"]
        P9["09_Health"]
        P10["10_About"]
        FB["dashboard/frame_buffer.py"]
        CO["dashboard/camera_owner.py"]
        LL["dashboard/latency_logger.py"]
    end

    subgraph API["API LAYER"]
        FAST["api/main.py"]
        JQ["api/job_queue.py"]
        WS["api/websocket_manager.py"]
        RC["api/redis_client.py"]
        BO["api/bulk_operations.py"]
        ATTAPI["api/attendance_service.py"]
        AUDA["api/audit_service.py"]
    end

    subgraph SVC["SERVICE LAYER"]
        RS["services/recognition_service.py"]
        AS["services/attendance_service.py"]
        ES["services/employee_service.py"]
        UFS["services/unknown_face_service.py"]
        AUD["services/audit_service.py"]
        BFP["services/brute_force_protection.py"]
        MFA["services/mfa_service.py"]
        OIDC["services/oidc_service.py"]
    end

    subgraph AI["AI PIPELINE"]
        AMFR["app/amfr_engine.py"]
        FD["app/face_detector.py"]
        REC["app/recognizer.py"]
        ENR["app/enrollment.py"]
        FQ["app/face_quality.py"]
        LD["app/liveness_detector.py"]
        DL["app/deep_liveness.py"]
        TRK["app/tracking.py"]
        AT["app/attendance.py"]
        LDET["app/live_detection.py"]
        ALG["recognition/alignment.py"]
    end

    subgraph CAM["CAMERA LAYER"]
        CB["camera/base.py"]
        CW["camera/webcam.py"]
        CP["camera/phone.py"]
        CS["camera/selector.py"]
        CD["camera/discovery.py"]
        CF["camera/fake.py"]
    end

    subgraph DB["DATA LAYER"]
        DBX["database/database.py"]
        MOD["database/models.py"]
        REP["database/repository.py"]
        ALE["alembic/*"]
        FA["FAISS index + metadata.json"]
        CSV["attendance/ CSV files"]
    end

    subgraph CFG["CONFIG"]
        CC["config/config.py"]
        YML["config/settings.yaml"]
        UT["utils/upload_security.py"]
        UI2["utils/image.py"]
    end

    %% UI → services
    P1 --> AS
    P1 --> ES
    P1 --> UFS
    P1 --> REP
    P2 --> ES
    P2 --> AS
    P3 --> ENR
    P3 --> REC
    P3 --> ES
    P4 --> RS
    P4 --> AS
    P4 --> CO
    P4 --> FB
    P4 --> LL
    P4 --> CS
    P4 --> CD
    P5 --> LDET
    P5 --> AS
    P5 --> CS
    P6 --> UFS
    P7 --> REP
    P8 --> CC
    P8 --> CS
    P9 --> CC
    P9 --> CS
    DASH --> P1

    %% Dashboard infra
    CO --> FB
    P4 --> CO

    %% Services → AI / DB
    RS --> AMFR
    RS --> FD
    RS --> REC
    RS --> ENR
    RS --> AS
    RS --> AUD
    RS --> REP
    AS --> AT
    AS --> REP
    AS --> AUD
    ES --> REP
    ES --> AUD
    ES -.-> ENR   %% FAISS rename/delete sync
    UFS --> REP
    UFS --> AUD
    UFS -.-> REC  %% convert: embedding
    UFS -.-> ENR  %% convert: FAISS add
    AUD --> REP
    BFP --> REP
    MFA --> DBX
    OIDC --> DBX

    %% AI internal
    AMFR --> FQ
    AMFR --> LD
    AMFR --> TRK
    LD --> DL
    LDET --> AMFR
    LDET --> FD
    LDET --> REC
    LDET --> ENR
    LDET --> AT
    LDET --> CS
    LDET --> REP
    REC --> ALG

    %% Camera factory
    CS --> CW
    CS --> CP
    CS --> CF
    CW --> CB
    CP --> CB
    CD --> CB

    %% API → services/db
    FAST --> RS
    FAST --> ES
    FAST --> AS
    FAST --> BFP
    FAST --> MFA
    FAST --> OIDC
    FAST --> JQ
    FAST --> WS
    FAST --> RC
    FAST --> BO
    FAST --> REP
    FAST --> UT
    JQ --> DBX
    BO --> DBX

    %% Config
    FD --> CC
    REC --> CC
    ENR --> CC
    FQ --> CC
    LD --> CC
    DL --> CC
    AMFR --> CC
    AT --> CC
    CC --> YML
    UI2 --> UT

    %% Data layer
    REP --> MOD
    REP --> DBX
    MOD --> DBX
    DBX --> ALE
    ENR --> FA
    AS --> CSV
    RC --> REDIS["Redis"]
    DBX --> SQL[(SQLite/PostgreSQL)]
```

## 23.2 Dependency Rules (architecture constraints)

| Rule | Enforced by |
|------|-------------|
| UI/API never touch AI modules directly | `services/recognition_service.py` is the only sanctioned entry |
| Only `camera/webcam.py` + `camera/phone.py` own `cv2.VideoCapture` | documented convention + `CameraOwner` singleton |
| Repositories are the only SQL layer | services call repos; pages use services/repos via cached helpers |
| Config is centralized | every module imports `config.config` constants |
| FAISS ↔ DB consistency | `EmployeeService` rename/delete sync |
| One active camera pipeline | `CameraOwner.acquire()` |

## 23.3 Layer Dependency Matrix (who depends on whom)

| Layer | Depends on |
|-------|-----------|
| Presentation (dashboard/) | services/, database/repository, camera/, config/, app/ (via services) |
| API (api/) | services/, database/, utils/, api/* helpers |
| Services (services/) | database/, app/ (sparingly), config/ |
| AI pipeline (app/) | config/, camera/ (only live_detection), database/ (only live_detection + recognition_service) |
| Camera (camera/) | config/ (via consumers), base |
| Data (database/) | config/, alembic |
| Config (config/) | nothing internal |

## 23.4 Circular Dependency Note

`app/live_detection.py` imports from `database/` and `services/`, while
`services/recognition_service.py` imports from `app/`. This creates a
soft cycle at import time; it works because imports are deferred inside
functions/methods where needed (e.g. `_log_attendance_db` imports
`get_session` inside the method) and Python's module cache handles the
order. Documented here for maintainers: prefer services→app one-way imports
going forward (the dashboard path already does this correctly via
`RecognitionService`).

---

*References: import statements across `app/*`, `services/*`, `api/*`,
`dashboard/*`, `camera/*`, `database/*`*

---

<!-- Section: 24_TECH_STACK.md -->
# Section 24 — Complete Tech Stack

## 24.1 Stack Summary Table

| Layer | Technology | Version |
|-------|-----------|---------|
| **Language** | Python | 3.10+ (3.11 in Docker) |
| **Person detection** | Ultralytics YOLO11 (nano) | ≥8.0.0 |
| **Face detection** | RetinaFace (InsightFace buffalo_l) | ≥0.7.3 |
| **Face embedding** | ArcFace (InsightFace buffalo_l, 512-D) | ≥0.7.3 |
| **Deep liveness** | MiniFASNetV2 ONNX + numpy fallback | onnxruntime ≥1.15 |
| **Vector search** | FAISS (flat/HNSW/IVF) | ≥1.7.0 |
| **Tracker** | Custom greedy IoU tracker | in-repo (`app/tracking.py`) |
| **ML runtime** | PyTorch (≠2.4.0), ONNX Runtime | ≥2.0 |
| **Dashboard** | Streamlit | ≥1.28 (badge: 1.59) |
| **Charts** | Plotly | ≥5.18 |
| **REST API** | FastAPI + Uvicorn | ≥0.100 / ≥0.21.5 |
| **Database (dev)** | SQLite | stdlib |
| **Database (prod)** | PostgreSQL | 16 (docker: 16-alpine) |
| **Cache/state** | Redis | 7 (docker: 7-alpine) |
| **ORM** | SQLAlchemy | 2.0 |
| **Migrations** | Alembic | bundled |
| **Auth** | JWT (python-jose) + bcrypt (passlib) + pyotp (MFA) + OIDC | — |
| **Rate limiting** | slowapi | ≥0.1.9 |
| **Metrics** | Prometheus client | ≥0.19 |
| **Realtime** | WebSockets (FastAPI) | — |
| **Container** | Docker multi-stage + docker-compose | — |
| **CI/CD** | GitHub Actions (lint, tests, Trivy, Grype, build) | — |
| **Image I/O** | OpenCV, Pillow, numpy | — |
| **Data tables** | pandas | ≥2.0 |
| **System metrics** | psutil | ≥5.9 |
| **HTTP** | httpx (OIDC), requests (camera discovery) | — |

## 24.2 Frontend

- **Streamlit** — 10-page dashboard (server-rendered, Python).
- **WebRTC** (optional `streamlit-webrtc`) — browser webcam on the Attendance page.
- **Plotly** — interactive analytics charts.
- **Custom HTML/CSS** — sidebar branding, status badges, unknown-face cards.

## 24.3 Backend

- **FastAPI** — REST + WebSocket + async job queue + lifespan init.
- **Service layer** — business logic façade.
- **Repository layer** — data access.
- **Background threads** — camera capture / AI worker / latency sampling
  (Streamlit process) and asyncio workers (API process).

## 24.4 AI Models

| Model | Role | Size | Source |
|-------|------|------|--------|
| YOLO11n | person detection | ~6 MB | Ultralytics (auto-download) |
| RetinaFace (buffalo_l) | face detection + landmarks | part of ~200 MB pack | InsightFace |
| ArcFace (buffalo_l) | 512-D embeddings | part of pack | InsightFace |
| MiniFASNetV2 | liveness CNN | ~4 MB | yakhyo/face-anti-spoofing releases |
| FAISS index | vector search | grows with enrollments | local files |

## 24.5 Databases

| Store | Use | Location |
|-------|-----|----------|
| SQLite | dev relational data | `data/face_recognition.db` |
| PostgreSQL | prod relational data | via `DATABASE_URL` / docker |
| Redis | ephemeral state/cache | `REDIS_URL` / docker |
| FAISS + metadata.json | embeddings | `embeddings/` |
| CSV files | attendance logs (compat) | `attendance/` |
| File system | unknown faces, uploads, logs, outputs | various dirs |

## 24.6 Security Stack

JWT access tokens + rotating refresh tokens, RBAC (7 roles, permission
matrix), TOTP MFA + hashed backup codes, OIDC SSO, bcrypt password hashing,
slowapi rate limiting, security headers, upload magic-byte validation,
brute-force lockout, audit trail, production secret-key guard.

## 24.7 Deployment Stack

Docker multi-stage build (python:3.11-slim + system deps), docker-compose
(PostgreSQL 16 + Redis 7 + app), GitHub Actions CI (python-ci, frontend-ci,
docker-build with Trivy + Grype SARIF, security-scan), systemd/uvicorn for
bare-metal production, scripts for backup/restore/seed/migrate.

---

*References: `requirements.txt`, `README.md`, `Dockerfile`, `docker-compose.yml`,
`.github/workflows/*`*

---

<!-- Section: 25_WHY_TECHNOLOGY.md -->
# Section 25 — Why Each Technology Was Chosen

## 25.1 Why YOLO (Ultralytics YOLO11)?

- **Single-pass detection:** predicts all boxes in one forward pass —
  real-time on CPU.
- **Ecosystem:** mature Python API (`YOLO(model)(frame)`), auto-download,
  ONNX export, active maintenance.
- **Nano size:** `yolo11n.pt` ~6 MB — feasible to ship/download in a
  college environment.
- **COCO-trained:** the "person" class works out of the box for
  attendance scenes.
- **Alternatives considered:** YOLOv8/YOLOv5 (older), MediaPipe (person
  landmarks only), HOG+SVM (classic, less robust).
- **Trade-off:** detects *people* not *faces* — hence the RetinaFace stage.

## 25.2 Why ArcFace (InsightFace buffalo_l)?

- **Discriminative embeddings:** additive-angular-margin training produces
  highly separable 512-D vectors.
- **Proven accuracy:** state-of-the-art on LFW/MegaFace-class benchmarks.
- **Single pack:** `buffalo_l` bundles RetinaFace + ArcFace → one model
  load, one dependency.
- **L2 normalization:** embeddings are unit-norm, so FAISS L2 distance ≈
  cosine distance — simple, well-understood matching.
- **Alternatives:** FaceNet (older, heavier), CosFace/SphereFace (similar
  family), Dlib ResNet (slower on CPU).
- **Trade-off:** ~200 MB download; CPU-only inference in this project.

## 25.3 Why FAISS?

- **Performance:** sub-linear ANN search (HNSW) vs brute-force O(N)
  comparison — critical as enrollments grow to thousands.
- **Offline/in-process:** runs locally, no server to operate — aligns with
  the offline-first requirement.
- **Flexibility:** flat (exact) / HNSW (speed-recall) / IVF (scale) index
  types, tunable via benchmark scripts.
- **Serialization:** `faiss.write_index`/`read_index` → simple persistence
  in `embeddings/`.
- **Alternatives:** Milvus/Qdrant (server-based, heavier), hnswlib
  (smaller API), pgvector (needs PostgreSQL 11+ and SQL integration),
  Chroma (higher overhead for this use).
- **Trade-off:** no native deletion — the project rebuilds the index on
  delete/rename (O(N)).

## 25.4 Why PostgreSQL (production)?

- **Concurrency & ACID:** many cameras + API clients writing attendance
  concurrently.
- **Advanced indexing:** composite indexes for the attendance/recognition
  hot paths (validated by the scalability migration).
- **JSON columns:** MFA backup codes, audit details, face metadata.
- **Industry standard:** tooling, backups (`pg_dump`), hosting options.
- **Alternatives:** MySQL (weaker JSON/composite-index ergonomics for this
  schema), MSSQL/Oracle (proprietary, heavy for a college).

## 25.5 Why SQLite (development)?

- **Zero configuration:** single file, no server — perfect for dev,
  demos, and small pilots.
- **Fast iteration:** `init_db()` fallback to `create_all()`.
- **Portable:** easy to share/test.
- **Trade-off:** single-writer — explicitly not for campus-scale
  concurrent production writes (PostgreSQL is the prod path).

## 25.6 Why Redis?

- **Fast ephemeral state:** attendance dedupe markers, recognition
  cooldowns, camera status, track identity cache — all with TTLs.
- **OIDC CSRF state:** short-lived one-time state values.
- **Graceful degradation:** every call is optional — the system runs fully
  without Redis (tests skip; API logs warnings).
- **Alternatives:** in-process dict (not shared across processes), Memcached
  (no rich types/TTL ergonomics), database tables (slower for hot state).

## 25.7 Why Streamlit?

- **Python-native UI:** the whole team's stack is Python — no JS needed.
- **Rerun model fits camera loops:** the live page leverages
  `st.rerun()` + session state + cached models elegantly.
- **Rapid iteration:** 10 pages built quickly with widgets, charts, forms.
- **Alternatives:** Gradio (demo-oriented, weaker multi-page apps), Dash
  (more control, more boilerplate), Flask+JS (full custom frontend cost),
  Panel.
- **Trade-off:** rerun model requires careful state management (solved via
  `CameraOwner` + global buffers + `@st.cache_data/resource`).

## 25.8 Why FastAPI?

- **Async-first:** WebSockets (event stream), async OIDC/httpx, async job
  queue — all natural.
- **Pydantic validation:** request/response schemas with strong validators
  (password policy, regex fields).
- **Auto docs:** `/docs` + `/redoc` — free API documentation for integrators.
- **Dependency injection:** `Depends()` powers auth/RBAC/permission chains.
- **Alternatives:** Flask (sync, manual validation/docs), Django REST
  (heavier, batteries-included), Starlette (lower-level).
- **Trade-off:** ASGI ecosystem slightly newer than WSGI.

## 25.9 Why MiniFASNet (deep liveness)?

- **Purpose-built:** a small CNN trained specifically for face
  anti-spoofing — catches print/screen attacks the software heuristics miss.
- **Lightweight:** ~4 MB ONNX, ~5 ms CPU inference.
- **Layered defense:** combined with LBP/blink/motion/screen heuristics for
  defense-in-depth.
- **Alternatives:** rPPG (needs longer video + quality), challenge-response
  (user cooperation), larger CNNs (slower).

## 25.10 Why the Custom IoU Tracker?

- **Zero dependencies** and predictable O(N²) matching for modest person
  counts.
- **Purpose-fit:** temporal score smoothing + identity stability is what
  AMFR needs; a full MOT (ByteTrack) adds complexity without proportional
  benefit for classroom scenes.
- **Honest limitation:** weaker under occlusion — flagged as future work
  (§29.3).

## 25.11 Why Docker + docker-compose?

- **Reproducible environment** for the AI stack (OpenCV system libs,
  torch, etc.).
- **One-command stack:** PostgreSQL + Redis + app with healthchecks.
- **CI parity:** the Docker image is built and vulnerability-scanned in
  CI (Trivy + Grype).
- **Portable demo:** a college IT team can deploy without deep Python
  knowledge.

## 25.12 Why GitHub Actions?

- **Free CI/CD for public repos**; multi-workflow split (Python tests,
  frontend verification, Docker build + container scanning, security).
- **SARIF uploads** surface container CVEs in the GitHub Security tab.
- **Alternatives:** GitLab CI, CircleCI, Jenkins (all viable; GH Actions
  co-located with the repo).

---

*References: `requirements.txt`, `README.md` (Key Design Decisions), code
comments in `app/*`, `scripts/benchmarks/*`*

---

<!-- Section: 26_DESIGN_PATTERNS.md -->
# Section 26 — Design Patterns

Design patterns identified in the source code, with concrete locations.

## 26.1 Repository Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `database/repository.py` (`StudentRepo`, `EmployeeRepo`, `AttendanceRepo`, `RecognitionLogRepo`, `UnknownFaceRepo`, `CameraRepo`, `AuditLogRepo`) |
| **How** | Each repo is a class of static methods taking a `Session`; callers control transactions |
| **Why** | Isolates SQL; business logic stays clean; unit-testable; consistent CRUD API |
| **Related** | `PageResult` pagination envelope shared with API/UI |

## 26.2 Factory Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `camera/selector.py` — `create_camera(source_type, **kwargs)`; `CAMERA_REGISTRY` maps slugs → classes |
| **How** | Factory maps a config string to the right `CameraSource` subclass and normalizes kwargs (device_id, url, etc.) |
| **Why** | Pipeline code never instantiates concrete camera classes; adding a camera type = one registry entry |
| **Also** | `SharedModelResources.load()` acts as a model factory with caching; `LiveDetection.open_camera()` uses the camera factory |

## 26.3 Singleton Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `dashboard/camera_owner.py` — `CameraOwner.__new__` with `_lock` + `_instance`; `api/redis_client.py` — `get_redis()` global instance; `app/deep_liveness.py` — `get_deep_liveness_detector()` global; `api/job_queue.py` + `api/websocket_manager.py` — module-level `job_queue`/`ws_manager`; `dashboard/frame_buffer.py` — module-level `frame_buffer`/`results_buffer` |
| **Why** | One camera owner, one Redis client, one model, one queue, one buffer per process |
| **Thread-safety** | `CameraOwner` uses a class-level `threading.Lock`; Redis client lazily created |

## 26.4 Dependency Injection (via constructor + FastAPI Depends)

| Aspect | Detail |
|--------|--------|
| **Where** | `RecognitionService.__init__(detector=None, recognizer=None, enrollment=None, amfr=None)` + `with_shared_models()`; FastAPI `Depends(get_current_user)` / `Depends(get_session)` / `Depends(require_permission(...))` |
| **How** | Models injected into services (defaults create new); FastAPI resolves auth/session dependencies |
| **Why** | Testability (mock injection), model sharing across pipelines, declarative auth |

## 26.5 Service Layer Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `services/*` (`RecognitionService`, `AttendanceService`, `EmployeeService`, `UnknownFaceService`, `AuditService`, `BruteForceProtection`, `MFAService`, `OIDCService`) |
| **How** | Services wrap repositories, add business rules + audit logging + cross-store sync (FAISS↔DB), and are the only layer both UI and API call |
| **Why** | Centralizes business logic; prevents UI/API from touching repositories/AI directly |

## 26.6 MVC / MVCS (Model-View-Controller-ish)

| Layer | In this project |
|-------|-----------------|
| **Model** | `database/models.py` (ORM) + FAISS index |
| **View** | `dashboard/pages/*` (Streamlit) |
| **Controller** | `services/*` + `api/main.py` (FastAPI routes) |
| **Note** | Not strict MVC; closer to **Layered Architecture** with a thin Controller (API) + Service layer — deliberately chosen for testability |

## 26.7 Other Patterns Observed

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Facade** | `RecognitionService.process_frame_detailed()` | one call hides the whole pipeline |
| **Adapter** | `CameraSource` ABC + implementations | uniform interface over very different cameras |
| **Strategy** | FAISS `index_type` (flat/hnsw/ivf); Liveness factor weights; AMFR thresholds | config-driven algorithm selection |
| **Template Method** | `CameraSource` abstract methods + shared lifecycle (`open/read/release`) | consistent camera lifecycle |
| **Data Transfer Object** | Pydantic schemas (`EmployeeResponse`, `TokenResponse`, `BulkResult`) | typed API boundaries |
| **Context Manager** | `get_session()` (contextmanager), `WebcamSource.__enter__/__exit__` | resource lifecycle |
| **Module-level singletons** | buffers, ws_manager, job_queue, redis | cross-component shared state |
| **Cache-aside** | `@st.cache_data/ttl`, `SharedModelResources._cache`, `_verified_at` | performance |
| **Guard (fail-fast)** | `_validate_production_secret_key()` | fail loudly in production |
| **Circuit-breaker-ish** | Redis degradation, camera reconnect loop, DB write try/except | resilience |

## 26.8 Pattern Trade-offs

| Pattern | Benefit realized | Risk |
|---------|------------------|------|
| Repository | clean data access | can add boilerplate for simple queries |
| Factory | camera extensibility | registry must stay in sync with kwargs mapping |
| Singleton | shared models/state | global state complicates tests (mitigated by `CameraOwner.reset()`) |
| Service Layer | testable business rules | two service packages (`services/` vs `api/`) have slight overlap (documented) |

---

*References: `camera/selector.py`, `dashboard/camera_owner.py`,
`services/*`, `database/repository.py`, `api/main.py`, `app/deep_liveness.py`*

---

<!-- Section: 27_PROJECT_FLOW.md -->
# Section 27 — Complete Project Flow

This section documents **every interaction between modules**, walking from
startup through the three primary user journeys and the operational paths.
Nothing is left unexplained.

## 27.1 Startup Sequence

```
streamlit run dashboard/app.py
  └─ dashboard/app.py
       ├─ set_page_config (wide)
       ├─ sidebar nav links to 10 pages
       ├─ init_db()  → database/database.py
       │    ├─ alembic.ini exists → run_migrations() → alembic upgrade head
       │    └─ else → Base.metadata.create_all + stamp head
       ├─ UnknownFaceService.auto_cleanup() → UnknownFaceRepo.delete_older_than(days=30)
       ├─ FaceEnrollment() → loads faiss.index + metadata.json (or creates)
       ├─ cfg.* sidebar stats (threshold, camera source)
       └─ st.switch_page("pages/01_Dashboard.py")

uvicorn api.main:app
  └─ lifespan
       ├─ init_db()
       ├─ register_default_handlers() → api/job_queue.py (batch_enroll, rebuild_index, cleanup_unknown)
       ├─ job_queue.start() → 3 asyncio workers
       └─ _validate_production_secret_key()  (fail-fast in production)
```

## 27.2 Journey A — Enroll a New Person

```
03_Enroll.py
  ├─ select camera source (CAMERA_CHOICES from camera/selector.py)
  ├─ employee details form (ID, name, dept)
  ├─ capture:
  │    webcam  → st.camera_input (browser)
  │    phone/IP → camera/selector.create_camera() → camera/phone.py *.open()
  │               → read 10 warm-up frames → preview → Confirm
  └─ _process_enrollment(frame, emp_id, name, dept)
       ├─ app/recognizer.py FaceRecognizer.extract_embedding(frame) → 512-D
       ├─ app/enrollment.py FaceEnrollment.search(emb, k=1, threshold=1.0)
       │    └─ duplicate? → warn & stop
       ├─ FaceEnrollment.enroll(name, emb) → index.add + metadata.append + _save()
       ├─ services/employee_service.py EmployeeService.create(emp_id, name, dept, faiss_id)
       │    └─ database/repository.py EmployeeRepo.create (commit/refresh)
       │    └─ services/audit_service.py AuditService.log("ENROLL", ...)
       └─ failure → rollback FaceEnrollment.remove_by_name(name)
```

## 27.3 Journey B — Live Recognition & Attendance

```
04_Live.py
  ├─ SharedModelResources.load() → RecognitionService() (models once)
  ├─ LiveRecognitionPipeline(source_type, **kwargs)
  │    └─ RecognitionService.with_shared_models(shared) → per-pipeline state
  ├─ start():
  │    ├─ camera/selector.create_camera(...).open()
  │    ├─ 3 daemon threads: capture / worker / latency
  │    └─ CameraOwner.acquire(cam, pipeline)
  ├─ capture loop: cam.read() → frame_buffer.put(frame)   [dashboard/frame_buffer.py]
  ├─ worker loop (adaptive 0.1/0.6 s):
  │    ├─ frame_buffer.get() → cv2.resize(320×240)
  │    ├─ RecognitionService.process_frame_detailed(small_frame)
  │    │     ├─ app/face_detector.py detect()            → person bboxes
  │    │     ├─ app/amfr_engine.py process_frame()
  │    │     │    ├─ app/tracking.py tracker.update()    → track_ids
  │    │     │    ├─ app/recognizer.py detect_face()     → face + landmarks + emb
  │    │     │    ├─ app/enrollment.py search()          → name/distance/confidence
  │    │     │    ├─ app/face_quality.py assess()        → quality score
  │    │     │    ├─ app/liveness_detector.py analyze_frame() → liveness (5 factors,
  │    │     │    │      deep via app/deep_liveness.py MiniFASNet/fallback)
  │    │     │    ├─ _decide() → AMFRDecision + risk_score
  │    │     │    └─ tracker.update(enriched)            → identity stability
  │    │     ├─ ACCEPT → services/attendance_service.py mark()
  │    │     │    ├─ AttendanceRepo.is_marked_today → create (commit)
  │    │     │    ├─ app/attendance.py AttendanceTracker.mark (CSV)
  │    │     │    └─ AuditService.log("MARK_ATTENDANCE")
  │    │     ├─ recognition log → RecognitionLogRepo.create (liveness/spoof/track)
  │    │     ├─ LOW_CONFIDENCE → _handle_unknown_face()
  │    │     │    └─ cv2.imwrite unknown_faces/ + UnknownFaceRepo.create + audit
  │    │     └─ REJECT_SPOOF → AuditService.log("SPOOF_ATTEMPT")
  │    ├─ scale bboxes to display size → results_buffer.put(results)
  │    └─ cache verified track_ids (_verified_at) for adaptive cadence
  ├─ display loop: frame_buffer.get() + results_buffer.get() → _draw_overlays()
  │    └─ dashboard pages show "✓ NAME · PRESENT" and today's attendance
  └─ stop(): CameraOwner.release() → pipeline.stop() → join threads → cam.release()
```

## 27.4 Journey C — Review Unknown Face → Employee

```
06_Unknown.py
  ├─ UnknownFaceService.get_statistics() / get_filtered()
  ├─ face cards: image from disk + DB row (camera, time, confidence)
  ├─ [Register Employee] → UnknownFaceService.convert_to_employee(id, emp_id, name, dept)
  │    ├─ load image (cv2.imread)
  │    ├─ FaceRecognizer.extract_embedding(image)
  │    ├─ EmployeeService.create (DB first — fail fast on duplicate)
  │    ├─ FaceEnrollment.enroll(name, emb)   (rollback employee if FAISS fails)
  │    ├─ UnknownFaceRepo.mark_converted
  │    └─ AuditService.log("CONVERT_UNKNOWN")
  ├─ [Ignore] → UnknownFaceRepo.mark_reviewed + audit
  ├─ [Delete] → UnknownFaceRepo.delete (row + image file) + audit
  └─ [Delete All] → UnknownFaceRepo.delete_all (bulk delete + file cleanup) + audit
```

## 27.5 Journey D — API Client

```
POST /auth/login
  ├─ BruteForceProtection.is_locked_out (failed_login_attempts)
  ├─ verify bcrypt password
  ├─ MFA required? → mfa_token (2 min, mfa_pending) → /auth/mfa/verify (TOTP/backup)
  └─ else → access_token + refresh_token (hash stored)
GET /employees?q=...
  ├─ get_current_user (JWT decode) → require_permission("employees","READ")
  │    └─ query user_roles → role_permissions → permissions
  ├─ EmployeeRepo.search_paginated → PageResult
  └─ audit log_event
POST /attendance  (manual mark)
  ├─ require_permission("attendance","CREATE")
  ├─ validate student + enrollment (api/attendance_service.py timetable checks)
  ├─ Attendance row + audit ATTENDANCE_MARKED
GET /events/stream (WebSocket)
  ├─ ws_manager.connect → broadcast_event on recognition events
GET /jobs → enqueue/status/cancel via api/job_queue.py
POST /bulk/students/import → BulkOperations.import_students_from_csv → BulkResult
```

## 27.6 Operational Flows

### Backup
`scripts/backup.py` → `find_pg_bin()` → preflight (psycopg2) → `pg_dump`
(SQL) + copy `faiss.index`/`metadata.json` → `manifest.json` (SHA-256) →
`backups/backup_<ts>/`.

### Restore
`scripts/restore.py` → verify hashes → (optional) terminate connections →
DROP DATABASE → CREATE DATABASE → `psql -f dump` → restore FAISS artifacts →
**restart app**.

### Seed
`scripts/seed_admin.py` → `init_db()` → seed 7 roles → seed permissions →
assign ALL to SUPER_ADMIN, subset to COLLEGE_ADMIN → create admin →
assign roles → commit. Idempotent.

### Dedupe
`scripts/dedupe_employees.py` → group by normalized name → pick survivor →
re-point attendance/recognition rows → delete duplicates; `--clean-stale`
removes employees with dead faiss_id (guarded).

### FAISS migration
`scripts/migrate_faiss_hnsw.py` → `reconstruct_n` → create new index from
config → train (IVF) → re-add → verify search.

### Bulk enroll
`scripts/bulk_enroll.py` → real (photos) or synthetic (random normalized
vectors, batched `index.add`) → optional `--db` employee records.

## 27.7 Cross-Cutting Interactions

| Concern | Modules involved |
|---------|------------------|
| Config | `config/config.py` ← `settings.yaml` → consumed by every app/service/camera module |
| Logging | `config/config.py` (rotating file + console) + module loggers; `python-json-logger` available |
| Audit | `services/audit_service.py` ← services + `api/main.py log_audit` → `audit_logs` |
| FAISS↔DB sync | `EmployeeService.update/delete` → `FaceEnrollment.rename/remove_by_name` |
| Attendance dual-write | `AttendanceService.mark` → DB + CSV (`app/attendance.py`) |
| State (Redis) | `api/redis_client.py` ← auth (OIDC state), cooldown, camera status |
| Real-time | `api/websocket_manager.py` ← `api/main.py` events/stream |
| Background jobs | `api/job_queue.py` ← `/jobs` endpoints + lifespan |
| Security headers/limits | `api/main.py` middleware stack |

## 27.8 Module Interaction Table (caller → callee)

| Caller | Callee(s) |
|--------|-----------|
| `04_Live.py` | camera/selector, services/recognition_service, services/attendance_service, dashboard/camera_owner, dashboard/frame_buffer, dashboard/latency_logger, camera/discovery |
| `RecognitionService` | app/face_detector, app/recognizer, app/enrollment, app/amfr_engine, services/attendance_service, services/audit_service, database/repository |
| `AMFREngine` | app/face_quality, app/liveness_detector, app/tracking |
| `LivenessDetector` | app/deep_liveness |
| `EmployeeService` | database/repository, services/audit_service, app/enrollment (sync) |
| `UnknownFaceService` | database/repository, services/employee_service, app/recognizer, app/enrollment, services/audit_service |
| `api/main.py` | all services, api/job_queue, api/websocket_manager, api/redis_client, api/bulk_operations, utils/upload_security, database/repository |
| `camera/selector` | camera/webcam, camera/phone, camera/fake |
| `LiveDetection` (CLI) | app/* , camera/selector, database/repository, services/employee_service |

---

*References: full call graphs traced through imports and function calls in
`dashboard/*`, `services/*`, `api/*`, `app/*`, `camera/*`, `scripts/*`*

---

<!-- Section: 28_CODE_QUALITY.md -->
# Section 28 — Code Quality Review

## 28.1 Architecture

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Separation of concerns | ⭐⭐⭐⭐ | Clear layers: camera / AI / services / repositories / API / dashboard |
| Single responsibility | ⭐⭐⭐⭐ | Modules are focused (detector, recognizer, tracker, quality, liveness...) |
| Dependency direction | ⭐⭐⭐ | Mostly clean; soft cycle: `app/live_detection.py` imports services+DB while `services/recognition_service.py` imports app (works via deferred imports; documented in §23.4) |
| Extensibility | ⭐⭐⭐⭐ | Camera factory registry, FAISS index strategy, AMFR weights — all config-driven |
| Config management | ⭐⭐⭐⭐ | Central `config.config` + YAML with defaults; comment-preserving save |

## 28.2 Maintainability

| Aspect | Assessment |
|--------|------------|
| Naming | Consistent, descriptive (module/class/method names match purpose) |
| Docstrings | Excellent — nearly every module/class/method documented with usage examples |
| Comments | Useful "why" comments (torch pin, magic-bytes rationale, Redis note) |
| Modularity | Each module independently testable |
| Dead/legacy code | `employees` table + `api/` service duplicates noted; `python-magic`/`secure`/`ydata-profiling` declared but partially unused |
| Duplication | Two audit paths (`services/audit_service.py` vs `api/audit_service.py`); two attendance services (`services/attendance_service.py` vs `api/attendance_service.py`) — intentional-ish but worth consolidating |

## 28.3 Scalability

| Dimension | Current | At scale |
|-----------|---------|----------|
| Enrollments | FAISS HNSW tuned (M=32, efS=128) | good to ~100K vectors; IVF option for more |
| Cameras | single active dashboard pipeline; API supports many | multiple pipeline instances share models (`with_shared_models`) |
| Concurrent writers | SQLite single-writer (dev) | PostgreSQL + composite indexes (prod) |
| Job processing | in-process asyncio (3 workers) | swap to Celery/Redis at scale (noted in job_queue.py) |
| Multi-process | models loaded per process | acceptable; consider Redis-backed recognition cache for multi-node |
| Analytics | SQL group-by on live DB | consider read replica / materialized views |

## 28.4 Performance

| Aspect | Verdict |
|--------|---------|
| Real-time design | Strong — thread separation, latest-frame buffers, downscaled AI, adaptive cadence, early exit |
| Hot-path hygiene | Good — psutil hoisted, EMA FPS, cached employee lookups |
| Potential bottlenecks | IoU matching Python loops; FAISS rebuild on delete/rename (O(N)); InsightFace CPU-only |
| Memory | Bounded buffers/windows; models cached once |

## 28.5 Security

| Aspect | Verdict |
|--------|---------|
| Authentication | Solid — bcrypt, JWT+rotation, MFA TOTP, OIDC |
| Authorization | RBAC with permission matrix; `require_permission` on most endpoints |
| Input validation | Pydantic + upload magic-bytes + body-size cap |
| Secrets | Prod guard fails fast; env-driven |
| Hardening notes | HSTS opt-in; TrustedHost `*` only in dev; uploads stored on local disk; Redis state validation degrades when Redis down (logged) |

## 28.6 Readability

- Code is **exceptionally readable**: ASCII pipeline diagrams in docstrings,
  clear stage labels, consistent formatting, `from __future__ import annotations`.
- Type hints used consistently.
- Long files: `api/main.py` (~2400 lines, 46 endpoints) and
  `dashboard/pages/04_Live.py` are the largest — candidates for splitting.

## 28.7 Testing

| Aspect | Assessment |
|--------|------------|
| Coverage | 20 modules; 490 tests green (with services); 484 without Redis |
| Unit tests | good per-module isolation (e.g., monkeypatched model paths) |
| Integration | PostgreSQL + Redis covered, graceful skip |
| CI | Python CI, frontend CI, Docker build + Trivy/Grype scan, security scan |
| Gaps | No tests for `api/main.py` endpoints (no TestClient suite found); WebSocket/analytics untested; benchmark scripts not CI-gated |

## 28.8 Recommended Improvements (prioritized)

### P1 — Correctness & Data integrity
1. **Store raw embeddings separately (`.npy`)** so FAISS delete/rebuild is
   faithful (explicitly recommended in `app/enrollment.py`).
2. **Add API endpoint tests** (FastAPI TestClient) — auth, RBAC, CRUD,
   refresh rotation, MFA flow.
3. **Consolidate the two audit services and two attendance services** into
   one canonical service each (avoid drift).

### P2 — Performance
4. Vectorize the IoU matching / greedy assignment (numpy) for many-person scenes.
5. ONNX-export YOLO + ArcFace for faster CPU inference.
6. Optional GPU execution provider path.

### P3 — Architecture
7. Break the `app/live_detection.py` ↔ `services/recognition_service.py`
   soft cycle by moving CLI-only DB writes behind a service.
8. Split `api/main.py` into routers (`auth`, `students`, `employees`,
   `attendance`, `cameras`, `analytics`, `jobs`, `bulk`).
9. Split `04_Live.py` into components (pipeline, discovery, UI).

### P4 — Ops & observability
10. Replace placeholder job handlers with real implementations (or Celery).
11. Add structured JSON logging wiring (python-json-logger declared).
12. Add alerting on `REJECT_SPOOF` / lockout events (audit already captures).

### P5 — Documentation drift
13. Update README's "ByteTrack" naming to the actual IoU tracker (this SDD
    documents the truth; README is aspirational).
14. Document the `api/` vs `services/` duplicate-service decision.

---

*References: codebase-wide review; `FINAL_ACCEPTANCE_REPORT.md`,
`docs/ARCHITECTURE.md`, `docs/SECURITY_REPORT.md`*

---

<!-- Section: 29_PRODUCTION_READINESS.md -->
# Section 29 — Production Readiness

## 29.1 Current Readiness Statement

**Status: ✅ PILOT DEPLOYMENT READY** (not yet full-campus "production proven").

Based on `FINAL_ACCEPTANCE_REPORT.md` (calibrated 2026-08-02):

| Claim | Status |
|-------|--------|
| Every client requirement implemented | ✅ Verified (gap analysis 9.8/10) |
| Automated tests | ✅ 490 passed, 0 failed (with Redis + PostgreSQL); 484 + 6 skipped without |
| Code complete & stable | ✅ All modules documented and tested |
| **On-site validation** (real-person attendance, spoof artifacts, multi-classroom, load) | ⏳ **Not yet proven** — scoped to the pilot plan |
| Full campus-wide rollout | 🚫 Requires pilot decision gates |

## 29.2 Readiness Matrix

| Area | Score | Evidence |
|------|-------|----------|
| Functional completeness | 9.8/10 | gap analysis report |
| Automated test coverage | High | 490 tests |
| Security posture | Good | SECURITY_REPORT.md + code review |
| Performance | Good (CPU) | PERFORMANCE_REPORT.md + benchmarks |
| Deployment automation | High | Docker, compose, CI, scripts |
| Ops (backup/restore/monitoring) | Good | scripts + health/metrics endpoints |
| Documentation | High | README, docs/, this SDD |
| On-site proven behavior | **Not yet** | pilot plan phases |

## 29.3 Missing Components / Known Limitations (verified from source)

1. **Native FAISS delete** — `remove()` raises `NotImplementedError`; raw
   embeddings not stored independently (rebuilds are O(N)).
2. **Real MOT tracker** — custom IoU tracker (no ByteTrack), identity
   switches possible under occlusion.
3. **Placeholder job handlers** — batch_enroll / rebuild_index /
   cleanup_unknown simulate work; no real queue persistence.
4. **No API endpoint test suite** — endpoints unexercised by CI.
5. **Single active dashboard camera** — multi-camera UI is future work
   (schema/API support it).
6. **CPU-only inference** — GPU paths not configured in code.
7. **HSTS opt-in**, trusted-host list must be set in production.
8. **Redis-optional degradation** — some features (OIDC CSRF state) weaken
   without Redis (logged).
9. **On-site pilot evidence** — the single biggest gap (see §29.4).

## 29.4 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Spoof attack not caught by current models | Medium | High | 5-factor liveness + AMFR hard gate; pilot spoof testing; model refresh path (`reload()`) |
| Recognition accuracy poor in real classroom lighting/angles | Medium | High | Quality gating + BORDERLINE; pilot phase tuning of thresholds |
| Identity switches under occlusion | Medium | Medium | Tracker stability + session dedupe; consider MOT upgrade |
| PostgreSQL/Redis operational failure | Low-Med | Medium | Health checks, backup/restore, graceful Redis degradation |
| Data loss (FAISS rebuild clears on bad index type) | Low | High | `remove_by_name` guards; `.npy` store recommended; backups include index |
| Default credentials used in production | Low (guarded) | High | Seed script + prod secret-key guard; document password change |
| Torch/Windows DLL issues | Medium (dev envs) | Medium | Version pin `!=2.4.0` documented |
| Scale beyond 1 camera → CPU saturation | Medium | Medium | Shared models, adaptive cadence, GPU roadmap |

## 29.5 Production Deployment Checklist

**Foundation**
- [ ] Python 3.10+/Docker installed; deps installed (`pip install -r requirements.txt`)
- [ ] `alembic upgrade head` applied; `python scripts/seed_admin.py` run
- [ ] `SECRET_KEY` ≥32 chars set; `ENVIRONMENT=production`
- [ ] `DATABASE_URL` → PostgreSQL; Redis running (`REDIS_URL`)
- [ ] `CORS_ORIGINS` and TrustedHost list configured
- [ ] HTTPS + `ENABLE_HSTS=1`; firewall closes DB/Redis ports

**System**
- [ ] Camera validated (`python main.py --debug` or Health page)
- [ ] Enrollment flow tested (Enroll page) with ≥1 person
- [ ] Live recognition tested; attendance marked in DB + CSV
- [ ] Unknown-face capture + review workflow tested
- [ ] API smoke test: login → token → `/employees` → `/attendance`
- [ ] Backup job scheduled (`scripts/backup.py` + cron) and restore tested
- [ ] Prometheus `/metrics` scraped; alerting on health/lockouts

**Pilot gating (per `docs/PILOT_DEPLOYMENT_PLAN.md`)**
- [ ] Real-person attendance accuracy measured (precision/recall)
- [ ] Spoof artifact testing (photo, screen, video) passed
- [ ] Multi-classroom operation validated
- [ ] Infrastructure load behaviour at target camera count validated
- [ ] Decision gate review before campus-wide rollout

## 29.6 Production vs Pilot Feature Parity

| Feature | Available now | Notes |
|---------|---------------|-------|
| Recognition + attendance | ✅ | employee path active |
| Student/timetable attendance | ✅ API | schema + `api/attendance_service.py` |
| Multi-camera config | ✅ API/DB | dashboard UI single-camera |
| Bulk enrollment | ✅ scripts + API | CSV import, synthetic scale tests |
| Backup/restore | ✅ scripts | PostgreSQL + FAISS + metadata |
| Monitoring | ✅ | `/health*`, `/metrics`, Health page, LatencyLogger |
| Batch jobs | ⚠️ | placeholders |
| FAISS delete at scale | ⚠️ | rebuild-based |
| GPU acceleration | ❌ | roadmap |

---

*References: `FINAL_ACCEPTANCE_REPORT.md`, `FINAL_DELIVERY_REPORT.md`,
`docs/PILOT_DEPLOYMENT_PLAN.md`, `docs/SECURITY_REPORT.md`,
`docs/GAP_ANALYSIS_COLLEGE_SCALE.md`, `docs/DEPLOYMENT.md`*

---

<!-- Section: 30_FINAL_SUMMARY.md -->
# Section 30 — Final Project Summary

## 30.1 Executive Summary

**FaceRecognitionAI** is a complete, **offline-first, real-time face
recognition and automatic attendance system** built for college-scale
deployment. It combines a **9-stage AI pipeline** (YOLO11 → tracking →
RetinaFace → face quality → 5-factor liveness → ArcFace → FAISS → AMFR →
attendance), a **10-page Streamlit dashboard**, a **secure 46-endpoint
FastAPI layer**, and **SQLite/PostgreSQL + Redis** persistence — all
verified by **490 automated tests** and supported by 15+ professional
documents and reports.

**Current status: PILOT DEPLOYMENT READY** — every requirement is
implemented and the automated suite is green; on-site validation is the
explicit next phase (see `docs/PILOT_DEPLOYMENT_PLAN.md`).

## 30.2 Complete Architecture (one diagram)

```
Camera (7 types + discovery)
  → Capture thread → FrameBuffer (latest frame)
  → Recognition worker (320×240)
      → YOLO11 → IoU Tracker → RetinaFace
      → FaceQuality → Liveness(5) → ArcFace 512-D
      → FAISS (HNSW) → AMFR risk decision
  → ACCEPT/BORDERLINE/UNKNOWN/SPOOF
  → AttendanceService (DB + CSV + audit) / UnknownFaceService / Audit
  → Streamlit dashboard (10 pages) + FastAPI (46 endpoints) + WebSocket events
  → SQLite(dev)/PostgreSQL(prod) + Redis(optional) + FAISS files
```

## 30.3 Tech Stack Summary

| Stack | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| AI | YOLO11n, RetinaFace, ArcFace (buffalo_l), MiniFASNetV2 ONNX, FAISS, custom IoU tracker, AMFR engine |
| Frontend | Streamlit + Plotly (+ optional WebRTC) |
| Backend | FastAPI + Uvicorn, WebSockets, async job queue |
| Data | SQLite (dev) / PostgreSQL 16 (prod), Redis 7, Alembic, SQLAlchemy 2.0 |
| Security | JWT + refresh rotation, bcrypt, TOTP MFA, OIDC SSO, RBAC (7 roles), slowapi, security headers, upload magic-bytes, brute-force lockout, audit logs |
| Ops | Docker multi-stage + docker-compose, GitHub Actions (CI + Trivy/Grype scans), backup/restore/seed/dedupe/migrate scripts |

## 30.4 Packages (headline)

opencv-python, numpy, pandas, Pillow, torch (≠2.4.0), ultralytics,
insightface, faiss-cpu, onnxruntime, psycopg2-binary, redis, fastapi,
uvicorn, python-multipart, python-magic, slowapi, secure, python-dotenv,
httpx, pyotp, passlib, python-jose, bcrypt, plotly, prometheus-client,
ydata-profiling, psutil, python-json-logger, gunicorn, hiredis,
ruamel.yaml, requests, sqlalchemy, alembic. (Full map in §15.)

## 30.5 Database Summary

20 tables + 2 association tables covering: RBAC (users/roles/permissions),
auth hardening (failed_login_attempts, refresh_tokens), college structure
(institutions → departments → courses → sections → classrooms → timetables),
people (students/staff/employees), enrollments, cameras, attendance,
recognition_log, unknown_faces, audit_logs — plus FAISS files and CSV
attendance logs. Full schema in §8.

## 30.6 Security Summary

Layered defense-in-depth: **biometric** (5-factor liveness + AMFR hard
spoof gate) and **cyber** (JWT + rotating refresh tokens, RBAC permission
matrix, TOTP MFA for privileged roles, OIDC SSO, bcrypt hashing with
strength policy, per-endpoint rate limiting, brute-force lockout, upload
magic-byte validation, security headers, production secret-key guard,
full audit trail). Details in §11.

## 30.7 Performance Summary

Real-time CPU design: thread-separated capture/AI/display, latest-frame
buffers, 320×240 AI downscale, adaptive inference cadence (verified tracks
→ 6× fewer runs), frame skip, early exit on empty scenes, HNSW search,
shared models (~2 GB RAM saved). Benchmarks + tuning in §19 and
`docs/PERFORMANCE_REPORT.md`.

## 30.8 Scalability Summary

- Enrollments: FAISS HNSW tuned to ~100K vectors; IVF option.
- Cameras: shared-model pipelines (`with_shared_models`); API/DB support
  many cameras; dashboard UI is single-camera (future).
- Writes: PostgreSQL + composite indexes (prod path).
- Jobs: in-process asyncio queue (swap to Celery at scale).
- Analytics: SQL aggregation; read-replica option at scale.

## 30.9 Features Checklist (what you get)

- [x] Full AI recognition pipeline with AMFR decisions
- [x] 5-factor anti-spoofing (incl. deep CNN)
- [x] Multi-camera support + network auto-discovery
- [x] Single + bulk enrollment; unknown-face review/convert workflow
- [x] Automatic attendance with 3-layer dedupe + CSV/DB dual-write
- [x] 10-page dashboard (stats, CRUD, live, records, gallery, analytics, settings, health, about)
- [x] Secure REST API + WebSocket event stream + Prometheus metrics
- [x] RBAC, MFA, OIDC, brute-force protection, audit trail
- [x] Backup/restore, seed, dedupe, FAISS migration scripts
- [x] Docker + CI/CD with container vulnerability scanning
- [x] 490 automated tests + benchmark suite

## 30.10 Future Scope

1. `.npy` raw-embedding store → faithful FAISS delete/rebuild.
2. Real ByteTrack/SORT tracker (occlusion robustness).
3. Real background jobs (batch enroll, index rebuild, cleanup) or Celery.
4. Multi-classroom dashboard UI + timetable-aware live attendance.
5. GPU inference path + ONNX YOLO/ArcFace export.
6. API endpoint test suite + router refactor.
7. Student self-service attendance app; BI/data-export integrations.
8. On-site pilot validation & threshold tuning (the current gate).

## 30.11 Recommendations

1. **Run the pilot** per `docs/PILOT_DEPLOYMENT_PLAN.md` — real-person
   accuracy, spoof testing, multi-classroom load — before campus rollout.
2. **Adopt the P1 improvements** from §28.8 (`.npy` embeddings, API tests,
   service consolidation).
3. **Set production secrets + HTTPS + HSTS** and enforce them in the
   deployment checklist (§29.5).
4. **Keep README naming aligned** with the actual tracker implementation.
5. **Use this SDD as the living spec** — update alongside code changes.

---

## Appendix — Related Reports (reference documents)

| Document | Purpose |
|----------|---------|
| `FINAL_ACCEPTANCE_REPORT.md` | Final acceptance vs client spec (490 tests green) |
| `FINAL_DELIVERY_REPORT.md` | Delivery summary (calibrated status) |
| `FINAL_VALIDATION_REPORT.md` / `PRODUCT_VALIDATION_REPORT.md` | Validation suites |
| `POSTGRESQL_VALIDATION_REPORT.md` / `LIVE_SYSTEM_VALIDATION_REPORT.md` | Infra + live validation |
| `SECURITY_REPORT.md` | Security posture & threat model |
| `PERFORMANCE_REPORT.md` | Measured performance |
| `GAP_ANALYSIS_COLLEGE_SCALE.md` | College-scale gap analysis (9.8/10) |
| `PILOT_DEPLOYMENT_PLAN.md` | Phased rollout plan with decision gates |
| `USER_MANUAL.md` / `ADMIN_MANUAL.md` / `API_DOCUMENTATION.md` / `DATABASE_SCHEMA.md` / `BACKUP_RESTORE_GUIDE.md` / `ARCHITECTURE.md` / `DEPLOYMENT.md` / `TROUBLESHOOTING.md` | Operational guides |

---

*Generated from the FaceRecognitionAI repository source code and its
existing documentation. Every section of this SDD is grounded in actual
code; any deviation between narrative and code is flagged explicitly.*

---

