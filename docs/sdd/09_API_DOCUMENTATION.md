# Section 9 — API Documentation

**Base URL:** `http://<host>:8000` (FastAPI, version 2.0.0)
**Interactive docs:** `/docs` and `/redoc` (disabled in production).

## 9.1 Authentication & Authorization Model

- **Bearer JWT** access tokens (HS256, `SECRET_KEY`, default 30 min expiry).
- **Refresh tokens** — opaque, stored hashed (SHA-256) in `refresh_tokens`,
  rotating on use; reuse of a revoked token revokes all of the user's tokens.
- **RBAC:** `require_permission(resource, action)` checks the user's
  role→permission mapping; `require_role(*roles)` checks membership.
- **MFA:** privileged roles require TOTP (see §11.6). Login returns
  `requires_mfa=true` + a short-lived `mfa_token`; client then calls
  `/auth/mfa/verify`.
- **Rate limiting:** slowapi keyed by client IP (defaults: login 10/min,
  general API 100/min, etc.).
- **Common error shape:** `{"error": "<detail>", "code": <http_status>}`.
- **Every response carries `X-Request-ID`.**

## 9.2 Standard Error Codes

| Code | Meaning |
|------|---------|
| 400 | Validation error / bad request (e.g. upload security, not enrolled in section) |
| 401 | Missing/invalid/expired token; wrong credentials; MFA failed |
| 403 | Insufficient permissions / disabled account / CSRF (OIDC state) |
| 404 | Resource not found |
| 409 | Duplicate (e.g. employee_id already exists) |
| 413 | Request body too large (>10 MB default) |
| 429 | Rate limited or account locked |
| 500 | Internal server error (generic message, no stack traces) |
| 501 | Feature not configured (e.g. OIDC not configured) |

## 9.3 Endpoint Reference

### 9.3.1 Auth

| Method | Path | Auth | Rate | Description |
|--------|------|------|------|-------------|
| POST | `/auth/login` | public | 10/min | Login; returns tokens or MFA challenge |
| POST | `/auth/logout` | user | 20/min | Audit logout |
| GET | `/auth/me` | user | 30/min | Current user profile + roles |
| POST | `/auth/change-password` | user | 5/min | Verify current + set new; revokes all refresh tokens |
| POST | `/auth/revoke-all-sessions` | user | 3/min | Revoke all refresh tokens |
| POST | `/auth/refresh` | public+token | 20/min | Rotate refresh token → new access+refresh |
| POST | `/auth/mfa/enroll` | mfa:UPDATE | 5/min | Generate TOTP secret + backup codes |
| POST | `/auth/mfa/verify` | mfa-token | 10/min | Verify TOTP/backup → full tokens |
| GET | `/auth/mfa/status` | user | — | MFA status + backup codes remaining |
| POST | `/auth/mfa/disable` | mfa:UPDATE | 5/min | Disable MFA |
| GET | `/auth/oidc/login` | public | 10/min | SSO auth URL + state |
| GET | `/auth/oidc/callback` | public | 10/min | SSO callback → tokens |

**Login request:**
```json
{ "username": "admin", "password": "AutoR!0t!ze*9!" }
```
**Login response (no MFA):**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "refresh_token": "<opaque>",
  "requires_mfa": false,
  "mfa_token": null
}
```
**Login response (MFA required):** `requires_mfa: true`, `mfa_token: "<2-min jwt>"`.

**JWT claims:** `sub` (user id), `username`, `roles`, `exp`, `iat`,
optionally `mfa_pending`, `mfa`, `oidc`.

### 9.3.2 Health & Monitoring

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | public | status/version/timestamp/database/redis |
| GET | `/health/live` | public | liveness probe |
| GET | `/health/ready` | public | readiness probe |
| GET | `/metrics` | public | Prometheus metrics (text format) |
| GET | `/system/status` | user | full system status snapshot |

### 9.3.3 Enrollment

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/enroll/upload` | enrollment:CREATE | Upload enrollment photo (magic-bytes validated, 5 MB max) → `{filename, size_bytes, message}` |

