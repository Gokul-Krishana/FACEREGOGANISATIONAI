# API Documentation — Face Recognition AI

**Version:** 2.0.0
**Date:** 2026-08-02
**Base URL:** `http://localhost:8000` (Docker: same port)
**Interactive docs:** http://localhost:8000/docs (Swagger UI) · http://localhost:8000/redoc

---

## 1. Overview

The FastAPI backend exposes a REST API for the enterprise deployment. It
provides authentication (JWT + MFA + OIDC), RBAC-protected CRUD for all
resources, live recognition events (SSE), background jobs, analytics, and
health probes.

**Security posture:**
- All endpoints except `/auth/*` login, `/health*`, `/metrics`, and
  `/events/stream` require a Bearer JWT.
- Rate limiting via `slowapi` (per-IP).
- Request body size limit (upload validation).
- Audit logging on all mutations.

### Authentication Flow

```
POST /auth/login  {username, password}
  → 200 {access_token, refresh_token, user}

POST /auth/mfa/verify  {totp_code}   (if MFA enabled)
  → 200 {access_token, ...}

Use:  Authorization: Bearer <access_token>
Refresh: POST /auth/refresh  {refresh_token}
```

---

## 2. Endpoint Reference

### 2.1 Authentication & Users

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| POST | `/auth/login` | — | Login with username + password (rate-limited, brute-force protected) |
| POST | `/auth/logout` | JWT | Revoke current session |
| GET | `/auth/me` | JWT | Current user profile + roles |
| POST | `/auth/change-password` | JWT | Change password |
| POST | `/auth/revoke-all-sessions` | JWT | Revoke every session for the user |
| POST | `/auth/mfa/enroll` | JWT | Begin MFA enrollment (returns TOTP secret + provisioning URI) |
| POST | `/auth/mfa/verify` | — | Verify TOTP and obtain tokens (post-login MFA challenge) |
| GET | `/auth/mfa/status` | JWT | MFA status for current user |
| POST | `/auth/mfa/disable` | JWT | Disable MFA |
| GET | `/auth/oidc/login` | — | Start OIDC flow (returns provider redirect URL) |
| GET | `/auth/oidc/callback` | — | OIDC callback → tokens |
| POST | `/auth/refresh` | — | Exchange refresh token for new access token |

**`POST /auth/login` request:**
```json
{
  "username": "admin",
  "password": "AutoR!0t!ze*9!"
}
```
**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800,
  "refresh_token": "…",
  "user": {"id": 1, "username": "admin", "email": "admin@college.edu", "roles": ["SUPER_ADMIN"]}
}
```

### 2.2 Health & Monitoring

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| GET | `/health` | — | Liveness: service up + DB connected |
| GET | `/health/live` | — | Liveness only (no DB) |
| GET | `/health/ready` | — | Readiness: DB + models + FAISS |
| GET | `/metrics` | — | Prometheus metrics |
| GET | `/system/status` | JWT | Detailed system status (cameras, models, queues) |

**`GET /health/ready` response:**
```json
{
  "status": "ready",
  "database": "ok",
  "faiss": "ok",
  "yolo_model": "ok",
  "insightface": "ok",
  "redis": "degraded",
  "timestamp": "2026-08-02T10:00:00Z"
}
```

### 2.3 Students

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| POST | `/students` | JWT | Create student |
| GET | `/students` | JWT | List students (paginated, searchable) |
| GET | `/students/{student_id}` | JWT | Get student by ID |
| POST | `/enroll/upload` | JWT | Upload enrollment image (validated) |

### 2.4 Employees (Recognition Identity)

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| POST | `/employees` | JWT | Create employee (optionally with photo) |
| GET | `/employees` | JWT | List employees (paginated, searchable) |
| GET | `/employees/{employee_id}` | JWT | Get employee |
| PUT | `/employees/{employee_id}` | JWT | Update employee (renames FAISS label) |
| DELETE | `/employees/{employee_id}` | JWT | Delete employee + remove FAISS embedding |

> **Important:** deleting an employee also removes their FAISS embedding, so
> they can no longer be recognised (verified in this release).

### 2.5 Cameras

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| POST | `/cameras` | JWT | Register a camera (name, index, location) |
| GET | `/cameras` | JWT | List cameras (paginated) |
| GET | `/cameras/{camera_id}` | JWT | Camera detail + health |

**`POST /cameras` request:**
```json
{
  "name": "Lecture Hall 2",
  "camera_index": 0,
  "location": "Building A, Floor 1"
}
```

### 2.6 Attendance

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| POST | `/attendance` | JWT | Manually mark attendance |
| GET | `/attendance` | JWT | List attendance (paginated, date-filtered) |

**`GET /attendance` query params:** `start_date`, `end_date`, `employee_id`,
`camera_id`, `skip`, `limit`.

### 2.7 Unknown Faces

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| GET | `/unknown-faces` | JWT | List unknown faces (paginated, filtered) |
| POST | `/unknown-faces/{face_id}/review` | JWT | Mark reviewed / convert to employee |

### 2.8 Analytics

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| GET | `/analytics/attendance-summary` | JWT | Daily/hourly attendance statistics |
| GET | `/analytics/camera-status` | JWT | Per-camera status rollup |

### 2.9 Real-Time Events (SSE)

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| GET | `/events/stream` | JWT (query or header) | Server-Sent Events stream of recognition/attendance events |

```
GET /events/stream?token=<access_token>
```
Events are JSON lines: `data: {"type": "attendance_marked", "payload": {...}}`.

### 2.10 Background Jobs

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| POST | `/jobs` | JWT | Enqueue a job (e.g. `rebuild_faiss`, `batch_enroll`) |
| GET | `/jobs` | JWT | List jobs |
| GET | `/jobs/{job_id}` | JWT | Job status |
| POST | `/jobs/{job_id}/cancel` | JWT | Cancel a pending job |

### 2.11 Bulk Operations

| Method | Path | Auth | Description |
|:-------|:-----|:-----|:------------|
| POST | `/bulk/students/import` | JWT | CSV import of students |
| POST | `/bulk/employees/import` | JWT | CSV import of employees |
| POST | `/bulk/cameras/status` | JWT | Bulk status check |
| GET | `/bulk/attendance/export` | JWT | CSV export of attendance |

---

## 3. Pagination Envelope

All list endpoints return:

```json
{
  "items": [...],
  "total": 142,
  "skip": 0,
  "limit": 50,
  "has_more": true
}
```

---

## 4. Error Format

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|:-------|:--------|
| 400 | Bad request / validation error |
| 401 | Missing/invalid token |
| 403 | Authenticated but insufficient RBAC permission |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Server error |

---

## 5. Rate Limits (defaults)

| Scope | Limit |
|:------|:------|
| `/auth/login` | 5 / minute per IP |
| `/auth/change-password` | 3 / minute |
| General API | 120 / minute |

---

## 6. Example: Full Recognition Event Flow

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"AutoR!0t!ze*9!"}' | jq -r .access_token)

# 2. Create an employee
curl -s -X POST http://localhost:8000/employees \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"employee_id":"EMP100","name":"Alice","department":"Engineering"}'

# 3. Manually mark attendance
curl -s -X POST http://localhost:8000/attendance \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"employee_id":1,"confidence":0.98}'

# 4. Health
curl -s http://localhost:8000/health/ready
```

---

## 7. Starting the API

```bash
# Dev (SQLite)
uvicorn api.main:app --reload --port 8000

# Production (PostgreSQL + Redis via Docker)
docker compose up -d db redis api
```

See `docs/DEPLOYMENT.md` for full instructions.
