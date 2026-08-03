# Section 5 — Complete AI Pipeline

## 5.1 Pipeline Overview

The recognition pipeline is a **sequential cascade of specialist models and
checks**. Each stage is deliberately placed so that cheap operations run
first and expensive ones run only when needed:

```
Camera frame (640×480)
   │
   ▼
① YOLO11 person detection          (app/face_detector.py)
   │  person bboxes only (COCO class 0)
   ▼
② Tracking (IoU matching)          (app/tracking.py)
   │  track_id per person; identity/temporal smoothing
   ▼
③ RetinaFace face detection        (app/recognizer.py)
   │  face bbox + 5 landmarks + det_score
   ▼
④ Face Quality assessment          (app/face_quality.py)
   │  0–1 quality score
   ▼
⑤ Liveness — 5 factors             (app/liveness_detector.py + app/deep_liveness.py)
   │  texture / blink / motion / screen / deep CNN
   ▼
⑥ ArcFace embedding (512-D)        (app/recognizer.py)
   │  L2-normalized vector
   ▼
⑦ FAISS nearest-neighbor search    (app/enrollment.py)
   │  name + L2 distance + confidence
   ▼
⑧ AMFR decision engine             (app/amfr_engine.py)
   │  risk score → ACCEPT / BORDERLINE / LOW_CONFIDENCE / REJECT_SPOOF
   ▼
⑨ Attendance + DB logging          (attendance.py, services/, repositories)
```

> **Note on ByteTrack:** the README and pipeline diagrams describe this stage
> as "ByteTrack" (its role in the cascade), but the shipped code implements a
> **custom greedy IoU multi-object tracker** (`app/tracking.py`), not the
> ByteTrack library. §5.3 documents what the code actually does.

## 5.2 Stage-by-Stage Detail

### Stage ① — YOLO11 Person Detection
- **Why used:** A dedicated person detector is the cheapest reliable way to
  localize people in a full frame; it also rejects non-face regions and lets
  the system skip the entire pipeline when nobody is present (early exit).
- **Why chosen:** Ultralytics YOLO11n is a small (~6 MB) COCO-trained model
  with excellent speed/accuracy on CPU, a mature Python API, and ONNX export
  support.
- **Alternatives:** YOLOv8/YOLOv5 (older), MediaPipe Pose (person
  landmarks), HOG+SVM (classic, slower to tune), MobileNet-SSD.
- **Advantages:** Single-pass detection, strong COCO benchmark, active
  ecosystem.
- **Disadvantages:** Detects *people*, not *faces* — needs the RetinaFace
  stage; COCO-trained (not face-specific).
- **Input:** BGR frame.
- **Output:** `[{"bbox": (x1,y1,x2,y2), "confidence", "class_id": 0}]`.
- **Implementation notes:** `FaceDetector.detect()` filters to class 0 and
  applies `cfg.YOLO_CONFIDENCE` (default 0.5/0.6). `crop_person()` adds 15%
  padding. Early exit: if no detections, the rest of the pipeline is skipped
  (~200 ms saved per empty frame).

### Stage ② — Tracking (custom IoU tracker)
- **Why used:** A single recognition on one frame is noisy. Tracking
  accumulates evidence over time (identity stability, score averages) so the
  AMFR decision is temporal, not instantaneous, and attendance is not marked
  twice for the same person walking across the room.
- **Why chosen (implementation):** a greedy IoU matcher is simple, fast, and
  dependency-free; it suits indoor camera scenes with modest occlusion.
- **Alternatives:** ByteTrack (SORT-based, SOTA), DeepSORT (appearance
  re-ID), Norfair, Kalman-filter trackers.
- **Advantages:** Zero extra dependencies; O(tracks×detections) IoU matrix;
  easy to reason about.
- **Disadvantages:** No motion prediction or appearance re-ID → identity
  switches under heavy occlusion; "ByteTrack" naming in docs overstates the
  shipped capability.
