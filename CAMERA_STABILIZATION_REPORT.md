# CAMERA STABILIZATION REPORT

**Status:** Stabilization fixes implemented; regression suite green; **real-camera
performance validated on hardware (Camera #0).** The camera → smooth feed → latency
chain is now measured. The **face-detection → green box → attendance → PRESENT** path
still requires an enrolled person standing in front of the camera (see §6/§7).

---

## 1. Root Causes Found

### Critical (would crash the Live page)

| # | File | Root cause |
|---|------|------------|
| 1 | `dashboard/frame_buffer.py` | Only **classes** `FrameBuffer`/`ResultsBuffer` were defined. `dashboard/pages/04_Live.py` imports module-level **singletons** `frame_buffer` / `results_buffer` (lines 163, 189, 396, 848) → `ImportError`/`NameError` the moment the Live page ran. |
| 2 | `dashboard/camera_owner.py` | `acquire()` referenced `pipeline_id`, a variable that **does not exist** in that scope → `NameError` on every START click. |
| 3 | `dashboard/pages/04_Live.py` | Results-buffer type mismatch: producer stored `results[0]` (a dict) but the page consumed it as a list (`results[0]` / `enumerate(results)` with `.get()`) → `KeyError`/`AttributeError` on recognized faces. |
| 4 | `dashboard/pages/04_Live.py` | `_start_recognition()` checked `can_acquire()` **before** releasing a stale acquisition. If a previous run left `CameraOwner` in `ACQUIRED` state, START would be permanently blocked. |
| 5 | `database/repository.py` | **Found during real-camera validation:** `RecognitionLogRepo.create()` did not accept `liveness_confidence` (or `is_spoof`/`track_id`), but `RecognitionService._log_recognition()` passes it → `TypeError: unexpected keyword argument` → **every recognition event silently failed to log** (warning only, no crash). The `RecognitionLog` model *does* have the columns; the repo just didn't forward them. |

### Path-inconsistency question (Priority 2) — resolved

The report flagged a `dashboard/frame_buffer.py` **vs** `camera/frame_buffer.py` inconsistency. **Verified: there is no `camera/frame_buffer.py` anywhere** — main tree, `heady-sight`, and `patch-tractor` worktrees all contain no such file, and every import in the codebase points to `dashboard.frame_buffer`. The only real problem was the missing **module-level singletons** in that canonical module (root cause #1 above). The canonical implementation is now explicitly documented as `dashboard/frame_buffer.py`.

---

## 2. Files Changed

| File | Change |
|------|--------|
| `dashboard/frame_buffer.py` | Canonical buffer hardened: added module-level singletons `frame_buffer` / `results_buffer`, per-frame IDs + wall-clock timestamps, `get_with_meta()`, `close()` shutdown, `is_closed`, canonical-path docstring. Still latest-frame-only (1 slot), thread-safe, never queues. |
| `dashboard/camera_owner.py` | Fixed `acquire()` NameError; documented `can_acquire()` param; moved pipeline/camera teardown **outside** the state lock in `release()` so a slow `stop()` (thread join ≤3s) never blocks concurrent `can_acquire()`/`acquire()`. |
| `dashboard/pages/04_Live.py` | Module-level singleton imports; `_capture_loop` pushes the full results list; `latest()` consumes list; `_stop_recognition(quiet=...)`; `_start_recognition()` releases stale ownership **first**, then acquires (no double-stop). |
| `database/repository.py` | `RecognitionLogRepo.create()` now accepts & persists `liveness_confidence`, `is_spoof`, `track_id` (fixes silent recognition-log failure). |
| `services/recognition_service.py` | `_log_recognition()` now forwards `is_spoof` to the repo (was only forwarding `liveness_confidence`). |
| `scripts/benchmarks/camera_validation.py` | **New** — real-camera validation harness (capture/display/recognition FPS, E2E P50/P95 latency, dropped frames, model pre-warm, try/finally camera release). |
| `scripts/benchmarks/probe_environment.py` | **New** — environment probe (cameras, enrollment, DB, models). |
| `tests/test_frame_buffer.py` | **New** — 44 tests: latest-only semantics, drop-stale, copy semantics, frame IDs/timestamps, thread-safety, close/shutdown, singletons. |
| `tests/test_camera_owner.py` | **New** — singleton, single-owner, START→STOP→START, release semantics, error handling, thread-safety (only 1 of N concurrent acquires wins). |
| `.gitignore` | Ignore generated `backups/*` artifacts, keep `backups/README.md`. |
| `backups/README.md` | **New** — documents why backup artifacts are git-ignored. |

Unrelated modified files (`config/settings.yaml`, `scripts/benchmarks/faiss_benchmark.py`) were **not** touched — they remain separate from the camera work per Priority 8.

---

## 3. Test Results (regression)

```
pytest tests/                                   → 443 passed, 21 warnings (89s)
pytest tests/test_frame_buffer.py test_camera_owner.py → 44 passed (1.4s)
pytest tests/test_repair.py                     → 87 passed (14.8s)  # Live page import + lifecycle + overlays
```

All tests pass. The Live-page import test (`_import_live_page`) now exercises the new singleton imports and succeeds.

---

## 4. Real-Camera Performance (measured on hardware)

**Environment:** Camera #0 (DirectShow, 640×480, DSHOW backend) · Windows ·
Python 3.12 · CPU inference · 1 enrolled embedding ("TestUser") · SQLite.
Method: `python scripts/benchmarks/camera_validation.py --seconds 8`. Two stable
runs are reported (the first, instrumentation-fixing run is excluded).

### Raw camera → FrameBuffer → display consumer (no AI)

| Metric | Run A | Run B | Notes |
|--------|-------|-------|-------|
| **Capture FPS** | 29.5 | 29.5 | Rate of successful `cam.read()` |
| **Display FPS** | 19.3 | 19.4 | Streamlit-style consumer read rate (~20Hz cadence, matches `04_Live.py`) |
| **Dropped frames** | 82 | 81 | Frames overwritten before first display (producer faster than consumer) |
| **E2E latency P50** | 16.1 ms | **16.7 ms** | Capture→put→first-display (time-to-first-display per unique frame) |
| **E2E latency P95** | 31.4 ms | **31.7 ms** | Includes display-sampling delay |

The feed is smooth: capture sustains ~29fps, the display loop keeps up at ~19–20fps,
and end-to-end latency is ~17ms median / ~32ms P95 — well within interactive range.

### Camera → full AI pipeline (YOLO11 → RetinaFace → Quality → Liveness → ArcFace → FAISS → AMFR)

| Metric | Run A | Run B | Notes |
|--------|-------|-------|-------|
| **Recognition FPS** | 2.8 | 2.5 | AI frames processed/sec (frame_skip=2, 320×240 input) |
| **AI latency P50** | 284.1 ms | 333.8 ms | Per `process_frame_detailed()` |
| **AI latency P95** | 689.5 ms | 760.1 ms | |

**Interpretation:** the video is smooth and live, but full AMFR inference is the
bottleneck (~2.5–2.8 AI frames/sec on CPU, ~335ms median per frame). This is expected
with `frame_skip=2` + 320×240 downscale on CPU. Face boxes drawn from the last AI pass
will update ~2–3×/sec while the raw feed stays fluid. If decision refresh rate needs to
improve: lower `frame_skip` to 1 (processes every frame — roughly doubles the AI decision
rate and CPU load), enable GPU/ONNX providers, or process at 256×192.

**Run-to-run variance:** AI-latency numbers vary substantially between runs (P50 ranged
~26ms to ~334ms across this session — warm-up state and CPU load). Treat the AI FPS/
latency figures as a range, not fixed values. First run on a fresh checkout also
downloads the deep-liveness ONNX model (~20s, written to `models/liveness/`); that disk
side effect is not suppressed by `--no-write` (which only patches pipeline DB/disk
writes).

---

## 5. START / STOP / Camera-Switch Results

Automated verification (mocked `CameraSource`) **plus** real-camera START/STOP during
the harness runs:

| Check | Result |
|-------|--------|
| Only one owner per physical camera | ✅ `test_concurrent_acquire_only_one_wins` — exactly 1 of 10 concurrent acquires succeeds |
| Streamlit reruns do not reopen camera | ✅ Singleton buffers + session-state pipeline survive reruns; camera opens only in `pipeline.start()` |
| START → STOP → START repeatedly | ✅ `test_start_stop_start_works`, `test_previous_camera_released_before_next_acquire`; harness opened/closed camera twice cleanly |
| Camera released on STOP | ✅ `test_release_releases_camera`, `test_release_clears_references` |
| No stale camera objects remain | ✅ `test_no_stale_objects_after_cycle` (camera/pipeline None, state FREE, owner_id None) |
| Duplicate capture threads | ✅ Single thread per pipeline; STOP joins it (timeout 3s) |
| Camera failure/disconnect | ✅ `test_repair.py` disconnect tests: status → DISCONNECTED/RECONNECTING, no crash |
| Release under exceptions | ✅ `test_release_handles_errors_gracefully` — teardown never raises |

**Real-camera observation:** Camera #0 opened and delivered frames successfully in both
validation runs; capture thread started and stopped cleanly each time with no camera
lock or leftover handle.

---

## 6. Recognition / Attendance Results

### Automated (unit-level)

| Flow | Verification |
|------|--------------|
| AMFR ACCEPT → employee lookup → AttendanceService → mark once | ✅ `test_repair.py::TestAttendanceDedup` (mark-once, session cache, cooldown) |
| GREEN box / name / ID / PRESENT label | ✅ `test_repair.py::TestOverlays` (green for ACCEPT, red for spoof, grey unknown, yellow borderline, ID subline) |
| Spoof → RED box + REJECT_SPOOF, no attendance | ✅ `test_repair.py` overlay + `recognition_service` spoof path |
| Result dict completeness (`attendance_marked`, `track_id`, `emp_id`, `emp_name`) | ✅ `test_repair.py::TestResultDictStructure` |

### Real-camera run (8s window)

- Pipeline ran end-to-end with the real camera: **20–24 AI frames processed**, no
  crashes, camera released cleanly.
- **No face was in front of the camera** during the automated window → every detection
  returned `LOW_CONFIDENCE` / `Unknown`. Attendance was therefore **not** exercised.
- **Bonus bug found & fixed:** recognition-log `TypeError` (root cause #5) — the live
  pipeline was logging recognition events silently to stderr instead of the DB. Fixed
  in `database/repository.py` + `services/recognition_service.py`.

---

## 7. Remaining Issues / Before-Merge Checklist

**Real-camera items still requiring a person in front of the camera (cannot be
automated):**

1. [ ] Enrolled person stands in front of camera → **GREEN BOX → name → student ID →
      AMFR ACCEPT → PRESENT** and a new attendance row appears (SQLite/PostgreSQL).
2. [ ] Unknown person → grey **UNKNOWN / Not Enrolled**, no attendance.
3. [ ] Spoof attempt (where test data/hardware permits) → RED box `REJECT_SPOOF`, no
      attendance, audit `SPOOF_ATTEMPT` row written.
4. [ ] Multi-person scene: all boxes drawn, attendance marked once per person.
5. [ ] Live UI session: START → STOP → START with real camera; switch PC/USB camera;
      page navigation + return; USB disconnect/reconnect mid-session.

**Done on real hardware (this run):**
- ✅ Camera opens, streams ~29fps, display keeps up (~19–20fps), E2E latency
  P50 16.7ms / P95 31.7ms.
- ✅ AI pipeline executes continuously without crashing; recognition FPS ~2.5.
- ✅ Camera released cleanly on STOP; no lock, no stale handle.

**Known non-blocking notes:**
- Recognition decision refresh is AI-bound (~2.5fps, P95 ~760ms) — see §4 tuning options.
- `_mock_st` Live-page importer emits a `PytestRemovedIn10Warning` for class-scoped
  fixtures (pre-existing; not part of this change).
- Redis `setex` deprecation warnings in `test_integration.py` (pre-existing).
- The FAISS benchmark edits remain un-merged; they are unrelated to camera
  stabilization (Priority 8).

**Validation tooling:**
- `python scripts/benchmarks/camera_validation.py --seconds 8 --no-write` — rerun
  anytime to re-measure FPS/latency on hardware **without writing to the production
  DB/disk** (patches unknown-face, recognition-log, attendance, and audit writes).
  Omit `--no-write` only when you specifically want to exercise the attendance
  write path (requires a face in front of the camera).
- `python scripts/benchmarks/probe_environment.py` — environment summary.
- `tools/diagnose_cameras.py` — camera connectivity diagnostics.

---

## 8. Summary

Four fatal runtime bugs (missing singletons, `pipeline_id` NameError, results-list/dict
mismatch, START-ordering deadlock) **plus one production data-integrity bug found during
real-camera validation** (silent recognition-log `TypeError`) are fixed. Canonical frame
buffer location is confirmed and documented. 44 new unit tests cover the camera-ownership
and frame-buffer requirements; the full regression suite (443 tests) passes. Real-camera
performance is now measured: smooth 29fps capture / 19–20fps display / 17–32ms E2E latency
with ~2.5fps AMFR inference on CPU. **Merge waits only on the person-in-front-of-camera
verification of the green-box → attendance → PRESENT flow** (checklist §7).
