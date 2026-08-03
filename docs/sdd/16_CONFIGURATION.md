# Section 16 — Configuration

## 16.1 Configuration Layers

The system is configured through **three layers** (later wins):

1. `config/settings.yaml` — user-editable, human-readable settings.
2. `config/config.py` — Python constants with fallback defaults.
3. Environment variables — for API/DB/Redis/OIDC/security (Docker-friendly).

## 16.2 `config/settings.yaml` (full reference, verified)

```yaml
camera:
  source_type: webcam        # webcam | android_usb | android_wifi | iphone_usb | iphone_wifi
  id: 0                      # device index
  url: "http://192.168.1.100:8080/video"
  width: 480
  height: 360
  fps: 15
  auto_connect: false

recognition:
  yolo_confidence: 0.60
  recognition_threshold: 1.0    # FAISS L2 distance (1.0-1.5 same person range)
  frame_skip: 2                 # process every Nth frame
  cooldown_seconds: 60          # re-mark window
  identity_ttl: 3.0             # verified-track revalidation seconds

database:
  type: sqlite                  # sqlite | postgresql
  path: data/face_recognition.db

enrollment:
  min_face_size: 100
  capture_count: 1

faiss:
  index_type: hnsw              # flat | hnsw | ivf
  hnsw: { M: 32, ef_construction: 200, ef_search: 128 }
  ivf:  { nlist: 200, nprobe: 256 }

amfr:
  face_quality_min_score: 0.35
  liveness_min_score: 0.30
  liveness_spoof_threshold: 0.15
  high_confidence_threshold: 0.70
  borderline_threshold: 0.40
  weight_arcface: 0.45
  weight_liveness: 0.35
  weight_quality: 0.20

deep_liveness:
  enabled: true
  threshold: 0.50
  use_fallback: true
  auto_download: true

unknown_faces:
  retention_days: 30            # 0 = never delete

logging:
  level: INFO
  file: logs/app.log
  max_size_mb: 10
  backup_count: 3
```

> **Note:** `recognition_threshold` defaults to **1.0** in the current
> settings.yaml (README's table mentions 1.2 in an older revision; the
> shipped YAML is authoritative).

## 16.3 `config/config.py` Behavior

- Loads YAML at import; missing keys fall back to Python defaults
  (`_get(*keys, default=...)`).
- Exposes typed module constants used everywhere:
  - Paths: `MODELS_DIR`, `EMBEDDINGS_DIR`, `ATTENDANCE_DIR`, `LOGS_DIR`,
    `OUTPUTS_DIR`, `UNKNOWN_FACES_DIR`, `DATASET_DIR`.
  - Models: `YOLO_MODEL_PATH`, `INSIGHTFACE_MODEL=buffalo_l`,
    `EMBEDDING_DIM=512`.
  - Detection: `YOLO_CONFIDENCE`, `RECOGNITION_THRESHOLD`, `FRAME_SKIP`,
    `COOLDOWN_SECONDS`, `IDENTITY_TTL`.
  - Camera: `CAMERA_ID`, `CAMERA_SOURCE_TYPE`, `CAMERA_URL`, `CAMERA_AUTO_CONNECT`.
  - AMFR: `FACE_QUALITY_MIN_SCORE`, `LIVENESS_MIN_SCORE`,
    `LIVENESS_SPOOF_THRESHOLD`, `AMFR_HIGH_CONFIDENCE_THRESHOLD`,
    `AMFR_BORDERLINE_THRESHOLD`, weights.
  - Deep liveness: `DEEP_LIVENESS_*`.
  - FAISS: `FAISS_INDEX_TYPE`, `FAISS_HNSW_*`, `FAISS_IVF_*`.
  - `UNKNOWN_FACE_RETENTION_DAYS`.
- **`save_settings(updates)`** — writes back to YAML using **ruamel.yaml
  round-trip** so comments survive; reloads in-memory dict.
- Creates required directories at import.
- Configures logging: console + `RotatingFileHandler` (10 MB × 3 backups).

## 16.4 Environment Variables (API & infra)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_TYPE` | `sqlite` | sqlite \| postgres |
| `DATABASE_URL` | — | PostgreSQL URL (required if postgres) |
| `SECRET_KEY` | dev placeholder | JWT signing; ≥32 chars enforced in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 30 | refresh token lifetime |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CORS_ORIGINS` | `http://localhost:8501` | comma-separated allowed origins |
| `ENVIRONMENT` | `development` | production disables docs + validates secret |
| `LOG_LEVEL` | INFO | logging level |
| `MAX_UPLOAD_SIZE_MB` | 5 | enrollment upload cap |
| `MAX_BODY_SIZE_BYTES` | 10 MB | request body cap |
| `MAX_FAILED_LOGIN_ATTEMPTS` | 5 | brute-force lockout |
| `LOCKOUT_DURATION_MINUTES` | 30 | lockout window |
| `PASSWORD_MIN_LENGTH` / `PASSWORD_REQUIRE_*` | 12 / true | password policy |
| `LOGIN_RATE_LIMIT` / `API_RATE_LIMIT` / `ENROLL_RATE_LIMIT` | 10/100/5 per minute | rate limits |
| `ENABLE_HSTS` | `0` | HSTS header toggle |
| `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_SCOPES`, `OIDC_REDIRECT_URI` | — | SSO |
| `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | admin / admin@college.edu / AutoR!0t!ze*9! | seed script |

## 16.5 Docker Configuration

### `Dockerfile` (multi-stage)
- `python:3.11-slim` base; installs system deps (OpenCV runtime libs
  libgl1/libglib2.0, libmagic), Python deps.
- `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `PIP_NO_CACHE_DIR=1`.
- GPU-capable (`docker run --gpus all`); healthcheck + verify step runs
  critical module imports after build.

### `docker-compose.yml` (3 services)

| Service | Image | Notes |
|---------|-------|-------|
| `faceai-db` | `postgres:16-alpine` | env `POSTGRES_USER/PASSWORD/DB` (defaults faceai/changeme/face_recognition), bound 127.0.0.1:5432, pg_isready healthcheck |
| `faceai-redis` | `redis:7-alpine` | `--requirepass` only when `REDIS_PASSWORD` set (avoids empty-flag crash), bound 127.0.0.1:6379, redis-cli ping healthcheck |
| app | built from Dockerfile | depends on healthy db + redis |

Volumes: `postgres_data`, `redis_data`.

> **Security note:** ports bound to **127.0.0.1 only** — not publicly
> accessible.

## 16.6 `alembic.ini`

Standard Alembic config; `database.py` points at `ROOT_DIR/alembic.ini`
for `run_migrations()`.

---

*References: `config/settings.yaml`, `config/config.py`, `api/main.py`
(Settings model), `Dockerfile`, `docker-compose.yml`, `alembic.ini`,
`docs/DEPLOYMENT.md`*