### 9.3.4 Students

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/students` | students:CREATE | Create student (201) |
| GET | `/students` | students:READ | Paginated list; `q`, `department_id`, `is_active`, `skip`, `limit` |
| GET | `/students/{id}` | students:READ | Get one |

`StudentCreate`: `{student_id, name, email?, department_id?}` (student_id pattern `^[a-zA-Z0-9\-]+$`).

### 9.3.5 Employees

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/employees` | employees:CREATE | Create (409 on duplicate) |
| GET | `/employees` | employees:READ | Paginated + `q` search |
| GET | `/employees/{id}` | employees:READ | Get one |
| PUT | `/employees/{id}` | employees:UPDATE | Partial update (name/department/photo_path) |
| DELETE | `/employees/{id}` | employees:DELETE | Delete + FAISS embedding removal (204) |

### 9.3.6 Cameras

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/cameras` | COLLEGE_ADMIN/SUPER_ADMIN | Create camera |
| GET | `/cameras` | cameras:READ | Paginated + `q`/`is_active`/`status` filters |
| GET | `/cameras/{id}` | cameras:READ | Get one |
| PATCH | `/cameras/{id}/status` | COLLEGE_ADMIN/SUPER_ADMIN | Set active/offline |

### 9.3.7 Attendance

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/attendance` | attendance:CREATE | Mark attendance (validates student + enrollment) |
| GET | `/attendance` | attendance:READ | Filtered by student/section/course/date range, paginated |

`AttendanceCreate`: `{student_id, section_id?, course_id?, classroom_id?, camera_id?, confidence [0-1], method, status}`.

### 9.3.8 Unknown Faces

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/unknown-faces` | unknown_faces:READ | Paginated + date/camera/reviewed filters |
| POST | `/unknown-faces/{id}/review` | unknown_faces:UPDATE | Mark reviewed |

### 9.3.9 Analytics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/analytics/attendance-summary` | analytics:READ | Aggregated attendance stats |
| GET | `/analytics/camera-status` | analytics:READ | Per-camera status |

### 9.3.10 Real-Time Events

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/events/stream` | user (WS) | WebSocket recognition event stream; supports `camera_id` filter; role-filtered for students |

### 9.3.11 Jobs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/jobs` | jobs:CREATE | Enqueue `batch_enroll` / `rebuild_index` / `cleanup_unknown` → `{job_id, status, job_type}` |
| GET | `/jobs` | jobs:READ | List (status filter, limit) |
| GET | `/jobs/{id}` | jobs:READ | Job status + progress |
| POST | `/jobs/{id}/cancel` | jobs:UPDATE | Cancel job |

### 9.3.12 Bulk Operations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/bulk/students/import` | students:CREATE | CSV student import → `BulkResult` |
| POST | `/bulk/employees/import` | employees:CREATE | CSV employee import |
| POST | `/bulk/cameras/status` | cameras:UPDATE | Bulk enable/disable |
| GET | `/bulk/attendance/export` | attendance:READ | CSV export (date/section filters) |

**BulkResult:** `{total, success, failed, skipped, errors[≤20], created_ids, elapsed_ms}`.

## 9.4 Security Headers (every response)

`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Permissions-Policy: camera=(), microphone=(), geolocation=()`,
`Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; ...`,
optional `Strict-Transport-Security` (when `ENABLE_HSTS=1`).

## 9.5 Production Secret-Key Guard

On startup, if `ENVIRONMENT=production`, the app **raises** unless
`SECRET_KEY` is set and ≥ 32 characters (fails loudly, no silent default).

---

*References: `api/main.py`, `api/bulk_operations.py`, `api/job_queue.py`,
`api/websocket_manager.py`, `docs/API_DOCUMENTATION.md`*
