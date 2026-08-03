# Database Schema — Face Recognition AI

**Version:** 2.0.0
**Date:** 2026-08-02
**Source of truth:** `database/models.py` + Alembic migrations (`alembic/versions/`)

---

## 1. Overview

The system uses SQLAlchemy ORM with two supported backends:

| Backend | Use case | Driver |
|:--------|:---------|:-------|
| **SQLite** | Development / pilot demo | built-in `sqlite3` |
| **PostgreSQL** | Production (college deployment) | `psycopg2` |

Migrations are managed with **Alembic** (3 revisions, head `9c4d2f6a7b11`).

```
institutions ─┬─ departments ─┬─ courses ──── sections ─┬─ timetables ── classrooms
              │               │                        └─ enrollments ── students
              │               └─ staff (faculty)
              └─ classrooms
employees (legacy/back-compat)
cameras ── unknown_faces ── recognition_log
attendance (FK to students / employees / sections / classrooms / staff / cameras / users)
users ─┬─ roles (RBAC) ── permissions
       └─ refresh_tokens / failed_login_attempts / audit_logs
```

> **Design note (Student vs Employee):** The college-scale schema stores
> recognised people as **`students`** (with `department_id`, enrolment year).
> The **`employees`** table is the *legacy recognition table* — it is what the
> live pipeline (`RecognitionService`) actually writes attendance against and
> what FAISS embeddings are linked to via `faiss_id`. Both identities are
> supported by the `attendance` table (nullable `student_id` + `employee_id`
> FKs). Consolidating the two into one identity table is a **future migration**
> item; it is intentionally not done in this release to preserve the working
> recognition path end-to-end.

---

## 2. Table Reference

### 2.1 `institutions`
College/university master records.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | autoincrement |
| `name` | String(255) | required |
| `code` | String(20) | unique, required |
| `address` | Text | |
| `phone` | String(20) | |
| `email` | String(255) | |
| `is_active` | Boolean | default `true` |

Relationships: `departments`

### 2.2 `departments`
Academic departments. **Note:** `head_id` FK uses `use_alter=True` with a
named constraint (`fk_departments_head_id`) to break the circular FK with
`staff`.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `institution_id` | FK → `institutions.id` | required |
| `name` | String(255) | required |
| `code` | String(20) | required |
| `head_id` | FK → `staff.id` | nullable, `use_alter=True` |
| `is_active` | Boolean | default `true` |

Unique: `(institution_id, code)`. Indexed: `idx_department_inst_code`.

### 2.3 `courses`
Course catalog.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `department_id` | FK → `departments.id` | required |
| `code` | String(50) | required |
| `name` | String(255) | required |
| `credits` | Integer | default 3 |
| `description` | Text | |
| `is_active` | Boolean | default `true` |

Unique: `(department_id, code)`.

### 2.4 `sections`
Course sections (e.g. "CSE-A", semester groups).

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `course_id` | FK → `courses.id` | required |
| `section_name` | String(50) | required |
| `semester` | String(20) | required |
| `year` | Integer | required |
| `max_capacity` | Integer | |

### 2.5 `classrooms`
Physical locations.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `institution_id` | FK → `institutions.id` | required |
| `building` | String(100) | required |
| `room_number` | String(20) | required |
| `capacity` | Integer | |
| `floor` | String(20) | |
| `is_active` | Boolean | default `true` |

Unique: `(building, room_number)`.

### 2.6 `timetables`
Class schedule (when/where a section meets).

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `section_id` | FK → `sections.id` | required |
| `classroom_id` | FK → `classrooms.id` | required |
| `day_of_week` | Integer | 0=Mon … 6=Sun |
| `start_time` | String(8) | `HH:MM:SS` |
| `end_time` | String(8) | `HH:MM:SS` |
| `instructor_id` | FK → `staff.id` | nullable |

### 2.7 `students`
Student records (the primary college identity table).

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `student_id` | String(20) | unique, required (e.g. `2021CSE001`) |
| `name` | String(100) | required |
| `email` | String(255) | |
| `phone` | String(20) | |
| `department_id` | FK → `departments.id` | nullable |
| `enrollment_year` | Integer | |
| `graduation_year` | Integer | |
| `is_active` | Boolean | default `true` |
| `created_at` | DateTime | UTC |

Indexed: `idx_student_id` (unique), `idx_student_name`, `idx_student_department_active`.

### 2.8 `staff`
Faculty / instructors.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `employee_id` | String(20) | unique, required |
| `name` | String(100) | required |
| `email` | String(255) | |
| `phone` | String(20) | |
| `department_id` | FK → `departments.id` | nullable |
| `position` | String(100) | |
| `is_active` | Boolean | default `true` |
| `created_at` | DateTime | |

