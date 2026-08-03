# Section 6 — Machine Learning Models

This section documents every AI model used, with architecture, training
data, working principle, output, accuracy, and limitations — verified
against the source code.

---

## 6.1 YOLO11 (Ultralytics) — Person Detection

| Attribute | Detail |
|-----------|--------|
| **File** | `models/yolo11n.pt` (auto-downloaded on first use) |
| **Used in** | `app/face_detector.py` |
| **Task** | Person localization (COCO class 0) |

**Architecture:** YOLO11 ("You Only Look Once") is a single-stage CNN
object detector. It divides the image into a grid and predicts bounding
boxes + class probabilities in one forward pass. The `n` (nano) variant is
the smallest: roughly 2.6M parameters, ~6 MB weights.

**Training dataset:** COCO (Common Objects in Context) — 118K training
images, 80 classes. The "person" class is the only one used here.

**Working principle:** Anchor-free detection with a backbone (CSPNet-style),
neck (PAN-FPN), and head producing box + class + confidence outputs. NMS
(Non-Maximum Suppression) removes duplicate boxes.

**Output:** person bounding boxes `(x1,y1,x2,y2)` + confidence.

**Accuracy:** Excellent on COCO person detection (~50+ mAP@0.5 for nano);
real-world accuracy depends on camera angle and distance.

**Limitations:**
- Detects whole people, not faces (needs RetinaFace stage).
- COCO-trained — no fine-tuning for classroom scenes.
- Runs on CPU here (`Ultralytics` default device is CPU in this codebase).
- Single-frame detection — no motion modelling.

---

## 6.2 RetinaFace — Face Detection + Landmarks

| Attribute | Detail |
|-----------|--------|
| **File** | Inside InsightFace `buffalo_l` pack (`~/.insightface` / `models/.insightface`) |
| **Used in** | `app/recognizer.py` |
| **Task** | Face detection + 5-point landmark regression |

**Architecture:** RetinaFace is a single-stage face detector built on a
ResNet/ResNeXt backbone with a feature pyramid (FPN) and context modules.
It predicts: face boxes, 5 facial landmarks, and a detection score. The
version in `buffalo_l` also performs face alignment internally.

**Training dataset:** WIDER FACE (32K images, 394K faces) plus extra
landmark annotations.

**Working principle:** Dense anchors over the feature pyramid; regression
head refines boxes/landmarks; NMS merges duplicates. `FaceAnalysis.prepare()`
uses det_size=(640,640).

**Output:** `face.bbox`, `face.landmark` (5×2), `face.det_score`,
`face.embedding` (used for ArcFace in this pipeline).

**Accuracy:** Very high recall on frontal and profile faces; landmarks are
stable enough for blink detection and alignment.

**Limitations:**
- CPU execution only (`CPUExecutionProvider`, `ctx_id=-1`).
- First face only is returned per call (`faces[0]`).
- Small/occluded faces can be missed.

---

## 6.3 ArcFace — Face Embedding

| Attribute | Detail |
|-----------|--------|
| **File** | Inside InsightFace `buffalo_l` pack |
| **Used in** | `app/recognizer.py` (embedding extraction) |
| **Task** | Map a face to a discriminative 512-D embedding |

**Architecture:** A ResNet-100 backbone (for buffalo_l) trained with the
**ArcFace (Additive Angular Margin)** loss: embeddings are pushed to a
hypersphere where the angle between vectors encodes identity distance.

**Training dataset:** WebFace42M / MS1MV3-scale face datasets (buffalo_l is
trained on large web face corpora).

**Working principle:** Face → CNN → 512-D feature vector → L2 normalization
(unit norm). Cosine similarity between two embeddings approximates the
probability they are the same person. In this codebase embeddings are
L2-normalized so **FAISS L2 distance ≈ cosine distance**.

**Output:** 512-D float32 unit-norm embedding (`EMBEDDING_DIM = 512`).

**Accuracy:** buffalo_l achieves state-of-the-art accuracy on LFW (99%+),
MegaFace, and IJB benchmarks.

**Limitations:**
- Requires a reasonably frontal, well-lit face (alignment helps).
- Fixed dimension (512).
- ~200 MB model pack download on first use.

---

## 6.4 MiniFASNet — Deep Liveness CNN

