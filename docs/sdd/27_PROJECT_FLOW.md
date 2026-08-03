# Section 27 — Complete Project Flow

This section documents **every interaction between modules**, walking from
startup through the three primary user journeys and the operational paths.
Nothing is left unexplained.

## 27.1 Startup Sequence

```
streamlit run dashboard/app.py
  └─ dashboard/app.py
       ├─ set_page_config (wide)
       ├─ sidebar nav links to 10 pages
       ├─ init_db()  → database/database.py
       │    ├─ alembic.ini exists → run_migrations() → alembic upgrade head
       │    └─ else → Base.metadata.create_all + stamp head
       ├─ UnknownFaceService.auto_cleanup() → UnknownFaceRepo.delete_older_than(days=30)
       ├─ FaceEnrollment() → loads faiss.index + metadata.json (or creates)
       ├─ cfg.* sidebar stats (threshold, camera source)
       └─ st.switch_page("pages/01_Dashboard.py")

uvicorn api.main:app
  └─ lifespan
       ├─ init_db()
       ├─ register_default_handlers() → api/job_queue.py (batch_enroll, rebuild_index, cleanup_unknown)
       ├─ job_queue.start() → 3 asyncio workers
       └─ _validate_production_secret_key()  (fail-fast in production)
```

## 27.2 Journey A — Enroll a New Person

```
03_Enroll.py
  ├─ select camera source (CAMERA_CHOICES from camera/selector.py)
  ├─ employee details form (ID, name, dept)
  ├─ capture:
  │    webcam  → st.camera_input (browser)
  │    phone/IP → camera/selector.create_camera() → camera/phone.py *.open()
  │               → read 10 warm-up frames → preview → Confirm
  └─ _process_enrollment(frame, emp_id, name, dept)
       ├─ app/recognizer.py FaceRecognizer.extract_embedding(frame) → 512-D
       ├─ app/enrollment.py FaceEnrollment.search(emb, k=1, threshold=1.0)
       │    └─ duplicate? → warn & stop
       ├─ FaceEnrollment.enroll(name, emb) → index.add + metadata.append + _save()
       ├─ services/employee_service.py EmployeeService.create(emp_id, name, dept, faiss_id)
       │    └─ database/repository.py EmployeeRepo.create (commit/refresh)
       │    └─ services/audit_service.py AuditService.log("ENROLL", ...)
       └─ failure → rollback FaceEnrollment.remove_by_name(name)
```

## 27.3 Journey B — Live Recognition & Attendance

```
04_Live.py
  ├─ SharedModelResources.load() → RecognitionService() (models once)
  ├─ LiveRecognitionPipeline(source_type, **kwargs)
  │    └─ RecognitionService.with_shared_models(shared) → per-pipeline state
  ├─ start():
  │    ├─ camera/selector.create_camera(...).open()
  │    ├─ 3 daemon threads: capture / worker / latency
  │    └─ CameraOwner.acquire(cam, pipeline)
  ├─ capture loop: cam.read() → frame_buffer.put(frame)   [dashboard/frame_buffer.py]
  ├─ worker loop (adaptive 0.1/0.6 s):
  │    ├─ frame_buffer.get() → cv2.resize(320×240)
  │    ├─ RecognitionService.process_frame_detailed(small_frame)
  │    │     ├─ app/face_detector.py detect()            → person bboxes
  │    │     ├─ app/amfr_engine.py process_frame()
  │    │     │    ├─ app/tracking.py tracker.update()    → track_ids
  │    │     │    ├─ app/recognizer.py detect_face()     → face + landmarks + emb
  │    │     │    ├─ app/enrollment.py search()          → name/distance/confidence
  │    │     │    ├─ app/face_quality.py assess()        → quality score
  │    │     │    ├─ app/liveness_detector.py analyze_frame() → liveness (5 factors,
  │    │     │    │      deep via app/deep_liveness.py MiniFASNet/fallback)
  │    │     │    ├─ _decide() → AMFRDecision + risk_score
  │    │     │    └─ tracker.update(enriched)            → identity stability
  │    │     ├─ ACCEPT → services/attendance_service.py mark()
  │    │     │    ├─ AttendanceRepo.is_marked_today → create (commit)
  │    │     │    ├─ app/attendance.py AttendanceTracker.mark (CSV)
  │    │     │    └─ AuditService.log("MARK_ATTENDANCE")
  │    │     ├─ recognition log → RecognitionLogRepo.create (liveness/spoof/track)
  │    │     ├─ LOW_CONFIDENCE → _handle_unknown_face()
  │    │     │    └─ cv2.imwrite unknown_faces/ + UnknownFaceRepo.create + audit
  │    │     └─ REJECT_SPOOF → AuditService.log("SPOOF_ATTEMPT")
  │    ├─ scale bboxes to display size → results_buffer.put(results)
  │    └─ cache verified track_ids (_verified_at) for adaptive cadence
  ├─ display loop: frame_buffer.get() + results_buffer.get() → _draw_overlays()
  │    └─ dashboard pages show "✓ NAME · PRESENT" and today's attendance
  └─ stop(): CameraOwner.release() → pipeline.stop() → join threads → cam.release()
```

## 27.4 Journey C — Review Unknown Face → Employee

