<div align="center">

# FACE RECOGNITION ATTENDANCE SYSTEM 2.0

### *Intelligent Attendance. Real-Time Recognition. Secure Identity Verification.*

<br/>

<img src="docs/assets/cinematic/cinematic_poster.png" alt="Face Recognition AI 2.0 Hero Poster" width="100%" style="border-radius: 12px; box-shadow: 0 10px 30px rgba(0, 240, 255, 0.15);" />

<br/><br/>

[![Python CI](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/python-ci.yml/badge.svg?branch=master)](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/python-ci.yml)
[![Linux Build & Compatibility CI](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/linux-build.yml/badge.svg?branch=master)](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/linux-build.yml)
[![Docker CI](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/docker-build.yml/badge.svg?branch=master)](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/docker-build.yml)
[![Apple iOS Build CI](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/ios-build.yml/badge.svg?branch=master)](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/actions/workflows/ios-build.yml)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-GHCR%20Container-2496ED?logo=docker&logoColor=white)](https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI/pkgs/container/faceregoganisationai)
[![Swift 5.9](https://img.shields.io/badge/Swift-5.9%20%7C%20iOS%2016+-F05138?logo=swift&logoColor=white)](ios/FaceRecognitionAttendance)

<br/>

[🎬 Cinematic Story](#the-cinematic-journey-one-continuous-flow) •
[📐 System Architecture](#4-cinematic-system-architecture) •
[⚡ Quick Start](#8-platform-installation-deployment) •
[🛡️ Security & Privacy](#11-security-privacy-biometric-data) •
[🧪 Verification (541/541 Tests)](#13-verification-test-certification)

<br/>

</div>

---

## Executive Summary

The **Face Recognition Attendance System 2.0** is an enterprise-grade biometric attendance verification platform engineered for colleges, universities, corporate headquarters, and high-security institutions. Powered by **YOLOv8**, **ArcFace 512-D embeddings**, **FAISS vector acceleration**, and **MiniFASNetV2 anti-spoofing**, the system transforms raw video streams into authenticated attendance events in less than **200 milliseconds**.

Operating across **Windows**, **Linux**, **Docker containers**, and **Apple iOS**, the platform pairs a high-throughput **FastAPI REST API** with a 10-page reactive **Streamlit Management Dashboard**, delivering atomic transaction guarantees, brute-force lockout, authenticated AES-256-GCM vector encryption at rest, and NIST SP 800-88 cryptographic biometric shredding.

---

## Table of Contents

- [1. The Cinematic Journey — One Continuous Flow](#the-cinematic-journey-one-continuous-flow)
  - [Scene 01 // The Problem](#scene-01-the-problem)
  - [Scene 02 // Capture](#scene-02-capture)
  - [Scene 03 // Detect](#scene-03-detect)
  - [Scene 04 // Verify Liveness](#scene-04-verify-liveness)
  - [Scene 05 // Recognize](#scene-05-recognize)
  - [Scene 06 // Record](#scene-06-record)
  - [Scene 07 // See the Result](#scene-07-see-the-result)
  - [Scene 08 // The Unified Ecosystem](#scene-08-the-unified-ecosystem)
- [2. Key Features](#2-key-features)
- [3. Complete Technology Stack](#3-complete-technology-stack)
- [4. Cinematic System Architecture](#4-cinematic-system-architecture)
- [5. AI Recognition Pipeline](#5-ai-recognition-pipeline)
- [6. Multi-Modal Anti-Spoofing & Liveness Defense](#6-multi-modal-anti-spoofing-liveness-defense)
- [7. Idempotent Attendance & Concurrency Control](#7-idempotent-attendance-concurrency-control)
- [8. Platform Installation & Deployment](#8-platform-installation-deployment)
  - [Windows Installation (DirectShow)](#windows-installation)
  - [Linux Ubuntu 22.04 LTS (V4L2 & systemd)](#linux-installation)
  - [Docker Container Deployment (GHCR)](#docker-deployment)
  - [Apple iOS Client (Swift 5.9 & SwiftUI)](#apple-ios-client)
- [9. REST API Specification](#9-rest-api-specification)
- [10. Management Dashboard & Telemetry](#10-management-dashboard-telemetry)
- [11. Security, Privacy & Biometric Data](#11-security-privacy-biometric-data)
- [12. 7-Pillar Production Hardening](#12-7-pillar-production-hardening)
- [13. Verification & Test Certification](#13-verification-test-certification)
- [14. Troubleshooting & Operational Guide](#14-troubleshooting-operational-guide)
- [15. Roadmap & Future Innovations](#15-roadmap-future-innovations)
- [16. Asset Credits & License](#16-asset-credits-license)

---

## The Cinematic Journey — One Continuous Flow

> *"A person approaches the camera. The AI detects their face, verifies liveness, recognizes their identity, validates authorization, records attendance in the database with duplicate protection, and updates the management dashboard in real time."*

Experience the complete, uninterrupted 0.2-second attendance sequence below:

<div align="center">
  <img src="docs/assets/cinematic/master_journey.gif" alt="Master Cinematic Journey: Continuous 8-Stage Flow" width="92%" style="border-radius: 8px; border: 1px solid #1E293B;" />
  <p><em>Master Journey Animation: Complete continuous pipeline transition across all 8 processing stages.</em></p>
</div>

<br/>

### Scene 01 // The Problem
> **"Attendance should be intelligent, automatic and secure."**

<div align="center">
  <img src="docs/assets/cinematic/scene_01_problem.gif" alt="Scene 01: The Problem" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

Traditional attendance systems rely on manual registers, RFID swipe bottlenecks, or fingerprint scanners that create long morning lines, high proxy attendance risks, and manual transcription errors. **Face Recognition AI 2.0** replaces manual friction with instantaneous, hands-free biometric verification.

---

### Scene 02 // Capture
> **"Every attendance journey begins with a live camera frame."**

<div align="center">
  <img src="docs/assets/cinematic/scene_02_camera.gif" alt="Scene 02: Camera Capture" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

The system establishes an ingestion pipeline utilizing native OS backends: **DirectShow / Media Foundation** on Windows, and **V4L2** on Linux. The resilient camera manager incorporates re-entrant locking, continuous frame jitter buffering, and an automatic exponential backoff supervisor that recovers from camera disconnects without application restarts.

---

### Scene 03 // Detect
> **"AI locates the face and evaluates whether it is suitable for recognition."**

<div align="center">
  <img src="docs/assets/cinematic/scene_03_detection.gif" alt="Scene 03: Face Detection" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

High-throughput neural detectors (**YOLOv8-Face** accelerated by ONNX Runtime) isolate facial bounding boxes in single-digit milliseconds. The engine extracts five crucial facial landmarks (eyes, nose, mouth corners) and applies a multi-criteria quality filter: Laplacian sharpness variance, face tilt/yaw thresholds, and illumination checks. Sub-quality or heavily occluded crops are filtered before downstream feature extraction.

---

### Scene 04 // Verify Liveness
> **"Check that the input appears to come from a real live person, not a photo or screen replay."**

<div align="center">
  <img src="docs/assets/cinematic/scene_04_liveness.gif" alt="Scene 04: Liveness Verification" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

Presentation attacks are repelled using a multi-layered defense. The **MiniFASNetV2** deep convolutional neural network evaluates micro-texture spatial frequency to identify high-resolution print paper grain, moiré patterns, and mobile screen bezel reflections. In live video mode, temporal Eye Aspect Ratio (EAR) blink cycle heuristics confirm physiological vitality. Fake attempts are rejected instantly.

---

### Scene 05 // Recognize
> **"AI compares facial features against enrolled identities to find a match."**

<div align="center">
  <img src="docs/assets/cinematic/scene_05_recognition.gif" alt="Scene 05: Face Recognition" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

Verified facial crops pass through deep **ArcFace ResNet** feature extractors, generating a normalized 512-dimensional mathematical vector signature. The query vector is searched against the enrolled database via **FAISS** (Facebook AI Similarity Search) using hierarchical navigable small-world (HNSW) graphs. Vector comparisons achieve sub-millisecond execution times even with college-scale directories.

---

### Scene 06 // Record
> **"Verified attendance is securely recorded, with duplicate protection."**

<div align="center">
  <img src="docs/assets/cinematic/scene_06_attendance.gif" alt="Scene 06: Attendance Recording" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

Once an identity is verified, the system generates an atomic database transaction. An **Idempotency Key** composed of the employee ID and calendar date (`YYYY-MM-DD:EMP_ID`) is enforced at the database level with a unique composite index. Multiple camera hits on the same day are deduplicated automatically, guaranteeing that an employee receives exactly one official attendance check-in.

---

### Scene 07 // See the Result
> **"Attendance updates appear instantly in the management dashboard."**

<div align="center">
  <img src="docs/assets/cinematic/scene_07_dashboard.gif" alt="Scene 07: Management Dashboard" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

The committed attendance record synchronizes across the system. The 10-page reactive **Streamlit Administrative Portal** updates KPI counters (`Total Present`, `Absent`, `Punctuality Rate`), streams the live CCTV feed, displays the employee's name and check-in timestamp in the live attendance ledger, and emits an auditable entry into the tamper-evident security log.

---

### Scene 08 // The Unified Ecosystem
> **"One connected, multi-platform attendance ecosystem."**

<div align="center">
  <img src="docs/assets/cinematic/scene_08_ecosystem.gif" alt="Scene 08: Ecosystem Overview" width="85%" style="border-radius: 8px; border: 1px solid #1E293B;" />
</div>

The platform runs harmoniously across environments:
- **Windows Baseline:** Native DirectShow video ingestion, multi-threaded supervisor, zero regressions preserved.
- **Linux Environment:** V4L2 device handling, systemd daemon management, POSIX path normalization.
- **Docker Container:** Multi-stage minimal container, non-root `faceai` user, automated healthcheck.
- **Apple iOS Client:** Swift 5.9 native mobile client, SwiftUI frontend, fail-closed Apple Security Keychain.

---

## 2. Key Features

- **⚡ Sub-200ms Processing Latency:** Real-time end-to-end processing pipeline from camera frame grab to database commit.
- **🎯 512-D ArcFace Deep Embeddings:** Additive Angular Margin loss embeddings for high discriminative feature separation.
- **🚀 Accelerated FAISS Search:** HNSW, Flat, and IVF indexing with vectorized batch comparison for enterprise directory scaling.
- **🛡️ Multi-Modal Anti-Spoofing:** MiniFASNetV2 deep convolutional neural networks combined with Eye Aspect Ratio (EAR) blink heuristics.
- **🔒 Idempotent Daily Check-ins:** Database-level uniqueness constraints eliminate duplicate check-in entries across multiple gate cameras.
- **🔐 7-Tier Enterprise RBAC:** Granular role enforcement (`SUPER_ADMIN`, `ADMIN`, `CAMPUS_DIRECTOR`, `ATTENDANCE_MANAGER`, `SECURITY_OFFICER`, `EMPLOYEE`, `STUDENT`) with 60 permissions.
- **🛡️ Authenticated Biometric Encryption:** AES-256-GCM vector encryption at rest with PBKDF2-HMAC-SHA256 key derivation (`utils/biometric_crypto.py`).
- **🗑️ Cryptographic Data Shredding:** NIST SP 800-88 compliant multi-pass overwrite and zeroing for deleted employee biometric vectors.
- **📊 10-Page Reactive Dashboard:** Streamlit management interface featuring live multi-camera previews, batch enrollment, and audit logs.
- **📱 Native Apple iOS App:** Swift 5.9 mobile client featuring strict fail-closed Apple Security Keychain storage.

---

## 3. Complete Technology Stack

| Domain | Technology / Component | Version / Spec | Role & Functionality |
| :--- | :--- | :--- | :--- |
| **Language** | Python | 3.10 – 3.12 | Core backend, AI pipeline, dashboard, and scripts |
| **Mobile Language** | Swift | 5.9+ | Native Apple iOS client application |
| **REST API** | FastAPI | 0.115+ | High-throughput asynchronous REST server with OpenAPI |
| **Web Server** | Uvicorn / Starlette | Production ASGI | Production async gateway with worker supervision |
| **Admin Portal** | Streamlit | 1.40+ | Modernized 10-page dark-mode administrative dashboard |
| **Computer Vision** | OpenCV (`cv2`) | 4.10+ | Frame ingestion, DirectShow (Win), V4L2 (Linux) |
| **Face Localization** | YOLOv8-Face / ONNX | Latest | Real-time face bounding box and landmark detection |
| **Feature Extraction** | ArcFace (InsightFace) | ResNet-50 / 100 | 512-dimensional mathematical feature extraction |
| **Vector Engine** | FAISS | 1.9+ | Sub-millisecond vector indexing and similarity retrieval |
| **Liveness Engine** | MiniFASNetV2 | ONNX Runtime | Deep convolutional neural network anti-spoofing |
| **Database** | SQLite / PostgreSQL | WAL / ACID | Transactional storage with Alembic schema migrations |
| **Security / Crypto** | Cryptography / Bcrypt | AES-256-GCM | Vector encryption at rest and password hashing |
| **Containerization** | Docker | Multi-Stage | Hardened container runtime with non-root user (`faceai`) |
| **Mobile Framework** | SwiftUI / SPM | iOS 16.0+ | Mobile interface with Apple Security Keychain persistence |

---

## 4. Cinematic System Architecture

```mermaid
flowchart TD
    subgraph INGESTION["1. INGESTION & ACQUISITION"]
        CAM["Live Video Cameras<br/>(DirectShow / V4L2 / RTSP)"] --> RCAM["ResilientCameraSource<br/>(Auto-reconnect, Jitter Buffer)"]
        RCAM --> FRAME["Raw RGB Video Frame"]
    end

    subgraph DETECTION["2. FACE LOCALIZATION & QUALITY"]
        FRAME --> YOLOV8["YOLOv8-Face Neural Detector<br/>(ONNX Runtime Engine)"]
        YOLOV8 --> BBOX["Bounding Box & 5 Landmarks"]
        BBOX --> QUALITY{"Quality Filter<br/>(Sharpness, Tilt, Illumin)"}
        QUALITY -- "Fails Threshold" --> REJECT_Q["Discard Frame"]
        QUALITY -- "Passes Quality" --> CROP["Aligned 112x112 Face Crop"]
    end

    subgraph LIVENESS["3. ANTI-SPOOFING VERIFICATION"]
        CROP --> FASNET["MiniFASNetV2 Deep CNN<br/>(Spatial Texture Analysis)"]
        CROP --> BLINK["Eye Aspect Ratio (EAR)<br/>(Blink Cycle Heuristics)"]
        FASNET & BLINK --> AMFR_L{"Liveness Gate"}
        AMFR_L -- "Spoof Detected" --> LOG_SPOOF["Reject & Audit Log Spoof"]
        AMFR_L -- "Genuine Live" --> LIVE_CROP["Validated Live Face"]
    end

    subgraph RECOGNITION["4. DEEP EMBEDDING & SEARCH"]
        LIVE_CROP --> ARCFACE["ArcFace Deep Feature Extractor<br/>(512-D Normalized Vector)"]
        ARCFACE --> FAISS["FAISS Vector Index<br/>(HNSW / Flat / IVF)"]
        FAISS --> MATCH{"Cosine Similarity<br/>Score >= Threshold?"}
        MATCH -- "Unknown Identity" --> UNK["Buffer in Unknown Faces"]
        MATCH -- "Matched Candidate" --> IDENTITY["Resolved Identity: EMP-XXXX"]
    end

    subgraph ATTENDANCE["5. IDEMPOTENT TRANSACTION"]
        IDENTITY --> CONSENT{"Biometric Consent<br/>Active & Valid?"}
        CONSENT -- "Withdrawn" --> SUPPRESS["Suppress Recognition"]
        CONSENT -- "Consented" --> IDEM_KEY["Generate Idempotency Key<br/>(YYYY-MM-DD:EMP_ID)"]
        IDEM_KEY --> DB_COMMIT[("Database Commit<br/>(PostgreSQL / SQLite WAL)")]
        DB_COMMIT --> AUDIT["Tamper-Evident Audit Record"]
    end

    subgraph INTERFACES["6. MULTI-PLATFORM SURFACES"]
        DB_COMMIT --> API["FastAPI REST Endpoints<br/>(:8000 OpenAPI Documentation)"]
        DB_COMMIT --> DASHBOARD["Streamlit Administrative Portal<br/>(:8501 10-Page Dark Theme)"]
        API --> IOS["Native Apple iOS Client<br/>(SwiftUI & Security Keychain)"]
    end

    style INGESTION fill:#080C16,stroke:#00F0FF,stroke-width:1px
    style DETECTION fill:#080C16,stroke:#3B82F6,stroke-width:1px
    style LIVENESS fill:#080C16,stroke:#8B5CF6,stroke-width:1px
    style RECOGNITION fill:#080C16,stroke:#00F0FF,stroke-width:1px
    style ATTENDANCE fill:#080C16,stroke:#10B981,stroke-width:1px
    style INTERFACES fill:#080C16,stroke:#3B82F6,stroke-width:1px
```

---

## 5. AI Recognition Pipeline

The recognition pipeline is built upon three foundational algorithms:

1. **YOLOv8-Face Detection:** Localizes human faces in milliseconds, outputting high-precision coordinates and 5 fiducial landmarks (left eye, right eye, nose, left mouth, right mouth).
2. **ArcFace Embedding Extraction:** Uses an Additive Angular Margin Loss architecture that maximizes intra-class compactness and inter-class discrepancy on a hypersphere manifold, outputting normalized 512-dimensional vectors.
3. **FAISS Indexing:** Fast search algorithms allow real-time vector queries across directories with minimal CPU and memory overhead:
   - `IndexHNSWFlat`: High-performance graph traversal for enterprise scalability.
   - `IndexFlatL2 / IndexFlatIP`: Exact cosine inner-product matching.
   - `IndexIVFFlat`: Inverted file clustering for resource-constrained instances.

---

## 6. Multi-Modal Anti-Spoofing & Liveness Defense

The platform mitigates presentation attacks through multi-modal gating:

```
                          ┌─────────────────────────────┐
                          │   Live Camera Face Stream   │
                          └──────────────┬──────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
   ┌───────────────────────────────┐           ┌───────────────────────────────┐
   │ MiniFASNetV2 Deep Neural Net  │           │   Eye Aspect Ratio (EAR)      │
   │ Micro-texture Fourier spectra │           │ Temporal blink cycle analysis │
   └───────────────┬───────────────┘           └───────────────┬───────────────┘
                   │                                           │
                   └─────────────────────┬─────────────────────┘
                                         ▼
                          ┌─────────────────────────────┐
                          │     Consensus Decision      │
                          │   Live >= 0.85 & Valid Blink│
                          └──────────────┬──────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
             [GENUINE LIVE FACE]                [SPOOF REJECTED]
             Proceeds to Matching               Blocked & Logged to Audit
```

- **Paper Print Attacks:** Detected by specular reflection absence and micro-texture high-frequency Fourier roll-off.
- **Screen Replay Attacks:** Caught by LCD/OLED RGB sub-pixel moiré patterns and screen bezel boundaries.
- **Static Video Loops:** Rejected through temporal micro-movement and eye blink cycle validation.

---

## 7. Idempotent Attendance & Concurrency Control

In enterprise facilities with multiple entrance gates, employees often pass several cameras within minutes. The system prevents duplicate records:

$$\text{Idempotency Key} = \text{SHA256}(\text{Date} \parallel \text{Employee ID})$$

```sql
-- Enforced unique constraint in database/models.py
CREATE UNIQUE INDEX uq_attendance_emp_date 
ON attendance (employee_id, date(timestamp));
```

When concurrent hits arrive from different cameras, the first transaction commits atomically while subsequent attempts trigger an idempotent pass with zero database duplication.

---

## 8. Platform Installation & Deployment

### Windows Installation

<details open>
<summary><b>Click to expand Windows DirectShow deployment steps</b></summary>
<br/>

**Requirements:** Windows 10/11 64-bit, Python 3.10–3.12, USB Webcam (DirectShow compatible).

```bash
# 1. Clone repository
git clone https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI.git
cd FACEREGOGANISATIONAI

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Initialize database schema
python -c "from database.database import init_db; init_db()"

# 5. Start FastAPI Backend (Terminal 1)
uvicorn api.main:app --host 127.0.0.1 --port 8000

# 6. Start Streamlit Dashboard (Terminal 2)
streamlit run dashboard/app.py --server.port 8501
```
Access the Dashboard at `http://localhost:8501` and API docs at `http://localhost:8000/docs`.
</details>

---

### Linux Installation

<details>
<summary><b>Click to expand Linux Ubuntu 22.04 LTS deployment steps</b></summary>
<br/>

**Requirements:** Ubuntu 22.04 LTS, Python 3.10–3.12, V4L2 USB camera or RTSP network stream.

```bash
# 1. Install Linux system libraries
sudo apt-get update && sudo apt-get install -y \
    libgl1 libglib2.0-0 libmagic1 v4l-utils curl

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install Linux dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements-linux.txt

# 4. Bootstrap database
python3 -c "from database.database import init_db; init_db()"

# 5. Launch with systemd services
sudo cp deployment/linux/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now faceai-api faceai-dashboard
```
</details>

---

### Docker Deployment

<details>
<summary><b>Click to expand Docker containerization commands</b></summary>
<br/>

The official container is published to the GitHub Container Registry:

```bash
# Pull production image from GHCR
docker pull ghcr.io/gokul-krishana/faceregoganisationai:latest

# Run container with persistent data volumes
docker run -d \
  --name faceai-app \
  -p 8000:8000 \
  -v faceai_data:/app/data \
  -v faceai_embeddings:/app/embeddings \
  -e JWT_SECRET_KEY="replace-with-your-strong-production-secret-key" \
  -e LOG_LEVEL="INFO" \
  ghcr.io/gokul-krishana/faceregoganisationai:latest

# Verify container health
curl -f http://localhost:8000/health
```
</details>

---

### Apple iOS Client

<details>
<summary><b>Click to expand Apple iOS Swift 5.9 client structure</b></summary>
<br/>

The iOS client is located in `ios/FaceRecognitionAttendance/` and connects to the backend API:

- **Swift Package Manager & Xcode Scheme:** Configured for iOS 16.0+.
- **Fail-Closed Security Keychain:** Uses Apple's Security framework (`SecItemAdd`, `SecItemCopyMatching`) for JWT token storage.
- **SwiftUI Frontend:** Includes authentication, attendance history, and status checks.

```bash
# Open in Xcode on macOS
cd ios/FaceRecognitionAttendance
open Package.swift # or use Xcode project FaceRecognitionAttendance.xcodeproj

# Build and execute unit tests via CLI
swift test
```
</details>

---

## 9. REST API Specification

The FastAPI backend provides interactive OpenAPI documentation at `/docs`:

| Method | Endpoint | Authorization | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/login` | Public | Authenticate user credentials and return JWT bearer token |
| `POST` | `/auth/refresh` | Bearer Token | Refresh expiring authentication tokens |
| `GET` | `/employees` | Role-Based | Retrieve paginated directory of registered employees |
| `POST` | `/employees` | Admin / HR | Register new employee and record biometric consent |
| `DELETE`| `/employees/{id}` | Admin | Delete employee and permanently shred biometric files |
| `POST` | `/attendance/record`| Camera / Device| Idempotently log verified biometric attendance |
| `GET` | `/attendance/today` | Authenticated | Retrieve all verified attendance records for today |
| `GET` | `/health` | Public | System liveness, database, and Redis fallback health |
| `GET` | `/health/system` | Admin | Deep system metrics: CPU, memory, FAISS vectors, DB count |

---

## 10. Management Dashboard & Telemetry

The Streamlit portal provides ten administrative pages:

1. **`01_Dashboard.py`**: Real-time KPI statistics, today's attendance metrics, and quick action controls.
2. **`02_Employees.py`**: Directory management, consent status indicators, and biometric shredding controls.
3. **`03_Enroll.py`**: Manual and batch enrollment with real-time pose and sharpness validation.
4. **`04_Live.py`**: Live multi-camera CCTV monitoring with bounding box overlays and health metrics.
5. **`05_Attendance.py`**: Filterable logs, CSV/Excel report exports, and manual override capabilities.
6. **`06_Unknown.py`**: Unknown face review for security personnel.
7. **`07_Analytics.py`**: Department punctuality charts, peak arrival times, and absentee trends.
8. **`08_Settings.py`**: Recognition thresholds, liveness sensitivity, and alert configurations.
9. **`09_Health.py`**: CPU, memory, camera FPS, FAISS synchronization, and service status.
10. **`10_About.py`**: Versioning, architecture documentation, and system licenses.

---

## 11. Security, Privacy & Biometric Data

- **Biometric Encryption at Rest:** Facial embeddings stored on disk are protected with authenticated **AES-256-GCM / Fernet** encryption (`utils/biometric_crypto.py`). Keys are derived using PBKDF2-HMAC-SHA256 with 100,000 iterations.
- **NIST SP 800-88 Cryptographic Shredding:** Withdrawing employee consent or deleting a record triggers permanent multi-pass random overwrites followed by zero-filling (`shred_file`) of biometric crops and vectors.
- **Auditable Consent Tracking:** Database schema explicitly tracks `consent_given`, `consent_date`, and `retention_policy_days`. Withdrawing consent suppresses real-time identification.
- **Fail-Closed Principle:** Corrupted frames, dropped streams, or ambiguous similarity matches default to rejection.
- **Brute-Force Lockout:** Automated account lockout and IP rate limiting defend administrative login endpoints.

---

## 12. 7-Pillar Production Hardening

The repository has completed seven comprehensive production hardening pillars:

```
┌────────────────────────────────────────────────────────────────────────┐
│               7-PILLAR PRODUCTION HARDENING FRAMEWORK                  │
├────────────────────┬───────────────────────────────────────────────────┤
│ 1. Enterprise RBAC │ 7 hierarchical roles, 60 granular permissions    │
│ 2. Biometric Crypto│ AES-256-GCM encryption & NIST SP 800-88 shredding │
│ 3. Vector Speed    │ FAISS vectorized batch search acceleration        │
│ 4. DB Reliability  │ Atomic SQLite WAL snapshots & pg_dump backups     │
│ 5. Modernized UI   │ Responsive dark mode theme across all 10 pages    │
│ 6. Supervisor      │ High-availability watchdog auto-restarting daemons│
│ 7. Documentation   │ Guides for administrators, employees, and backup  │
└────────────────────┴───────────────────────────────────────────────────┘
```

---

## 13. Verification & Test Certification

The repository maintains an automated regression testing and validation framework:

- **Local Regression Test Suite:** **541 Passed, 0 Failed, 6 Skipped (100% Pass Rate)** in 109.97s across 27 test modules.
- **Database Integrity Check:** **100% Healthy** (Zero SQLite foreign key violations, synchronized FAISS index).
- **Dashboard Integrity:** **10/10 Pages Verified** operational without unhandled exceptions.
- **GitHub Actions Status:**
  - `Python CI`: 6/6 jobs passed on Python 3.11 & 3.12 (Lint, Types, Deps, Migration, Pytest).
  - `Linux Build CI`: Ubuntu 22.04 LTS system libraries, migrations, and container tests passed.
  - `Docker CI`: Production multi-stage image built, scanned with Trivy & Grype, and pushed to GHCR.
  - `Apple iOS Build CI`: Swift 5.9 Linux package build and macOS simulator launch passed.
- **Protected Windows Baseline:** Preserved at git tag `windows-baseline-v2.0` (commit `756e47a`).

---

## 14. Troubleshooting & Operational Guide

<details>
<summary><b>Click to expand common operational solutions</b></summary>
<br/>

| Problem | Root Cause | Solution |
| :--- | :--- | :--- |
| Camera fails to initialize on Windows | DirectShow device occupied or blocked | Verify index in `camera/selector.py`; confirm camera privacy settings allow access. |
| `faiss.swigfaiss_avx2` warning on startup | Host CPU lacks AVX2 extensions | Expected fallback; library initializes using standard instruction set. |
| 401 Unauthorized from API | Missing or expired JWT token | Request fresh token via `POST /auth/login` and attach `Authorization: Bearer <token>`. |
| Attendance record not appearing | Daily duplicate check-in suppressed | Check `attendance` table; records are idempotently logged once per calendar day. |
| Database migration mismatch | Alembic out of sync | Run `alembic upgrade head` to align schema with latest revision. |
</details>

---

## 15. Roadmap & Future Innovations

- [ ] Multi-tenant cloud synchronization for multi-campus institutional deployments.
- [ ] Active challenge-response liveness (randomized head-nod / blink prompts).
- [ ] Edge TPU and TensorRT acceleration for 60+ FPS multi-camera RTSP ingestion.
- [ ] Push notifications for the native iOS employee attendance client.

---

## 16. Asset Credits & License

- **License:** Proprietary institutional software. All rights reserved.
- **Visual Assets:** Custom synthesized vector illustrations and animations. See [ASSET_CREDITS.md](docs/ASSET_CREDITS.md) for full attribution.
- **Core Engineering:** Antigravity AI Systems & Reliability Engineering Team.

<br/>

<div align="center">
  <sub>Engineered for reliable, real-time institutional identity verification.</sub>
</div>
