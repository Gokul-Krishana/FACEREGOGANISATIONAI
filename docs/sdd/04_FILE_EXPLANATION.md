# Section 4 — Complete File Explanation

Every important file in the repository, explained with: purpose,
responsibilities, classes, functions, inputs, outputs, dependencies, flow,
complexity, and interactions.

---

## 4.1 Entry Points

### `main.py` — CLI Entry Point
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Command-line interface for live recognition, single-image processing, enrollment, pipeline testing, and diagnostics |
| **Classes** | None (module-level functions) |
| **Functions** | `cmd_webcam()`, `cmd_image()`, `cmd_enroll()`, `cmd_test()`, `cmd_debug()`, `main()` |
| **Inputs** | CLI args: `--camera-id`, `--source-type`, `--camera-url`, `--image`, `--enroll`, `--test`, `--debug` |
| **Outputs** | Annotated video window, annotated images in `outputs/`, console logs |
| **Dependencies** | `config.config`, `app.live_detection.LiveDetection`, `cv2`, `numpy` |
| **Flow** | Parse args → route to command → each command builds a `LiveDetection` pipeline and runs it |
| **Complexity** | O(n) frames; simple orchestration |
| **Interactions** | Wraps the entire `app/` pipeline; uses `camera.selector.create_camera()` via `LiveDetection.open_camera()` |

### `dashboard/app.py` — Streamlit Entry Point
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Bootstrap the Streamlit dashboard, sidebar navigation, DB init, auto-cleanup |
| **Dependencies** | `database.database.init_db`, `services.unknown_face_service.UnknownFaceService.auto_cleanup`, `app.enrollment.FaceEnrollment`, `config.config`, `streamlit` |
| **Flow** | `st.set_page_config` → sidebar links to 10 pages → `init_db()` → `auto_cleanup()` → footer stats → `st.switch_page("pages/01_Dashboard.py")` |

### `run.bat` / `run.sh` / `clear_cache.py`
- `run.bat`/`run.sh` — convenience launchers (install deps, run dashboard or API).
- `clear_cache.py` — clears FAISS metadata/index caches (ops utility).

---

## 4.2 Core AI Pipeline (`app/`)

### `app/face_detector.py` — YOLO Person Detector
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Detect people in a frame using YOLO11 (person class only) |
| **Class** | `FaceDetector` |
| **Functions** | `detect(frame, conf_threshold)`, `crop_person(frame, bbox, padding)`, `get_largest_detection(detections)` |
| **Inputs** | BGR frame (H×W×3), optional confidence threshold |
| **Outputs** | List of `{"bbox": (x1,y1,x2,y2), "confidence": float, "class_id": 0}` |
| **Dependencies** | `ultralytics.YOLO`, `config.config`, `cv2`, `numpy` |
| **Flow** | `model(frame)` → filter `cls==0` → convert boxes to ints |
| **Complexity** | Model inference is the dominant cost; per-frame O(1) detections |
| **Interactions** | First stage of every pipeline; crops feed `recognizer.detect_face()` |

### `app/recognizer.py` — RetinaFace + ArcFace
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Face detection with 5-point landmarks (RetinaFace) and 512-D embedding (ArcFace) |
| **Class** | `FaceRecognizer` |
| **Functions** | `extract_embedding()`, `detect_face()`, `get_landmarks()`, `compute_similarity()`, `embedding_dim()` |
| **Inputs** | BGR image (person crop or face) |
| **Outputs** | 512-D L2-normalized float32 embedding, or face dict `{"bbox","landmarks","embedding","det_score"}` |
| **Dependencies** | `insightface.FaceAnalysis` (`buffalo_l`), `config.config` |
| **Flow** | `app.get(img)` → take first face → normalize embedding to unit norm |
| **Complexity** | One CNN pass per person; det_size 640×640 |
| **Interactions** | Consumed by enrollment, AMFR, enrollment page, bulk enroll |

### `app/enrollment.py` — FAISS Vector Store
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Persistent face-embedding store with nearest-neighbor search |
| **Class** | `FaceEnrollment` |
| **Functions** | `enroll()`, `search()`, `remove()` (NotImplemented), `remove_by_name()`, `rename()`, `clear()`, `all_persons()`, `count()`, `unique_count()`, `_save()`, `_create_index()`, `status()` |
| **Inputs** | Names + 512-D embeddings; queries + thresholds |
| **Outputs** | Match list `{"name","confidence","distance"}`; status dict |
| **Dependencies** | `faiss`, `numpy`, `config.config` |
| **Flow** | Load index+metadata at init; search via `index.search`; confidence = `1/(1+d²)` |
| **Complexity** | Search O(log n) HNSW, O(n) flat; delete/rename rebuild O(n) |
| **Interactions** | Used by recognizer pipeline, services (employee rename/delete sync), scripts |

