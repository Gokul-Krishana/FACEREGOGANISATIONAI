# Architecture — Face Recognition AI

## Overview

Face Recognition AI is an offline-first, real-time face recognition and automatic attendance system. It uses **AMFR (Adaptive Multi-Factor Recognition)** — a composite decision engine that combines face quality, liveness detection, ArcFace similarity, and temporal consistency to produce reliable recognition decisions.

## System Diagram

```
Camera (PC / USB / Android / iPhone / IP)
    ↓
CameraSource (unified abstraction via create_camera())
    ↓
[ Background Worker Thread — LiveRecognitionPipeline ]
    │
    ├── Frame Capture @ 640×480
    ├── Downscale to 320×240 for AI
    │
    ├── YOLO11 — Person Detection
    ├── Multi-Frame Tracker (IoU-based)
    ├── RetinaFace — Face Detection + 5-point Landmarks
    ├── Face Quality — Blur/Lighting/Pose Assessment
    ├── Deep Liveness — CNN-based Anti-Spoofing
    ├── ArcFace — 512-D L2-normalized Embedding
    ├── FAISS — Similarity Search (HNSW/IVF/Flat)
    └── AMFR — Composite Risk Scoring + Decision
           ↓
    RecognitionService (orchestrator)
           ↓
    AttendanceService → PostgreSQL / SQLite
           ↓
    Streamlit Dashboard (live UI @ :8501)
```

## Key Design Decisions

### 1. Single Camera Owner

`camera/webcam.py` (`WebcamSource`, `USBAnySource`) is the **exclusive** owner of `cv2.VideoCapture`. No other module opens raw OpenCV cameras — they go through `create_camera()` in `camera/selector.py`.

This prevents:
- Multiple `VideoCapture` objects opening the same device
- Camera index conflicts between UI and backend
- Camera leaks from unreleased handles

### 2. Shared Models, Isolated State

Heavy AI models (YOLO, InsightFace, FAISS, AMFR) are loaded **once** into `SharedModelResources`. Multiple camera pipelines can share these read-only resources while keeping independent per-camera state (frame counters, FPS, session tracking).

```
SharedModelResources (loaded once @ module level)
    ├── FaceDetector (YOLO11n)
    ├── FaceRecognizer (InsightFace buffalo_l)
    ├── FaceEnrollment (FAISS HNSW index)
    └── AMFREngine (decision engine)
           ↑
    Pipeline 1 ← Camera 1
    Pipeline 2 ← Camera 2 (not yet supported via UI)
```

### 3. RecognitionService as Central Orchestrator

The `RecognitionService` in `services/recognition_service.py` is the **only** place where the full AI pipeline runs. Both the Streamlit dashboard and the FastAPI layer call this service — they never touch AI modules directly.

### 4. Downscaled AI, Sharp Display

For performance, the AI pipeline (YOLO, ArcFace, FAISS) runs on a **320×240 downscaled** version of the camera frame. After recognition, bounding box coordinates are scaled back to **640×480** and overlays are drawn on the original high-resolution frame. This gives:
- **4× faster** YOLO/ArcFace inference
- **Sharp 640×480** display quality

### 5. AMFR Decision States

| State | Visual | Action | Confidence |
|-------|--------|--------|------------|
| ✅ ACCEPT | Green box + ✓ NAME + PRESENT | Mark attendance | risk ≥ 0.70 |
| ⚠️ BORDERLINE | Yellow box + NAME? + COLLECTING | Collect more frames | risk ≥ 0.40 |
| ❓ LOW_CONFIDENCE | Grey box + ? UNKNOWN | Save unknown snapshot | risk < 0.40 |
| 🚫 REJECT_SPOOF | Red box + ⚠ SPOOF | Security alert + audit | liveness < 0.15 |

## Component Map

| Component | Path | Role |
|-----------|------|------|
| Camera Abstraction | `camera/` | Unified source interface |
| Webcam | `camera/webcam.py` | Laptop/USB camera (owns cv2.VideoCapture) |
| Phone Cameras | `camera/phone.py` | Android/iPhone Wi-Fi/USB |
| Camera Factory | `camera/selector.py` | `create_camera()` factory |
| YOLO Detector | `app/face_detector.py` | Person detection |
| Face Recognizer | `app/recognizer.py` | RetinaFace + ArcFace |
| FAISS | `app/enrollment.py` | Embedding storage/search |
| AMFR | `app/amfr_engine.py` | Decision engine |
| Face Quality | `app/face_quality.py` | Blur/lighting/pose |
| Liveness | `app/liveness_detector.py` | Multi-factor liveness |
| Deep Liveness | `app/deep_liveness.py` | CNN anti-spoofing |
| Tracking | `app/tracking.py` | Multi-frame IoU tracker |
| Recognition Service | `services/recognition_service.py` | Pipeline orchestrator |
| Attendance Service | `services/attendance_service.py` | Attendance CRUD |
| Employee Service | `services/employee_service.py` | Employee management |
| Dashboard | `dashboard/` | Streamlit UI (10 pages) |
| Database | `database/` | SQLAlchemy + Alembic |
| API | `api/main.py` | FastAPI REST layer |
| Utils | `utils/` | Image processing, upload security |

