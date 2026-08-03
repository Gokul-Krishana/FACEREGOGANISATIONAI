# Backup & Restore Guide — Face Recognition AI

**Version:** 2.0.0
**Date:** 2026-08-02

---

## 1. Why Backups Matter Here

This system stores two kinds of data that are expensive to recreate:

1. **The database** — employees, students, attendance records, audit logs, users.
2. **The FAISS face embeddings** — every enrolled person's face fingerprint.
   If these are lost, every person must be **re-enrolled** in person.

Backups must always capture **both**, plus the configuration.

---

## 2. What to Back Up

| # | Artifact | Path | Required |
|:--|:---------|:-----|:---------|
| 1 | Database (PostgreSQL) | SQL dump via `pg_dump` | ✅ |
| 2 | FAISS index | `embeddings/faiss.index` | ✅ |
| 3 | Embedding metadata | `embeddings/metadata.json` | ✅ (must match #2) |
| 4 | Unknown face images | `unknown_faces/` | Optional (operational) |
| 5 | Configuration | `config/settings.yaml`, `.env` | ✅ |
| 6 | Uploaded photos | `uploads/` | Optional |

> **SQLite (development) note:** if running SQLite, back up the file
> `data/face_recognition.db` (use the SQLite backup API, not a live file copy).

---

## 3. Automated Backup (Recommended)

The repo ships `scripts/backup.py` which captures the **database + FAISS +
metadata** into a timestamped folder with a `manifest.json` (including SHA-256
hashes for integrity verification):

```bash
# Default: PostgreSQL at localhost:5432, output to backups/
python scripts/backup.py

# Custom output directory
python scripts/backup.py --output /backups/faceai

# Custom database
python scripts/backup.py --url postgresql://faceai:pass@db:5432/face_recognition
```

**Result:**
```
backups/backup_20260802_101530/
├── face_recognition.sql     # pg_dump output
├── faiss.index              # FAISS vectors
├── metadata.json            # embedding metadata
└── manifest.json            # hashes + metadata + redacted URL
```

### 3.1 Schedule with cron (Linux) or Task Scheduler (Windows)

```bash
# Daily at 02:30
30 2 * * * cd /opt/face-recognition-ai && python scripts/backup.py >> logs/backup.log 2>&1

# Keep last 30 backups, delete older
find /backups/faceai -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

### 3.2 Manual backup (no script / quick copy)

```bash
# Database
pg_dump -U faceai face_recognition > backup_$(date +%Y%m%d).sql

# FAISS + metadata
cp embeddings/faiss.index  embeddings/backup_$(date +%Y%m%d).index
cp embeddings/metadata.json embeddings/backup_$(date +%Y%m%d).json
```

---

## 4. Restore

### 4.1 Using the restore script

```bash
python scripts/restore.py --backup-dir backups/backup_20260802_101530 \
    --url postgresql://faceai:pass@localhost:5432/face_recognition
```

The script verifies the manifest hashes, restores the SQL dump, and copies the
FAISS index + metadata back into place.

### 4.2 Manual restore

```bash
# 1. Restore database (target DB must be empty or you accept overwrite)
psql -U faceai face_recognition < backup_20260802.sql

# 2. Restore FAISS index + metadata (STOP the dashboard/API first so the index
#    is not held open)
cp backup_20260802/faiss.index   embeddings/faiss.index
cp backup_20260802/metadata.json embeddings/metadata.json

# 3. Restart services
docker compose restart api dashboard
# or
streamlit run dashboard/app.py
```

> ⚠️ **Never overwrite `faiss.index` while a live recognition pipeline is
> running** — the in-memory index must be reloaded. Restart the app after
> restoring.

---

## 5. Restore Drill (Quarterly)

1. Copy a backup folder to a **test machine** (never the live system).
2. `docker compose up -d db`
3. Restore the SQL dump.
4. Copy FAISS files + restart.
5. Verify: `python tools/validate_startup.py` (FAISS check shows the expected
   embedding count) and spot-check an employee's attendance history.

---

## 6. Integrity Checks

- `scripts/backup.py` records SHA-256 for every artifact in `manifest.json`.
- Verify a backup:
  ```bash
  sha256sum -c <(grep sha256 backups/backup_*/manifest.json | sed 's/.*"sha256": "//;s/".*//')
  ```
- The **🩺 System Health** page shows whether FAISS metadata count matches the
  index count — a mismatch after restore means the two files came from
  different points in time.

---

## 7. Disaster Scenarios

| Scenario | Recovery |
|:---------|:---------|
| Database lost, FAISS intact | Restore DB dump; FAISS metadata names must match employee names — verify with Health page |
| FAISS lost, DB intact | Re-enroll all people (bulk: `scripts/bulk_enroll.py` from `dataset/students/`) |
| Both lost | Full restore from latest backup; if none, manual re-enrollment of every person |
| Restore to new server | Fresh install → `alembic upgrade head` → restore DB → copy FAISS → seed admin |

---

## 8. Encryption & Off-Site Copy

- Encrypt backups at rest (e.g. `age`/`gpg` or encrypted volume) — they contain
  **biometric data**.
- Copy to a second location (cloud bucket, external drive) daily.
- Store at least one backup **off-premises**.
- Biometric data handling must comply with your institution's data-protection
  policy (e.g. GDPR/DPDP considerations: keep retention bounded, restrict
  access).

---

## 9. Related

- `scripts/backup.py`, `scripts/restore.py` — automation
- `docs/DEPLOYMENT.md` — production setup
- `docs/SECURITY_REPORT.md` — data protection posture
- `docs/ADMIN_MANUAL.md` §6 — quick reference