### `app/face_quality.py` — Quality Assessment
| Attribute | Detail |
|-----------|--------|
| **Class** | `FaceQualityAssessment` |
| **Functions** | `assess()`, `_assess_blur()`, `_assess_brightness()`, `_assess_contrast()`, `_assess_face_size()`, `_assess_det_score()`, `_assess_pose()` |
| **Metrics** | Laplacian variance (blur), mean brightness, stddev contrast, face size ratio, det score, landmark-based pose |
| **Outputs** | `{"overall": 0-1, "passed": bool, "metrics": {...}, "failure_reasons": [...]}` |
| **Complexity** | O(face_area) pixel ops; ~sub-ms |
| **Interactions** | Called by `AMFREngine._evaluate_person()` |

### `app/liveness_detector.py` — Multi-Factor Liveness
| Attribute | Detail |
|-----------|--------|
| **Class** | `LivenessDetector`, `LivenessResult` |
| **Functions** | `analyze_frame()`, `reset()`, `register_blink()`, `_analyze_texture()` (LBP), `_compute_approximate_ear()`, `_update_blink_state()`, `_analyze_motion()`, `_detect_screen_edges()`, `_fail_result()` |
| **Inputs** | Face crop + optional 5-point landmarks |
| **Outputs** | `LivenessResult` with per-factor scores (texture/blink/motion/screen/dl) + `is_live` |
| **Weights** | With DL: 0.15/0.20/0.15/0.10/0.40; without DL: 0.25/0.35/0.25/0.15 |
| **Dependencies** | `cv2`, `numpy`, `app.deep_liveness` (optional), `config.config` |
| **Complexity** | LBP downsampled to 48×48 (~0.1 ms); deep factor ~5 ms |
| **Interactions** | Instantiated **per track** by AMFR engine (isolated blink/motion state) |

### `app/deep_liveness.py` — CNN Anti-Spoofing
| Attribute | Detail |
|-----------|--------|
| **Purpose** | Deep-learning liveness (MiniFASNet ONNX) with a numpy fallback CNN |
| **Class** | `DeepLivenessDetector`, `DeepLivenessResult` |
| **Functions** | `predict()`, `_load_model()`, `_download_model()`, `_predict_onnx()`, `_preprocess()`, `_align_face()`, `_predict_fallback()`, `_estimate_uniformity()`, `reload()` |
| **Model** | `MiniFASNetV2.onnx` (80×80 input, 3-class softmax), downloaded from yakhyo/face-anti-spoofing releases |
| **Fallback** | 3-channel histogram + FFT spectral + gradient + color-correlation features, ~0.5 ms |
| **Outputs** | `DeepLivenessResult` (dl_score, is_live, inference_time_ms, model_available) |
| **Complexity** | ONNX ~5 ms; fallback ~0.5 ms |
| **Interactions** | Singleton via `get_deep_liveness_detector()`; used by `LivenessDetector` |

### `app/tracking.py` — IoU Multi-Object Tracker
| Attribute | Detail |
|-----------|--------|
| **Class** | `TrackState` (dataclass), `MultiFrameTracker` |
| **Functions** | `update()`, `reset()`, `_compute_iou_matrix()`, `_iou()`, `_greedy_assign()`, `_create_track()`, `_update_track()`, `_apply_detection()`, `_prune_lost_tracks()` |
| **Inputs** | Detection dicts (bbox + scores), frame shape |
| **Outputs** | Active `TrackState` list with accumulated scores, identity, stability |
| **Complexity** | IoU matrix O(tracks×detections); greedy assignment O(n²) worst case |
| **Interactions** | Updated twice per frame by AMFR (identity feedback loop) |

