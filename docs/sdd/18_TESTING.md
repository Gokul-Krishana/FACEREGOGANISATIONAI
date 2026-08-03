# Section 18 — Testing

## 18.1 Test Suite Overview

- **Runner:** pytest (`pytest.ini` config at repo root).
- **Count:** 20 test modules; **490 tests passing with Redis+PostgreSQL**,
  484 passing + 6 skipped without Redis.
- **Command:** `python -m pytest tests/ -v`
- **Coverage:** `python -m pytest tests/ --cov=app --cov=services --cov=database`

## 18.2 Test File Reference

| Test file | Type | Covers |
|-----------|------|--------|
| `test_enrollment.py` | Unit | FAISS enroll/search/remove_by_name/rename/clear/status, thresholds |
| `test_attendance_service.py` | Unit/Service | Marking, daily dedupe, queries, stats |
| `test_employee_service.py` | Unit/Service | CRUD, name→FAISS sync on rename/delete |
| `test_repair.py` | Unit | Camera selection + config-UI repair regressions |
| `test_repository.py` | Unit | Repository CRUD (employees, attendance, unknown faces) |
| `test_repository_pagination.py` | Unit | `PageResult`, skip/limit, has_more |
| `test_face_quality.py` | Unit | All quality metrics + failure reasons |
| `test_deep_liveness.py` | Unit | ONNX preprocess shape, fallback path (monkeypatched to force fallback), thresholds |
| `test_liveness_detector.py` | Unit | 5-factor scoring, blink state, screen detection, spoof reasons |
| `test_tracking.py` | Unit | IoU matching, greedy assignment, identity stability, pruning |
| `test_upload_security.py` | Unit | Magic bytes, size limits, dimensions, safe filenames |
| `test_brute_force_protection.py` | Unit | Lockout, IP rate limit, reset on success, lockout info |
| `test_ip_camera.py` | Unit | IP camera source open/read/release |
| `test_phone_cameras.py` | Unit | Phone camera sources (Android/iPhone modes) |
| `test_camera_owner.py` | Unit | Singleton ownership, acquire/release transitions |
| `test_frame_buffer.py` | Unit | Latest-frame semantics, close, IDs/timestamps |
| `test_latency_logger.py` | Unit | Rolling stats, percentiles |
| `test_audit_service.py` | Unit | Audit logging |
| `test_integration.py` | Integration | PostgreSQL + Redis live paths (skips when unavailable) |

## 18.3 Test Types

### Unit Tests
- Target a single module with mocked/forced dependencies.
- Example: `test_deep_liveness.py` **monkeypatches** `_get_model_path` and
  `_download_model` so tests deterministically exercise the fallback path
  regardless of local model presence.

### Service Tests
- Exercise `services/*` against the real SQLite DB (in-memory or temp file)
  via `get_session()`; verify audit + FAISS side effects.

### Integration Tests
- `test_integration.py` — needs live **PostgreSQL + Redis**; gracefully
  skips when services are unavailable (this is the "6 skipped" set).
- Verified green in the acceptance run: 490 passed with services.

### Performance / Benchmark Scripts (`scripts/benchmarks/`)
Not pytest — standalone scripts:
- `faiss_benchmark.py` — index build/query latency at scale.
- `tune_hnsw.py` / `tune_ivf.py` — parameter sweeps → tuned config.
- `camera_validation.py` — camera FPS + E2E latency measurement.
- `fake_camera_validation.py` — hardware-free pipeline validation.
- `profile_pipeline.py` — per-stage timing (YOLO/RetinaFace/ArcFace/FAISS/AMFR).
- `benchmark_real_embeddings.py` — recognition with real embeddings.
- `scalability_benchmark.py` — enrollment count scaling.
- `probe_environment.py` — dependency/environment probing.
- `validate_amfr.py` — AMFR decision validation.

## 18.4 Conventions & Fixtures

- `tests/conftest.py` provides shared fixtures.
- Tests are deterministic where possible (monkeypatch model paths).
- DB-dependent tests use project SQLite path or create temp databases
  (`reset_db()` available in `database/database.py`).

## 18.5 CI/CD

`.github/workflows/`:
- `python-ci.yml` — Python lint/tests on push/PR.
- `frontend-ci.yml` — dashboard verification scripts
  (`scripts/verify_dashboard_pages.py`, `verify_attendance_page.py`,
  `verify_health_page.py`).
- `docker-build.yml` — multi-arch image build; **Trivy + Grype** container
  vulnerability scans with SARIF uploads to the GitHub Security tab;
  critical-module import verification.
- `security-scan.yml` — additional security scanning.

## 18.6 Coverage Guidance

- Aim: app/, services/, database/ covered by the unit+service suites.
- Benchmark scripts validate performance characteristics that unit tests
  can't (latency, throughput, recall at scale).
- Reports: `FINAL_VALIDATION_REPORT.md`, `FINAL_ACCEPTANCE_REPORT.md`,
  `PRODUCT_VALIDATION_REPORT.md` document historical suite results.

---

*References: `pytest.ini`, `tests/*`, `.github/workflows/*`,
`scripts/verify_*.py`, `scripts/benchmarks/*`, validation reports*
