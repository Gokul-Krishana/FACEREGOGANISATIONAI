# Security Report — Face Recognition AI

**Version:** 2.0.0
**Date:** 2026-08-02

---

## 1. Scope

This report documents the security posture of the Face Recognition AI system:
the attack surface, implemented controls, and residual risks. It is written for
institutional review (IT security, data-protection officers).

---

## 2. Threat Model (Summary)

| Threat | Category | Mitigation |
|:-------|:---------|:-----------|
| Spoofing with printed photo | Presentation attack | Deep liveness (5-factor) + AMFR REJECT_SPOOF |
| Spoofing with screen replay | Presentation attack | Screen-edge + motion + deep CNN detection |
| Unauthorised API access | AuthN | JWT + bcrypt + RBAC + MFA + OIDC |
| Brute-force login | AuthN | Rate limiting + lockout + `failed_login_attempts` |
| Uploaded malware / bad files | Input | Magic-byte validation (`utils/upload_security.py`) |
| Camera credential theft | Secrets | Credential references, never plaintext storage |
| SQL injection | Data | SQLAlchemy ORM (parameterised queries) |
| Data breach (biometric/attendance) | Data | Encrypted backups, least-privilege, retention |
| Malicious containers | Infra | Non-root user, read-only root FS, tmpfs |
| Credential exposure in logs | Infra | Safe-error policy, redacted URLs in backup manifest |

---

## 3. Authentication & Identity

| Control | Implementation | Verified |
|:--------|:---------------|:---------|
| Password hashing | **bcrypt** (salted) | ✅ |
| Access tokens | JWT, 30-min expiry (configurable), `Authorization: Bearer` | ✅ |
| Refresh tokens | Rotating, hashed at rest, revocable, per-device | ✅ |
| Multi-factor auth | **TOTP** (`pyotp`), backup codes, per-user | ✅ |
| OIDC | Azure AD / Keycloak / Google via `oidc_sub` | ✅ |
| RBAC | 7 roles × (11 resources × 5 actions), seeded + checked per endpoint | ✅ |
| Session revocation | `POST /auth/revoke-all-sessions` | ✅ |
| Brute-force protection | Lockout after 5 failures / 30 min + slowapi rate limits | ✅ |

**API enforcement:** FastAPI dependencies resolve the JWT and verify the
required `(resource, action)` permission before handlers run. All mutation
endpoints log to `audit_logs`.

---

## 4. Anti-Spoofing (Biometric Presentation Attacks)

The recognition pipeline enforces liveness **before** acceptance:

```
RetinaFace → FaceQuality → LivenessDetector (5 factors) → DeepLiveness CNN → AMFR
```

| Factor | Detects |
|:-------|:--------|
| Texture (LBP) | printed photos |
| Blink | static images |
| Motion | replayed video |
| Screen-edge | digital screens |
| Deep CNN (ONNX MiniFASNet) | high-quality prints / subtle screens |

**AMFR decision states:** `ACCEPT` (attendance), `BORDERLINE` (collect more
frames), `LOW_CONFIDENCE` (unknown), `REJECT_SPOOF` (hard reject + audit log
with liveness/quality/distance metrics).

> **Fix in this release:** the deep-liveness ONNX model auto-download URL was
> dead (404). It now points to a maintained MiniFASNetV2 export (verified:
> real face scores live=1.0, ~9 ms inference). The built-in CNN fallback
> remains for offline/first-run environments.

---

## 5. Application Security

| Area | Control |
|:-----|:--------|
| Input validation | Pydantic schemas on every endpoint; upload magic-byte checks |
| Upload security | `utils/upload_security.py` — extension + magic bytes + size limits |
| Rate limiting | slowapi per-IP (login 5/min, general 120/min) |
| Request size | Body-size limiter middleware |
| Headers | `secure` package security headers (HSTS, X-Content-Type-Options, etc.) |
| Error handling | Safe errors — **no credentials/paths leaked** in API responses |
| Logging | Structured JSON logging (python-json-logger); rotating files |
| Audit trail | Every auth/CRUD/recognition action → `audit_logs` |

---

## 6. Infrastructure / Deployment Security