### `app/amfr_engine.py` — Adaptive Multi-Factor Recognition
| Attribute | Detail |
|-----------|--------|
| **Class** | `AMFREngine`, `AMFRDecision` (enum) |
| **Functions** | `process_frame()`, `reset()`, `status()`, `_get_liveness_detector()`, `_evaluate_person()`, `_decide()` |
| **Inputs** | Frame, detections, embeddings, FAISS results, face data |
| **Outputs** | Augmented detections: `name`, `confidence`, `amfr_decision`, `risk_score`, `amfr_details` |
| **Decision logic** | Liveness gate (hard reject) → quality gate → arcface score → weighted risk = 0.45·arcface + 0.35·liveness + 0.20·quality → thresholds (0.70 ACCEPT, 0.40 BORDERLINE) |
| **Complexity** | Per-person: quality + liveness + tracking; moderate |
| **Interactions** | Core of `RecognitionService` and `LiveDetection` |

### `app/attendance.py` — CSV Attendance Logger
| Attribute | Detail |
|-----------|--------|
| **Class** | `AttendanceTracker` |
| **Functions** | `mark()`, `today()`, `by_date()`, `all_records()`, `statistics()` |
| **Outputs** | Per-day CSV files (`attendance/YYYY-MM-DD.csv`) |
| **Flow** | `mark()` dedupes per name per day |
| **Interactions** | Used by `AttendanceService` (dual-write) and CLI `LiveDetection` |

### `app/live_detection.py` — CLI Pipeline Orchestrator
| Attribute | Detail |
|-----------|--------|
| **Class** | `LiveDetection` |
| **Functions** | `process_frame()`, `open_camera()`, `run()`, `process_image()`, `process_video()`, `status()`, `_draw_overlay()`, `_draw_info_card()`, `_log_attendance_db()`, `_save_unknown_face()`, `_interactive_enroll()`, `_debug_faiss()` |
| **Flow** | YOLO → RetinaFace → ArcFace → FAISS → AMFR → attendance + unknown handling |
| **Interactions** | Instantiated by `main.py` CLI and the Attendance page's WebRTC transformer |

---

## 4.3 Recognition & Camera (`recognition/`, `camera/`)

### `recognition/alignment.py`
| Attribute | Detail |
|-----------|--------|
| **Functions** | `align_face()`, `align_face_from_bbox()`, `normalize_intensity()` |
| **Purpose** | Similarity-transform face alignment to canonical landmarks (224×224), CLAHE normalization |
| **Interactions** | Available to any consumer; the live pipeline embeds alignment inside InsightFace/detector pre-processing |

### `camera/base.py`
`CameraSource` (ABC): `name`, `source_type`, `open()`, `release()`, `read()`,
`is_opened()`, `set_resolution()`, `get_resolution()`, `info()`. `CameraError` exception.

### `camera/webcam.py`
| Class | Detail |
|-------|--------|
| `WebcamSource` | OpenCV webcam with DirectShow→MSMF→Default backend fallback |
| `USBAnySource` | Auto-scans indices 0..9, prefers a given index, uses first working camera |
| `list_webcams()` / `list_all_cameras()` | Index probing helpers |

### `camera/phone.py`
| Class | Transport |
|-------|-----------|
| `AndroidWiFiSource` | IP Webcam HTTP MJPEG (`http://ip:8080/video`), connectivity pre-check with `requests` |
| `AndroidUSBSource` | DroidCam USB (DirectShow) with Wi-Fi fallback |
| `iPhoneWiFiSource` | EpocCam RTSP/HTTP |
| `iPhoneUSBSource` | EpocCam/DroidCam virtual DirectShow camera (default index 2) |
| `IPCameraSource` | Generic RTSP/HTTP/MJPEG |

### `camera/selector.py`
`CAMERA_REGISTRY` slug→class map; `create_camera(source_type, **kwargs)`
factory; `select_camera_cli()`; `select_camera_ui(st)`; `get_available_cameras()`.

### `camera/discovery.py`
`scan_network(timeout, max_workers)` — probes 1..254 in the /24 subnet on
ports 8080/4747, matches HTTP signatures (IP Webcam / DroidCam / EpocCam),
returns deduplicated `DiscoveredCamera` list.

### `camera/fake.py`
`FakeCameraSource` — synthetic gradient frames at target FPS with optional
jitter; used by benchmarks and hardware-free tests.

---

## 4.4 Service Layer (`services/`)