| Attribute | Detail |
|-----------|--------|
| **File** | `models/liveness/MiniFASNetV2.onnx` (~4 MB, auto-downloaded from `yakhyo/face-anti-spoofing` releases) |
| **Used in** | `app/deep_liveness.py` |
| **Task** | Binary-ish anti-spoofing (live vs presentation attack) |

**Architecture:** MiniFASNet is a lightweight CNN (~1.6M params) from the
Silent-Face-Anti-Spoofing project. It takes a small face crop and emits
class logits. The ONNX export used here expects **80×80 RGB** input and
produces **3 class logits** `[spoof, fake, live]` (postprocessed with
softmax; index 2 = live).

**Training dataset:** The SFAS (Silent-Face-Anti-Spoofing) training set of
real and attack faces (printed photos, screens, etc.).

**Working principle:** Standard CNN feature extraction + classification.
The repository also ships a **fallback**: if ONNX Runtime or the model file
is unavailable, a numpy-only classifier runs using color histograms, FFT
frequency distribution, gradient statistics, and channel correlation
(~0.5 ms/call).

**Output:** `DeepLivenessResult(dl_score 0–1, is_live, inference_time_ms)`.
Threshold: `DEEP_LIVENESS_THRESHOLD = 0.50`.

**Accuracy:** Strong against print/screen attacks on its training
distribution; the fallback is heuristic.

**Limitations:**
- Model source moved upstream (the original repo removed the ONNX export —
  this project now uses the maintained yakhyo export; noted in code comments).
- 80×80 input is low resolution.
- Spoofing techniques evolve; periodic model refresh is recommended.
- ONNX inference ~5 ms per face (CPU).

---

## 6.5 FAISS — Vector Search Index (not a model, but an AI-infrastructure component)

| Attribute | Detail |
|-----------|--------|
| **File** | `embeddings/faiss.index` + `embeddings/metadata.json` |
| **Used in** | `app/enrollment.py` |
| **Task** | Approximate/exact nearest-neighbor search over 512-D embeddings |

**Architecture:** Three supported index types (config in `settings.yaml`):
- `flat` — `IndexFlatL2`, exact brute-force (best recall, slow at scale).
- `hnsw` — `IndexHNSWFlat`, hierarchical navigable small-world graph
  (default; M=32, efConstruction=200, efSearch=128).
- `ivf` — `IndexIVFFlat`, inverted-file with Voronoi cells
  (nlist=200, nprobe=256).

**Working principle:** `index.add()` builds the index; `index.search(query,
k)` returns distances + indices. HNSW/Flat/IVF support `reconstruct()`,
which is used for delete/rename rebuilds. HNSW search parameters are not
persisted by `faiss.write_index`, so they are restored at load time.

**Output:** top-k `(distances, indices)`.

**Accuracy/recall:** Flat = 100% recall; HNSW/IVF approximate (tuned by
benchmarks in `scripts/benchmarks/`).

**Limitations:**
- **No native delete** — `remove()` raises `NotImplementedError`;
  `remove_by_name()`/`rename()` rebuild the index in O(N).
- Raw embeddings are not stored independently (recommended future: `.npy`).

---

## 6.6 The Tracker (not a neural model, but an algorithm)

**Implementation:** `app/tracking.py` — greedy IoU matcher (documented in
§5.3). No Kalman filter, no appearance re-ID. It is described as
"ByteTrack" in README diagrams, but the shipped code is the custom IoU
tracker.

---

## 6.7 Model Accuracy Summary

| Model | Metric | Expected Range (CPU, this project) |
|-------|--------|------------------------------------|
| YOLO11n | Person detection conf | > 0.5 (threshold `YOLO_CONFIDENCE`) |
| RetinaFace | det_score | typically 0.9–1.0 on clear faces |
| ArcFace | Embedding cosine/L2 | L2 < threshold (1.0 default) for same person |
| FAISS confidence | `1/(1+d²)` | > 0.7 for confident matches |
| MiniFASNet | dl_score | ≥ 0.5 live; < 0.15 spoof-hard-reject |
| AMFR risk | weighted composite | ≥ 0.70 ACCEPT; ≥ 0.40 BORDERLINE |

---

*References: `requirements.txt` (torch, ultralytics, insightface, faiss-cpu,
onnxruntime), `app/*`, `config/config.py`*
