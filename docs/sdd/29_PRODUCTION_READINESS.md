# Section 29 — Production Readiness

## 29.1 Current Readiness Statement

**Status: ✅ PILOT DEPLOYMENT READY** (not yet full-campus "production proven").

Based on `FINAL_ACCEPTANCE_REPORT.md` (calibrated 2026-08-02):

| Claim | Status |
|-------|--------|
| Every client requirement implemented | ✅ Verified (gap analysis 9.8/10) |
| Automated tests | ✅ 490 passed, 0 failed (with Redis + PostgreSQL); 484 + 6 skipped without |
| Code complete & stable | ✅ All modules documented and tested |
| **On-site validation** (real-person attendance, spoof artifacts, multi-classroom, load) | ⏳ **Not yet proven** — scoped to the pilot plan |
| Full campus-wide rollout | 🚫 Requires pilot decision gates |

## 29.2 Readiness Matrix

| Area | Score | Evidence |
|------|-------|----------|
| Functional completeness | 9.8/10 | gap analysis report |
| Automated test coverage | High | 490 tests |
| Security posture | Good | SECURITY_REPORT.md + code review |
| Performance | Good (CPU) | PERFORMANCE_REPORT.md + benchmarks |
| Deployment automation | High | Docker, compose, CI, scripts |
| Ops (backup/restore/monitoring) | Good | scripts + health/metrics endpoints |
| Documentation | High | README, docs/, this SDD |
| On-site proven behavior | **Not yet** | pilot plan phases |

## 29.3 Missing Components / Known Limitations (verified from source)

1. **Native FAISS delete** — `remove()` raises `NotImplementedError`; raw
   embeddings not stored independently (rebuilds are O(N)).
2. **Real MOT tracker** — custom IoU tracker (no ByteTrack), identity
   switches possible under occlusion.
3. **Placeholder job handlers** — batch_enroll / rebuild_index /
   cleanup_unknown simulate work; no real queue persistence.
4. **No API endpoint test suite** — endpoints unexercised by CI.
5. **Single active dashboard camera** — multi-camera UI is future work
   (schema/API support it).
6. **CPU-only inference** — GPU paths not configured in code.
7. **HSTS opt-in**, trusted-host list must be set in production.
8. **Redis-optional degradation** — some features (OIDC CSRF state) weaken
   without Redis (logged).
9. **On-site pilot evidence** — the single biggest gap (see §29.4).

## 29.4 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Spoof attack not caught by current models | Medium | High | 5-factor liveness + AMFR hard gate; pilot spoof testing; model refresh path (`reload()`) |
| Recognition accuracy poor in real classroom lighting/angles | Medium | High | Quality gating + BORDERLINE; pilot phase tuning of thresholds |
| Identity switches under occlusion | Medium | Medium | Tracker stability + session dedupe; consider MOT upgrade |
| PostgreSQL/Redis operational failure | Low-Med | Medium | Health checks, backup/restore, graceful Redis degradation |
| Data loss (FAISS rebuild clears on bad index type) | Low | High | `remove_by_name` guards; `.npy` store recommended; backups include index |
| Default credentials used in production | Low (guarded) | High | Seed script + prod secret-key guard; document password change |
| Torch/Windows DLL issues | Medium (dev envs) | Medium | Version pin `!=2.4.0` documented |
| Scale beyond 1 camera → CPU saturation | Medium | Medium | Shared models, adaptive cadence, GPU roadmap |

## 29.5 Production Deployment Checklist

**Foundation**
- [ ] Python 3.10+/Docker installed; deps installed (`pip install -r requirements.txt`)
- [ ] `alembic upgrade head` applied; `python scripts/seed_admin.py` run
- [ ] `SECRET_KEY` ≥32 chars set; `ENVIRONMENT=production`
- [ ] `DATABASE_URL` → PostgreSQL; Redis running (`REDIS_URL`)
- [ ] `CORS_ORIGINS` and TrustedHost list configured
- [ ] HTTPS + `ENABLE_HSTS=1`; firewall closes DB/Redis ports

**System**
- [ ] Camera validated (`python main.py --debug` or Health page)
- [ ] Enrollment flow tested (Enroll page) with ≥1 person
- [ ] Live recognition tested; attendance marked in DB + CSV
- [ ] Unknown-face capture + review workflow tested
- [ ] API smoke test: login → token → `/employees` → `/attendance`
- [ ] Backup job scheduled (`scripts/backup.py` + cron) and restore tested
- [ ] Prometheus `/metrics` scraped; alerting on health/lockouts

**Pilot gating (per `docs/PILOT_DEPLOYMENT_PLAN.md`)**
- [ ] Real-person attendance accuracy measured (precision/recall)
- [ ] Spoof artifact testing (photo, screen, video) passed
- [ ] Multi-classroom operation validated
- [ ] Infrastructure load behaviour at target camera count validated
- [ ] Decision gate review before campus-wide rollout

## 29.6 Production vs Pilot Feature Parity

| Feature | Available now | Notes |
|---------|---------------|-------|
| Recognition + attendance | ✅ | employee path active |
| Student/timetable attendance | ✅ API | schema + `api/attendance_service.py` |
| Multi-camera config | ✅ API/DB | dashboard UI single-camera |
| Bulk enrollment | ✅ scripts + API | CSV import, synthetic scale tests |
| Backup/restore | ✅ scripts | PostgreSQL + FAISS + metadata |
| Monitoring | ✅ | `/health*`, `/metrics`, Health page, LatencyLogger |
| Batch jobs | ⚠️ | placeholders |
| FAISS delete at scale | ⚠️ | rebuild-based |
| GPU acceleration | ❌ | roadmap |

---

*References: `FINAL_ACCEPTANCE_REPORT.md`, `FINAL_DELIVERY_REPORT.md`,
`docs/PILOT_DEPLOYMENT_PLAN.md`, `docs/SECURITY_REPORT.md`,
`docs/GAP_ANALYSIS_COLLEGE_SCALE.md`, `docs/DEPLOYMENT.md`*
