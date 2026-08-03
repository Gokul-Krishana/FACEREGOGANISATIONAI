# Section 14 — Performance

## 14.1 Performance Strategy

The system is designed for **real-time CPU inference on commodity hardware**.
Every stage is optimized to reduce wasted work while keeping the display fluid.

## 14.2 Threading Model

| Thread | Owner | Work | Lifecycle |
|--------|-------|------|-----------|
| Capture loop | `LiveRecognitionPipeline` | reads camera → `frame_buffer.put()` | daemon; stopped via join(3s) |
| Recognition worker | `LiveRecognitionPipeline` | AMFR pipeline → `results_buffer` | daemon; adaptive cadence |
| Latency sampler | `LiveRecognitionPipeline` | E2E frame age → `LatencyLogger` | daemon; 0.05 s cadence |
| Job queue workers | `api/job_queue.py` | asyncio tasks (3 workers) | started/stopped by FastAPI lifespan |
| WebSocket heartbeat | `api/websocket_manager.py` | ping + dead-client cleanup | asyncio task, 15 s |

**Why background threads:** Streamlit reruns the script top-to-bottom; the
camera must survive reruns, so capture/AI run in daemon threads and the UI
only reads the latest frames/results (non-blocking).

## 14.3 Queues & Buffers

| Buffer | Semantics | Prevents |
|--------|-----------|----------|
| `FrameBuffer(maxlen=1)` | latest-frame-only; stale frames dropped | queue buildup on slow consumers |
| `ResultsBuffer(maxlen=1)` | latest results only | stale overlays |
| `asyncio.Queue(maxsize=100)` (job queue) | bounded job queue | unbounded memory |
| WebSocket event buffer | last 100 events | slow-client disconnect data loss |

**Key property:** writers never block on slow readers; readers never wait.

## 14.4 Frame Buffer Benefits

- Camera thread can run at full capture rate while AI is still processing
  the previous frame.
- Streamlit reruns always see the newest frame, so video never lags by an
  accumulating queue.
- `get_with_meta()` returns timestamps → precise E2E latency measurement.

## 14.5 Caching

| Cache | Where | Effect |
|-------|-------|--------|
| `SharedModelResources._cache` | 04_Live.py | YOLO/InsightFace/FAISS/AMFR loaded **once** (~2 GB RAM saved across pipelines) |
| `with_shared_models()` | recognition_service | shares models, isolates per-pipeline state |
| `_employee_cache` | LiveDetection | name→employee_id DB lookup avoided per frame |
| `_verified_at` track cache | pipeline | verified scenes run AI 6× less often (0.6 s vs 0.1 s) |
| `st.cache_data` | dashboard pages | SQL/DF results cached with TTL (3–60 s) |
| `st.cache_resource` | dashboard | long-lived resources across reruns |
| Redis (optional) | api/redis_client | attendance dedupe, camera status, cooldowns, OIDC state |

## 14.6 AI-Specific Optimizations

| Optimization | Implementation | Benefit |
|--------------|----------------|---------|
| Frame skip | `FRAME_SKIP=2` (CLI/service) | 50–75% fewer inferences |
| Downscale | AI on 320×240 (`AI_PROCESS_SIZE`) | ~4× faster YOLO/ArcFace |
| Early exit | no detections → skip FAISS/AMFR | ~200 ms saved on empty frames |
| Adaptive cadence | verified tracks → 0.6 s interval | big CPU saving when scene is stable |
| Camera FPS cap | 15 FPS via CAP_PROP_FPS | less USB bandwidth |
| LBP downscale | 48×48 for texture analysis | ~0.1 ms per call |
| HNSW index | approximate ANN (efSearch=128) | sub-linear search |
| FPS EMA | `0.9*old + 0.1*new` | stable FPS readouts |
| psutil hoisted | module-level import | no repeated import lookup in hot path |

## 14.7 GPU Usage

- **Currently CPU-only inference:** InsightFace uses
  `CPUExecutionProvider`; onnxruntime uses `CPUExecutionProvider`.
- Dockerfile supports GPU builds (`--gpus all`) — the base image includes
  GPU-capable deps, but the code paths run on CPU by default.
- GPU acceleration is future work for higher multi-camera FPS.

## 14.8 CPU Usage

- YOLO11n: ~15–40 ms/frame (CPU).
- InsightFace (RetinaFace+ArcFace) on person crop: ~20–60 ms.
- MiniFASNet ONNX: ~5 ms; fallback CNN: ~0.5 ms.
- Quality/LBP/blink/motion: sub-ms each.
- With frame-skip + downscale + adaptive cadence, total CPU is modest for a
  single camera on a modern laptop.

## 14.9 Memory Usage

- Models in RAM: YOLO11n ~6 MB weights + runtime; buffalo_l ~200 MB;
  FAISS index grows with enrollments (512-D float32 = 2 KB/vector + graph
  overhead for HNSW); fallback CNN negligible.
- Streamlit reruns are cheap because models are cached in `_cache`.
- LatencyLogger window bounded (500 samples); WS event buffer bounded (100).

## 14.10 Measured Performance (references)

The repository includes benchmark scripts and reports:
- `scripts/benchmarks/profile_pipeline.py` — per-stage profiling.
- `scripts/benchmarks/faiss_benchmark.py` — index build/query timing.
- `scripts/benchmarks/camera_validation.py` — camera latency/FPS.
- `scripts/benchmarks/fake_camera_validation.py` — hardware-free pipeline FPS/latency.
- `scripts/benchmarks/scalability_benchmark.py` — enrollment scale tests.
- `docs/PERFORMANCE_REPORT.md` — measured GPU-accelerated report.
- `scripts/benchmarks/tune_hnsw.py` / `tune_ivf.py` — index tuning
  (M=32, efC=200, efS=128; nlist=200, nprobe=256).

## 14.11 Optimization Recommendations (future)

1. ONNX-export YOLO + ArcFace for faster, more portable inference.
2. GPU execution providers when NVIDIA hardware is available.
3. Reduce re-validation frequency (raise `identity_ttl` carefully).
4. Batch FAISS searches across detections.
5. Vectorize the IoU matching loop (currently Python loops over track×detection).

---

*References: `dashboard/pages/04_Live.py`, `dashboard/frame_buffer.py`,
`config/settings.yaml`, `scripts/benchmarks/*`, `docs/PERFORMANCE_REPORT.md`*
