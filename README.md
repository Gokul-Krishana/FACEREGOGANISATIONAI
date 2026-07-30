<div align="center">
  <h1>🤖 Face Recognition AI</h1>
  <p><strong>Real-Time Face Recognition & Automatic Attendance System</strong></p>
  <p>
    <a href="https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI">
      <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python">
    </a>
    <a href="https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions">
      <img src="https://img.shields.io/badge/Tests-393%20passing-22c55e?logo=pytest" alt="Tests">
    </a>
    <a href="https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/blob/master/LICENSE">
      <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="License">
    </a>
    <a href="https://streamlit.io">
      <img src="https://img.shields.io/badge/Streamlit-1.59-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
    </a>
    <a href="https://ultralytics.com/yolo">
      <img src="https://img.shields.io/badge/AI-YOLO11%20%7C%20ArcFace%20%7C%20FAISS-ff6f00" alt="AI Stack">
    </a>
    <a href="https://fastapi.tiangolo.com">
      <img src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi" alt="FastAPI">
    </a>
    <a href="https://www.docker.com">
      <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker" alt="Docker">
    </a>
    <br>
    <img src="https://img.shields.io/badge/Status-Production%20Ready-22c55e" alt="Status">
    <img src="https://img.shields.io/badge/Privacy-Offline%20First-6366f1" alt="Offline First">
  </p>
