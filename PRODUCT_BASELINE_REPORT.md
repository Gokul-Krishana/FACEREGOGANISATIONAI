# Product Baseline Report

**Date:** 2026-07-30  
**Commit:** `c484b7c` (feat: configurable FAISS indexes)  
**Project:** FaceRecognitionAI

---

## 1. Test Suite Summary

| Metric | Value |
|--------|-------|
| Collected | 371 (with integration) |
| Passed | 339 |
| Failed | 0 |
| Skipped | 6 (Redis unavailable) |
| Errors | 1 (FK teardown in integration test) |
| Warnings | 14 (matplotlib deprecation) |
| Runtime | 61.6s |

## 2. Architecture

### Camera Layer (8 cv2.VideoCapture call sites)

| File | Location | Purpose |
|------|----------|---------|
| `camera/webcam.py` | Lines 60, 62, 133, 160, 162, 255, 257 | Core camera implementation |
| `camera/phone.py` | Lines 85, 181, 194, 288, 390, 485, 487 | Android/iPhone/IP cameras |
| `camera/selector.py` | Line 294 | Camera discovery |
| `app/live_detection.py` | Lines 299, 301, 389 | Legacy detection |
| `main.py` | Line 264 | CLI tool |
| `dashboard/pages/04_Live.py` | Line 410 | Camera scan |
| `dashboard/pages/09_Health.py` | Line 59 | Health check |
| `dashboard/pages/08_Settings.py` | Lines 329, 331 | Settings |

**Issue:** 8 files independently open cameras - risk of conflicting camera ownership.

### Database Layer

| Table | Purpose | Status |
|-------|---------|--------|
| `students` | Primary student records | ✅ Exists |
| `employees` | Legacy employee records | ⚠️ Dual identity path |
| `attendance` | Attendance records (FK to both students + employees) | ✅ Exists |
| `unknown_faces` | Unknown snapshots | ✅ Exists |
| `cameras` | Camera registry | ✅ Exists |
| `audit_logs` | Audit trail | ✅ Exists |

**Issue:** Dual `Student` + `Employee` identity path creates confusion.

### AI Pipeline

| Component | Status | Notes |
|-----------|--------|-------|
| YOLO11 detection | ✅ Working | Single shared instance |
| Multi-frame tracking | ✅ Working | Per-track state |
| RetinaFace detection | ✅ Working | Via InsightFace |
| Face Quality | ✅ Working | Configurable threshold |
| Deep Liveness | ✅ Working | CNN-based anti-spoof |
| ArcFace 512-D | ✅ Working | `buffalo_l` model |
| FAISS (Flat/IVF/HNSW) | ✅ Working | Configurable index type |
| AMFR | ✅ Working | Composite risk scoring |

## 3. Bug Fix Status (From Critical Repair Phase)

| # | Bug | Status | Fix |
|---|-----|--------|-----|
| 1 | Attendance never auto-marked | ✅ FIXED | `get_by_name()` lookup instead of `get_by_employee_id()` |
| 2 | No PRESENT shown | ✅ FIXED | `attendance_marked` propagated to result dicts |
| 3 | Disk flooding with unknowns | ✅ FIXED | 3-second cooldown in `_handle_unknown_face` |
| 4 | Deleted employee still recognized | ✅ FIXED | `remove_by_name()` after DB delete |
| 5 | Repeated DB calls after restart | ✅ FIXED | Session cache updated even on `mark()`=False |

## 4. PostgreSQL Validation

| Component | Status |
|-----------|--------|
| PostgreSQL server | ✅ Available on localhost:5432 |
| Alembic migrations | ✅ Applied correctly (PostgresqlImpl) |
| FastAPI server | ✅ Running on port 8000 |
| Attendance writes | ✅ Verified in PostgreSQL |
| Duplicate prevention | ✅ Verified |
| Integration tests | ✅ 11/11 PostgreSQL tests pass |

## 5. Redis Status

| Component | Status |
|-----------|--------|
| Redis server | ❌ Not available locally |
| Fallback behavior | ✅ Verified graceful degradation |
| Cooldown caching | ⚠️ In-memory fallback active |

## 6. Test Coverage (test_repair.py)

| Category | Tests | Status |
|----------|-------|--------|
| Pipeline lifecycle | 8 | ✅ All pass |
| Overlay drawing | 14 | ✅ All pass |
| Camera disconnect | 2 | ✅ All pass |
| Thread safety | 2 | ✅ All pass |
| Attendance dedup | 7 | ✅ All pass |
| Result dict structure | 7 | ✅ All pass |
| Unknown face cooldown | 3 | ✅ All pass |
| Employee service + FAISS | 3 | ✅ All pass |
| FAISS remove_by_name | 6 | ✅ All pass |
| Employee lookup | 4 | ✅ All pass |
| Full regression | 2 | ✅ All pass |
| **Total** | **59** | **✅ 59/59 pass** |

## 7. Known Issues

| Issue | Severity | Area |
|-------|----------|------|
| Dual Student/Employee identity | MEDIUM | Database |
| FK teardown error in integration test | LOW | Test/infrastructure |
| Redis not available locally | MEDIUM | Infrastructure |
| Health endpoint returns hardcoded "connected" for Redis | LOW | API |
| Camera opened from 8 different call sites | HIGH | Architecture |
| No startup validation | MEDIUM | Operations |
| Scattered logger usage (mix of print, logging, st.warning) | LOW | Code quality |

## 8. P0 Readiness

| Flow | Status |
|------|--------|
| PC Camera → Live Video | ✅ PARTIAL (code exists, verified via unit tests) |
| Known Student → Green Box | ✅ PARTIAL (fixes applied, overlay logic tested) |
| Name + Student ID | ✅ FIXED (employee lookup chain verified) |
| AMFR ACCEPT | ✅ Existing (never disabled) |
| Attendance Stored → PRESENT | ✅ FIXED (attendance_marked propagated) |
| Employee Delete + FAISS Sync | ✅ FIXED (tested with real FAISS) |
| Unknown Delete + Bulk Delete | ✅ PARTIAL (tested at repo level) |
| **Overall** | **🟡 PARTIAL** — core flow repaired, full E2E hardware test pending |
