# Administrator Manual — Face Recognition AI

**Version:** 2.0.0
**Date:** 2026-08-02
**Audience:** System administrators / IT staff operating the system in a college
environment.

---

## 1. Role of the Administrator

The administrator is responsible for:

- Installing, configuring, and updating the system
- Managing the **Employee/Student database** and **FAISS face embeddings**
- Managing **cameras**
- Monitoring system **health** (CPU, RAM, GPU, database, Redis, cameras)
- Handling **unknown faces** and **spoof alerts**
- Performing **backups** and **restores**
- Managing **user accounts** (API/admin users, RBAC roles, MFA)

---

## 2. System Architecture (Administrator View)

```
Cameras (Webcam / USB / Android / iPhone / IP-RTSP)
    │
    ▼
Streamlit Dashboard (port 8501)          FastAPI Backend (port 8000)
    │  operator UI                          │  REST API + auth + jobs
    ▼                                       ▼
        ┌───────────────┴──────────────┐
        ▼                              ▼
   PostgreSQL (5432)              Redis (6379, optional)
   source of truth                cache / cooldowns
        │
        ▼
   FAISS index (embeddings/faiss.index) — face vectors
   Filesystem — unknown_faces/, uploads/, logs/
```

**Three components must be running:**

| Component | Command |
|:----------|:--------|
| Dashboard | `streamlit run dashboard/app.py` (or Docker `dashboard` service) |
| API | `uvicorn api.main:app --host 0.0.0.0 --port 8000` (Docker `api`) |
| Database | PostgreSQL (Docker `db`) or SQLite (dev, auto-created) |

---

## 3. First-Time Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify everything is healthy
python tools/validate_startup.py

# 3. Run database migrations
alembic upgrade head

# 4. Seed the admin user + RBAC roles
python scripts/seed_admin.py

# 5. Start the API (recommended order: db → redis → api → dashboard)
uvicorn api.main:app --host 0.0.0.0 --port 8000 &

# 6. Start the dashboard
streamlit run dashboard/app.py
```

Open http://localhost:8501.

> ⚠️ **Production checklist:** set `SECRET_KEY` (64+ random chars),
> `ENVIRONMENT=production`, strong PostgreSQL password, Redis password, HTTPS
> reverse proxy. See `docs/DEPLOYMENT.md`.

---

## 4. Day-to-Day Operations

### 4.1 Managing Employees (People Who Can Be Recognised)

Use the **👥 Employees** page:

| Action | Where | Notes |
|:-------|:------|:------|
| Create | Employees → Add | Enter unique employee ID + name |
| Edit | Employees → edit | Renaming updates the FAISS label so recognition keeps working |
| Delete | Employees → delete | **Removes DB row AND FAISS embedding** — person can no longer be recognised |
| Re-enroll | Enroll page | Capture a new face → new embedding replaces old |

**Enrollment workflow (📸 Enroll page):** select camera → allow browser camera
permission → click "Capture" → the face is detected, an ArcFace 512-D embedding
is extracted, added to FAISS, and an employee record is created/updated.

### 4.2 Managing Cameras

Live Recognition page → camera selector:
- **PC Camera / USB** — auto-detected, pick from list
- **Android (Wi-Fi)** — IP Webcam URL (`http://<phone-ip>:8080/video`)
- **iPhone (Wi-Fi)** — EpocCam
- **IP / RTSP** — `rtsp://user:pass@host:554/stream1`

Use **Scan Cameras** to auto-discover local + network cameras.

**Camera health** is shown on the Live page and the **🩺 System Health** page:
status, FPS, latency, last seen, recognition count.

> Credentials for RTSP cameras are stored as a **credential reference**, never
> as plaintext in the database.

### 4.3 Monitoring Health

The **🩺 System Health** page shows live checks:

| Check | What it verifies |
|:------|:-----------------|
| Database | Connectivity (SQLite/PostgreSQL) |
| Redis | Optional — falls back to in-memory if unavailable |
| YOLO11 | Person-detection model loads |
| InsightFace | RetinaFace + ArcFace models |
| FAISS | Index loads; metadata count matches index count |
| Disk | Storage usage |
| Cameras | Per-camera status |

Quick-fix buttons: restart camera pipeline, rebuild FAISS, clear caches.

### 4.4 Unknown Faces & Spoof Alerts

- **🔴 Unknown Faces** page — gallery of people the system couldn't identify.
- Actions: **review**, **convert to employee** (captures their face as a new
  enrollment), **delete** (single or bulk).
- **Retention policy:** unknown faces auto-delete after
  `unknown_faces.retention_days` (default 30; `0` disables).
- **Spoof attempts** are logged to the audit trail with the liveness score
  (`SPOOF_ATTEMPT` events). Check the API audit logs or database `audit_logs`
  table.

### 4.5 Attendance Management

