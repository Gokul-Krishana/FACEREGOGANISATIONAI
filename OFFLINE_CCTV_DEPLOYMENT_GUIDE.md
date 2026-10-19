# OFFLINE CCTV ATTENDANCE PLATFORM — DEPLOYMENT & INTEGRATION GUIDE

**Project:** FaceRecognitionAI  
**Target Environment:** Air-Gapped College Campus / Corporate Facility  
**Date:** October 20, 2026  
**Document Classification:** Production Operational Guide  

---

## 1. System Architecture & Topology

The FaceRecognitionAI edge platform operates completely **offline** on a local server or on-premises edge workstation. No internet connectivity, external cloud APIs, or third-party telemetry are required.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PHYSICAL CCTV CAMERAS                           │
│  [Camera 1: Hall A]      [Camera 2: Main Gate]      [Camera 3: Library] │
└───────────────────┬───────────────────┬───────────────────┬────────────┘
                    │ (PoE Gigabit LAN) │                   │
                    ▼                   ▼                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   LOCAL EDGE INFERENCE SERVER                          │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Capture Layer (LiveCameraManager)                               │  │
│  │  - Independent RTSP workers (TCP transport, buffer size = 1)     │  │
│  │  - Bounded LatestFrameBuffer (Capacity: 1, Newest-Wins)          │  │
│  │  - Automatic exponential backoff reconnection                    │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │                                  │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │  Vision & Biometric Inference Engine                             │  │
│  │  - Person Detection: YOLO11n (CPU/GPU)                           │  │
│  │  - Face Detection & 5-pt Alignment: RetinaFace                   │  │
│  │  - Face Quality Filter: Blur (Laplacian), Lighting, Pose         │  │
│  │  - Deep Anti-Spoofing: MiniFASNetV2 + Texture Liveness           │  │
│  │  - Embedding: ArcFace 512-D L2 Normalized                        │  │
│  │  - Vector Search: FAISS (Cosine Similarity via L2)               │  │
│  │  - Decision Engine: AMFR (Adaptive Multi-Factor Recognition)     │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │                                  │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │  Storage & Services Layer                                        │  │
│  │  - Attendance Deduplication & Cooldown Cache                     │  │
│  │  - On-Premises Relational DB: SQLite / PostgreSQL                │  │
│  │  - Vector Index Persistence: data/embeddings/faiss.bin           │  │
│  │  - Audit Trail & Unknown Face Isolation Directory                │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │                                  │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │  Presentation & Monitoring Layer                                 │  │
│  │  - FastAPI Backend (Port 8000)                                   │  │
│  │  - Next.js 16 Enterprise Dashboard (Port 3000)                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CCTV Camera Compatibility & RTSP Configuration

### Supported Camera Types
- **IP / Network CCTV Cameras:** Any camera supporting standard RTSP over H.264 / MJPEG (Hikvision, Dahua, Axis, Hanwha, Uniview, TP-Link Vigi, Reolink, etc.).
- **NVR / DVR Streaming Channels:** RTSP sub-streams from Network Video Recorders.
- **USB / Local Devices:** DirectShow / V4L2 webcams and USB capture cards.

### Recommended RTSP Stream URL Formats

| Manufacturer | Primary / Sub-Stream RTSP URL Format |
|:---|:---|
| **Hikvision** | `rtsp://<user>:<password>@<ip>:554/Streaming/Channels/102` (Substream recommended) |
| **Dahua** | `rtsp://<user>:<password>@<ip>:554/cam/realmonitor?channel=1&subtype=1` |
| **Uniview** | `rtsp://<user>:<password>@<ip>:554/unicast/c1/s1/live` |
| **TP-Link Vigi** | `rtsp://<user>:<password>@<ip>:554/stream2` |
| **Generic ONVIF** | `rtsp://<user>:<password>@<ip>:554/live/ch0` or `/h264Preview_01_main` |