### 2.9 `employees`
**Legacy recognition table** — the table the live pipeline writes against.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `employee_id` | String(20) | unique, required |
| `name` | String(100) | required — matches FAISS metadata label |
| `department` | String(100) | |
| `photo_path` | String(500) | |
| `faiss_id` | Integer | nullable — index position in FAISS |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

**Identity path:** FAISS metadata name → `EmployeeRepo.get_by_name()` (fallback
`get_by_employee_id`) → `employees.id` → `attendance.employee_id`. Renaming or
deleting an employee keeps FAISS in sync (see `EmployeeService.update/delete`).

### 2.10 `enrollments`
Student ↔ section membership.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `student_id` | FK → `students.id` | required |
| `section_id` | FK → `sections.id` | required |
| `enrollment_date` | DateTime | |
| `status` | String(20) | default `ACTIVE` |

Unique: `(student_id, section_id)`.

### 2.11 `cameras`
Centralised camera configuration with credential references.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `name` | String(100) | required |
| `camera_index` | Integer | local device index |
| `camera_id` | String(50) | unique (UUID/custom) |
| `stream_url` | String(500) | RTSP/HTTP URL |
| `credential_ref` | String(255) | **reference only, never the password** |
| `location` | String(200) | |
| `building` | String(100) | |
| `room` | String(50) | |
| `classroom_id` | FK → `classrooms.id` | nullable |
| `is_active` | Boolean | default `true` |
| `status` | String(20) | default `OFFLINE` (LIVE/RECONNECTING/…) |
| `last_seen` | DateTime | |
| `fps` | Integer | |
| `resolution` | String(20) | |
| `created_at` / `updated_at` | DateTime | |

### 2.12 `attendance`
Timetable-aware attendance records. **`employee_id` is the production path**;
`student_id` is supported for the college-schema path.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `student_id` | FK → `students.id` | nullable |
| `employee_id` | FK → `employees.id` | nullable |
| `section_id` | FK → `sections.id` | nullable |
| `course_id` | FK → `courses.id` | nullable |
| `classroom_id` | FK → `classrooms.id` | nullable |
| `instructor_id` | FK → `staff.id` | nullable |
| `camera_id` | FK → `cameras.id` | nullable |
| `timestamp` | DateTime | indexed, default UTC now |
| `recognized_at` | DateTime | |
| `confidence` | Float | default 1.0 |
| `method` | String(50) | default `FACE_RECOGNITION` |
| `status` | String(20) | default `PRESENT` |
| `marked_by_user_id` | FK → `users.id` | manual override |
| `marked_manually` | Boolean | default `false` |
| `manual_notes` | Text | |

Indexed: `timestamp`, `(student_id, timestamp)`, `(student_id, section_id)`,
`(course_id, timestamp)`, `(camera_id, timestamp)`.

### 2.13 `recognition_log`
One row per recognition event (analytics / audit).

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `employee_id` | FK → `employees.id` | nullable |
| `student_id` | FK → `students.id` | nullable |
| `is_known` | Boolean | required |
| `confidence` | Float | |
| `liveness_confidence` | Float | |
| `is_spoof` | Boolean | default `false` |
| `track_id` | String(50) | ByteTrack-style track ID |
| `timestamp` | DateTime | indexed |
| `camera_id` | FK → `cameras.id` | |
| `classroom_id` | FK → `classrooms.id` | |
| `section_id` | FK → `sections.id` | |
| `face_snapshot_path` | String(500) | |
| `embedding_path` | String(500) | |
| `frame_number` | Integer | |
| `processing_time_ms` | Float | |

### 2.14 `unknown_faces`
Unknown-person snapshots with retention policy.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `image_path` | String(500) | required |
| `embedding_path` | String(500) | |
| `thumbnail_path` | String(500) | |
| `camera_id` | FK → `cameras.id` | |
| `classroom_id` | FK → `classrooms.id` | |
| `timestamp` | DateTime | indexed |
| `confidence` | Float | |
| `liveness_score` | Float | |
| `track_id` | String(50) | |
| `is_spoof` | Boolean | default `false` |
| `reviewed` | Boolean | default `false` |
| `reviewed_by` | FK → `users.id` | |
| `reviewed_at` | DateTime | |
| `converted_to_employee` | Boolean | default `false` |
| `notes` | Text | |
| `retention_expires_at` | DateTime | retention policy |
| `face_metadata` | JSON | |

### 2.15 `users`
Authentication users (admin dashboard / API).

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `username` | String(100) | unique, required |
| `email` | String(255) | unique, required |
| `password_hash` | String(255) | bcrypt |
| `oidc_sub` | String(255) | OIDC subject (unique, nullable) |
| `oidc_provider` | String(50) | |
| `auth_method` | String(20) | `local` / `oidc` / `both` |
| `is_mfa_enabled` | Boolean | default `false` |
| `mfa_totp_secret` | String(64) | Base32 TOTP secret |
| `mfa_backup_codes` | JSON | hashed |
| `mfa_last_verified` | DateTime | |
| `is_active` | Boolean | default `true` |
| `last_login_at` | DateTime | |
| `created_at` / `updated_at` | DateTime | |

