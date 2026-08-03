# Section 17 — Deployment

## 17.1 Prerequisites

- **Python 3.10+** (3.11 recommended; Docker uses 3.11-slim).
- **pip**, optional **venv**.
- Windows: no extra system deps for webcam (DirectShow); OpenCV wheels
  include everything.
- Linux: `libgl1`, `libglib2.0-0` (or use Docker).
- PostgreSQL 16 (production), Redis 7 (optional, recommended).
- Models auto-download on first run: YOLO11n (~6 MB), InsightFace buffalo_l
  (~200 MB), MiniFASNet ONNX (~4 MB).

## 17.2 Development (Windows / Linux)

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head                # create schema
python scripts/seed_admin.py        # create admin + RBAC (first time)

# CLI mode
python main.py                      # live webcam
python main.py --debug              # diagnostics

# Dashboard
streamlit run dashboard/app.py      # http://localhost:8501

# API (optional)
uvicorn api.main:app --reload --port 8000   # http://localhost:8000/docs
```

**Verification:** `python tools/validate_startup.py`.

## 17.3 Production (Linux server)

| Step | Command / action |
|------|------------------|
| 1. System deps | `apt install -y libgl1 libglib2.0-0 libmagic1` |
| 2. Code + venv | clone repo, create venv, `pip install -r requirements.txt` |
| 3. Database | `DB_TYPE=postgres DATABASE_URL=postgresql://faceai:pass@localhost:5432/face_recognition` |
| 4. Migrations | `alembic upgrade head` |
| 5. Secrets | `export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")`; `ENVIRONMENT=production` |
| 6. Redis | install + `REDIS_URL=redis://localhost:6379/0` |
| 7. API service | systemd unit running `uvicorn api.main:app --host 0.0.0.0 --port 8000` (or gunicorn with uvicorn workers) |
| 8. Dashboard service | systemd unit running `streamlit run dashboard/app.py --server.port 8501` |
| 9. Reverse proxy (optional) | nginx/Caddy → TLS → HSTS (`ENABLE_HSTS=1`), trusted hosts configured |
| 10. Health checks | `/health`, `/health/ready`, `/health/live`; Prometheus `/metrics` |

**Production guardrails (fail-fast):**
- `ENVIRONMENT=production` + default/short `SECRET_KEY` → startup **raises**.
- API docs disabled in production.
- `TrustedHostMiddleware` — set explicit allowed hosts (dev uses `*`).

## 17.4 Docker Deployment

```bash
# Build image
docker build -t face-recognition-ai .

# Full stack (PostgreSQL + Redis + app)
docker-compose up -d

# GPU variant (if NVIDIA hardware)
docker run --gpus all -p 8000:8000 face-recognition-ai
```

`docker-compose.yml` provides `faceai-db` (postgres:16-alpine),
`faceai-redis` (redis:7-alpine), and the app service, with healthchecks and
localhost-only ports.

## 17.5 Deployment Checklist (see also §29.5)

1. ✅ Python/Docker installed, deps installed
2. ✅ DB migrated (`alembic upgrade head`), admin seeded
3. ✅ `SECRET_KEY` set (≥32 chars) in production
4. ✅ `ENVIRONMENT=production`
5. ✅ Redis reachable (or accept degraded mode)
6. ✅ Camera tested (`python main.py --debug` or dashboard Health page)
7. ✅ First enrollment done (Enroll page)
8. ✅ Backup configured (`scripts/backup.py` + cron)
9. ✅ Firewall: 8501/8000 only as needed; DB/Redis on 127.0.0.1
10. ✅ TLS + HSTS behind reverse proxy

## 17.6 Environment Matrix

| Concern | Development | Production |
|---------|-------------|------------|
| DB | SQLite (default) | PostgreSQL 16 |
| Redis | optional | recommended |
| Docs | `/docs` enabled | disabled |
| SECRET_KEY | default dev value | required, ≥32 chars |
| CORS | localhost:8501 | explicit origins |
| Trusted hosts | `*` | explicit list |
| HSTS | off | on after TLS |
| Logging | INFO console | JSON structured (python-json-logger available) |

## 17.7 Backup & Restore (ops)

- **Backup:** `python scripts/backup.py` — pg_dump + FAISS index + metadata
  + manifest (SHA-256 hashes) into `backups/backup_<ts>/`.
- **Restore:** `python scripts/restore.py --backup-dir backups/backup_<ts>`
  — verifies integrity → terminates connections → drop/recreate DB →
  restore SQL → restore FAISS artifacts. `--dry-run` to preview;
  `--no-db` to skip DB. **App must be stopped first** (DROP DATABASE needs
  no active connections).
- **Cron suggestion:** nightly backup + off-site copy
  (see `docs/BACKUP_RESTORE_GUIDE.md`).

---

*References: `Dockerfile`, `docker-compose.yml`, `run.sh`, `run.bat`,
`docs/DEPLOYMENT.md`, `docs/BACKUP_RESTORE_GUIDE.md`, `scripts/backup.py`,
`scripts/restore.py`, `tools/validate_startup.py`*
