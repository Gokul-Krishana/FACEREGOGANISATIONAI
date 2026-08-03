# Section 3 — Complete Folder Structure

## 3.1 Full Repository Tree (verified from source)

```
FaceRecognitionAI/
│
├── main.py                     # CLI entry point (live / image / enroll / test / debug)
├── requirements.txt            # Python dependencies
├── pytest.ini                  # pytest configuration
├── alembic.ini                 # Alembic migration config
├── Dockerfile                  # Multi-stage container build
├── docker-compose.yml          # App + PostgreSQL + Redis orchestration
├── run.bat / run.sh            # Convenience launchers
├── clear_cache.py              # Cache-clearing utility
├── README.md                   # Project readme
├── LICENSE                     # MIT license
│
├── app/                        # ⭐ Core AI pipeline (see 3.1.1)
│   ├── amfr_engine.py          #   AMFR decision engine
│   ├── face_detector.py        #   YOLO11 person detection
│   ├── face_quality.py         #   Face quality assessment
│   ├── liveness_detector.py    #   4 software liveness factors
│   ├── deep_liveness.py        #   MiniFASNet CNN anti-spoofing
│   ├── recognizer.py           #   RetinaFace + ArcFace
│   ├── enrollment.py           #   FAISS index management
│   ├── tracking.py             #   IoU multi-object tracker
│   ├── attendance.py           #   CSV attendance logging
│   └── live_detection.py       #   CLI pipeline orchestrator
│
├── recognition/                # Face alignment utilities
│   └── alignment.py            #   Landmark-based face alignment + CLAHE
│
├── camera/                     # Camera abstraction layer (see 3.1.2)
│   ├── base.py                 #   CameraSource ABC
│   ├── webcam.py               #   Webcam + USB auto-detect
│   ├── phone.py                #   Android/iPhone + IP cameras
│   ├── selector.py             #   Factory + CLI/Streamlit selectors
│   ├── discovery.py            #   Network camera discovery
│   └── fake.py                 #   Synthetic camera for testing
│
├── dashboard/                  # Streamlit UI (see 3.1.3)
│   ├── app.py                  #   Entry point + sidebar nav
│   ├── frame_buffer.py         #   Thread-safe latest-frame buffer
│   ├── camera_owner.py         #   Singleton camera ownership
│   ├── latency_logger.py       #   E2E latency statistics
│   └── pages/
│       ├── 01_Dashboard.py     #   Overview + stats
│       ├── 02_Employees.py     #   Employee CRUD
│       ├── 03_Enroll.py        #   Face enrollment
│       ├── 04_Live.py          #   Live recognition pipeline
│       ├── 05_Attendance.py    #   Attendance records + live camera
│       ├── 06_Unknown.py       #   Unknown face gallery
│       ├── 07_Analytics.py     #   Plotly charts
│       ├── 08_Settings.py      #   Config editor
│       ├── 09_Health.py        #   System health
│       └── 10_About.py         #   About & stack
│
├── services/                   # Business logic layer (see 3.1.4)
│   ├── recognition_service.py  #   Pipeline orchestrator (dashboard/API entry)
│   ├── attendance_service.py   #   Attendance marking + queries
│   ├── employee_service.py     #   Employee CRUD + FAISS sync
│   ├── unknown_face_service.py #   Unknown face lifecycle
│   ├── audit_service.py        #   Audit trail
│   ├── brute_force_protection.py
│   ├── mfa_service.py          #   TOTP MFA
│   └── oidc_service.py         #   SSO integration
│
├── api/                        # FastAPI REST layer (see 3.1.5)
│   ├── main.py                 #   App + all endpoints
│   ├── attendance_service.py   #   Timetable-aware attendance
│   ├── audit_service.py        #   API audit logging
│   ├── bulk_operations.py      #   CSV imports/exports
│   ├── job_queue.py            #   Async background jobs
│   ├── redis_client.py         #   Redis state helpers
│   └── websocket_manager.py    #   Real-time event stream
│
├── database/                   # ORM + repository (see 3.1.6)
│   ├── database.py             #   Engine, session, init_db
│   ├── models.py               #   All ORM models
│   └── repository.py           #   Repository pattern CRUD
│
├── config/                     # Configuration
│   ├── config.py               #   Central config (YAML + defaults + logging)
│   └── settings.yaml           #   User-editable settings
│
├── utils/                      # Utilities
│   ├── image.py                #   Image I/O helpers
│   └── upload_security.py      #   Upload validation (magic bytes)
│
├── scripts/                    # Admin & benchmark scripts (see 3.1.7)
│   ├── seed_admin.py           #   First admin + RBAC bootstrap
│   ├── backup.py               #   PostgreSQL + FAISS backup
│   ├── restore.py              #   Restore from backup
│   ├── bulk_enroll.py          #   Bulk face enrollment
│   ├── dedupe_employees.py     #   Duplicate cleanup
│   ├── migrate_faiss_hnsw.py   #   FAISS index migration
│   └── benchmarks/             #   Performance/validation scripts
│       ├── faiss_benchmark.py      #   FAISS speed tests
│       ├── tune_hnsw.py            #   HNSW parameter tuning
│       ├── tune_ivf.py             #   IVF parameter tuning
│       ├── benchmark_real_embeddings.py
│       ├── camera_validation.py    #   Camera latency/FPS
│       ├── fake_camera_validation.py
│       ├── scalability_benchmark.py
│       ├── profile_pipeline.py     #   Per-stage profiling
│       ├── probe_environment.py
│       └── validate_amfr.py        #   AMFR decision validation
│
├── alembic/                    # Schema migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 1bf6aa4e001c_initial_schema.py
│       ├── 2a7c9e4f1b3d_add_failed_login_attempts_table.py
│       └── 9c4d2f6a7b11_add_scalability_indexes.py
│
├── tests/                      # 20 pytest modules (see 3.1.8)
│
├── tools/                      # Diagnostics
│   ├── validate_startup.py     #   Startup health check
│   └── diagnose_cameras.py     #   Camera troubleshooting
│
├── models/                     # AI model weights
│   ├── yolo11n.pt              #   YOLO person detector
│   ├── .insightface/           #   InsightFace buffalo_l pack
│   └── liveness/               #   MiniFASNet ONNX model
│
├── embeddings/                 # FAISS vector database
│   ├── faiss.index
│   └── metadata.json
│
├── attendance/                 # Per-day CSV attendance logs
├── unknown_faces/              # Unknown face snapshots
├── uploads/                    # Enrollment image uploads (API)
├── outputs/                    # CLI processed images
├── dataset/                    # Test images
├── logs/                       # Rotating application logs
├── data/                       # SQLite database (dev)
├── backups/                    # Backup snapshots
│
└── docs/                       # Existing documentation
    ├── ARCHITECTURE.md, DEPLOYMENT.md, TROUBLESHOOTING.md
    ├── USER_MANUAL.md, ADMIN_MANUAL.md, API_DOCUMENTATION.md
    ├── DATABASE_SCHEMA.md, SECURITY_REPORT.md, PERFORMANCE_REPORT.md
    ├── BACKUP_RESTORE_GUIDE.md, PILOT_DEPLOYMENT_PLAN.md
    ├── GAP_ANALYSIS_COLLEGE_SCALE.md
    └── sdd/                    # ★ This Software Design Document
```

