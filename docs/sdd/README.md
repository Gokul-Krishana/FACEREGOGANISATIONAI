# FaceRecognitionAI — Complete Software Design Document (SDD)

**Project:** Face Recognition AI — Real-Time Face Recognition & Automatic Attendance System
**Version:** 2.0.0 (API) / 1.0 (Dashboard)
**Document status:** Official project documentation
**Generated from:** The actual source code of the repository (nothing assumed).

---

## 📚 How to use this document

This SDD is split into **30 sections**, each in its own file so it is easy to
navigate and maintain. A **combined single-file version** is available at
[`docs/PROJECT_DOCUMENTATION.md`](../PROJECT_DOCUMENTATION.md) for printing,
PDF export, and submission.

Every statement in these documents is grounded in the repository source code.
Where a feature is aspirational, missing, or a known limitation, it is
explicitly marked as such.

---

## 📑 Section Index

| # | Section | File | Summary |
|---|---------|------|---------|
| 1 | Project Overview | [`01_PROJECT_OVERVIEW.md`](01_PROJECT_OVERVIEW.md) | Goal, problem, solution, objectives, scope, features, benefits, applications, future scope |
| 2 | System Architecture | [`02_SYSTEM_ARCHITECTURE.md`](02_SYSTEM_ARCHITECTURE.md) | Full architecture + diagrams of the 8-stage pipeline |
| 3 | Complete Folder Structure | [`03_FOLDER_STRUCTURE.md`](03_FOLDER_STRUCTURE.md) | Every folder, why it exists, what it holds |
| 4 | Complete File Explanation | [`04_FILE_EXPLANATION.md`](04_FILE_EXPLANATION.md) | Every important file: purpose, classes, functions, flow, dependencies |
| 5 | Complete AI Pipeline | [`05_AI_PIPELINE.md`](05_AI_PIPELINE.md) | YOLO11 → ByteTrack → RetinaFace → Quality → Liveness → ArcFace → FAISS → AMFR → Attendance |
| 6 | Machine Learning Models | [`06_MACHINE_LEARNING_MODELS.md`](06_MACHINE_LEARNING_MODELS.md) | YOLO11, RetinaFace, ArcFace, MiniFASNet, FAISS, tracker internals |
| 7 | Database | [`07_DATABASE.md`](07_DATABASE.md) | SQLite, PostgreSQL, Redis, ORM, Alembic, Repository pattern |
| 8 | Complete Database Schema | [`08_DATABASE_SCHEMA.md`](08_DATABASE_SCHEMA.md) | Every table, columns, keys, indexes, ER diagram |
| 9 | API Documentation | [`09_API_DOCUMENTATION.md`](09_API_DOCUMENTATION.md) | Every endpoint: request, response, auth, errors |
| 10 | Streamlit Dashboard | [`10_STREAMLIT_DASHBOARD.md`](10_STREAMLIT_DASHBOARD.md) | All 10 pages, widgets, workflows |
| 11 | Security | [`11_SECURITY.md`](11_SECURITY.md) | JWT, RBAC, OIDC, MFA, liveness, upload security, audit, rate limiting, brute force |
| 12 | Attendance System | [`12_ATTENDANCE_SYSTEM.md`](12_ATTENDANCE_SYSTEM.md) | Complete attendance workflow |
| 13 | Camera System | [`13_CAMERA_SYSTEM.md`](13_CAMERA_SYSTEM.md) | Camera manager, owner, frame buffer, threads, multi-camera |
| 14 | Performance | [`14_PERFORMANCE.md`](14_PERFORMANCE.md) | Threading, queues, caching, GPU/CPU/memory, optimisations |
| 15 | Packages & Libraries | [`15_PACKAGES.md`](15_PACKAGES.md) | Every dependency: purpose, why, alternatives, usage |
| 16 | Configuration | [`16_CONFIGURATION.md`](16_CONFIGURATION.md) | settings.yaml, config.py, env vars, Docker |
| 17 | Deployment | [`17_DEPLOYMENT.md`](17_DEPLOYMENT.md) | Windows, Linux, Docker, production, development |
| 18 | Testing | [`18_TESTING.md`](18_TESTING.md) | Unit, integration, performance tests, coverage |
| 19 | Benchmarks | [`19_BENCHMARKS.md`](19_BENCHMARKS.md) | FAISS, AMFR, latency, FPS, accuracy benchmarks |
| 20 | Complete Workflow | [`20_COMPLETE_WORKFLOW.md`](20_COMPLETE_WORKFLOW.md) | Camera → attendance sequence diagram |
| 21 | Complete Data Flow | [`21_DATA_FLOW.md`](21_DATA_FLOW.md) | Full data flow diagram |
| 22 | Complete Class Diagram | [`22_CLASS_DIAGRAM.md`](22_CLASS_DIAGRAM.md) | UML class diagrams |
| 23 | Complete Module Diagram | [`23_MODULE_DIAGRAM.md`](23_MODULE_DIAGRAM.md) | Module dependency diagram |
| 24 | Complete Tech Stack | [`24_TECH_STACK.md`](24_TECH_STACK.md) | Languages, frameworks, libraries, models, databases |
| 25 | Why Each Technology | [`25_WHY_TECHNOLOGY.md`](25_WHY_TECHNOLOGY.md) | Rationale for YOLO, ArcFace, FAISS, PostgreSQL, Redis, Streamlit, FastAPI, SQLite |
| 26 | Design Patterns | [`26_DESIGN_PATTERNS.md`](26_DESIGN_PATTERNS.md) | Repository, Factory, Singleton, DI, Service Layer |
| 27 | Complete Project Flow | [`27_PROJECT_FLOW.md`](27_PROJECT_FLOW.md) | Every module interaction |
| 28 | Code Quality Review | [`28_CODE_QUALITY.md`](28_CODE_QUALITY.md) | Architecture, maintainability, scalability review + improvements |
| 29 | Production Readiness | [`29_PRODUCTION_READINESS.md`](29_PRODUCTION_READINESS.md) | Readiness, missing components, risks, checklist |
| 30 | Final Project Summary | [`30_FINAL_SUMMARY.md`](30_FINAL_SUMMARY.md) | Executive summary, architecture, recommendations |

