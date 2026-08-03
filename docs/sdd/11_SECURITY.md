# Section 11 — Security

## 11.1 Security Model Overview

The system has **two security surfaces**:
1. **Physical/biometric** — liveness anti-spoofing on the camera pipeline.
2. **Cyber** — the FastAPI web layer (auth, RBAC, MFA, OIDC, rate limiting,
   upload security, audit).

All cyber-security features are implemented in `api/main.py`,
`services/*`, `utils/upload_security.py`; biometric security lives in
`app/liveness_detector.py` + `app/deep_liveness.py`.

## 11.2 JWT (JSON Web Tokens)

| Aspect | Detail |
|--------|--------|
| Library | `python-jose` (`jose`), HS256 |
| Secret | `SECRET_KEY` env (default dev-only `dev-secret-change-in-production`; **production startup fails loudly if unset/short**) |
| Access token | 30 min default (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| Claims | `sub` (user id), `username`, `roles`, `exp`, `iat` |
| Validation | `get_current_user()` decodes, loads user, checks `is_active` |
| Refresh tokens | Opaque 48-char `secrets.token_urlsafe`, **SHA-256 hash stored** in `refresh_tokens`; 30-day expiry; **rotation** (old revoked, `replaced_by` chain); **reuse detection** revokes all tokens |
| Logout/session revoke | `/auth/revoke-all-sessions`, password change revokes all |

## 11.3 RBAC (Role-Based Access Control)

- **7 roles** (`RoleName`): SUPER_ADMIN, COLLEGE_ADMIN, HOD, FACULTY, SECURITY, STUDENT, STAFF.
- **Permissions:** 11 resources (students, employees, cameras, attendance,
  analytics, enrollment, mfa, users, unknown_faces, jobs, audit_logs) × 5
  actions (READ/CREATE/UPDATE/DELETE/EXECUTE) + institution/department/
  course/section/classroom READ extras.
- **Mapping:** `role_permissions` + `user_roles` association tables.
- **Enforcement:** FastAPI dependencies `require_permission(resource, action)`
  and `require_role(*roles)`.
- **Seeding:** `scripts/seed_admin.py` assigns **all** permissions to
  SUPER_ADMIN, a management subset to COLLEGE_ADMIN.
- **MFA policy:** SUPER_ADMIN always requires MFA; COLLEGE_ADMIN, HOD,
  SECURITY also require MFA (`MFAService.requires_mfa`).

## 11.4 Password Security

- **Hashing:** bcrypt via `passlib.CryptContext(schemes=["bcrypt"])`.
- **Policy** (configurable env): min 12 chars, uppercase + lowercase +
  digit + special required; common weak-password blocklist.
- **Change flow:** verify current → enforce policy → hash → revoke all
  refresh tokens → audit.
- **Seed default** (`ADMIN_PASSWORD=AutoR!0t!ze*9!`) — change in production.

## 11.5 Brute Force Protection

`services/brute_force_protection.py` (uses `failed_login_attempts` table):

| Policy | Value |
|--------|-------|
| Max failed attempts per username | 5 |
| Lockout duration | 30 minutes |
| IP rate limit | 20 attempts/minute |
| Attempts cleanup | older than 7 days |
| Success resets | successful login recorded; lockout counts only failures after last success |
| Warning | ≥3 failures → "N attempts remaining" message |
| HTTP status on lock | 429 Too Many Requests |

## 11.6 MFA (Multi-Factor Authentication)

| Aspect | Detail |
|--------|--------|
| Type | TOTP (time-based one-time password) via `pyotp` |
| Enrollment | `/auth/mfa/enroll` → base32 secret + provisioning URI (QR) + 8 backup codes |
| Backup codes | 10-char hex, **SHA-256 hashed** in DB, one-time use, constant-time compare (`hmac.compare_digest`) |
| Verify | `/auth/mfa/verify` accepts TOTP (1-window drift tolerance) or backup code; only `mfa_pending` tokens accepted (prevents bypass) |
| MFA token | 2-minute JWT with `mfa_pending: true` |
| Required for | SUPER_ADMIN, COLLEGE_ADMIN, HOD, SECURITY |

## 11.7 OIDC (SSO)

- Provider-agnostic via well-known discovery (Azure AD, Keycloak, Okta, Google).
- Env: `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`,
  `OIDC_SCOPES`, `OIDC_REDIRECT_URI`.
- Flow: `/auth/oidc/login` (state stored in Redis, 5-min TTL, one-time use)
  → provider → `/auth/oidc/callback` (state validated → code exchange →
  user sync → JWT).
- If the IdP performed MFA, `mfa_last_verified` is set (no second challenge).
- Degradation: if Redis is down, CSRF state validation is skipped with a
  warning logged.

## 11.8 Liveness (Biometric Anti-Spoofing)

- **5 factors** (see §5.2⑤): LBP texture, blink (EAR), motion, screen-edge
  detection, deep CNN (MiniFASNet ONNX 80×80).
- **AMFR gates:** liveness below `LIVENESS_SPOOF_THRESHOLD (0.15)` →
  hard REJECT_SPOOF + `SPOOF_ATTEMPT` audit log.
- **Per-track state:** each tracked person gets its own `LivenessDetector`
  so one person's blink/motion doesn't pollute another's score.
- **Fallback:** if ONNX model unavailable → numpy spectral classifier.

## 11.9 Upload Security

`utils/upload_security.py` — used by `/enroll/upload`:
- **Magic bytes** format detection (JPEG/PNG/GIF/WebP) — never trusts the
  extension.
- **Size limit** (5 MB default, `MAX_UPLOAD_SIZE_MB`).
- **Pillow verify** — rejects truncated/corrupt images.
- **Dimension limits** — 4096×4096, 8 MP max.
- **Server-side filenames** — `enroll_<ts>_<uuid>.<ext>` (path-traversal
  immune); `sanitize_filename()` strips path components + null bytes.
- **Request body cap** — 10 MB middleware (`MAX_BODY_SIZE_BYTES`).

## 11.10 Audit Logs

`AuditLog` table (see §8.2.9) records: action, actor (+type), actor_id,
timestamp, resource_type/id, description, **IP**, **user-agent**,
request_id, JSON details, severity (INFO/WARNING/ERROR/CRITICAL).
Every sensitive path calls `log_audit()` or `AuditService.log()` — login
success/failure, attendance, enrollment, config changes, spoof attempts,
session revocation.

## 11.11 Rate Limiting

- **slowapi** `Limiter(key_func=get_remote_address)` + `SlowAPIMiddleware`.
- Per-endpoint limits: login 10/min, logout 20/min, me 30/min,
  change-password 5/min, enroll-upload 5/min, general API 100/min
  (`API_RATE_LIMIT`), jobs 20/min, bulk 30/min.
- `/health`, `/metrics` exempt.

## 11.12 Security Headers

Applied by response middleware: `X-Content-Type-Options`, `X-Frame-Options:
DENY`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy` (blocks
camera/mic/geo in the API), `Content-Security-Policy`, optional HSTS
(`ENABLE_HSTS=1`). Additional middleware: CORS (configurable origins),
TrustedHost (Host-header protection, `*` only in dev), X-Request-ID tracing.

## 11.13 Other Security Practices

- **Safe errors:** global handlers return generic messages — no stack
  traces or internals leaked; 500s log server-side with `exc_info`.
- **Docs disabled in production** (`docs_url=None`).
- **Redis bound to localhost** in docker-compose (127.0.0.1) and PostgreSQL
  bound to 127.0.0.1; both have healthchecks.
- **Refresh tokens in POST body** (not query params) so they never appear
  in access logs.
- **Production secret-key validation** at startup (fail-fast).
- **Idempotent seed** — safe to re-run.

## 11.14 Known Gaps / Notes

- `TrustedHostMiddleware` with `allowed_hosts=["*"]` in dev only; set
  explicit hosts in production.
- OIDC state validation degrades when Redis is unavailable (logged).
- Uploads are validated but stored on local disk — production should use an
  immutable store + signed URLs (see §29).
- HSTS is opt-in (`ENABLE_HSTS=1`) — enable after HTTPS is configured.

---

*References: `api/main.py`, `services/*`, `utils/upload_security.py`,
`docs/SECURITY_REPORT.md`, `scripts/seed_admin.py`*
