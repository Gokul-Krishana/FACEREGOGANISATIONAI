# Section 19 — Benchmarks

## 19.1 Benchmark Suite (`scripts/benchmarks/`)

| Script | What it measures | Typical usage |
|--------|------------------|---------------|
| `faiss_benchmark.py` | FAISS index build time, search latency, recall at N vectors | `python scripts/benchmarks/faiss_benchmark.py` |
| `tune_hnsw.py` | HNSW M / efConstruction / efSearch sweeps | generates tuned params (now M=32, efC=200, efS=128 in settings.yaml) |
| `tune_ivf.py` | IVF nlist / nprobe sweeps | generates tuned params (nlist=200, nprobe=256) |
| `benchmark_real_embeddings.py` | Recognition with real ArcFace embeddings | accuracy/confidence realism check |
| `camera_validation.py` | Camera FPS, E2E latency (p50/p95), drop rate | per-camera hardware validation |
| `fake_camera_validation.py` | Pipeline FPS/latency without hardware | CI-friendly validation |
| `scalability_benchmark.py` | Enrollment scale (100 → 100K vectors) | capacity planning |
| `profile_pipeline.py` | Per-stage timing (YOLO/RetinaFace/ArcFace/FAISS/AMFR) | identifies bottlenecks |
| `probe_environment.py` | Dependency versions, GPU availability, env sanity | pre-deployment |
| `validate_amfr.py` | AMFR decision correctness (accept/borderline/reject) | threshold sanity |

## 19.2 Key Benchmarked Quantities

### FAISS
- **Index type comparison:** flat vs hnsw vs ivf — build time, query time,
  memory, recall@1.
- **Search latency:** sub-ms at thousands of vectors (HNSW); tuning scripts
  produced the shipped defaults.
- **Recall trade-off:** efSearch higher → better recall, slower query.

### AMFR
- `validate_amfr.py` verifies the decision matrix:
  - high liveness + high arcface → ACCEPT
  - marginal scores → BORDERLINE
  - low everything → LOW_CONFIDENCE
  - liveness below spoof threshold → REJECT_SPOOF

### Latency
- **E2E frame latency:** Camera → FrameBuffer → display (measured by
  `camera_validation.py` and the Live page's `LatencyLogger`):
  p50/p95/avg ms.
- **AI pipeline latency:** per-stage ms (profile_pipeline.py) and total
  frame processing time.
- **FPS:** capture FPS, AI FPS, display FPS (EMA-smoothed).

### Accuracy
- **Recognition confidence** = `1/(1+d²)` mapping from FAISS L2 distance.
- **Threshold guidance** (settings.yaml comments):
  - 0.0–0.5 → exact duplicate
  - 0.5–1.0 → same person, similar conditions
  - 1.0–1.5 → same person, different lighting/angle (default threshold 1.0)
  - 1.5–2.0 → possibly different person
  - >2.0 → almost certainly different person

### Precision / Recall (operational)
- No formal PR curves are shipped; `benchmark_real_embeddings.py` and the
  acceptance reports provide empirical accuracy observations. On-site
  precision/recall measurement is an explicit **pilot phase task**
  (see `docs/PILOT_DEPLOYMENT_PLAN.md`).

## 19.3 Where Results Live

| Artifact | Content |
|----------|---------|
| `docs/PERFORMANCE_REPORT.md` | Measured GPU-accelerated performance |
| `docs/GAP_ANALYSIS_COLLEGE_SCALE.md` | College-scale capacity analysis |
| `FINAL_ACCEPTANCE_REPORT.md` | Test + validation summary (490 green) |
| `POSTGRESQL_VALIDATION_REPORT.md` | PostgreSQL + Redis validation |
| `LIVE_SYSTEM_VALIDATION_REPORT.md` | Live pipeline verification |
| `CAMERA_STABILIZATION_REPORT.md` | Camera stability validation |

## 19.4 Running a Quick Benchmark

```bash
python scripts/benchmarks/faiss_benchmark.py
python scripts/benchmarks/fake_camera_validation.py
python scripts/benchmarks/profile_pipeline.py
python scripts/benchmarks/validate_amfr.py
python tools/validate_startup.py     # environment sanity
```

---

*References: `scripts/benchmarks/*`, `docs/PERFORMANCE_REPORT.md`,
`docs/GAP_ANALYSIS_COLLEGE_SCALE.md`, validation reports*