---

## 🔗 Related Documentation (existing project reports)

The repository already contains extensive validation and operations
documentation. These are referenced as appendices throughout this SDD:

| Document | Content |
|----------|---------|
| [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) | Detailed system architecture & component map |
| [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) | Docker deployment, env vars, backup |
| [`docs/TROUBLESHOOTING.md`](../TROUBLESHOOTING.md) | Common issues & solutions |
| [`FINAL_ACCEPTANCE_REPORT.md`](../../FINAL_ACCEPTANCE_REPORT.md) | Acceptance vs client spec (490 tests green with Redis) |
| [`FINAL_VALIDATION_REPORT.md`](../../FINAL_VALIDATION_REPORT.md) | Final validation (393 tests passing) |
| [`PRODUCT_VALIDATION_REPORT.md`](../../PRODUCT_VALIDATION_REPORT.md) | Full product validation |
| [`SECURITY_REPORT.md`](../SECURITY_REPORT.md) | Security posture & threat model |
| [`PERFORMANCE_REPORT.md`](../PERFORMANCE_REPORT.md) | Measured GPU performance |
| [`DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md) | Database schema & index strategy |
| [`API_DOCUMENTATION.md`](../API_DOCUMENTATION.md) | REST API reference |
| [`USER_MANUAL.md`](../USER_MANUAL.md) | End-user guide |
| [`ADMIN_MANUAL.md`](../ADMIN_MANUAL.md) | Administrator guide |
| [`BACKUP_RESTORE_GUIDE.md`](../BACKUP_RESTORE_GUIDE.md) | Backup & restore guide |
| [`PILOT_DEPLOYMENT_PLAN.md`](../PILOT_DEPLOYMENT_PLAN.md) | Phased college rollout plan |
| [`GAP_ANALYSIS_COLLEGE_SCALE.md`](../GAP_ANALYSIS_COLLEGE_SCALE.md) | College-scale spec gap analysis |

---

## 📊 Repository Snapshot (verified from source)

| Metric | Value |
|--------|-------|
| Python packages | ~30 core dependencies |
| Test files | 20 pytest modules |
| Tests (with Redis + PostgreSQL) | **490 passed, 0 failed** |
| Tests (without Redis) | 484 passed, 6 skipped |
| Dashboard pages | 10 |
| API endpoints | 46 |
| Database tables | 20 + 2 association tables |
| AI models | YOLO11n, RetinaFace, ArcFace (buffalo_l), MiniFASNet (ONNX), FAISS |
| Roles | 7 (SUPER_ADMIN → STAFF) |
