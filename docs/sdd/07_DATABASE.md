# Section 7 — Database

## 7.1 Simple Language Explanation

The system stores three kinds of data:

1. **Relational data** (people, attendance, cameras, users, roles, audit
   logs) → SQLite in development, PostgreSQL in production.
2. **Face vectors** (512-D embeddings) → FAISS index files (see §6.5).
3. **Temporary/runtime state** (cooldowns, camera status, OIDC state) →
   Redis (optional, degrades gracefully).

SQLAlchemy ORM maps Python classes to tables; Alembic versions schema
changes; the Repository pattern wraps all queries.

## 7.2 Database Engines

### SQLite (development / default)
- **Connection URL:** `sqlite:///data/face_recognition.db`
- **Set via:** `DB_TYPE=sqlite` (default) in `database/database.py`.
- **Advantages:** zero-config, single file, perfect for dev and small pilots.
- **Disadvantages:** single-writer, limited concurrency — not for campus-scale
  concurrent writes.

### PostgreSQL (production)
- **Connection URL:** from `DATABASE_URL` env var (`DB_TYPE=postgres`).
- **Advantages:** concurrency, ACID, indexes, JSON columns, maturity.
- **Used by:** production college deployment; `docker-compose.yml` provides
  `postgres:16-alpine` with healthcheck.
- **Backup/restore:** `scripts/backup.py` / `scripts/restore.py` (pg_dump).

### Redis (optional cache/state)
- **Connection URL:** `REDIS_URL` (default `redis://localhost:6379/0`).
- **Used for:** student last-seen, attendance dedupe markers, camera status,
  recognition cooldowns, track identity cache, OIDC CSRF state.
- **Key design property:** *every* Redis call in `api/redis_client.py` is
  wrapped so failure degrades gracefully — tests skip when Redis is absent.

## 7.3 ORM — SQLAlchemy 2.0

- **Declarative base:** `database/models.py` defines `Base(DeclarativeBase)`.
- **Session:** `SessionLocal = sessionmaker(...)`; `get_session()` context
  manager yields a Session; callers commit/rollback.
- **Types used:** Integer, String, Text, Boolean, Float, DateTime, JSON,
  Enum (via SAEnum where needed), ForeignKey, Index, Table (associations).
- **Timestamps:** `_utcnow()` helper returns naive UTC.

## 7.4 Migration — Alembic

- **Config:** `alembic.ini`; environment: `alembic/env.py`.
- **Versions** (in `alembic/versions/`):
  1. `1bf6aa4e001c` — initial schema (index on `unknown_faces.timestamp`).
  2. `2a7c9e4f1b3d` — `failed_login_attempts` table + composite indexes.
  3. `9c4d2f6a7b11` — scalability indexes (students, attendance, recognition_log, unknown_faces, audit_logs).
- **Auto-init:** `init_db()` runs `alembic upgrade head` if `alembic.ini`
  exists; falls back to `Base.metadata.create_all()` and stamps the DB.

## 7.5 Repository Pattern

`database/repository.py` defines per-entity repositories, each a class of
static methods taking a `Session`:

| Repository | Entity | Key operations |
|------------|--------|----------------|
| `StudentRepo` | students | create, get, search (name/id prefix), count |
| `EmployeeRepo` | employees | create, get_by_*, search (paginated), update (whitelisted), delete, count |
| `AttendanceRepo` | attendance | create, get_by_date/today/employee, is_marked_today, statistics |
| `RecognitionLogRepo` | recognition_log | create (with liveness/spoof/track), get_recent, get_by_date |
| `UnknownFaceRepo` | unknown_faces | create, get_all/filtered, stats, mark_reviewed/converted, notes, delete/all, delete_older_than |
| `CameraRepo` | cameras | create, get_all/active/by_id/by_index |
| `AuditLogRepo` | audit_logs | create, get_recent, get_by_action |

**Pagination:** `PageResult(items, total, skip, limit)` with `has_more`
property; `_paginate()` helper counts + slices. Search uses **prefix
patterns** (`name%`) so indexes can be used.

**Why the pattern:** keeps SQL out of business logic, makes services thin,
enables unit testing with a session mock, and gives a consistent CRUD API.

## 7.6 Why Each Table Exists (summary — full schema in §8)

| Group | Tables | Purpose |
|-------|--------|---------|
| RBAC | users, roles, permissions, user_roles, role_permissions | Authentication + authorization |
| Auth extras | failed_login_attempts, refresh_tokens | Brute-force protection; token rotation |
| College structure | institutions, departments, courses, sections, classrooms, timetables | Model the college so attendance is timetable-aware |
| People | students, staff, employees | People records (students + staff + legacy employees) |
| Enrollment | enrollments | Student ↔ section membership |
| Cameras | cameras | Multi-camera config with credentials refs |
| Attendance | attendance | Timetable-aware attendance records |
| Recognition | recognition_log | Every recognition event (analytics) |
| Unknown faces | unknown_faces | Snapshots + review workflow |
| Audit | audit_logs | Compliance/security trail |

## 7.7 Data Consistency Between Stores

- **Employee rename/delete** propagates to **FAISS** via
  `EmployeeService.update()`/`delete()` → `enrollment.rename()` /
  `remove_by_name()`.
- **Attendance** is dual-written to the DB (via repository) and to **CSV**
  (via `AttendanceTracker`) for backward compatibility.
- **Unknown face conversion** creates an Employee record first, then adds the
  embedding to FAISS (rolls back the employee if FAISS fails).

---

*References: `database/*`, `alembic/*`, `api/redis_client.py`, `scripts/backup.py`,
`docker-compose.yml`, `docs/DATABASE_SCHEMA.md`*
