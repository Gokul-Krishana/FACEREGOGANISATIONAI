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
