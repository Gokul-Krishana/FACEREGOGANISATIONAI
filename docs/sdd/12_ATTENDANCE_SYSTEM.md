# Section 12 — Attendance System

## 12.1 Simple Explanation

A person walks in front of the camera. The system recognizes their face,
checks they haven't already been marked today, and records their attendance
with a timestamp and confidence score — in **both** the database and a
per-day CSV file. The dashboard then shows today's attendance, and analytics
produce reports.

## 12.2 Complete Workflow

```
Student/Employee enters camera view
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  Recognition pipeline (YOLO → RetinaFace → Quality →    │
│  Liveness → ArcFace → FAISS)                             │
└─────────────────────────────────────────────────────────┘
        │
        ▼
AMFR decision engine
   ├─ ACCEPT ─────────────► ─┐
   ├─ BORDERLINE ──────────►  │ (collect more frames)
   ├─ LOW_CONFIDENCE ─────►  │ (save unknown face)
   └─ REJECT_SPOOF ────────►  │ (alert + audit, NO attendance)
                             ▼
                    ┌─────────────────────┐
                    │ _maybe_mark_attendance│  (RecognitionService /
                    │  / AttendanceService  │   LiveDetection)
                    └─────────────────────┘
        │ checks
        ▼
  1. Session cooldown?  (COOLDOWN_SECONDS=60, per name)
  2. Already marked today in DB?  (AttendanceRepo.is_marked_today)
        │
        ▼  (both clear)
┌─────────────────────────────────────────────────────────┐
│  WRITE                                                │
│  • DB: attendance row (employee_id, confidence,        │
│        timestamp, method=FACE_RECOGNITION,             │
│        status=PRESENT, camera_id)                      │
│  • CSV: attendance/YYYY-MM-DD.csv                      │
│  • Audit: AuditService.log("MARK_ATTENDANCE", ...)     │
│  • RecognitionLog row (is_known=True, liveness,        │
│        quality, track_id)                              │
└─────────────────────────────────────────────────────────┘
        │
        ▼
Dashboard: Live page shows "✓ NAME · PRESENT"
Attendance page: today's table updates (5 s auto-refresh)
Analytics: daily/hourly charts update
```

## 12.3 Dual-Write Design (why both DB and CSV?)

| Store | Purpose | Who reads it |
|-------|---------|--------------|
| SQLite/PostgreSQL `attendance` | Structured queries, analytics, API | Dashboard, API, analytics |
| `attendance/YYYY-MM-DD.csv` | Backward compatibility with the original CLI (`app/attendance.py`) | CLI mode, manual inspection, simple exports |

`AttendanceService.mark()` writes both; `LiveDetection._log_attendance_db()`
writes the DB side for the CLI pipeline. The CSV logger can be deprecated
once the terminal app is fully replaced (noted in the service docstring).

## 12.4 Deduplication (preventing double-marking)

Three layers prevent duplicates:
1. **Session cache** — `_marked_this_session` set (per pipeline/session).
2. **Cooldown** — per-name timestamp; only re-marks after
   `COOLDOWN_SECONDS` (default 60 s) AND a session reset.
3. **Database** — `AttendanceRepo.is_marked_today()` checks for an existing
   row for the employee today before inserting.

Result: exactly **one attendance record per person per day** (per employee).

## 12.5 Data Model Fields

| Field | Source | Notes |
|-------|--------|-------|
| employee_id / student_id | recognition lookup | employee path is active |
| section_id / course_id / classroom_id | API manual mark (timetable-aware) | optional |
| camera_id | pipeline | which camera captured |
| timestamp | `_utcnow()` | when marked |
| confidence | AMFR risk score | 0–1 |
| method | `FACE_RECOGNITION` (or manual) | |
| status | `PRESENT` (or ABSENT/LATE/EXCUSED via API) | |
| marked_manually / marked_by_user_id / manual_notes | API manual override | audit trail for corrections |

## 12.6 Attendance Queries & Reports

| Query | Implementation |
|-------|----------------|
| Today's records | `AttendanceRepo.get_today()` / `AttendanceService.get_today()` |
| By date | `get_by_date(date)` |
| By employee | `get_by_employee(id)` (history) |
| Statistics | `get_statistics()` → today_count, unique_today, total_records, unique_employees |
| Dashboard cards | Dashboard page via `get_home_stats()` (10 s cache) |
| Charts | Analytics page: daily/hourly bars, top employees, confidence histogram |
| CSV export | Attendance page download button; `api/bulk_operations.py export_attendance_csv()` |
| API | GET `/attendance` (filters + pagination); POST `/attendance` (manual) |

## 12.7 Timetable-Aware Attendance (API layer)

`api/attendance_service.py` adds college semantics for manual marks:
- `is_class_in_session()` — checks weekday + time against `timetables`
  with a 10-minute grace period.
- `is_student_enrolled()` — student must be an ACTIVE enrollment in the section.
- `create_attendance()` — derives course/classroom/section when possible and
  rejects non-enrolled students.

> **Note:** the live camera pipeline marks attendance by *employee* (legacy
> path). Student/timetable-aware marking is available via the API and is the
> intended college path per the schema.

## 12.8 Reset & Session Semantics

- **Reset Session Markers** (Live page) → `reset_tracking()` clears the
  session set + cooldowns + AMFR tracker state → people can be re-marked.
- **Per-day reset** is automatic (dedupe checks today's date).
- **CLI:** pressing `R` clears `_marked_this_session`.

## 12.9 Failure Handling

- If DB write fails (e.g. DB down), the pipeline logs a warning and
  **does not crash** — CSV may still record the event.
- `_log_attendance_db()` silently returns when no employee record exists
  (unknown person → unknown-face path instead).
- Recognition logs are best-effort (`logger.warning` on failure).

---

*References: `app/attendance.py`, `services/attendance_service.py`,
`services/recognition_service.py`, `api/attendance_service.py`,
`database/repository.py`, `dashboard/pages/05_Attendance.py`*
