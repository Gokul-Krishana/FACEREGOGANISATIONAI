<div align="center">
  <h1>🟢 Face Recognition AI</h1>
  <p><strong>Real-time face recognition & automatic attendance system</strong></p>
  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue" />
    <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
    <img alt="Tests" src="https://img.shields.io/badge/Tests-137%20passing-brightgreen" />
    <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-1.28%2B-red" />
    <img alt="AI" src="https://img.shields.io/badge/AI-YOLO11%20%7C%20ArcFace%20%7C%20FAISS-orange" />
  </p>
</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [📱 Phone Camera Setup](#-phone-camera-setup)
- [Dashboard Pages](#-dashboard-pages)
- [CLI Reference](#-cli-reference)
- [Configuration](#-configuration)
- [Testing](#-testing)
- [Project Structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## 📖 Overview

**Face Recognition AI** is a production-ready, real-time face recognition system that runs entirely **offline** — no cloud services required. It combines a powerful AI pipeline with an intuitive Streamlit dashboard to provide:

- **Real-time face recognition** at 15-30 FPS
- **Automatic attendance marking** with SQLite persistence
- **Multi-camera support** — webcam, USB, Android, iPhone, IP cameras
- **Dual camera mode** — run two cameras simultaneously
- **Unknown face detection** with gallery management
- **Rich analytics** with interactive Plotly charts
- **System health monitoring** with live diagnostics

The AI pipeline: **YOLO11** → **RetinaFace** → **ArcFace** → **FAISS**

---

## ✨ Features

### 🎯 Core Recognition
| Feature | Description |
|---------|-------------|
| Face Detection | YOLO11 person detection + RetinaFace face detection |
| Face Recognition | ArcFace 512-D embeddings with FAISS similarity search |
| Multi-face | Supports multiple faces per frame |
| Real-time | 15-30 FPS on modern hardware (GPU optional) |

### 📱 Camera Support
| Camera Type | Connection | Setup Required |
|-------------|------------|----------------|
| 💻 Laptop Webcam | Built-in | None |
| 🔌 USB Webcam | Plug & Play | None (UVC compatible) |
| 📱 Android (Wi-Fi) | HTTP MJPEG | IP Webcam app |
| 📱 Android (USB) | USB | DroidCam app |
| 📱 iPhone (Wi-Fi) | RTSP/HTTP | EpocCam app |
| 📱 iPhone (USB) | DirectShow | EpocCam app |
| 🌐 IP Camera | RTSP/HTTP | Camera credentials |

### 📊 Dashboard
- **🏠 Dashboard** — Overview with stats, recognition status, recent attendance
- **👥 Employees** — CRUD management with search
- **📸 Enroll** — Face enrollment from any camera
- **📹 Live Recognition** — Dual camera mode (Android + iPhone)
- **📋 Attendance** — Live camera + attendance records
- **🔴 Unknown Faces** — Gallery with review/convert workflow
- **📈 Analytics** — Interactive charts (daily, hourly, weekly)
- **⚙️ Settings** — Full configuration editor
- **🩺 System Health** — Live monitoring & diagnostics
- **ℹ️ About** — Version info & technology stack

### 🗄️ Data Management
- **SQLite** — All data stored locally
- **FAISS** — Vector similarity search
- **CSV Export** — Download attendance data
- **Auto-cleanup** — Configurable retention for unknown faces
- **Audit Log** — All actions tracked

---

## 🔧 System Architecture

```
┌──────────────┐     ┌──────────────┐
│   Camera 1   │     │   Camera 2   │     ← Dual camera support
│  (Android)   │     │   (iPhone)   │
└──────┬───────┘     └──────┬───────┘
       │                     │
       └─────────┬───────────┘
                 │  Frame
                 ▼
        ┌────────────────┐
        │    YOLO11      │     Person Detection (conf ≥ 0.5)
        └───────┬────────┘
                 │  Person crop
                 ▼
        ┌────────────────┐
        │   RetinaFace   │     Face Detection & Alignment
        └───────┬────────┘
                 │  Aligned face
                 ▼
        ┌────────────────┐
        │    ArcFace     │     512-D Embedding
        └───────┬────────┘
                 │  Embedding vector
                 ▼
        ┌────────────────┐
        │     FAISS      │     L2 Nearest Neighbor Search
        └───────┬────────┘
                 │  Match / No match
                 ▼
        ┌────────────────────┐
        │  ✅ Known          │  → Mark attendance in SQLite
        │  🔴 Unknown        │  → Save to Unknown Faces gallery
        └────────────────────┘
```

### Key Design Decisions

- **Shared models**: YOLO, InsightFace, and FAISS are loaded **once** in memory and shared across all cameras
- **Isolated pipelines**: Each camera has its own frame counter, session tracking, and FPS calculation
- **Background threads**: Camera capture runs in daemon threads, never blocking the UI
- **Offline first**: All processing is local — no internet connection required after model download

---

## 🚀 Installation

### Prerequisites

- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **pip** (Python package manager)
- **Git** (for cloning, optional)

### Step 1: Clone or Download

```bash
git clone https://github.com/YOUR_USERNAME/FaceRecognitionAI.git
cd FaceRecognitionAI
```

Or download the ZIP and extract it.

### Step 2: Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ **Note:** The first run will download model files automatically:
> - YOLO11 (`yolo11n.pt`, ~6 MB)
> - InsightFace (`buffalo_l`, ~200 MB)
> 
> These are downloaded once and cached locally.

### Step 4: Run Database Migrations

```bash
alembic upgrade head
```

---

## ⚡ Quick Start

### Start the Dashboard

```bash
# Windows
run.bat

# macOS / Linux
./run.sh
```

Then open **http://localhost:8501** in your browser.

### Or Use the CLI

```bash
# Live recognition with laptop webcam
python main.py

# Enroll a face
python main.py --enroll "John Doe"

# Run diagnostics
python main.py --debug

# Run pipeline test
python main.py --test
```

---

## 📱 Phone Camera Setup

### Option A: Android Wi-Fi (IP Webcam) — *Easiest*

1. Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) on your Android phone
2. Connect your phone to the **same Wi-Fi network** as your laptop
3. Open the app and tap **Start Server**
4. Note the URL shown (e.g., `http://192.168.1.100:8080/video`)

**In the dashboard:**
- Go to **📹 Live Recognition** page
- Set Camera 1 source to **📱 Android (Wi-Fi)**
- Paste the URL
- Click **▶️ Start Dual Cameras**

**Or via CLI:**
```bash
python main.py --source-type android_wifi --camera-url http://192.168.1.100:8080/video
run.bat android-wifi http://192.168.1.100:8080/video
```

### Option B: Android USB (DroidCam)

1. Install [DroidCam](https://www.dev47apps.com/) on your phone and PC
2. Connect your phone via USB
3. Enable **USB Debugging** on Android (Developer Options)
4. Open DroidCam on both devices and select **USB mode**

```bash
python main.py --source-type android_usb --camera-id 1
run.bat android-usb 1
```

### Option C: iPhone Wi-Fi (EpocCam)

1. Install [EpocCam](https://www.elgato.com/us/en/s/epoccam) on your iPhone and PC
2. Connect both to the same Wi-Fi network
3. Open EpocCam on your iPhone

```bash
python main.py --source-type iphone_wifi --camera-url http://192.168.1.101:8080/video
run.bat iphone-wifi http://192.168.1.101:8080/video
```

### Option D: iPhone USB (EpocCam)

```bash
python main.py --source-type iphone_usb --camera-id 2
run.bat iphone-usb 2
```

### Option E: IP / Security Camera (RTSP)

```bash
python main.py --source-type ip_camera --camera-url rtsp://admin:pass@192.168.1.200:554/stream1
run.bat ip-camera rtsp://admin:pass@192.168.1.200:554/stream1
```

### 📡 Auto-Discovery

The **📹 Live Recognition** page has a **Scan Network** button that auto-discovers IP Webcam and EpocCam devices on your local network. Detected cameras appear with **Cam 1** / **Cam 2** buttons to auto-fill the configuration.

---

## 📊 Dashboard Pages

| Page | Icon | Description |
|------|------|-------------|
| **Dashboard** | 🏠 | Overview with stats, recognition status, recent attendance |
| **Employees** | 👥 | CRUD management with search, attendance history |
| **Enroll** | 📸 | Face enrollment from any camera source |
| **Live Recognition** | 📹 | Dual camera mode (Android + iPhone simultaneously) |
| **Attendance** | 📋 | Live camera + attendance records with CSV export |
| **Unknown Faces** | 🔴 | Gallery with review, convert to employee, bulk delete |
| **Analytics** | 📈 | Interactive charts (daily, hourly, weekly, department) |
| **Settings** | ⚙️ | Full configuration editor with camera diagnostics |
| **System Health** | 🩺 | Live monitoring, diagnostics, quick-fix buttons |
| **About** | ℹ️ | Version info, technology stack, camera guide |

---

## 🖥️ CLI Reference

| Command | Description |
|---------|-------------|
| `python main.py` | Live recognition with default webcam |
| `python main.py --source-type android_wifi --camera-url URL` | Phone camera via Wi-Fi |
| `python main.py --source-type ip_camera --camera-url URL` | IP camera via RTSP/HTTP |
| `python main.py --enroll "NAME"` | Enroll a face from webcam |
| `python main.py --enroll "NAME" --source-type android_wifi --camera-url URL` | Enroll from phone camera |
| `python main.py --debug` | Run diagnostics (camera, models, etc.) |
| `python main.py --test` | Test pipeline with dataset/ images |
| `python main.py --image photo.jpg` | Process a single image |
| `python main.py --help` | Full CLI reference |

### All Camera Source Types

| `--source-type` | Description |
|----------------|-------------|
| `webcam` | 💻 Laptop / USB webcam (default) |
| `usb_auto` | 🔌 Auto-detect any USB camera |
| `android_wifi` | 📱 Android via IP Webcam |
| `android_usb` | 📱 Android via DroidCam |
| `iphone_wifi` | 📱 iPhone via EpocCam Wi-Fi |
| `iphone_usb` | 📱 iPhone via EpocCam USB |
| `ip_camera` | 🌐 Generic IP/RTSP camera |

---

## ⚙️ Configuration

Edit `config/settings.yaml` directly or use the **⚙️ Settings** page in the dashboard.

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `camera.source_type` | `webcam` | Camera source type |
| `camera.id` | `0` | Camera device index |
| `camera.url` | `http://...` | Camera URL (phone/IP cameras) |
| `recognition.yolo_confidence` | `0.5` | YOLO detection threshold |
| `recognition.recognition_threshold` | `1.0` | FAISS L2 distance threshold |
| `recognition.frame_skip` | `2` | Process every Nth frame |
| `recognition.cooldown_seconds` | `60` | Re-mark cooldown |
| `unknown_faces.retention_days` | `30` | Auto-delete after N days |
| `logging.level` | `INFO` | Log level |

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov=services --cov=database

# Run specific test file
python -m pytest tests/test_attendance_service.py -v
```

All **137 tests** verify:
- ✅ Face enrollment pipeline
- ✅ Face recognition & FAISS search
- ✅ Database CRUD operations
- ✅ Camera source initialization
- ✅ Attendance marking & queries
- ✅ Audit logging
- ✅ Unknown face lifecycle

---

## 📁 Project Structure

```
FaceRecognitionAI/
│
├── app/                    # Core AI pipeline modules
│   ├── face_detector.py    # YOLO11 person detection
│   ├── recognizer.py       # RetinaFace + ArcFace embedding
│   ├── enrollment.py       # FAISS index management
│   ├── attendance.py       # CSV attendance logging
│   └── live_detection.py   # Integrated live pipeline
│
├── camera/                 # Camera abstraction layer
│   ├── base.py             # CameraSource interface
│   ├── webcam.py           # Webcam / USB camera
│   ├── phone.py            # Phone camera (Android/iPhone)
│   ├── selector.py         # Camera factory pattern
│   └── discovery.py        # Network auto-discovery
│
├── config/                 # Configuration
│   ├── __init__.py
│   ├── config.py           # Python config module
│   └── settings.yaml       # User-editable settings (YAML)
│
├── dashboard/              # Streamlit web UI
│   ├── app.py              # Main entry point + navigation
│   └── pages/              # 10 dashboard pages
│       ├── 01_Dashboard.py     # 🏠 Home with overview
│       ├── 02_Employees.py     # 👥 Employee management
│       ├── 03_Enroll.py        # 📸 Face enrollment
│       ├── 04_Live.py          # 📹 Dual camera live feed
│       ├── 05_Attendance.py    # 📋 Attendance records
│       ├── 06_Unknown.py       # 🔴 Unknown face gallery
│       ├── 07_Analytics.py     # 📈 Charts & trends
│       ├── 08_Settings.py      # ⚙️ Configuration editor
│       ├── 09_Health.py        # 🩺 System health monitoring
│       └── 10_About.py         # ℹ️ About & credits
│
├── database/               # ORM & database layer
│   ├── __init__.py
│   ├── database.py         # SQLAlchemy session management
│   ├── models.py           # All SQLAlchemy models
│   └── repository.py       # CRUD repository pattern
│
├── services/               # Business logic layer
│   ├── __init__.py
│   ├── attendance_service.py   # Attendance marking
│   ├── employee_service.py     # Employee CRUD
│   ├── recognition_service.py  # Recognition pipeline
│   ├── unknown_face_service.py # Unknown face lifecycle
│   └── audit_service.py        # Audit trail logging
│
├── embeddings/             # FAISS index + metadata
│   ├── faiss.index         # Binary FAISS index
│   └── metadata.json       # Name-to-ID mapping
│
├── models/                 # Model weights
│   └── yolo11n.pt          # YOLO11 nano model
│
├── tests/                  # 137+ pytest test cases
│   ├── test_attendance_service.py
│   ├── test_employee_service.py
│   ├── test_enrollment.py
│   ├── test_repository.py
│   ├── test_ip_camera.py
│   ├── test_phone_cameras.py
│   └── ...
│
├── main.py                 # CLI entry point
├── requirements.txt        # Python dependencies
├── LICENSE                 # MIT License
├── .gitignore              # Git ignore rules
├── run.bat                 # Windows launcher
├── run.sh                  # macOS/Linux launcher
└── README.md               # This file
```

---

## 🔧 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| **Camera not detected** | Close apps using the camera (Zoom, Teams). Try different device indices (0, 1, 2). For phone cameras, install the required app first. |
| **No face detected** | Ensure good lighting. Position face clearly in frame. Avoid extreme angles. Minimum face size ~100px. |
| **Low recognition accuracy** | Lower the recognition threshold in Settings. Re-enroll with better lighting. Enroll multiple angles. |
| **Slow performance** | Increase `frame_skip` in Settings. Use a smaller YOLO model. Close other GPU-intensive apps. |
| **FAISS index error** | Delete `embeddings/faiss.index` and re-enroll employees. Ensure `embeddings/` directory is writable. |
| **Model download fails** | Check internet connection. Models download once on first run. Manual: download `yolo11n.pt` to `models/`. |
| **Database locked** | Ensure only one instance is running. Delete `data/*.db` files (backup first) and re-run migrations. |

### Diagnostics

Run the built-in diagnostics:

```bash
# CLI diagnostics
python main.py --debug

# Dashboard health page
# → 🩺 System Health page at http://localhost:8501
```

### Getting Help

- Check the **🩺 System Health** page for live component status
- Review `logs/app.log` for detailed error traces
- Use the **⚙️ Settings** → **Camera Diagnostics** to scan for cameras

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
    <a href="https://pytorch.org">PyTorch</a>
  </p>
</div>