</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Quick Start](#-quick-start)
- [Dashboard](#-dashboard)
- [📱 Phone Camera Setup](#-phone-camera-setup)
- [CLI Reference](#-cli-reference)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Project Structure](#-project-structure)
- [Performance Optimizations](#-performance-optimizations)
- [Documentation](#-documentation)
- [License](#-license)

---

## 📖 Overview

**Face Recognition AI** is a production-ready, real-time face recognition and automatic attendance system that runs entirely **offline** — no cloud services required. Built with a modern AI stack, it combines a powerful recognition pipeline with an intuitive Streamlit dashboard.

### 🎯 Key Capabilities

| Capability | Detail |
|:-----------|:--------|
| **Recognition Pipeline** | YOLO11 → RetinaFace → ArcFace → FAISS → AMFR |
| **Anti-Spoofing** | Multi-factor liveness detection (texture, blink, motion, screen, deep CNN) |
| **Decision Engine** | AMFR — Adaptive Multi-Factor Recognition with risk scoring |
| **Camera Types** | Webcam, USB, Android (Wi-Fi/USB), iPhone (Wi-Fi/USB), IP/RTSP |
| **Performance** | Processes AI on 320×240 downscale, displays at 640×480 sharp |
| **Database** | SQLite (dev) / PostgreSQL (prod) with Alembic migrations |
| **Tests** | 🏆 **393 passing** — 0 failing, 6 gracefully skipped (Redis optional) |

### 💡 Use Cases

- 🏫 **College/University** — Automatic attendance for lectures and exams
- 🏢 **Corporate** — Employee check-in and access logging
- 🏭 **Manufacturing** — Secure area access and shift tracking
- 🏥 **Healthcare** — Staff attendance and visitor logging

---

## ✨ Features

### 🧠 Core AI Pipeline

```
Camera Frame → YOLO11 → Tracking → RetinaFace → Face Quality → Liveness → ArcFace → FAISS → AMFR → Attendance
```

| Stage | Model | Output |
|:------|:------|:-------|
| Person Detection | **YOLO11n** (Ultralytics) | Bounding boxes at 0.5 confidence |
| Face Detection | **RetinaFace** (InsightFace) | 5-point landmarks + face bbox |
| Face Quality | Blur/Lighting/Pose Assessment | 0-1 quality score (min: 0.35) |
| Liveness | 5-Factor Detection (Texture + Blink + Motion + Screen + Deep CNN) | 0-1 liveness score |
| Embedding | **ArcFace** (InsightFace buffalo_l) | 512-D L2-normalized vector |
| Search | **FAISS** (HNSW/IVF/Flat) | Nearest neighbor + L2 distance |
| Decision | **AMFR Engine** | Risk score + ACCEPT/BORDERLINE/REJECT/UNKNOWN |

### 🛡️ AMFR Decision States

| Decision | Visual | Action |
|:---------|:-------|:-------|
| ✅ **ACCEPT** | 🟢 Green box + Name + PRESENT | Attendance marked in database |
| ⚠️ **BORDERLINE** | 🟡 Yellow box + "COLLECTING FRAMES" | Collect more frames for confirmation |
| ❓ **LOW_CONFIDENCE** | ⚫ Grey box + "UNKNOWN" | Unknown face snapshot saved |
| 🚫 **REJECT_SPOOF** | 🔴 Red box + "SPOOF DETECTED" | Security alert + audit log |

### 📸 Camera Support

| Camera Type | Connection | Setup |
|:------------|:-----------|:------|
| 💻 **PC Webcam** | Built-in | ✅ None |
| 🔌 **USB Camera** | Plug & Play | ✅ Auto-detect |
| 📱 **Android (Wi-Fi)** | IP Webcam HTTP | Install IP Webcam app |
| 📱 **Android (USB)** | DroidCam | Install DroidCam app |
| 📱 **iPhone (Wi-Fi)** | EpocCam RTSP | Install EpocCam app |
| 📱 **iPhone (USB)** | EpocCam DirectShow | Install EpocCam app |
| 🌐 **IP / RTSP Camera** | Ethernet/Wi-Fi | Camera credentials |

---

## 🔧 System Architecture

<pre>
┌─────────────────────────────────────────────────────────────┐
│                        SharedModelResources                 │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────────┐ │
│  │ YOLO11n   │  │ Insight  │  │ FAISS  │  │    AMFR      │ │
│  │ Detector  │  │ Face     │  │ HNSW   │  │    Engine    │ │
│  └──────────┘  └──────────┘  └────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
         ▲              ▲            ▲              ▲
         │              │            │              │
    ┌────┴──────────────┴────────────┴──────────────┴────┐
    │              LiveRecognitionPipeline                │
    │  ┌─────────────┐  ┌───────────┐  ┌──────────────┐ │
    │  │ Capture Loop│  │ Frame     │  │ Overlay      │ │
    │  │ (Bg Thread) │  │ Downscale │  │ Drawing      │ │
    │  └─────────────┘  └───────────┘  └──────────────┘ │
    └────────────────────────┬────────────────────────────┘
                             │
    ┌────────────────────────┴────────────────────────────┐
    │                RecognitionService                    │
    │  YOLO → RetinaFace → ArcFace → FAISS → AMFR → DB   │
    └────────────────────────┬────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
    ┌─────────▼─────────┐       ┌───────────▼──────────┐
    │  AttendanceService │       │  Dashboard (Streamlit)│
    │     (PostgreSQL/   │       │  10 Pages • Live Feed│
    │       SQLite)      │       │  • Charts • Settings │
    └───────────────────┘       └──────────────────────┘
</pre>

### Key Design Decisions

1. **Shared Models** — YOLO, InsightFace, FAISS, AMFR loaded **once** in memory, shared across all camera pipelines
2. **Isolated State** — Each camera gets independent frame counters, FPS, session tracking
3. **Background Threads** — Camera capture runs in daemon threads, never blocking the UI
4. **Downscaled AI** — YOLO/ArcFace processes on 320×240; display stays at 640×480 with scaled bounding boxes
5. **Offline First** — Everything runs locally — no internet after model download
6. **Single Camera Owner** — `camera/webcam.py` is the exclusive owner of `cv2.VideoCapture`

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **pip** (Python package manager)

### 1. Clone & Setup

```bash
git clone https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI.git
cd FaceRecognitionAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head
```

> ⚠️ **First run** will automatically download:
> - YOLO11 (`yolo11n.pt`, ~6 MB)
> - InsightFace (`buffalo_l`, ~200 MB)

### 2. Start the Dashboard

```bash
streamlit run dashboard/app.py
```

Then open **http://localhost:8501** 🎉

### 3. Run Startup Validation

```bash
python tools/validate_startup.py
```

### Or Use the CLI

```bash
# Live recognition with webcam
python main.py

# Enroll a face
python main.py --enroll "John Doe"

# Run diagnostics
python main.py --debug

# Process a single image
python main.py --image photo.jpg
```

---

## 📊 Dashboard

The Streamlit dashboard provides **10 fully functional pages**:

| Page | Icon | Purpose |
|:-----|:----:|:--------|
| **Dashboard** | 🏠 | Overview with stats, recognition status, recent attendance |
| **Employees** | 👥 | CRUD management with search and attendance history |
| **Enroll** | 📸 | Face enrollment from any camera source |
| **Live Recognition** | 📹 | Real-time camera feed with AMFR overlays |
| **Attendance** | 📋 | Attendance records with live camera view |
| **Unknown Faces** | 🔴 | Gallery with review/convert/delete workflow |
| **Analytics** | 📈 | Interactive Plotly charts (daily, hourly, weekly) |
| **Settings** | ⚙️ | Full configuration editor + camera diagnostics |
| **System Health** | 🩺 | Live component monitoring & quick-fix buttons |
| **About** | ℹ️ | Version info, technology stack, credits |

### Live Recognition Workflow

```
1. Select PC Camera (default) → 2. Click START → 3. Camera feed appears
4. Person stands in front → 5. Green box + name + PRESENT
6. Attendance auto-marked → 7. Check Today's Attendance table
```

---

## 📱 Phone Camera Setup

### Android (Wi-Fi) — Easiest

1. Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) on your phone
2. Connect both devices to the **same Wi-Fi**
3. Open app → tap **Start Server**
4. Note the URL (e.g., `http://192.168.1.100:8080/video`)

**In dashboard:** 📹 Live → Select "Android Phone" → Enter URL → START

### Android (USB)

1. Install [DroidCam](https://www.dev47apps.com/) on phone + PC
2. Connect via USB with **USB Debugging** enabled
3. Open DroidCam on both → Select **USB mode**

### iPhone (Wi-Fi)

1. Install [EpocCam](https://www.elgato.com/us/en/s/epoccam) on iPhone + PC
2. Connect both to same Wi-Fi
3. Open EpocCam on iPhone → Use in dashboard

### IP / Security Camera

```bash
python main.py --source-type ip_camera --camera-url rtsp://admin:pass@192.168.1.200:554/stream1
```

### 🔍 Auto-Discovery

The **Live Recognition** page has a **Scan Cameras** button that detects:
- Local PC/USB cameras (via device index probing)
- Network phone cameras (IP Webcam, EpocCam via mDNS)

---

## 🖥️ CLI Reference

| Command | Description |
|:--------|:------------|
| `python main.py` | Live recognition with default webcam |
| `python main.py --source-type android_wifi --camera-url URL` | Phone camera via Wi-Fi |
| `python main.py --enroll "NAME"` | Enroll a face |
| `python main.py --debug` | Run diagnostics |
| `python main.py --test` | Test pipeline with dataset/ images |
| `python main.py --image photo.jpg` | Process single image |

### All Camera Source Types

| `--source-type` | Description |
|:----------------|:------------|
| `webcam` | 💻 Laptop / USB webcam (default) |
| `usb_auto` | 🔌 Auto-detect any USB camera |
| `android_wifi` | 📱 Android via IP Webcam |
| `android_usb` | 📱 Android via DroidCam |
| `iphone_wifi` | 📱 iPhone via EpocCam Wi-Fi |
| `iphone_usb` | 📱 iPhone via EpocCam USB |
| `ip_camera` | 🌐 Generic IP/RTSP camera |

---

## ⚙️ Configuration

Edit `config/settings.yaml` or use the **Settings** page in the dashboard.

### Key Settings

| Setting | Default | Description |
|:--------|:-------:|:------------|
| `camera.source_type` | `webcam` | Camera source type |
| `camera.id` | `0` | Camera device index |
| `recognition.yolo_confidence` | `0.5` | YOLO detection threshold |
| `recognition.recognition_threshold` | `1.2` | FAISS L2 distance threshold |
| `recognition.frame_skip` | `4` | Process every Nth frame (higher = faster) |
| `recognition.cooldown_seconds` | `60` | Re-mark attendance cooldown |
| `faiss.index_type` | `hnsw` | FAISS index: flat, hnsw, ivf |
| `amfr.high_confidence_threshold` | `0.70` | ACCEPT threshold |
| `amfr.borderline_threshold` | `0.40` | BORDERLINE threshold |
| `deep_liveness.enabled` | `true` | Deep CNN anti-spoofing |
| `unknown_faces.retention_days` | `30` | Auto-delete unknown faces |

---

## 🧪 Testing

```bash
# Run all 393 tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov=services --cov=database

# Run specific test file
python -m pytest tests/test_enrollment.py -v

# Run integration tests (requires PostgreSQL + Redis)
python -m pytest tests/test_integration.py -v
```

### Test Suite (393 Passing ✅)

| Test File | Tests | Coverage |
|:----------|:-----:|:---------|
| `test_enrollment.py` | 28 | Face enrollment + FAISS operations |
| `test_attendance_service.py` | 12 | Attendance marking + queries |
| `test_employee_service.py` | 18 | Employee CRUD |
| `test_repair.py` | 28 | Camera selection + config UI |
| `test_repository.py` | — | Repository pattern CRUD |
| `test_face_quality.py` | — | Face quality assessment |
| `test_deep_liveness.py` | — | Deep CNN liveness detection |
| `test_liveness_detector.py` | — | Multi-factor liveness |
| `test_tracking.py` | — | Multi-frame tracking |
| `test_upload_security.py` | — | File upload validation |
| `test_brute_force_protection.py` | — | Rate limiting + locking |
| `test_ip_camera.py` | — | IP camera source |
| `test_phone_cameras.py` | — | Phone camera sources |
| `test_integration.py` | 18 | PostgreSQL + Redis (6 skipped) |

---

## 📁 Project Structure

```
FaceRecognitionAI/
│
├── app/                    # Core AI pipeline modules
│   ├── amfr_engine.py      # Adaptive Multi-Factor Recognition
│   ├── face_detector.py    # YOLO11 person detection
│   ├── recognizer.py       # RetinaFace + ArcFace embedding
│   ├── enrollment.py       # FAISS index management
│   ├── deep_liveness.py    # CNN-based anti-spoofing
│   ├── liveness_detector.py# Multi-factor liveness
│   ├── face_quality.py     # Blur/lighting/pose assessment
│   ├── tracking.py         # Multi-frame IoU tracker
│   └── live_detection.py   # CLI pipeline
│
├── camera/                 # Camera abstraction layer
│   ├── base.py             # CameraSource interface
│   ├── webcam.py           # Webcam / USB camera (owns cv2.VideoCapture)
│   ├── phone.py            # Phone camera (Android/iPhone)
│   ├── selector.py         # Camera factory create_camera()
│   └── discovery.py        # Network auto-discovery
│
├── dashboard/              # Streamlit web UI (10 pages)
│   ├── app.py              # Main entry + navigation
│   └── pages/
│       ├── 01_Dashboard.py     # 🏠 Overview
│       ├── 02_Employees.py     # 👥 Employee management
│       ├── 03_Enroll.py        # 📸 Face enrollment
│       ├── 04_Live.py          # 📹 Live recognition
│       ├── 05_Attendance.py    # 📋 Attendance records
│       ├── 06_Unknown.py       # 🔴 Unknown face gallery
│       ├── 07_Analytics.py     # 📈 Charts & trends
│       ├── 08_Settings.py      # ⚙️ Configuration editor
│       ├── 09_Health.py        # 🩺 System health
│       └── 10_About.py         # ℹ️ About & credits
│
├── services/               # Business logic layer
│   ├── recognition_service.py   # Pipeline orchestrator
│   ├── attendance_service.py    # Attendance marking
│   ├── employee_service.py      # Employee CRUD
│   ├── unknown_face_service.py  # Unknown face lifecycle
│   ├── audit_service.py         # Audit trail
│   ├── brute_force_protection.py# Rate limiting
│   ├── mfa_service.py           # MFA backend
│   └── oidc_service.py          # OIDC integration
│
├── api/                    # FastAPI REST layer
│   ├── main.py             # FastAPI application
│   ├── attendance_service.py
│   ├── audit_service.py
│   ├── bulk_operations.py
│   ├── job_queue.py
│   ├── redis_client.py
│   └── websocket_manager.py
│
├── database/               # ORM & database layer
│   ├── database.py         # SQLAlchemy session
│   ├── models.py           # All models
│   └── repository.py       # CRUD repository
│
├── config/                 # Configuration
│   ├── config.py           # Python config module
│   └── settings.yaml       # User-editable YAML
│
├── utils/                  # Utilities
│   ├── image.py            # Image processing helpers
│   └── upload_security.py  # File upload validation
│
├── scripts/                # Benchmark & admin scripts
│   ├── benchmarks/         # FAISS tuning, AMFR validation
│   ├── bulk_enroll.py      # Bulk face enrollment
│   ├── migrate_faiss_hnsw.py
│   └── seed_admin.py       # Admin user seeding
│
├── tests/                  # 393+ pytest tests
├── docs/                   # Architecture, deployment, troubleshooting
├── embeddings/             # FAISS index + metadata
├── models/                 # YOLO weights
├── main.py                 # CLI entry point
├── Dockerfile              # Docker image
├── docker-compose.yml      # Multi-service setup
├── requirements.txt        # Dependencies
└── README.md               # This file
```

---

## 🚀 Performance Optimizations

The system includes several key optimizations for real-time performance:

| Optimization | Detail | Benefit |
|:-------------|:-------|:--------|
| **Frame Skip** | Processes every 4th frame | 75% fewer AI inferences |
| **AI Downscale** | YOLO/ArcFace runs on 320×240 | 4× faster inference |
| **Early Exit** | Skips FAISS/AMFR when no people detected | ~200ms saved per empty frame |
| **Camera FPS Cap** | Camera capped at 15 FPS | Less USB bandwidth |
| **Shared Models** | All models loaded once | Reduces memory by ~2GB |
| **Background Thread** | Non-blocking capture loop | UI stays responsive |
| **Debug Logging** | Pipeline logs at DEBUG level | Zero I/O in production |
| **HNSW Index** | Configurable FAISS HNSW graph | Fast approximate search |

---

## 📚 Documentation

| Document | Description |
|:---------|:------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Detailed system architecture & component map |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker deployment, environment variables, backup |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues, solutions & known limitations |

### Validation Reports

| Report | Description |
|:-------|:------------|
| [BASELINE_REPORT.md](BASELINE_REPORT.md) | Initial project baseline (312 tests, 296 pass) |
| [FINAL_VALIDATION_REPORT.md](FINAL_VALIDATION_REPORT.md) | Final validation (393 tests, all passing) |
| [FUNCTIONAL_REPAIR_REPORT.md](FUNCTIONAL_REPAIR_REPORT.md) | Critical bug fixes & root cause analysis |
| [LIVE_SYSTEM_VALIDATION_REPORT.md](LIVE_SYSTEM_VALIDATION_REPORT.md) | Live pipeline verification |
| [POSTGRESQL_VALIDATION_REPORT.md](POSTGRESQL_VALIDATION_REPORT.md) | PostgreSQL + Redis validation |
| [PRODUCT_BASELINE_REPORT.md](PRODUCT_BASELINE_REPORT.md) | Full product baseline |
| [PRODUCT_VALIDATION_REPORT.md](PRODUCT_VALIDATION_REPORT.md) | Full product validation |

### Technology Stack

| Component | Technology |
|:----------|:-----------|
| **Face Detection** | YOLO11n (Ultralytics) |
| **Face Recognition** | InsightFace (RetinaFace + ArcFace) |
| **Vector Search** | FAISS (HNSW/IVF/Flat) |
| **Anti-Spoofing** | Deep Liveness CNN + 5-factor detection |
| **Decision Engine** | AMFR (Adaptive Multi-Factor Recognition) |
| **Dashboard** | Streamlit (10 pages) |
| **API** | FastAPI |
| **Database** | SQLite / PostgreSQL (Alembic migrations) |
| **Cache** | Redis (optional, graceful fallback) |
| **Container** | Docker + docker-compose |
| **CI/CD** | GitHub Actions (lint, test, scan, build) |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

You are free to use, modify, and distribute this software for personal or commercial purposes.

---

<div align="center">
  <p>Built with ❤️ using open-source software</p>
  <p>
    <a href="https://ultralytics.com/yolo">YOLO11</a> •
    <a href="https://github.com/deepinsight/insightface">InsightFace</a> •
    <a href="https://faiss.ai">FAISS</a> •
    <a href="https://streamlit.io">Streamlit</a> •
    <a href="https://fastapi.tiangolo.com">FastAPI</a> •
    <a href="https://pytorch.org">PyTorch</a>
  </p>
  <p>
    <a href="https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI">
      <img src="https://img.shields.io/badge/GitHub-Face%20Recognition%20AI-181717?logo=github" alt="GitHub">
    </a>
  </p>
</div>