- **Input:** detection dicts with `bbox` (+ optional scores).
- **Output:** `TrackState` objects with `track_id`, `total_frames`,
  `consistent_frames`, `identity`, `identity_confidence`,
  `identity_stability`, score accumulators, `spoof_frame_count`,
  `attendance_marked`.
- **Implementation notes:** Two `update()` calls per frame in AMFR — first
  with bbox-only detections (assigns track IDs), then with enriched results
  (feeds identity back for smoothing). Tracks disappear after
  `max_disappeared=30` frames.

### Stage ③ — RetinaFace Face Detection
- **Why used:** Converts a person bbox into a precise face bbox + 5 facial
  landmarks — needed for alignment, quality, liveness (blink), and cropping.
- **Why chosen:** Bundled inside InsightFace's `buffalo_l` pack, so it shares
  the runtime with ArcFace (one load, one dependency).
- **Alternatives:** MTCNN, YuNet (OpenCV Zoo), SCRFD, DSFD.
- **Advantages:** Accurate 5-point landmarks; tuned for ArcFace pipelines.
- **Disadvantages:** Heavier than YOLO; CPU-only in this project
  (`CPUExecutionProvider`).
- **Input:** person crop.
- **Output:** `{"bbox", "landmarks" (5×2), "embedding", "det_score"}` or
  `None` when no face.
- **Implementation notes:** `detect_face()` normalizes the embedding too;
  `get_landmarks()` is a separate helper.

### Stage ④ — Face Quality Assessment
- **Why used:** Poor faces (blurry, dark, tiny, extreme angle) produce
  unreliable embeddings and false reject/accept. Quality gates the whole
  decision.
- **Why chosen:** 6 interpretable CV metrics — no extra model download.
- **Alternatives:** SER-FIQ, FaceQnet (learned quality estimators).
- **Advantages:** Fast, explainable, zero deps.
- **Disadvantages:** Heuristic — less calibrated than learned models.
- **Input:** face crop, det_score, face bbox, frame shape, landmarks.
- **Output:** `overall` 0–1, `passed`, `metrics`, `failure_reasons`.
- **Threshold:** `FACE_QUALITY_MIN_SCORE = 0.35`; weights:
  blur 0.30, brightness 0.15, contrast 0.10, size 0.15, det 0.20, pose 0.10.

### Stage ⑤ — Liveness (5 factors)
- **Why used:** Defeat presentation attacks (printed photo, phone screen,
  replayed video) that defeat 2D face recognition.
- **Factors:**
  1. **Texture (LBP):** real skin has high-variance LBP histograms; prints/screens are uniform.
  2. **Blink (EAR):** eye-aspect-ratio state machine detects natural blinks.
  3. **Motion:** frame-differencing/optical-flow magnitude (liveness needs natural motion).
  4. **Screen edges:** Canny edge density near borders flags phone/tablet bezels.
  5. **Deep CNN:** MiniFASNet ONNX (80×80, 3-class softmax) or numpy fallback.
- **Why chosen:** layered defense-in-depth; the deep model catches what
  software heuristics miss; weights: 0.15/0.20/0.15/0.10/0.40 (deep dominant
  when available).
- **Alternatives:** single CNN only, remote photoplethysmography (rPPG),
  challenge-response (user gestures).
- **Advantages:** No user cooperation; real-time; works offline.
- **Disadvantages:** Software factors are heuristic; deep model needs a
  download; spoofs can evolve (training-data staleness).
- **Input:** face crop + landmarks (per-track detector instance).
- **Output:** `LivenessResult` with per-factor scores + `is_live`.

### Stage ⑥ — ArcFace Embedding
- **Why used:** Produces a compact, discriminative, L2-normalized 512-D
  representation whose cosine similarity approximates identity distance.
- **Why chosen:** Industry-standard face embedding (1:N recognition leader on
  LFW/MegaFace), bundled in `buffalo_l`.
- **Alternatives:** FaceNet, CosFace, SphereFace, Dlib ResNet.
- **Advantages:** High accuracy, large margin loss, robust to pose/lighting
  after alignment.
- **Disadvantages:** Embedding dim fixed; needs ~200 MB model pack.
- **Input:** person crop.
- **Output:** 512-D float32 unit-norm vector (or None).

