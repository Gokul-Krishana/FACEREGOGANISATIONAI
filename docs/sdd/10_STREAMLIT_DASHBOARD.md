# Section 10 — Streamlit Dashboard

**Run:** `streamlit run dashboard/app.py` → http://localhost:8501
**Layout:** wide, expanded sidebar. Sidebar contains navigation links, DB
init status, auto-cleanup status, FAISS embedding count, recognition
threshold, and camera source.

## 10.1 Page-by-Page Explanation

### Page 01 — Dashboard (🏠 Overview)
| Element | Description |
|---------|-------------|
| **Summary cards** | Total Employees, Today's Attendance (+unique delta), Unknown Faces (pending review), System Status |
| **Recognition Status** | YOLO/InsightFace/FAISS load badges + pipeline health badges + config path |
| **Recent Attendance** | Table (time/employee/id/dept/confidence) — `st.cache_data(ttl=10)` |
| **Camera Status** | Active cameras from DB |
| **Quick Actions** | Buttons that `st.switch_page()` to every page |
| **Today's Overview** | Attendance / Unique Present / Unknown Today / Pending Review metrics |
| **Recent Recognition Activity** | RecognitionLog table |
| **Configuration** | Live values of `cfg.*` settings |
| **Getting Started + Pipeline Architecture** | Expanders with guide and ASCII pipeline diagram |

**Workflow:** Landing page for operators — glance at today's numbers, jump to
Live/Enroll/Attendance.

### Page 02 — Employees (👥 CRUD)
| Element | Description |
|---------|-------------|
| **Stats** | Total, Departments, FAISS-Enrolled, Active |
| **Search** | Text input → `EmployeeService.search()` (name/id/dept prefix) |
| **Table** | ID, Name, Department, FAISS ID, Today ✅, Enrolled date |
| **Edit expander** | Select employee → form (name/dept) → `EmployeeService.update()` (also renames FAISS label) |
| **Delete expander** | Select → type ID to confirm → `EmployeeService.delete()` (removes FAISS embedding) |
| **Add form** | Employee ID + Name + Department → `EmployeeService.create()` (duplicates → error) |
| **Attendance history** | Per-employee records (first 10 employees) |

### Page 03 — Enroll (📸 Face Enrollment)
| Element | Description |
|---------|-------------|
| **Camera source** | Selectbox of all `CAMERA_CHOICES` + URL/device fields per type |
| **Employee details form** | ID (required), Name (required), Department |
| **Capture** | Webcam → `st.camera_input` (browser); Phone/IP → `CameraSource` snapshot (10 warm-up frames) |
| **Preview/Confirm** | Image preview, "Confirm & Enroll" / "Recapture" |
| **Processing** | `FaceRecognizer.extract_embedding` → duplicate check → `FaceEnrollment.enroll` → `EmployeeService.create` (rolls back FAISS on DB failure) |

**Workflow:** form → capture → confirm → embedding → FAISS + DB → success →
"Enroll Another" or "View Employees".

### Page 04 — Live (📹 Live Recognition) ⭐
The most complex page. See §10.2 for architecture and §13 for camera system.

| Element | Description |
|---------|-------------|
| **Camera select** | PC/USB/Android/iPhone/IP with per-type config (`_render_camera_config`) |
| **Scan Cameras** | `scan_local_cameras()` + `scan_network()` discovery results |
| **START/STOP** | `_start_recognition()` / `_stop_recognition()` via `CameraOwner` |
| **Status badge** | LIVE / CONNECTING / RECONNECTING / DISCONNECTED / READY |
| **Video area** | Latest frame + overlays from `results_buffer` (drawn at display time) |
| **Sidebar live stats** | Capture FPS, AI FPS, pipeline latency, people count, worker errors, E2E latency p50/p95 |
| **Today's attendance** | Cached table (3 s TTL) |

### Page 05 — Attendance (📋 Records + Live Camera)
| Element | Description |
|---------|-------------|
| **Camera mode** | Browser Webcam (WebRTC, needs `streamlit-webrtc`) or Phone/IP Camera (`PhoneAttendanceFeed` background thread) |
| **Live camera** | WebRTC transformer `AttendanceVideoTransformer` (uses `LiveDetection`), or phone feed preview |
| **Today's summary** | Total Marks, Unique Present, All-Time Records, Employees Ever Marked |
| **Historical records** | Date picker, Export CSV, Refresh; per-date table + stats (unique, avg confidence) |
| **Pipeline debug** | Expander with config + status |
| **Auto-refresh** | Every 5 s when camera active |

### Page 06 — Unknown (🔴 Gallery + Review)
| Element | Description |
|---------|-------------|
| **Stats** | Today, This Week, Pending Review, Converted |
| **Bulk actions** | Delete All (with count), warning |
| **Filters** | Date range, Status (All/Not Reviewed/Reviewed/Converted), Max results |
| **Face cards** | Image, time, camera, confidence, status badge (Converted/Ignored/Unreviewed); actions: Register Employee, Ignore, Delete, Notes |