### `services/recognition_service.py` — Pipeline Orchestrator ⭐
| Attribute | Detail |
|-----------|--------|
| **Purpose** | The single entry point the dashboard/API use for frame processing |
| **Functions** | `process_frame()`, `process_frame_detailed()`, `with_shared_models()`, `reset_tracking()`, `status()`, `_maybe_mark_attendance()`, `_log_recognition()`, `_handle_unknown_face()`, `_draw_overlay()` |
| **Flow** | YOLO → RetinaFace → ArcFace → FAISS → AMFR → attendance/unknown/spoof actions → DB logging |
| **Key detail** | `with_shared_models()` shares models across pipelines but keeps per-pipeline state |
| **Interactions** | Consumes `FaceDetector`, `FaceRecognizer`, `FaceEnrollment`, `AMFREngine`; writes via `AttendanceService`, `RecognitionLogRepo`, `UnknownFaceRepo`, `AuditService` |

### `services/attendance_service.py`
`mark()` (DB+CSV dual write, dedupe per day, audit), `get_today()`,
`get_by_date()`, `get_by_employee()`, `get_statistics()`, `to_dict()`.

### `services/employee_service.py`
`create()`, `get_by_employee_id()`, `get_by_id()`, `get_by_name()`, `update()`
(renames FAISS label on name change), `get_all()`, `search()`, `delete()`
(removes FAISS embedding), `remove_faiss_embedding()`, `count()`, `to_dict()`.

### `services/unknown_face_service.py`
`get_statistics()`, `get_all()`, `get_filtered()`, `get_by_id()`,
`mark_reviewed()`, `delete()`, `update_notes()`, `convert_to_employee()`
(full workflow: load image → ArcFace embedding → FAISS → DB → mark converted),
`delete_all()`, `auto_cleanup()`.

### `services/audit_service.py`
`log(action, description, operator, employee_id)`, `get_recent()`, `get_by_action()`.

### `services/brute_force_protection.py`
`is_locked_out()`, `record_failed_attempt()`, `record_successful_login()`,
`get_lockout_info()`, `cleanup_old_attempts()`. Constants: 5 attempts /
30 min lockout / 20 IP requests per minute / 7-day cleanup.

### `services/mfa_service.py`
TOTP via `pyotp`: `generate_secret()`, `verify_totp()`, `generate_backup_codes()`
(SHA-256 hashed), `verify_backup_code()`, `enroll_user()`, `disable_mfa()`,
`verify_and_update()`, `requires_mfa()` (super-admin and admin roles always MFA).

### `services/oidc_service.py`
Provider-agnostic OIDC (discovery endpoint, code exchange, user sync):
`OIDCUserInfo` dataclass, `get_login_url()`, `handle_callback()`, `sync_user()`.

---

## 4.5 API Layer (`api/`)

### `api/main.py` — FastAPI App (46 endpoints)
| Attribute | Detail |
|-----------|--------|
| **Middleware** | SlowAPI rate limiter, CORS, TrustedHost, security headers, request-ID, body-size limit |
| **Security** | `HTTPBearer`, JWT decode, `require_permission()` (RBAC), `require_role()`, bcrypt via passlib |
| **Endpoints** | Auth (login/logout/me/change-password/revoke-all/mfa/oidc/refresh), health/metrics, enroll/upload, students CRUD, employees CRUD, cameras CRUD, attendance, unknown-faces, analytics, events/stream (WS), jobs, bulk, health/ready/live, system/status |
| **Dependencies** | FastAPI, slowapi, jose, passlib, sqlalchemy, pydantic, prometheus_client |

### `api/redis_client.py`
`RedisClient` — student last-seen, attendance dedupe keys, camera status,
recognition cooldown, track identity cache, generic cache_get/set/delete.
Singleton via `get_redis()`.

### `api/job_queue.py`
In-process asyncio job queue (`JobQueue`, `Job`, `JobStatus`). Handlers:
`batch_enroll`, `rebuild_index`, `cleanup_unknown` (currently simulated).

### `api/websocket_manager.py`
`WebSocketManager` — per-camera event streams, role-based filtering, heartbeat
(15 s), event buffering (last 100), `broadcast_event()`, `send_personal()`.

### `api/bulk_operations.py`
`BulkOperations` — `import_students_from_csv()`, `import_employees_from_csv()`,
`bulk_update_camera_status()`, `export_attendance_csv()`; `BulkResult` dataclass.

### `api/attendance_service.py`
Timetable-aware: `is_class_in_session()`, `is_within_time_window()`,
`is_student_enrolled()`, `get_today_attendance()`, `create_attendance()`,
`get_attendance_summary()`.

