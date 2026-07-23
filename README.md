# 🟢 Face Recognition AI

Real-time face recognition & attendance system using YOLO11 → RetinaFace → ArcFace → FAISS. Supports phone cameras (Android, iPhone), IP cameras, USB webcams, and laptop webcams.

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
# Core dependencies:
pip install streamlit opencv-python numpy torch faiss-cpu insightface ruamel.yaml \
    sqlalchemy alembic requests Pillow streamlit-webrtc pandas pytest
```

### 2. Start the dashboard

```bash
# Windows
run.bat

# macOS / Linux
./run.sh
```

Then open **http://localhost:8501** in your browser.

---

## 📱 Using Your Phone as a Camera

### Option A: Android Wi-Fi (IP Webcam) — *Easiest*

1. Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) on your Android phone
2. Connect your phone to the **same Wi-Fi network** as your laptop
3. Open the app and tap **Start Server**
4. Note the URL shown (e.g. `http://192.168.1.100:8080/video`)
5. On your laptop:

```bash
# CLI mode
python main.py --source-type android_wifi --camera-url http://192.168.1.100:8080/video

# Or using the launcher
run.bat android-wifi http://192.168.1.100:8080/video
```

Or in the **Streamlit Dashboard**:
- Go to **📹 Live Recognition** page → configure Camera 1 as **Android (Wi-Fi)** with the URL
- Or go to **📋 Attendance** page → switch to **📱 Phone / IP Camera** mode → configure

### Option B: Android USB (DroidCam)

1. Install [DroidCam](https://www.dev47apps.com/) on your phone and PC
2. Connect via USB, open DroidCam on both, select **USB mode**
3. On your laptop:

```bash
python main.py --source-type android_usb --camera-id 1
run.bat android-usb 1
```

### Option C: iPhone Wi-Fi (EpocCam)

1. Install [EpocCam](https://www.elgato.com/us/en/s/epoccam) on your iPhone and PC
2. Connect both to the same Wi-Fi, open EpocCam on iPhone
3. On your laptop:

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

### Option F: USB Auto (Plug & Play)

For Android 14+ with USB Webcam mode, or any UVC camera:

```bash
python main.py --source-type usb_auto
run.bat usb-auto
```

> **Tip:** The **📹 Live Recognition** dashboard page has a **Scan Network** button that auto-discovers IP Webcam and EpocCam devices on your local network. Click it and detected cameras appear with **Cam 1** / **Cam 2** buttons to auto-fill the configuration.

---

## 🖥️ CLI Reference

| Command | Description |
|---------|-------------|
| `python main.py` | Live recognition with laptop webcam |
| `python main.py --source-type android_wifi --camera-url URL` | Phone camera via Wi-Fi |
| `python main.py --source-type ip_camera --camera-url URL` | IP camera via RTSP/HTTP |
| `python main.py --enroll NAME` | Enroll a new face (add `--source-type` for phone cameras) |
| `python main.py --debug` | Run diagnostics (camera, models, etc.) |
| `python main.py --test` | Test pipeline with dataset/ images |
| `python main.py --help` | Full CLI reference |

### Supported camera source types

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

## 📊 Dashboard Pages

| Page | Description |
|------|-------------|
| **📊 Dashboard** | Overview with stats & quick actions |
| **👥 Employees** | Manage registered employees |
| **📸 Enroll** | Enroll faces from any camera source |
| **📹 Live Recognition** | Dual phone camera live feed with recognition |
| **📋 Attendance** | Live camera + attendance records |
| **🔴 Unknown Faces** | Review & convert unknown faces |
| **📈 Analytics** | Charts & trends |
| **⚙️ Settings** | Configure camera, recognition, logging |

### How the pipeline works

```
Phone Camera → Wi-Fi/USB → Laptop
                              │
                              ▼
                    ┌──────────────┐
                    │   YOLO11     │  Person detection
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │  RetinaFace  │  Face detection
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │   ArcFace    │  512-D embedding
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │    FAISS     │  Nearest neighbor search
                    └──────┬───────┘
                           ▼
               ✅ Recognized name + bounding box
               📋 Attendance automatically marked
               🔴 Unknown faces saved to gallery
```

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

All tests (currently 137+) verify: enrollment, face recognition, database CRUD, camera sources, attendance, audit logging, and the full pipeline.

---

## 🗂️ Project Structure

```
FaceRecognitionAI/
├── app/              # Core pipeline (YOLO, ArcFace, FAISS, attendance)
├── camera/           # Camera abstraction (7 source types)
├── dashboard/        # Streamlit web UI (8 pages)
├── database/         # SQLAlchemy ORM + Alembic migrations
├── services/         # Business logic layer
├── config/           # YAML-driven configuration
├── embeddings/       # FAISS index + metadata
├── models/           # yolo11n.pt model
├── tests/            # 137+ pytest cases
├── main.py           # CLI entry point
├── run.bat           # Windows launcher
├── run.sh            # macOS/Linux launcher
└── README.md         # This file
```

---

## 🔧 Configuration

Edit `config/settings.yaml` to change:
- Camera source type & URL
- Recognition thresholds
- Frame processing rate
- Unknown face retention period
- Logging level

Or use the **⚙️ Settings** page in the dashboard.