### Critical CCTV Settings (In Camera Web Admin)
1. **RTSP Transport:** Set to **TCP** (enforced by the backend). UDP causes packet loss leading to macroblocking and frozen decoded frames.
2. **Sub-Stream for AI:** Configure the camera's sub-stream to **1280×720 or 640×480 @ 15–20 FPS**. High-resolution 4K streams waste bandwidth and CPU decoding cycles without increasing facial recognition accuracy (the pipeline downscales to 320×240 for detection).
3. **Encoding:** Use **H.264 Baseline or Main profile** (avoid H.265/HEVC unless hardware-accelerated decoding is configured).
4. **I-Frame / Keyframe Interval:** Set GOP (Group of Pictures) to **1x or 2x frame rate** (e.g., 1 keyframe every 15–30 frames). This ensures the reconnect worker immediately acquires a picture without waiting for seconds.

---

## 3. Offline Readiness Checklist

Before deploying the server into an air-gapped facility without internet:

- [x] **Neural Network Weights Pre-Downloaded:**
  - `models/yolo11n.pt` (~6 MB)
  - `models/buffalo_l/` (RetinaFace `det_10g.onnx`, ArcFace `w600k_r50.onnx`, ~200 MB)
  - `models/MiniFASNetV2.onnx` (~1.5 MB for deep anti-spoofing)
- [x] **Offline Dependencies Installed:**
  - Python wheels and virtualenv created: `pip install -r requirements.txt`.
  - Node.js dependencies installed: `cd frontend && npm install`.
  - Next.js production bundle compiled: `cd frontend && npm run build`.
- [x] **Local Database Initialized:**
  - Alembic migrations applied: `alembic upgrade head`.
  - Initial administrator account created.
- [x] **Vector Index Initialized:**
  - Local FAISS index file created at `data/embeddings/faiss.bin`.
- [x] **Zero Cloud Calls:**
  - Google Fonts disabled; system sans-serif font stack used.
  - Analytics and telemetry disabled.

---

## 4. Hardware Sizing & Capacity Guidelines

| Server Profile | CPU & RAM | Recommended Cameras | Expected Latency | Notes |
|:---|:---|:---:|:---:|:---|
| **Entry Workstation** | Intel Core i5 / AMD Ryzen 5, 8GB RAM | 1–2 Streams | 55–75 ms | Tested configuration; 11–14 FPS per camera |
| **Standard Edge Server** | Intel Core i7 / Xeon 8-Core, 16GB RAM | 3–6 Streams | 40–60 ms | Multi-threaded capture workers |
| **Enterprise Server with GPU** | NVIDIA RTX 3060/4060 or T4, 32GB RAM | 10–20 Streams | 15–30 ms | CUDA TensorRT acceleration enabled |

---

## 5. Multi-Condition Biometric Enrollment Instructions

To ensure robust attendance recognition despite ordinary appearance changes (glasses, hairstyles, facial hair, varying lighting):

1. **Step 1: Frontal Clean Image**  
   Capture a clear, evenly lit frontal photograph of the student looking directly at the camera without glasses.
2. **Step 2: Eyeglasses Condition (If Applicable)**  
   If the student routinely wears spectacles, capture a second enrollment image wearing their ordinary glasses. Ensure glare is minimized.
3. **Step 3: Varied Angle / Expression**  
   Capture a third photo at a slight 10–15° angle with a natural expression.
4. **Biometric Normalization:**  
   The ArcFace extractor normalizes each face crop using affine transformation based on the 5 detected facial landmarks (left eye, right eye, nose tip, left mouth corner, right mouth corner). This ensures facial geometry is compared independent of hairstyle, ear visibility, or head roll.

---

## 6. Service Startup Commands

### Starting the Services on Windows:
```cmd
:: Terminal 1: Backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

:: Terminal 2: Frontend
cd frontend
npm run start
```
Or simply run:
```cmd
run.bat
```

### Accessing the Dashboard:
Open any web browser on the local network at:
```
http://<local-server-ip>:3000
```
API documentation available locally at:
```
http://<local-server-ip>:8000/docs
```