## Data Flow — Recognition

```
Frame (640×480)
  → Downscale to 320×240
    → YOLO11 — person detection
      → Multi-frame tracker — assign track IDs
        → RetinaFace — detect + align face
          → Face Quality — assess blur/lighting/pose
            → Deep Liveness — CNN anti-spoofing
              → ArcFace — 512-D embedding
                → FAISS — search nearest neighbor
                  → AMFR — composite risk score
                    → Result dict with bbox + decision
  → Scale bbox back to 640×480 coordinates
  → Draw overlays on original 640×480 frame
  → Display in Streamlit
  → If ACCEPT: mark attendance in database
```

## Database Schema

### Core Tables

```sql
employees:
  id              SERIAL PRIMARY KEY
  employee_id     VARCHAR(50) UNIQUE NOT NULL   -- e.g. "EMP001"
  name            VARCHAR(200) NOT NULL          -- display name
  department      VARCHAR(100)
  faiss_id        INTEGER
  photo_path      TEXT
  created_at      TIMESTAMP DEFAULT NOW()
  updated_at      TIMESTAMP

attendance:
  id              SERIAL PRIMARY KEY
  employee_id     INTEGER REFERENCES employees(id)
  confidence      FLOAT
  timestamp       TIMESTAMP DEFAULT NOW()
  status          VARCHAR(20) DEFAULT 'PRESENT'

unknown_faces:
  id              SERIAL PRIMARY KEY
  image_path      TEXT NOT NULL
  camera_id       INTEGER
  timestamp       TIMESTAMP DEFAULT NOW()
  reviewed        BOOLEAN DEFAULT FALSE
  converted       BOOLEAN DEFAULT FALSE

recognition_logs:
  id              SERIAL PRIMARY KEY
  employee_id     INTEGER REFERENCES employees(id)
  is_known        BOOLEAN
  confidence      FLOAT
  liveness_score  FLOAT
  timestamp       TIMESTAMP DEFAULT NOW()

cameras:
  id              SERIAL PRIMARY KEY
  name            VARCHAR(100)
  camera_id       INTEGER
  stream_url      TEXT
  location        VARCHAR(200)
  is_active       BOOLEAN DEFAULT TRUE

users:
  id              SERIAL PRIMARY KEY
  username        VARCHAR(100) UNIQUE
  password_hash   VARCHAR(255)
  roles           TEXT[]       -- ARRAY of role names
```

### Migrations

Alembic migrations in `alembic/versions/`:
- `1bf6aa4e001c_initial_schema.py` — Core tables
- `2a7c9e4f1b3d_add_failed_login_attempts_table.py` — Security
- `9c4d2f6a7b11_add_scalability_indexes.py` — Performance indexes

## Performance Architecture

```
Camera @ 15 FPS, 640×480
    │
    ├── Frame 0: process → downscale to 320×240 → full AI pipeline (YOLO → ... → AMFR)
    ├── Frame 1: skip → show previous results (no AI)
    ├── Frame 2: skip → show previous results (no AI)
    ├── Frame 3: skip → show previous results (no AI)
    └── Frame 4: process → downscale to 320×240 → full AI pipeline
```

With `frame_skip=4` and 15 FPS camera:
- **AI runs at ~3.75 Hz** (sustainable on CPU)
- **Display updates at 15 FPS** (smooth video)
- **Camera capped at 15 FPS** (reduces USB bandwidth)

## Security Architecture

```
Request → Rate Limiter (slowapi) → Auth (JWT) → RBAC → Handler
                                                       ↓
                                              Audit Service → DB
```

- **Brute force protection**: Failed login tracking + account locking
- **MFA**: Time-based one-time passwords (TOTP)
- **OIDC**: OpenID Connect for SSO integration
- **Upload validation**: File type, size, content scanning
- **Audit logging**: All CRUD operations + security events logged
- **Rate limiting**: Per-endpoint limits (slowapi)
