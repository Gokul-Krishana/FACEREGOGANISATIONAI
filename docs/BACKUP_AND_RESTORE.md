# Backup & Disaster Recovery Guide — Face Recognition AI v2.1.0

**Operational Manual for Disaster Recovery & High-Availability Backups**  
**Supported Databases:** SQLite (Atomic WAL snapshot) & PostgreSQL (`pg_dump`)  
**Artifacts Protected:** Relational Database, FAISS Vector Index, Metadata JSON, System Manifest  

---

## 1. Overview of System State

A complete Face Recognition AI backup snapshot consists of three synchronized components:

1. **Relational Database**: Employee records, course enrollments, attendance timestamps, audit trails, camera configurations, and user credentials.
2. **FAISS Vector Index (`embeddings/faiss.index`)**: Mathematical vector space containing high-dimensional facial embeddings.
3. **Identity Metadata (`embeddings/metadata.json`)**: ID-to-name mapping between the FAISS index and the database primary keys.
4. **Cryptographic Manifest (`manifest.json`)**: Contains SHA-256 hashes, creation timestamps, and database configuration metadata.

---

## 2. Automated Backup Execution

The backup utility auto-detects whether your deployment uses SQLite or PostgreSQL:

### 2.1. Standard Snapshot Command
```bash
python scripts/backup.py
```

### 2.2. Custom Destination Directory
```bash
python scripts/backup.py --output /var/backups/faceai
```

### 2.3. SQLite Technical Mechanics
When running against SQLite (`data/face_recognition.db`), the backup tool:
1. Forces a WAL checkpoint (`PRAGMA wal_checkpoint(TRUNCATE);`) to flush pending transactions.
2. Uses the native `sqlite3.backup` API to create an atomic, non-blocking snapshot page-by-page.
3. Stores the snapshot in `backups/backup_YYYYMMDD_HHMMSS/database.sqlite`.

### 2.4. PostgreSQL Technical Mechanics
When running against PostgreSQL (`postgresql://...`), the backup tool:
1. Connects to the server to verify credentials and accessibility.
2. Invokes `pg_dump` with `--no-owner` and `--no-privileges` to produce a portable SQL dump.
3. Masks all database passwords in the generated manifest.

---

## 3. Disaster Recovery & Restoration

### 3.1. Dry-Run Verification (Recommended First Step)
Always verify the integrity of the backup before applying it:
```bash
python scripts/restore.py --backup-dir backup_20261123_200628 --dry-run
```
This validates:
- SHA-256 hash matching of the database dump
- SHA-256 hash matching of `faiss.index`
- SHA-256 hash matching of `metadata.json`

### 3.2. Restoring SQLite
```bash
python scripts/restore.py --backup-dir backup_20261123_200628
```
The script creates a pre-restore backup (`face_recognition.db.pre_restore`), copies the snapshot into place, executes `PRAGMA integrity_check;`, and restores the FAISS index files.

### 3.3. Restoring PostgreSQL
```bash
python scripts/restore.py --backup-dir backup_20261123_200628 --url postgresql://faceai:secret@localhost:5432/face_recognition
```
The script terminates active database connections, drops the old database, creates a fresh database, and streams the SQL dump through `psql`.

---

## 4. Database Integrity Verification

Run the database integrity check at any time to verify system health:
```bash
python scripts/verify_database_integrity.py
```

Optional cleanup of orphaned foreign keys:
```bash
python scripts/verify_database_integrity.py --fix-orphans
```

Outputs:
- SQLite low-level corruption check (`PRAGMA integrity_check`)
- Foreign key relationship check (`PRAGMA foreign_key_check`)
- Table record count verification
- FAISS vector count vs metadata length synchronization

