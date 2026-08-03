# Pilot Deployment Plan — Face Recognition AI

**Version:** 2.0.0
**Date:** 2026-08-02
**Purpose:** A staged, evidence-based path from pilot deployment to full campus
rollout. Each phase has explicit **success criteria** and a **decision gate** —
proceed to the next phase only when the previous phase's criteria are met.

> This plan exists because **automated tests are not a substitute for on-site
> validation**. The software is ready for Phase 1; Phases 2–4 prove scale on
> real hardware before any campus-wide commitment.

---

## 0. Phase Summary

| Phase | Name | Scope | Duration (typical) | Gate to next |
|:------|:-----|:------|:-------------------|:-------------|
| **0** | Pre-Pilot Hardening | 1 classroom, staged infra | 1–2 weeks | §Gate 0 |
| **1** | Pilot | 1 classroom, production stack | 4–6 weeks | §Gate 1 |
| **2** | Multi-Classroom | 3–10 classrooms | 1 term | §Gate 2 |
| **3** | Multi-Building | 10–50 cameras | 1–2 terms | §Gate 3 |
| **4** | Campus-Wide | 50+ cameras, multi-campus option | ongoing | continuous |

---

## 1. Phase 0 — Pre-Pilot Hardening (Infrastructure)

**Objective:** stand up the production stack exactly as it will run at pilot,
and verify the deployment itself.

### Activities
- [ ] Deploy with `docker compose up -d` (PostgreSQL + Redis + API + Dashboard)
- [ ] Set production env: random `SECRET_KEY`, strong DB/Redis passwords, `ENVIRONMENT=production`
- [ ] `alembic upgrade head`; verify migrations apply cleanly
- [ ] `python tools/validate_startup.py` — all critical checks pass
- [ ] `python scripts/seed_admin.py` — admin user + RBAC seeded
- [ ] Configure HTTPS reverse proxy (nginx/Caddy) in front of Dashboard + API
- [ ] Schedule encrypted off-site backups (`scripts/backup.py` + cron); run one restore drill
- [ ] Verify GPU inference: `python -c "import torch; print(torch.cuda.is_available())"` → `True`
  (CPU-only is supported, but GPU is strongly recommended for multi-person throughput)
- [ ] Verify Redis is connected (Health page shows Redis OK; integration tests run, not skip)

### Success criteria (Gate 0)
1. Fresh-install from the deployment guide works on the **pilot machine** with
   no manual steps beyond the guide.
2. All health checks pass; Redis and PostgreSQL show healthy.
3. Backup + restore drill succeeds (data intact after restore).
4. Full automated suite green on the deployment machine: **490 passed, 0 failed**
   (with Redis running; 484 without Redis — the Redis tests skip when absent).

---

## 2. Phase 1 — Pilot (Single Classroom)

**Objective:** prove the core acceptance criteria with real people, real camera,
real attendance.

### Activities
- [ ] Install camera per `USER_MANUAL.md` (§5); enrol 5–10 pilot volunteers (📸 Enroll)
- [ ] Daily live recognition sessions (e.g. 2 lectures/day, 4 weeks)
- [ ] Run the on-site validation checklist from `FINAL_ACCEPTANCE_REPORT.md` §5:
  - Real-person green-box → PRESENT
  - Spoof artifact (printed photo, phone screen) → REJECT_SPOOF
  - Multi-person walk-through (2+ crossing)
  - Camera unplug/replug → auto-reconnect
  - START → STOP → START repeated cycles
- [ ] Collect measured metrics on **deployment hardware** (not the dev laptop):
  camera FPS, display FPS, recognition FPS, E2E latency, CPU/GPU/RAM
  (use `scripts/benchmarks/profile_pipeline.py` and `camera_validation.py`)
- [ ] Verify attendance success rate: > 98% of pilot volunteers marked on entry
- [ ] Verify duplicate prevention: no double records in a full session
- [ ] Weekly admin review: unknown faces, spoof alerts, audit log

### Success criteria (Gate 1) — **the decision gate before scaling**
| Criterion | Target |
|:----------|:-------|
| Attendance success rate | ≥ 98% of pilot volunteers |
| False acceptance (wrong person marked) | 0 confirmed incidents |
| Spoof rejection | 100% of tested artifacts rejected |
| Live feed responsiveness | ≥ 15 effective FPS during sessions |
| Uptime | 100% during scheduled sessions (no crash) |
| Camera recovery | auto-reconnects within ~15 s of interruption |
| Resource stability | no unbounded memory/queue growth over 4 weeks |

**Gate 1: PASS ⇒ expand to multi-classroom (Phase 2). FAIL ⇒ fix root cause,
re-run Phase 1.**

---

## 3. Phase 2 — Multi-Classroom (3–10 Classrooms)

**Objective:** prove multi-camera operation, concurrency, and centralised
administration.