## 3.2 Folder-by-Folder Rationale

### 3.2.1 `app/` — Core AI Pipeline ⭐
**Why it exists:** Contains every AI component. Kept separate from
presentation/API so models can be loaded once and shared. Each module is
independently testable (there are matching `tests/test_*.py` files).
**Dependencies:** `config/`, `camera/` (via live_detection), `database/`,
`services/` (for DB logging).

### 3.2.2 `camera/` — Camera Abstraction
**Why it exists:** The pipeline must not care *where* frames come from.
The `CameraSource` ABC + factory makes adding a new camera type a one-file
change. This is also the only layer allowed to touch `cv2.VideoCapture`.

### 3.2.3 `dashboard/` — Streamlit UI
**Why it exists:** Provides the operator interface. `frame_buffer.py` and
`camera_owner.py` are the canonical shared infrastructure that survive
Streamlit reruns — critical because Streamlit reruns the script top-to-bottom
on every interaction.

### 3.2.4 `services/` — Business Logic Layer
**Why it exists:** The dashboard and API both need attendance/employee/
recognition operations. Services centralize that logic, wrap repositories,
add audit logging, and keep the FAISS index in sync with the DB
(e.g. rename/delete propagation).

### 3.2.5 `api/` — FastAPI REST Layer
**Why it exists:** Enterprise integration: programmatic access to students,
employees, cameras, attendance, analytics, jobs, and real-time events.
Contains its own security stack (JWT, RBAC, rate limiting, headers).

### 3.2.6 `database/` — ORM + Repository
**Why it exists:** Centralizes schema (models), connection/session
management, and all SQL queries (repository). The repository pattern keeps
business logic free of SQLAlchemy noise and makes testing with mocks easy.

### 3.2.7 `scripts/` — Admin & Benchmarks
**Why it exists:** One-off/ops tasks that shouldn't live in the app:
seeding, backup/restore, dedupe, migrations, bulk enrollment, and
performance benchmarking/tuning.

### 3.2.8 `tests/` — Automated Tests
**Why it exists:** 490 tests protect the system. Each module has a matching
test file. Integration tests require PostgreSQL + Redis (they skip when
unavailable).

### 3.2.9 `alembic/` — Migrations
**Why it exists:** Schema changes must be versioned and repeatable across
dev/prod. Three migrations exist: initial schema index, failed-login table,
and scalability indexes.

### 3.2.10 Data directories (`embeddings/`, `attendance/`, `unknown_faces/`,
`logs/`, `data/`, `uploads/`, `outputs/`, `backups/`)
**Why they exist:** Persistent state that must not be in git. Paths are
created automatically by `config/config.py` at import time.

---

*References: `config/config.py`, `README.md`, repository tree*
