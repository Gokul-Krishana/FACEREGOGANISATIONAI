# Section 26 — Design Patterns

Design patterns identified in the source code, with concrete locations.

## 26.1 Repository Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `database/repository.py` (`StudentRepo`, `EmployeeRepo`, `AttendanceRepo`, `RecognitionLogRepo`, `UnknownFaceRepo`, `CameraRepo`, `AuditLogRepo`) |
| **How** | Each repo is a class of static methods taking a `Session`; callers control transactions |
| **Why** | Isolates SQL; business logic stays clean; unit-testable; consistent CRUD API |
| **Related** | `PageResult` pagination envelope shared with API/UI |

## 26.2 Factory Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `camera/selector.py` — `create_camera(source_type, **kwargs)`; `CAMERA_REGISTRY` maps slugs → classes |
| **How** | Factory maps a config string to the right `CameraSource` subclass and normalizes kwargs (device_id, url, etc.) |
| **Why** | Pipeline code never instantiates concrete camera classes; adding a camera type = one registry entry |
| **Also** | `SharedModelResources.load()` acts as a model factory with caching; `LiveDetection.open_camera()` uses the camera factory |

## 26.3 Singleton Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `dashboard/camera_owner.py` — `CameraOwner.__new__` with `_lock` + `_instance`; `api/redis_client.py` — `get_redis()` global instance; `app/deep_liveness.py` — `get_deep_liveness_detector()` global; `api/job_queue.py` + `api/websocket_manager.py` — module-level `job_queue`/`ws_manager`; `dashboard/frame_buffer.py` — module-level `frame_buffer`/`results_buffer` |
| **Why** | One camera owner, one Redis client, one model, one queue, one buffer per process |
| **Thread-safety** | `CameraOwner` uses a class-level `threading.Lock`; Redis client lazily created |

## 26.4 Dependency Injection (via constructor + FastAPI Depends)

| Aspect | Detail |
|--------|--------|
| **Where** | `RecognitionService.__init__(detector=None, recognizer=None, enrollment=None, amfr=None)` + `with_shared_models()`; FastAPI `Depends(get_current_user)` / `Depends(get_session)` / `Depends(require_permission(...))` |
| **How** | Models injected into services (defaults create new); FastAPI resolves auth/session dependencies |
| **Why** | Testability (mock injection), model sharing across pipelines, declarative auth |

## 26.5 Service Layer Pattern

| Aspect | Detail |
|--------|--------|
| **Where** | `services/*` (`RecognitionService`, `AttendanceService`, `EmployeeService`, `UnknownFaceService`, `AuditService`, `BruteForceProtection`, `MFAService`, `OIDCService`) |
| **How** | Services wrap repositories, add business rules + audit logging + cross-store sync (FAISS↔DB), and are the only layer both UI and API call |
| **Why** | Centralizes business logic; prevents UI/API from touching repositories/AI directly |

## 26.6 MVC / MVCS (Model-View-Controller-ish)

| Layer | In this project |
|-------|-----------------|
| **Model** | `database/models.py` (ORM) + FAISS index |
| **View** | `dashboard/pages/*` (Streamlit) |
| **Controller** | `services/*` + `api/main.py` (FastAPI routes) |
| **Note** | Not strict MVC; closer to **Layered Architecture** with a thin Controller (API) + Service layer — deliberately chosen for testability |

## 26.7 Other Patterns Observed

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Facade** | `RecognitionService.process_frame_detailed()` | one call hides the whole pipeline |
| **Adapter** | `CameraSource` ABC + implementations | uniform interface over very different cameras |
| **Strategy** | FAISS `index_type` (flat/hnsw/ivf); Liveness factor weights; AMFR thresholds | config-driven algorithm selection |
| **Template Method** | `CameraSource` abstract methods + shared lifecycle (`open/read/release`) | consistent camera lifecycle |
| **Data Transfer Object** | Pydantic schemas (`EmployeeResponse`, `TokenResponse`, `BulkResult`) | typed API boundaries |
| **Context Manager** | `get_session()` (contextmanager), `WebcamSource.__enter__/__exit__` | resource lifecycle |
| **Module-level singletons** | buffers, ws_manager, job_queue, redis | cross-component shared state |
| **Cache-aside** | `@st.cache_data/ttl`, `SharedModelResources._cache`, `_verified_at` | performance |
| **Guard (fail-fast)** | `_validate_production_secret_key()` | fail loudly in production |
| **Circuit-breaker-ish** | Redis degradation, camera reconnect loop, DB write try/except | resilience |

## 26.8 Pattern Trade-offs

| Pattern | Benefit realized | Risk |
|---------|------------------|------|
| Repository | clean data access | can add boilerplate for simple queries |
| Factory | camera extensibility | registry must stay in sync with kwargs mapping |
| Singleton | shared models/state | global state complicates tests (mitigated by `CameraOwner.reset()`) |
| Service Layer | testable business rules | two service packages (`services/` vs `api/`) have slight overlap (documented) |

---

*References: `camera/selector.py`, `dashboard/camera_owner.py`,
`services/*`, `database/repository.py`, `api/main.py`, `app/deep_liveness.py`*
