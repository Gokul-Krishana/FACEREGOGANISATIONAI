# Architecture — Face Recognition AI

## Overview

Face Recognition AI is an offline-first, real-time face recognition and automatic attendance system for college deployment. It uses **AMFR (Adaptive Multi-Factor Recognition)** — a composite decision engine that combines face quality, liveness detection, ArcFace similarity, and temporal consistency to produce reliable recognition decisions.

## System Diagram

```
Camera (PC / USB / Android / iPhone / IP)
    ↓
CameraSource (unified abstraction)
    ↓
[ Background Worker Thread ]
    ├── YOLO11 — Person Detection
    ├── Multi-Frame Tracking
    ├── RetinaFace — Face Detection + Landmarks
    ├── Face Quality — Blur/lighting/pose assessment
    ├── Deep Liveness — CNN-based anti-spoofing
    ├── ArcFace — 512-D embedding extraction
    ├── FAISS — Similarity search (Flat/IVF/HNSW)
    └── AMFR — Composite risk scoring + decision
           ↓
    RecognitionService
           ↓
    AttendanceService → PostgreSQL/SQLite
           ↓
    Streamlit Dashboard (live UI)
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
SharedModelResources (loaded once)
    ├── FaceDetector (YOLO)
    ├── FaceRecognizer (InsightFace + ArcFace)
    ├── FaceEnrollment (FAISS)
    └── AMFREngine
           ↑
    Pipeline 1 ← Camera 1
    Pipeline 2 ← Camera 2
```

### 3. RecognitionService as Central Orchestrator

The `RecognitionService` in `services/recognition_service.py` is the **only** place where the full AI pipeline runs. Both the Streamlit dashboard and the FastAPI layer call this service — they never touch AI modules directly.

### 4. AMFR Decision States

| State | Visual | Action |
|-------|--------|--------|
| ACCEPT | Green box + name + PRESENT | Attendance marked |
| BORDERLINE | Yellow box + "COLLECTING FRAMES" | No attendance, collect more data |
| LOW_CONFIDENCE | Grey box + "UNKNOWN" | Save unknown face snapshot |
| REJECT_SPOOF | Red box + "SPOOF DETECTED" | Security alert, audit log |

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
| Recognition Service | `services/recognition_service.py` | Pipeline orchestrator |
| Attendance Service | `services/attendance_service.py` | Attendance CRUD |
| Employee Service | `services/employee_service.py` | Employee management |
| Dashboard | `dashboard/` | Streamlit UI |
| Database | `database/` | SQLAlchemy + Alembic |
| API | `api/main.py` | FastAPI REST layer |

## Data Flow — Recognition

```
Frame → YOLO → Track → RetinaFace → Quality → Liveness → ArcFace → FAISS → AMFR → Decision
```

1. **YOLO11** detects people in the frame
2. **Multi-frame tracker** assigns track IDs to maintain identity across frames
3. **RetinaFace** detects and aligns faces within each person crop
4. **Face Quality** assesses blur, lighting, and pose
5. **Deep Liveness** detects spoof attempts (photos, videos, masks)
6. **ArcFace** extracts a 512-D embedding vector
7. **FAISS** searches for the nearest enrolled embedding
8. **AMFR** combines quality, liveness, similarity, and tracking history into a final decision
9. **Result** is stored in the database and forwarded to the UI

## Database Schema (Core)

```
employees: id, employee_id, name, department, faiss_id, created_at
attendance: id, employee_id, confidence, timestamp, status
unknown_faces: id, image_path, camera_id, timestamp, reviewed, converted
recognition_logs: id, employee_id, is_known, confidence, timestamp
cameras: id, name, camera_id, stream_url, location, is_active
users: id, username, password_hash, roles
audit_logs: id, action, actor, description, timestamp
```

## Startup Validation

Run `python tools/validate_startup.py` to check all components before starting the application.
