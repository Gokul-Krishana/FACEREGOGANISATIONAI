# Administrator Guide — Face Recognition AI v2.1.0

**Production System Operations & Security Manual**  
**Platforms:** Windows 10/11, Linux (Ubuntu 22.04+), Docker, Apple iOS  
**Compliance Standards:** GDPR (Art. 9/17), BIPA, CCPA/CPRA, NIST SP 800-88  

---

## 1. Executive Overview & Architecture

Face Recognition AI v2.1.0 provides an enterprise-scale attendance management and biometric access system across Windows, Linux, and iOS clients.

```
                           +---------------------------+
                           |  Apple iOS Client (Swift) |
                           |  - Keychain Fail-Closed   |
                           +-------------+-------------+
                                         | REST / JWT
                                         v
+-----------------------+          +---------------------------+          +-----------------------+
| Windows Workstations  | -------> |  FastAPI Backend (8000)   | <------- | Linux Ubuntu / Docker |
| - DirectShow Cam (0)  |          |  - RBAC (7 Roles)         |          | - Systemd Services    |
| - Streamlit Dashboard |          |  - Brute-Force Lockout    |          | - Gunicorn / Uvicorn  |
+-----------------------+          |  - Rate Limiting (SlowAPI)|          +-----------------------+
                                   +-------------+-------------+
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
                       v                                                   v
          +-------------------------+                         +-------------------------+
          | Database Storage        |                         | Biometric & Vector Data |
          | - SQLite (WAL Mode)     |                         | - FAISS HNSW / Flat L2  |
          | - PostgreSQL Enterprise |                         | - AES-256-GCM Encrypted |
          +-------------------------+                         +-------------------------+
```

---

## 2. Platform Installation & Startup Procedures

### 2.1. Windows Deployment (DirectShow / USB Cameras)
1. **Prerequisites**: Python 3.10-3.12, Visual C++ Redistributable 2015-2022.
2. **Environment Setup**:
   ```powershell
   git clone https://github.com/Gokul-Krishana/FACEREGOGANISATIONAI.git
   cd FACEREGOGANISATIONAI
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **Run Services**:
   ```powershell
   # Start Backend API
   uvicorn api.main:app --host 127.0.0.1 --port 8000

   # Start Dashboard
   streamlit run dashboard/app.py --server.port 8501
   ```
4. **Camera Verification**: Windows DirectShow (`cv2.CAP_DSHOW`) is automatically preferred for low-latency, freeze-free camera streams.

### 2.2. Linux Deployment (Ubuntu 22.04 LTS / Systemd)
1. **Prerequisites**: Python 3.11/3.12, libgl1, libglib2.0-0.
2. **Systemd Service Setup**:
   Copy deployment unit files from `deployment/linux/` to `/etc/systemd/system/`:
   ```bash
   sudo cp deployment/linux/faceai-api.service /etc/systemd/system/
   sudo cp deployment/linux/faceai-dashboard.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now faceai-api faceai-dashboard
   ```
3. **Docker Compose Deployment**:
   ```bash
   docker compose -f deployment/docker-compose.yml up -d
   ```

### 2.3. iOS Client Configuration
- **Xcode Build**: Open `ios/FaceRecognitionAttendance` in Xcode 16+.
- **Fail-Closed Security**: Physical devices strictly require Apple Security Keychain persistence for JWT tokens (`#if os(iOS) && !targetEnvironment(simulator)`). If Keychain entitlements or lock state fail, the app immediately fails closed.
- **Backend URL**: Configure `APIConfig.baseURL` to point to the secure HTTPS API endpoint.

---

## 3. Security & Access Control (RBAC)

The system enforces 7 distinct RBAC roles:
1. `SUPER_ADMIN`: Full system control, database migration, key rotation, and audit review.
2. `COLLEGE_ADMIN`: Departmental enrollment, camera administration, and report exports.
3. `HOD`: Departmental attendance approvals and timetable schedules.
4. `FACULTY`: Course section attendance verification and manual adjustments.
5. `SECURITY`: Real-time camera feeds, spoof alerts, and unknown face triage.
6. `STAFF`: Non-academic employee self-service.
7. `STUDENT`: Attendance self-verification.

### 3.1. Brute-Force & Lockout Policy
- **Threshold**: 5 consecutive failed login attempts within 30 minutes triggers temporary account lockout.
- **Duration**: 30-minute lockout cooldown.
- **Unlocking**: Super administrators can manually clear lockouts via `BruteForceProtection.clear_lockout(username)`.

---

## 4. Biometric Privacy, GDPR & Consent Management

Face Recognition AI v2.1.0 is engineered for strict privacy compliance (GDPR Art. 9/17, BIPA, CCPA/CPRA):

1. **Biometric Encryption at Rest**:
   All 512-D ArcFace vectors and exported biometric profiles are protected with authenticated AES-256-GCM / Fernet encryption via `utils/biometric_crypto.py`.
2. **Consent Tracking**:
   Each employee and student record tracks `consent_given` (Boolean) and `consent_date`. If consent is withdrawn (`consent_given = False`), the camera pipeline automatically suppresses recognition and attendance logging for that subject.
3. **NIST SP 800-88 Cryptographic Shredding**:
   When an employee requests biometric deletion, the system performs a multi-pass overwrite (random noise -> alternate bits -> zeros) before unlinking photo files from disk, purges FAISS index embeddings, and writes an auditable destruction log.
4. **Automated Data Retention Purge**:
   Run scheduled retention cleanup:
   ```bash
   python -c "from services.data_retention_service import DataRetentionService; DataRetentionService.run_retention_purge(unknown_days=30, audit_days=365)"
   ```

---

## 5. Automated Backup & Disaster Recovery

The unified backup tool automatically snapshots both SQLite and PostgreSQL databases alongside FAISS indexes and metadata:

### 5.1. Creating a Snapshot
```bash
python scripts/backup.py
```
Outputs:
- Database snapshot (`database.sqlite` or `dump.sql`)
- Vector index (`faiss.index`)
- Identity mapping (`metadata.json`)
- Cryptographic SHA-256 manifest (`manifest.json`)

### 5.2. Restoring a Snapshot
```bash
# Verify integrity without applying
python scripts/restore.py --backup-dir backup_20261123_200628 --dry-run

# Restore system state
python scripts/restore.py --backup-dir backup_20261123_200628
```

---

## 6. Service Watchdog & High Availability

Deploy the watchdog daemon to continuously supervise FastAPI and Streamlit services:
```bash
# Check health once
python scripts/service_watchdog.py --check-once

# Run continuous supervisor with auto-restart
python scripts/service_watchdog.py --interval 15 --auto-restart
```

Logs are recorded in `logs/watchdog.log`.