### 2.16 `roles` / `permissions` / `user_roles` / `role_permissions`
RBAC. 7 roles (`SUPER_ADMIN`, `COLLEGE_ADMIN`, `HOD`, `FACULTY`, `SECURITY`,
`STUDENT`, `STAFF`). Permissions are `(resource, action)` pairs — 11 resources ×
5 actions (`CREATE/READ/UPDATE/DELETE/EXECUTE`). Seeded by `scripts/seed_admin.py`.

### 2.17 `refresh_tokens`
Rotating refresh tokens.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `user_id` | FK → `users.id` | indexed |
| `token_hash` | String(128) | unique |
| `expires_at` | DateTime | |
| `created_at` | DateTime | |
| `revoked_at` | DateTime | |
| `replaced_by` | String(128) | rotation chain |
| `device_info` / `ip_address` | | |

### 2.18 `failed_login_attempts`
Brute-force protection ledger.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `username` | String(100) | indexed |
| `ip_address` | String(45) | indexed |
| `user_agent` | String(500) | |
| `attempted_at` | DateTime | indexed |
| `success` | Boolean | |

### 2.19 `audit_logs`
Immutable audit trail.

| Column | Type | Notes |
|:-------|:-----|:------|
| `id` | Integer PK | |
| `action` | String(50) | e.g. `USER_LOGIN`, `ATTENDANCE_MARKED`, `SPOOF_ATTEMPT` |
| `actor` | String(100) | operator name |
| `actor_type` | String(20) | `USER` / `SYSTEM` / `SERVICE` |
| `actor_id` | FK → `employees.id` | nullable |
| `timestamp` | DateTime | indexed |
| `resource_type` / `resource_id` | | |
| `description` | Text | |
| `ip_address` / `user_agent` / `request_id` | | |
| `details` | JSON | |
| `severity` | String(20) | `INFO` / `WARNING` / `ERROR` / `CRITICAL` |

---

## 3. Index Strategy

| Table | Index | Purpose |
|:------|:------|:--------|
| `attendance` | `idx_attendance_timestamp` | today/date-range queries |
| `attendance` | `idx_attendance_student_timestamp` | per-student history |
| `attendance` | `idx_attendance_camera_timestamp` | per-camera rollup |
| `recognition_log` | `idx_recognition_timestamp`, `idx_recognition_is_known` | analytics |
| `recognition_log` | `idx_recognition_camera_timestamp` | camera drill-down |
| `unknown_faces` | `idx_unknown_retention` | retention sweeps |
| `unknown_faces` | `idx_unknown_camera_reviewed` | gallery filtering |
| `users` | unique `username`, unique `email` | auth lookups |
| `audit_logs` | `idx_audit_timestamp`, `idx_audit_action` | audit queries |

> Designed for 500K+ FAISS embeddings and large attendance volumes: attendance
> and recognition reads are always index-scoped (by date + person/camera), and
> all list endpoints paginate (see `PageResult`).

---

## 4. Alembic Migrations

| Revision | Description |
|:---------|:------------|
| `1bf6aa4e001c` | Initial schema (institutions → attendance, RBAC, audit) |
| `2a7c9e4f1b3d` | Add `failed_login_attempts` table |
| `9c4d2f6a7b11` | Add scalability indexes |

Apply with:

```bash
alembic upgrade head
```

**Known constraint detail:** `departments.head_id` → `staff.id` is a circular FK
declared with `use_alter=True` and the *named* constraint
`fk_departments_head_id`. The name is required so schema teardown
(`drop_all`) works cleanly (fixed in this release).

---

## 5. Non-Database State (not in PostgreSQL)

These are persisted on the filesystem / FAISS, not in the database:

| Artifact | Path | Content |
|:---------|:-----|:--------|
| FAISS index | `embeddings/faiss.index` | 512-D HNSW/IVF/Flat vectors |
| Embedding metadata | `embeddings/metadata.json` | `[{name, id}]` |
| Unknown face images | `unknown_faces/` | snapshots |
| Uploads | `uploads/` | enrollment photos |
| Logs | `logs/app.log` | rotating logs |
| SQLite (dev) | `data/face_recognition.db` | dev database |

> **Consistency requirement:** FAISS metadata and the database must stay in
> sync — the services layer enforces this on enroll / rename / delete
> (`EnrollmentService`, `EmployeeService`, `scripts/dedupe_employees.py`).