| Control | Where |
|:--------|:------|
| Non-root user | Dockerfile (`USER faceai`) |
| Read-only root filesystem | Docker + docker-compose (`read_only: true`) |
| tmpfs for writable paths | `/tmp`, `/app/outputs`, `/app/attendance` |
| Named volumes for state | embeddings, unknown_faces, logs, uploads, data |
| DB/Redis bound to localhost | docker-compose (`127.0.0.1:5432`, `127.0.0.1:6379`) |
| Redis password | `REDIS_PASSWORD` env |
| Health endpoints unauthenticated only | `/health`, `/health/ready` (no data) |
| GPU optional | commented NVIDIA runtime stanza |

---

## 7. Data Protection (Biometric & Attendance)

- **Biometric data** = face embeddings in FAISS + enrollment photos. These are
  personal data under GDPR/DPDP-style regimes; the institution must register
  processing, bound retention, and restrict access.
- **Retention:** unknown faces auto-purge after `retention_days` (default 30).
  Attendance and audit data retain per institutional policy.
- **Backups:** `scripts/backup.py` produces hashed manifests with **redacted
  credentials**; encrypt backups at rest and keep off-site copies.
- **Deletion flow:** deleting an employee removes the DB record **and** their
  FAISS embedding (verified in tests) — a genuine right-to-be-forgotten path.
- **Dedup cleanup tool:** `scripts/dedupe_employees.py` merges duplicate
  records and re-attributes history (dry-run by default).

---

## 8. Secure Development & Verification

| Activity | Evidence |
|:---------|:---------|
| Unit tests incl. security modules | `test_upload_security.py`, `test_brute_force_protection.py`, `test_deep_liveness.py` (37 tests) |
| Integration tests (PostgreSQL + Redis) | `test_integration.py` — 17 passing against live PostgreSQL + Redis |
| CI security scan | `.github/workflows/security-scan.yml` + container scans in `docker-build.yml` (Trivy **and** Grype, SARIF → Security tab) |
| CI lint + tests | `.github/workflows/python-ci.yml` |
| Startup validation | `tools/validate_startup.py` — **8/8 SYSTEM READY** (with Redis + PostgreSQL running) |

**This release's test suite: 490 passed, 0 failed, 0 errors** (with Redis + PostgreSQL running).

---

## 9. Residual Risks & Recommendations

| # | Risk | Severity | Recommendation |
|:-:|:-----|:---------|:---------------|
| 1 | RTSP credentials referenced but storage of actual secrets is deployment-defined | Medium | Integrate a secrets manager (Vault/KMS) for `credential_ref` |
| 2 | Streamlit has no built-in login for the dashboard | Medium | Put the dashboard behind a reverse proxy (nginx/Caddy) with institutional SSO |
| 3 | Redis optional — fallback runs without cooldown caching | Low | Always deploy Redis in production |
| 4 | Deep-liveness CNN is a fallback classifier (not full MiniFASNet) when ONNX unavailable | Low | Pre-download the ONNX model into `models/liveness/` in the image |
| 5 | Default credentials (`faceai/changeme`, dev `SECRET_KEY`) | High if unchanged | Enforce strong passwords + random SECRET_KEY in production checklist |
| 6 | ~~No runtime dependency scanning of the Docker image~~ **Addressed in this release** | Medium → ✅ | Runtime dependency scanning added to `.github/workflows/docker-build.yml` — **Trivy** (CRITICAL/HIGH SARIF) + **Grype** (Anchore, severity-cutoff high, only-fixed) — both report to the GitHub Security tab |

---

## 10. Compliance Considerations

- **Access control:** RBAC + audit trail satisfy typical "who did what when"
  requirements.
- **Data minimisation:** retention policies + delete-with-FAISS-sync.
- **Consent & notice:** display signage at camera locations (institutional
  responsibility).
- **Breach readiness:** encrypted off-site backups + restore drills
  (`docs/BACKUP_RESTORE_GUIDE.md`).

---

## 11. Related

- `docs/API_DOCUMENTATION.md` — auth/RBAC/rate limits per endpoint
- `docs/DEPLOYMENT.md` — production security checklist
- `docs/BACKUP_RESTORE_GUIDE.md` — encrypted backups
- `tests/test_upload_security.py`, `tests/test_brute_force_protection.py` — security tests