### `api/audit_service.py`
`log_event()`, `log_recognition_event()`, `log_security_alert()`,
`get_audit_logs()`, `export_logs()`.

---

## 4.6 Database Layer (`database/`)

### `database/database.py`
`DB_TYPE` env switch (sqlite default / postgres via `DATABASE_URL`), engine,
`SessionLocal`, `get_session()` context manager, `init_db()` (Alembic →
create_all fallback → stamp), `run_migrations()`, `reset_db()`.

### `database/models.py`
20 tables + 2 association tables (see §8 for full schema). Key enums:
`RoleName` (7 roles), `ActionType`, `AuditAction`.

### `database/repository.py`
`PageResult` dataclass; repos: `StudentRepo`, `EmployeeRepo`, `AttendanceRepo`,
`RecognitionLogRepo`, `UnknownFaceRepo`, `CameraRepo`, `AuditLogRepo`.
All take a Session; callers control transactions.

---

## 4.7 Config, Utils, Scripts, Tools

### `config/config.py`
Loads `settings.yaml` with defaults; exposes typed constants
(`YOLO_CONFIDENCE`, `RECOGNITION_THRESHOLD`, AMFR weights, FAISS params,
paths, logging config). `save_settings()` preserves YAML comments via
ruamel round-trip. Creates required directories at import.

### `utils/upload_security.py`
`validate_image_upload()` — magic-bytes format detection (JPEG/PNG/GIF/WebP),
size limit, Pillow verification, dimension checks, server-side filename
(`enroll_<ts>_<uuid>.<ext>`). `UploadSecurityError`, `sanitize_filename()`.

### `utils/image.py`
`read_image()`, `save_image()`, `resize_to_height()`, `draw_rounded_rect()`.

### `scripts/seed_admin.py`
Seeds 7 roles, permissions (11 resources × 5 actions + extras), assigns all to
SUPER_ADMIN, subset to COLLEGE_ADMIN, creates admin user. Idempotent.

### `scripts/backup.py` / `scripts/restore.py`
Backup: pg_dump (plain SQL) + FAISS index + metadata + manifest.json with
SHA-256 hashes. Restore: integrity verify → terminate connections → drop →
create → restore DB → restore FAISS artifacts.

### `scripts/bulk_enroll.py`
Real mode (scan photo dir) or synthetic mode (generate N random L2-normalized
512-D embeddings in batches). `--db` creates employee records; `--dry-run`
validates without saving.

### `scripts/dedupe_employees.py`
Groups employees by normalized name, picks survivor (valid FAISS id, else
earliest), re-points attendance/recognition rows, deletes duplicates.
`--clean-stale` removes employees whose faiss_id is gone (guarded against
empty metadata).

### `scripts/migrate_faiss_hnsw.py`
Extracts vectors via `reconstruct_n`, rebuilds with current config, re-adds
in batches, verifies with a search test.

### `tools/validate_startup.py`
Import checks, env checks, model presence, DB init — prints a health report.

### `tools/diagnose_cameras.py`
Camera diagnostics: lists devices, tests capture, reports issues.

---

## 4.8 Test Files (`tests/`)

| File | Covers |
|------|--------|
| `test_enrollment.py` | FAISS enroll/search/remove/rename/clear |
| `test_attendance_service.py` | Marking, dedupe, queries |
| `test_employee_service.py` | CRUD + FAISS sync |
| `test_repair.py` | Camera selection + config UI repairs |
| `test_repository.py` / `test_repository_pagination.py` | Repository CRUD + pagination |
| `test_face_quality.py` | Quality metrics |
| `test_deep_liveness.py` | ONNX + fallback paths (forced fallback via monkeypatch) |
| `test_liveness_detector.py` | Multi-factor liveness |
| `test_tracking.py` | IoU tracker |
| `test_upload_security.py` | Upload validation |
| `test_brute_force_protection.py` | Lockout + rate limiting |
| `test_ip_camera.py` / `test_phone_cameras.py` | Camera sources |
| `test_camera_owner.py` | Singleton ownership |
| `test_frame_buffer.py` / `test_latency_logger.py` | Buffers/stats |
| `test_audit_service.py` | Audit trail |
| `test_integration.py` | PostgreSQL + Redis (skips when unavailable) |

---

*References: all files listed; `tests/`, `scripts/`, `tools/` directories*