**Workflow:** unknown face captured by pipeline → admin reviews → convert to
employee (via `UnknownFaceService.convert_to_employee`) or ignore/delete.

### Page 07 — Analytics (📈 Charts)
Charts (Plotly):
1. Daily Attendance (bar, last 30 days)
2. Hourly Attendance (bar)
3. Top Employees (horizontal bar)
4. Recognition Accuracy (known vs unknown pie)
5. Department Distribution (pie)
6. Recognition Confidence Distribution (histogram)

### Page 08 — Settings (⚙️ Config Editor)
Full configuration editor over `settings.yaml` via `cfg.save_settings()`
(comment-preserving), plus camera diagnostics. **Verify:** camera source,
recognition thresholds, AMFR weights, deep liveness, unknown-face retention,
logging.

### Page 09 — Health (🩺 System Health)
Live component monitoring + quick-fix buttons (model reload, DB check,
camera diagnostic). Pairs with `tools/validate_startup.py`.

### Page 10 — About (ℹ️)
Version info, technology stack, credits.

## 10.2 Live Page Internals (the heart of the UI)

### `SharedModelResources` (dataclass)
- `load()` caches a `RecognitionService` as a class attribute `_cache`.
- All heavy models (YOLO, InsightFace, FAISS, AMFR) load **once**.
- New pipelines use `RecognitionService.with_shared_models(shared.service)`
  → independent per-camera state, shared models.

### `LiveRecognitionPipeline`
- **start()** — `create_camera(source_type, **kwargs)` → open → set 640×480,
  FPS cap 15 → start 3 daemon threads:
  1. `_capture_loop` — reads camera, puts **latest raw frame** into
     `frame_buffer` at capture rate; handles reconnect (up to 5 attempts).
  2. `_recognition_worker` — pulls latest frame, downscales to 320×240,
     runs `process_frame_detailed()`, scales bboxes back, caches verified
     track IDs for **adaptive cadence** (0.10 s normal → 0.60 s when all
     tracks verified & fresh), publishes to `results_buffer`.
  3. `_latency_loop` — records E2E frame age (now − put timestamp) into
     `LatencyLogger` every 0.05 s while LIVE.
- **stop()** — joins threads (3 s timeout), releases camera, clears buffers.
- **Overlays** — `_draw_overlays()`: green ✓NAME+PRESENT (ACCEPT), red
  ⚠SPOOF (REJECT), yellow NAME? COLLECTING FRAMES (BORDERLINE), grey
  ?UNKNOWN (LOW_CONFIDENCE); sublines for ID/department/confidence/liveness.

### Thread-safe buffers
- `frame_buffer` (FrameBuffer, maxlen=1) — latest raw frame, drops stale.
- `results_buffer` (ResultsBuffer, maxlen=1) — latest recognition results.
- Both in `dashboard/frame_buffer.py`, shared module-level singletons.

### `CameraOwner` (singleton)
Guarantees **one camera owner at a time**; `acquire()/release()` manage
state FREE → ACQUIRED → FREE; teardown happens outside the state lock so
slow `pipeline.stop()` never blocks concurrent checks. Survives Streamlit
reruns via `st.session_state.pipeline`.

## 10.3 Widget & Interaction Summary

| Widget | Pages | Purpose |
|--------|-------|---------|
| `st.metric` | 1,2,5,6 | KPI cards |
| `st.dataframe` | 1,2,5,6 | Tabular data |
| `st.selectbox` | 2,3,4,5,8 | Source/entity selection |
| `st.text_input` / `st.number_input` | 2,3,4,5,8 | Form fields |
| `st.form` | 2,3 | Submission + validation |
| `st.camera_input` | 3 | Browser webcam capture |
| `st.image` | 4,5,6 | Video frames / photos |
| `st.button` / `st.download_button` | 1,4,5,6 | Actions / CSV export |
| `st.expander` | 1,2,5,6,8 | Progressive disclosure |
| `st.rerun` / `st.switch_page` | 1,3,4,5,8 | Navigation & refresh |
| `st.cache_data` / `st.cache_resource` | 1,4,5,7 | Caching (SQL/DF/models) |
| `st.session_state` | 3,4,5,8 | Survive reruns |

## 10.4 Dashboard Data Sources

| Page | Services/Repos used |
|------|---------------------|
| Dashboard | EmployeeRepo, AttendanceRepo, RecognitionLogRepo, UnknownFaceRepo, CameraRepo, FaceEnrollment |
| Employees | EmployeeService, AttendanceRepo |
| Enroll | FaceRecognizer, FaceEnrollment, EmployeeService |
| Live | RecognitionService, AttendanceService, CameraOwner, buffers |
| Attendance | AttendanceService, EmployeeRepo, LiveDetection, CameraSource |
| Unknown | UnknownFaceService, CameraRepo |
| Analytics | AttendanceRepo, RecognitionLogRepo, UnknownFaceRepo, EmployeeRepo |

---

*References: `dashboard/app.py`, `dashboard/pages/*`, `dashboard/frame_buffer.py`,
`dashboard/camera_owner.py`, `dashboard/latency_logger.py`, `docs/USER_MANUAL.md`*
