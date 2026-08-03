# Section 25 — Why Each Technology Was Chosen

## 25.1 Why YOLO (Ultralytics YOLO11)?

- **Single-pass detection:** predicts all boxes in one forward pass —
  real-time on CPU.
- **Ecosystem:** mature Python API (`YOLO(model)(frame)`), auto-download,
  ONNX export, active maintenance.
- **Nano size:** `yolo11n.pt` ~6 MB — feasible to ship/download in a
  college environment.
- **COCO-trained:** the "person" class works out of the box for
  attendance scenes.
- **Alternatives considered:** YOLOv8/YOLOv5 (older), MediaPipe (person
  landmarks only), HOG+SVM (classic, less robust).
- **Trade-off:** detects *people* not *faces* — hence the RetinaFace stage.

## 25.2 Why ArcFace (InsightFace buffalo_l)?

- **Discriminative embeddings:** additive-angular-margin training produces
  highly separable 512-D vectors.
- **Proven accuracy:** state-of-the-art on LFW/MegaFace-class benchmarks.
- **Single pack:** `buffalo_l` bundles RetinaFace + ArcFace → one model
  load, one dependency.
- **L2 normalization:** embeddings are unit-norm, so FAISS L2 distance ≈
  cosine distance — simple, well-understood matching.
- **Alternatives:** FaceNet (older, heavier), CosFace/SphereFace (similar
  family), Dlib ResNet (slower on CPU).
- **Trade-off:** ~200 MB download; CPU-only inference in this project.

## 25.3 Why FAISS?

- **Performance:** sub-linear ANN search (HNSW) vs brute-force O(N)
  comparison — critical as enrollments grow to thousands.
- **Offline/in-process:** runs locally, no server to operate — aligns with
  the offline-first requirement.
- **Flexibility:** flat (exact) / HNSW (speed-recall) / IVF (scale) index
  types, tunable via benchmark scripts.
- **Serialization:** `faiss.write_index`/`read_index` → simple persistence
  in `embeddings/`.
- **Alternatives:** Milvus/Qdrant (server-based, heavier), hnswlib
  (smaller API), pgvector (needs PostgreSQL 11+ and SQL integration),
  Chroma (higher overhead for this use).
- **Trade-off:** no native deletion — the project rebuilds the index on
  delete/rename (O(N)).

## 25.4 Why PostgreSQL (production)?

- **Concurrency & ACID:** many cameras + API clients writing attendance
  concurrently.
- **Advanced indexing:** composite indexes for the attendance/recognition
  hot paths (validated by the scalability migration).
- **JSON columns:** MFA backup codes, audit details, face metadata.
- **Industry standard:** tooling, backups (`pg_dump`), hosting options.
- **Alternatives:** MySQL (weaker JSON/composite-index ergonomics for this
  schema), MSSQL/Oracle (proprietary, heavy for a college).

## 25.5 Why SQLite (development)?

- **Zero configuration:** single file, no server — perfect for dev,
  demos, and small pilots.
- **Fast iteration:** `init_db()` fallback to `create_all()`.
- **Portable:** easy to share/test.
- **Trade-off:** single-writer — explicitly not for campus-scale
  concurrent production writes (PostgreSQL is the prod path).

## 25.6 Why Redis?

- **Fast ephemeral state:** attendance dedupe markers, recognition
  cooldowns, camera status, track identity cache — all with TTLs.
- **OIDC CSRF state:** short-lived one-time state values.
- **Graceful degradation:** every call is optional — the system runs fully
  without Redis (tests skip; API logs warnings).
- **Alternatives:** in-process dict (not shared across processes), Memcached
  (no rich types/TTL ergonomics), database tables (slower for hot state).

## 25.7 Why Streamlit?

- **Python-native UI:** the whole team's stack is Python — no JS needed.
- **Rerun model fits camera loops:** the live page leverages
  `st.rerun()` + session state + cached models elegantly.
- **Rapid iteration:** 10 pages built quickly with widgets, charts, forms.
- **Alternatives:** Gradio (demo-oriented, weaker multi-page apps), Dash
  (more control, more boilerplate), Flask+JS (full custom frontend cost),
  Panel.
- **Trade-off:** rerun model requires careful state management (solved via
  `CameraOwner` + global buffers + `@st.cache_data/resource`).

## 25.8 Why FastAPI?

- **Async-first:** WebSockets (event stream), async OIDC/httpx, async job
  queue — all natural.
- **Pydantic validation:** request/response schemas with strong validators
  (password policy, regex fields).
- **Auto docs:** `/docs` + `/redoc` — free API documentation for integrators.
- **Dependency injection:** `Depends()` powers auth/RBAC/permission chains.
- **Alternatives:** Flask (sync, manual validation/docs), Django REST
  (heavier, batteries-included), Starlette (lower-level).
- **Trade-off:** ASGI ecosystem slightly newer than WSGI.

## 25.9 Why MiniFASNet (deep liveness)?

- **Purpose-built:** a small CNN trained specifically for face
  anti-spoofing — catches print/screen attacks the software heuristics miss.
- **Lightweight:** ~4 MB ONNX, ~5 ms CPU inference.
- **Layered defense:** combined with LBP/blink/motion/screen heuristics for
  defense-in-depth.
- **Alternatives:** rPPG (needs longer video + quality), challenge-response
  (user cooperation), larger CNNs (slower).

## 25.10 Why the Custom IoU Tracker?

- **Zero dependencies** and predictable O(N²) matching for modest person
  counts.
- **Purpose-fit:** temporal score smoothing + identity stability is what
  AMFR needs; a full MOT (ByteTrack) adds complexity without proportional
  benefit for classroom scenes.
- **Honest limitation:** weaker under occlusion — flagged as future work
  (§29.3).

## 25.11 Why Docker + docker-compose?

- **Reproducible environment** for the AI stack (OpenCV system libs,
  torch, etc.).
- **One-command stack:** PostgreSQL + Redis + app with healthchecks.
- **CI parity:** the Docker image is built and vulnerability-scanned in
  CI (Trivy + Grype).
- **Portable demo:** a college IT team can deploy without deep Python
  knowledge.

## 25.12 Why GitHub Actions?

- **Free CI/CD for public repos**; multi-workflow split (Python tests,
  frontend verification, Docker build + container scanning, security).
- **SARIF uploads** surface container CVEs in the GitHub Security tab.
- **Alternatives:** GitLab CI, CircleCI, Jenkins (all viable; GH Actions
  co-located with the repo).

---

*References: `requirements.txt`, `README.md` (Key Design Decisions), code
comments in `app/*`, `scripts/benchmarks/*`*