### Activities
- [ ] Deploy 3–10 cameras across classrooms; register each in the Cameras page
- [ ] Concurrent recognition sessions (2–3 classrooms simultaneously)
- [ ] Validate phone-camera (Android/iPhone) use cases on the pilot network
- [ ] Validate PostgreSQL under concurrent writes (multiple classrooms writing attendance)
- [ ] 24 h soak test on deployment hardware (or weekend-long)
- [ ] Validate per-camera health dashboard, camera switching, live switching without restart
- [ ] Review scalability metrics: per-camera recognition FPS at 2×, 3×, 5× concurrency

### Success criteria (Gate 2)
1. All classrooms independently stable with correct per-classroom attendance.
2. 24 h soak: no crash, no memory leak, no unbounded queues (verified by metrics).
3. PostgreSQL handles concurrent attendance writes with no integrity errors;
   page load stays < 2 s at 5× concurrency.
4. Centralised admin workflows (employees, unknown faces, analytics) work at scale.

---

## 4. Phase 3 — Multi-Building (10–50 Cameras)

**Objective:** prove building-scale deployment with centralised ops.

### Activities
- [ ] Expand to 10–50 cameras across buildings; organise by building/room metadata
- [ ] Deploy Redis for cooldown caching and event queue (already in stack)
- [ ] Validate FAISS at scale: 1K–10K enrolled embeddings, HNSW search latency
- [ ] Roll out SSO (OIDC) for staff/security role access
- [ ] Establish ops runbooks: daily health review, weekly backup verification,
      incident response for camera/network failures
- [ ] Validate retention policy automation (unknown faces, logs, backups)

### Success criteria (Gate 3)
1. FAISS search stays < 10 ms at full enrolment size.
2. Camera health monitoring detects outages and alerts within the ops loop.
3. Backup/restore proven at scale (drill on a staging copy).
4. No single point of failure in the deployed topology (DB/Redis backed up,
   restart policies, reverse proxy).

---

## 5. Phase 4 — Campus-Wide / Multi-Campus (50+ Cameras)

**Objective:** campus-wide operation with the option to federate multiple
campuses.

### Activities
- [ ] 50+ cameras; load-balanced API workers behind the reverse proxy
- [ ] Multi-campus: per-institution namespace (`institutions` table) and
      centralised admin or federated deployments
- [ ] Capacity planning review: storage (unknown faces), log volume, backup window
- [ ] Annual security review + penetration test (see `SECURITY_REPORT.md` residual risks)
- [ ] Continuous improvement loop: monthly metrics review, quarterly restore drill

### Success criteria (Gate 4 — continuous)
1. All Phase-3 criteria hold at campus scale.
2. Recovery-time objective met for camera/API/DB failures.
3. Institutional data-protection obligations met (retention, access control,
   audit).

---

## 6. Cross-Cutting: Measured Metrics to Collect Every Phase

| Metric | Tool | Reported in |
|:-------|:-----|:------------|
| Camera FPS / Display FPS | `scripts/benchmarks/camera_validation.py` | Performance Report |
| Recognition FPS / stage latencies | `scripts/benchmarks/profile_pipeline.py` | Performance Report |
| CPU / GPU / RAM / VRAM | profiler + Health page | Performance Report |
| E2E latency (P50/P95) | `dashboard/latency_logger.py` | Performance Report |
| Recognition accuracy | pilot sessions (confusion: accept/reject/unknown) | Validation Report |
| Attendance success rate | sessions ÷ enrolled present | Validation Report |
| Spoof rejection rate | artifact tests | Security Report |

Re-measure on **the actual deployment hardware** at the start of each phase —
numbers from a dev laptop must not be assumed to transfer.

---

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|:-----|:-----------|:-------|:-----------|
| GPU unavailable on deployment hardware | Med | Lower multi-person FPS | CPU mode supported; size pilot to ≤ 1 classroom first |
| Lighting/angles differ from lab | Med | Lower recognition accuracy | Re-enrol on-site; tune `recognition_threshold` |
| Network camera instability | Med | Missed attendance windows | Auto-reconnect + health monitoring; ops runbook |
| Redis not running in pilot | Low | Cooldown cache degraded | In-memory fallback; verify Redis at Gate 0 |
| Attendance privacy concerns | Low-Med | Institutional friction | Display signage; retention bounded; access control (Security Report) |

---

## 8. Related Documents

- `FINAL_ACCEPTANCE_REPORT.md` — what is/isn't validated today
- `docs/DEPLOYMENT.md` — production deployment
- `docs/ADMIN_MANUAL.md` — operations & maintenance
- `docs/PERFORMANCE_REPORT.md` — current measured numbers (dev hardware)
- `docs/SECURITY_REPORT.md` — security posture & residual risks
- `docs/BACKUP_RESTORE_GUIDE.md` — backup/restore automation
