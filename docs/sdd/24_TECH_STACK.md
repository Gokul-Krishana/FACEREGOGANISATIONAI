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