Attendance is **automatic** — AMFR ACCEPT marks it (green box + PRESENT).
Duplicate marking is prevented three ways: session cache, cooldown
(`cooldown_seconds`, default 60 s), and a DB "already marked today" check.

**Manual marking** is available via the API: `POST /attendance`.

---

## 5. User & Access Management (API)

### 5.1 RBAC Roles

| Role | Capabilities |
|:-----|:-------------|
| `SUPER_ADMIN` | Everything |
| `COLLEGE_ADMIN` | Broad management (students, employees, cameras, attendance, users) |
| `HOD` | Department-level management |
| `FACULTY` | Mark/view attendance |
| `SECURITY` | View cameras + unknown faces |
| `STUDENT` | View own attendance |
| `STAFF` | Basic attendance access |

### 5.2 Seed / Reset Admin

```bash
python scripts/seed_admin.py              # idempotent
ADMIN_USERNAME=admin ADMIN_PASSWORD='...' python scripts/seed_admin.py
```

### 5.3 MFA & OIDC

- **MFA:** enabled per-user via `POST /auth/mfa/enroll` (TOTP — Google
  Authenticator compatible) then `POST /auth/mfa/verify`.
- **OIDC:** configure via `POST /auth/oidc/login`; supports Azure AD /
  Keycloak / Google via `oidc_provider`.

---

## 6. Backup & Restore

> ⚠️ This is the single most important routine. See
> `docs/BACKUP_RESTORE_GUIDE.md` for the full guide.

**Quick reference:**

```bash
# Automated full backup (PostgreSQL + FAISS + metadata)
python scripts/backup.py

# Restore
python scripts/restore.py --backup-dir backups/backup_YYYYMMDD_HHMMSS --url <postgres-url>
```

**What must be backed up:**
1. Database (SQL dump)
2. `embeddings/faiss.index` + `embeddings/metadata.json` (faces!)
3. `unknown_faces/` (optional, operational)
4. `config/settings.yaml` (configuration)

---

## 7. Troubleshooting (Administrator Quick Reference)

| Symptom | Likely cause | Fix |
|:--------|:-------------|:----|
| Live page stuck "CONNECTING" | Camera in use / disconnected | Click STOP → START; check camera on another app |
| "No face detected" | Camera blocked / dark room | Allow browser camera permission; improve lighting |
| Recognition threshold too strict/loose | FAISS L2 threshold | Settings page → `recognition_threshold` (1.0–1.5 typical) |
| Attendance not marked | Cooldown (60 s) or already marked | Wait; check "Today's Attendance" table |
| Duplicate employee names | Legacy data | `python scripts/dedupe_employees.py` (dry-run first) |
| YOLO slow / CPU inference | No CUDA torch | Install CUDA torch (`pip install --index-url https://download.pytorch.org/whl/cu128 torch torchvision`); verify with `python -c "import torch; print(torch.cuda.is_available())"` |
| Torch import fails on Windows (`fbgemm.dll`) | torch 2.4.0 bug | Upgrade: `pip install "torch>=2.5,!=2.4.0"` |
| Redis connection refused | Redis down | Optional — system runs on in-memory fallback; start Redis to restore caching |
| FAISS metadata mismatch | Desync after manual edits | Health page → Rebuild FAISS; or `scripts/migrate_faiss_hnsw.py` |
| Unknown faces flooding disk | Low recognition threshold / many visitors | Raise threshold; enable retention policy |

See also `docs/TROUBLESHOOTING.md`.

---

## 8. Maintenance Routines

### Daily
- Check System Health page (DB, Redis, models, cameras, disk)
- Review Unknown Faces page; convert/delete as policy dictates
- Spot-check Today's Attendance for anomalies

### Weekly
- Review audit log for spoof attempts / failed logins
- Verify backups ran (`backups/` directory)
- Check disk usage and log rotation (`logs/app.log` max 10 MB × 3)

### Monthly
- Rotate `SECRET_KEY` and admin passwords
- Run `python tools/validate_startup.py`
- Run `python -m pytest tests/ -q` to confirm the suite is green
- Verify FAISS ↔ database consistency (Health page shows counts)

### Quarterly
- Full restore drill from a recent backup
- Capacity review: FAISS size, attendance volume, camera count
- Review retention policy and audit retention

---

## 9. Upgrading the System

```bash
git pull
pip install -r requirements.txt
alembic upgrade head          # apply new migrations
python tools/validate_startup.py
python -m pytest tests/ -q    # regression check
```

Backup **before** upgrading. FAISS index format is forward-compatible within
the same major version; if the index type changes (flat→hnsw), use
`scripts/migrate_faiss_hnsw.py`.

---

## 10. Contact & Escalation

- **Logs:** `logs/app.log` (rotating, INFO level by default; set `logging.level: DEBUG` in `config/settings.yaml` for troubleshooting).
- **API logs:** Docker `docker compose logs -f api`.
- **Metrics:** `GET /metrics` (Prometheus format) for external monitoring.