### Stage ⑦ — FAISS Search
- **Why used:** Brute-force pairwise comparison of 512-D vectors is O(N) per
  query; FAISS gives sub-linear ANN search with tunable recall.
- **Why chosen:** Facebook AI's high-performance vector library; CPU support;
  multiple index types; serialization.
- **Alternatives:** Milvus, Qdrant, hnswlib, pgvector, Chroma.
- **Advantages:** Battle-tested, fast, in-process (offline).
- **Disadvantages:** Not a database (no native delete → index rebuild); no
  transactions; approximate indices trade recall.
- **Input:** query embedding, k=1, threshold.
- **Output:** `[{"name", "confidence", "distance"}]`; confidence = `1/(1+d²)`.
- **Index types:** `flat` (exact), `hnsw` (default; M=32, efC=200, efS=128),
  `ivf` (nlist=200, nprobe=256).

### Stage ⑧ — AMFR Decision Engine
- **Why used:** A single similarity score is a weak signal. AMFR fuses
  **ArcFace similarity + liveness + quality** into a weighted risk score and
  applies gates so spoofs are hard-rejected and marginal matches are
  deferred (BORDERLINE) instead of guessed.
- **Weights:** arcface 0.45, liveness 0.35, quality 0.20.
- **Gates:** liveness gate (spoof → REJECT_SPOOF), quality gate (soft).
- **Thresholds:** ≥0.70 ACCEPT; ≥0.40 BORDERLINE; low → LOW_CONFIDENCE.
- **Input:** detection, embedding, FAISS results, face data, track_id.
- **Output:** augmented detection: `name`, `confidence`, `amfr_decision`,
  `risk_score`, `amfr_details`, `trigger_security_alert`.

### Stage ⑨ — Attendance + Logging
- ACCEPT → `AttendanceService.mark()` (DB + CSV, per-day dedupe, audit) +
  `RecognitionLogRepo.create()`.
- BORDERLINE → log recognition (known, not marked), keep collecting frames.
- REJECT_SPOOF → log `is_spoof=True` + `AuditService.log("SPOOF_ATTEMPT")`.
- LOW_CONFIDENCE → save unknown face (cooldown 3 s) + `UnknownFaceRepo.create()`.

## 5.3 Tracking Deep-Dive (what the code actually does)

`MultiFrameTracker.update(detections, frame_shape)`:
1. If no detections → mark all tracks disappeared.
2. If no tracks → create tracks for all detections.
3. Else compute **IoU matrix** between track bboxes and detection bboxes.
4. **Greedy assignment**: repeatedly pick the highest-IoU pair until < 0.01.
5. Update matched tracks (`_update_track`), increment disappear counts for
   unmatched tracks, prune tracks gone > 30 frames, create new tracks for
   unmatched detections.

`TrackState` accumulates `arcface_distances`, `liveness_scores`,
`quality_scores`, `amfr_decisions` and exposes averages + `identity_stability`
(= consistent_frames / total_frames). The AMFR engine feeds identity back in
the second `update()` call, enabling temporal smoothing of names and scores.

## 5.4 AMFR Decision Table (visual)

| Decision | Condition | Visual | Action |
|----------|-----------|--------|--------|
| ✅ ACCEPT | risk ≥ 0.70, live, quality ok | 🟢 Green + name + PRESENT | Attendance marked |
| ⚠️ BORDERLINE | 0.40 ≤ risk < 0.70 (or arcface>0.3 & quality>0.4) | 🟡 Yellow + "COLLECTING FRAMES" | More frames |
| ❓ LOW_CONFIDENCE | risk < 0.40, no arcface match | ⚫ Grey + UNKNOWN | Unknown snapshot |
| 🚫 REJECT_SPOOF | liveness < 0.15 or not live | 🔴 Red + SPOOF | Reject + alert + audit |

---

*References: `app/amfr_engine.py`, `app/live_detection.py`,
`services/recognition_service.py`, `dashboard/pages/04_Live.py`, `README.md`*