```
06_Unknown.py
  ├─ UnknownFaceService.get_statistics() / get_filtered()
  ├─ face cards: image from disk + DB row (camera, time, confidence)
  ├─ [Register Employee] → UnknownFaceService.convert_to_employee(id, emp_id, name, dept)
  │    ├─ load image (cv2.imread)
  │    ├─ FaceRecognizer.extract_embedding(image)
  │    ├─ EmployeeService.create (DB first — fail fast on duplicate)
  │    ├─ FaceEnrollment.enroll(name, emb)   (rollback employee if FAISS fails)
  │    ├─ UnknownFaceRepo.mark_converted
  │    └─ AuditService.log("CONVERT_UNKNOWN")
  ├─ [Ignore] → UnknownFaceRepo.mark_reviewed + audit
  ├─ [Delete] → UnknownFaceRepo.delete (row + image file) + audit
  └─ [Delete All] → UnknownFaceRepo.delete_all (bulk delete + file cleanup) + audit
```

## 27.5 Journey D — API Client

```
POST /auth/login
  ├─ BruteForceProtection.is_locked_out (failed_login_attempts)
  ├─ verify bcrypt password
  ├─ MFA required? → mfa_token (2 min, mfa_pending) → /auth/mfa/verify (TOTP/backup)
  └─ else → access_token + refresh_token (hash stored)
GET /employees?q=...
  ├─ get_current_user (JWT decode) → require_permission("employees","READ")
  │    └─ query user_roles → role_permissions → permissions
  ├─ EmployeeRepo.search_paginated → PageResult
  └─ audit log_event
POST /attendance  (manual mark)
  ├─ require_permission("attendance","CREATE")
  ├─ validate student + enrollment (api/attendance_service.py timetable checks)
  ├─ Attendance row + audit ATTENDANCE_MARKED
GET /events/stream (WebSocket)
  ├─ ws_manager.connect → broadcast_event on recognition events
GET /jobs → enqueue/status/cancel via api/job_queue.py
POST /bulk/students/import → BulkOperations.import_students_from_csv → BulkResult
```

## 27.6 Operational Flows

### Backup
`scripts/backup.py` → `find_pg_bin()` → preflight (psycopg2) → `pg_dump`
(SQL) + copy `faiss.index`/`metadata.json` → `manifest.json` (SHA-256) →
`backups/backup_<ts>/`.

### Restore
`scripts/restore.py` → verify hashes → (optional) terminate connections →
DROP DATABASE → CREATE DATABASE → `psql -f dump` → restore FAISS artifacts →
**restart app**.

### Seed
`scripts/seed_admin.py` → `init_db()` → seed 7 roles → seed permissions →
assign ALL to SUPER_ADMIN, subset to COLLEGE_ADMIN → create admin →
assign roles → commit. Idempotent.

### Dedupe
`scripts/dedupe_employees.py` → group by normalized name → pick survivor →
re-point attendance/recognition rows → delete duplicates; `--clean-stale`
removes employees with dead faiss_id (guarded).

### FAISS migration
`scripts/migrate_faiss_hnsw.py` → `reconstruct_n` → create new index from
config → train (IVF) → re-add → verify search.

### Bulk enroll
`scripts/bulk_enroll.py` → real (photos) or synthetic (random normalized
vectors, batched `index.add`) → optional `--db` employee records.

## 27.7 Cross-Cutting Interactions

| Concern | Modules involved |
|---------|------------------|
| Config | `config/config.py` ← `settings.yaml` → consumed by every app/service/camera module |
| Logging | `config/config.py` (rotating file + console) + module loggers; `python-json-logger` available |
| Audit | `services/audit_service.py` ← services + `api/main.py log_audit` → `audit_logs` |
| FAISS↔DB sync | `EmployeeService.update/delete` → `FaceEnrollment.rename/remove_by_name` |
| Attendance dual-write | `AttendanceService.mark` → DB + CSV (`app/attendance.py`) |
| State (Redis) | `api/redis_client.py` ← auth (OIDC state), cooldown, camera status |
| Real-time | `api/websocket_manager.py` ← `api/main.py` events/stream |
| Background jobs | `api/job_queue.py` ← `/jobs` endpoints + lifespan |
| Security headers/limits | `api/main.py` middleware stack |

## 27.8 Module Interaction Table (caller → callee)

| Caller | Callee(s) |
|--------|-----------|
| `04_Live.py` | camera/selector, services/recognition_service, services/attendance_service, dashboard/camera_owner, dashboard/frame_buffer, dashboard/latency_logger, camera/discovery |
| `RecognitionService` | app/face_detector, app/recognizer, app/enrollment, app/amfr_engine, services/attendance_service, services/audit_service, database/repository |
| `AMFREngine` | app/face_quality, app/liveness_detector, app/tracking |
| `LivenessDetector` | app/deep_liveness |
| `EmployeeService` | database/repository, services/audit_service, app/enrollment (sync) |
| `UnknownFaceService` | database/repository, services/employee_service, app/recognizer, app/enrollment, services/audit_service |
| `api/main.py` | all services, api/job_queue, api/websocket_manager, api/redis_client, api/bulk_operations, utils/upload_security, database/repository |
| `camera/selector` | camera/webcam, camera/phone, camera/fake |
| `LiveDetection` (CLI) | app/* , camera/selector, database/repository, services/employee_service |

---

*References: full call graphs traced through imports and function calls in
`dashboard/*`, `services/*`, `api/*`, `app/*`, `camera/*`, `scripts/*`*
