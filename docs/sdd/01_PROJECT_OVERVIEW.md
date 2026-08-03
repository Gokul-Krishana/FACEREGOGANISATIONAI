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
