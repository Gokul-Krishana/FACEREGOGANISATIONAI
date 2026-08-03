"""
AMFR Validation Benchmark - A/B/C/D Comparison
=================================================

Compares four recognition pipelines:

    A: ArcFace + FAISS (baseline - no quality, no liveness)
    B: Quality + ArcFace + FAISS
    C: Quality + Liveness + ArcFace + FAISS
    D: Full AMFR (Quality + Liveness + ArcFace + FAISS + Tracking + Decision)

USES REAL ENROLLED FAISS INDEX + REAL TEST IMAGES.
Note: Quality/liveness scores use synthetic face crops because
the pipeline normally receives crops from RetinaFace (not available
from embeddings alone).

Usage:
    python scripts/benchmarks/validate_amfr.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config.config as cfg  # noqa: E402
from app.recognizer import FaceRecognizer  # noqa: E402
from app.face_quality import FaceQualityAssessment  # noqa: E402
from app.liveness_detector import LivenessDetector  # noqa: E402
from app.enrollment import FaceEnrollment  # noqa: E402
from app.amfr_engine import AMFREngine, AMFRDecision  # noqa: E402


def extract_embeddings(image_dir: Path) -> Tuple[List[np.ndarray], List[str], List[str]]:
    recognizer = FaceRecognizer()
    embeddings: List[np.ndarray] = []
    names: List[str] = []
    image_paths: List[str] = []
    for img_path in sorted(image_dir.glob("*.*")):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp"):
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        emb = recognizer.extract_embedding(img)
        if emb is not None:
            embeddings.append(emb)
            names.append(img_path.stem)
            image_paths.append(str(img_path))
    return embeddings, names, image_paths


def validate_variant(
    variant: str,
    embeddings: np.ndarray,
    names: List[str],
    enrollment: FaceEnrollment,
    quality: Optional[FaceQualityAssessment] = None,
    liveness: Optional[LivenessDetector] = None,
    amfr: Optional[AMFREngine] = None,
    num_queries: int = 10,
) -> Dict[str, Any]:
    if len(embeddings) == 0:
        return {"variant": variant, "error": "No query embeddings", "n_queries": 0}

    n = min(num_queries, len(embeddings))
    query_embs = embeddings[:n]
    query_names = names[:n]

    predictions: List[str] = []
    ground_truth: List[str] = []
    latencies: List[float] = []
    accepted: List[bool] = []

    for emb, name in zip(query_embs, query_names):
        t0 = time.perf_counter()

        matches = enrollment.search(emb, k=1, threshold=cfg.RECOGNITION_THRESHOLD)
        faiss_name = matches[0]["name"] if matches else "Unknown"
        faiss_conf = matches[0]["confidence"] if matches else 0.0

        quality_score = 0.5
        liveness_score = 0.5
        is_live = True
        risk_score = faiss_conf

        if variant in ("B", "C", "D") and quality is not None:
            # NOTE: Synthetic face crop - quality/liveness scores are not
            # representative of real pipeline performance. In production,
            # RetinaFace provides the actual face crop.
            qr = quality.assess(
                face_img=np.ones((100, 100, 3), dtype=np.uint8) * 128,
                det_score=0.95,
                face_bbox=(10, 10, 90, 90),
                img_shape=(480, 640),
                landmarks=np.array([[30, 40], [70, 40], [50, 60], [35, 80], [65, 80]]),
            )
            quality_score = qr["overall"]

        if variant in ("C", "D") and liveness is not None:
            lr = liveness.analyze_frame(
                face_img=np.ones((100, 100, 3), dtype=np.uint8) * 128,
                landmarks=np.array([[30, 40], [70, 40], [50, 60], [35, 80], [65, 80]]),
            )
            liveness_score = lr.liveness_score
            is_live = lr.is_live

        if variant == "D" and amfr is not None and matches:
            arcface_dist = matches[0].get("distance", 1.0)
            decision, risk_score, _ = amfr._decide(
                arcface_distance=arcface_dist,
                liveness_score=liveness_score,
                quality_score=quality_score,
                is_live=is_live,
                faiss_confidence=faiss_conf,
            )
            prediction = faiss_name if decision == AMFRDecision.ACCEPT else "Unknown"
            is_accepted = decision == AMFRDecision.ACCEPT
        else:
            is_accepted = faiss_conf >= cfg.AMFR_HIGH_CONFIDENCE_THRESHOLD
            prediction = faiss_name if is_accepted else "Unknown"

        latencies.append((time.perf_counter() - t0) * 1000)
        predictions.append(prediction)
        ground_truth.append(name)
        accepted.append(is_accepted)

    correct = sum(1 for p, g in zip(predictions, ground_truth) if p == g)
    false_accepts = sum(1 for p, g in zip(predictions, ground_truth) if p != "Unknown" and p != g)
    false_rejects = sum(1 for a, g in zip(accepted, ground_truth) if not a and g != "Unknown")
    true_accepts = sum(1 for a, g in zip(accepted, ground_truth) if a and g != "Unknown")
    n_known = sum(1 for g in ground_truth if g != "Unknown")
    n_unknown = sum(1 for g in ground_truth if g == "Unknown")
    latencies.sort()

    accuracy = correct / max(n, 1)
    precision = true_accepts / max(true_accepts + false_accepts, 1)
    recall = true_accepts / max(n_known, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9) if (precision + recall) > 0 else 0.0
    far = false_accepts / max(n_unknown, 1) if n_unknown > 0 else 0.0
    frr = false_rejects / max(n_known, 1) if n_known > 0 else 0.0
    tar = true_accepts / max(n_known, 1) if n_known > 0 else 0.0

    return {
        "variant": variant,
        "description": {
            "A": "ArcFace + FAISS (baseline)",
            "B": "Quality + ArcFace + FAISS",
            "C": "Quality + Liveness + ArcFace + FAISS",
            "D": "Full AMFR (Quality+Liveness+ArcFace+FAISS+Tracking+Decision)",
        }[variant],
        "n_queries": n,
        "n_known": n_known,
        "n_unknown": n_unknown,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "far": round(far, 4),
        "frr": round(frr, 4),
        "tar": round(tar, 4),
        "avg_latency_ms": round(float(np.mean(latencies)), 4),
        "p50_latency_ms": round(float(np.median(latencies)), 4),
        "p95_latency_ms": round(float(latencies[int(n * 0.95)]), 4),
        "correct": int(correct),
        "false_accepts": int(false_accepts),
        "false_rejects": int(false_rejects),
        "true_accepts": int(true_accepts),
    }


def main() -> int:
    print("=" * 72)
    print("AMFR Validation - A/B/C/D Comparison")
    print("=" * 72)

    print("\n[1/3] Loading models and data...")
    _recognizer = FaceRecognizer()
    enrollment = FaceEnrollment()
    quality = FaceQualityAssessment()
    liveness = LivenessDetector(use_deep_liveness=False)
    amfr = AMFREngine()

    dataset_dir = ROOT / "dataset"
    query_embs, query_names, _ = extract_embeddings(dataset_dir)
    if len(query_embs) == 0:
        print("\n  [ERROR] No query embeddings from dataset/")
        print("  Add face images to dataset/ and try again.")
        return 1

    query_embs_arr = np.array(query_embs, dtype=np.float32)
    print(f"\n  Enrolled: {enrollment.all_persons()} ({enrollment.count()} total)")
    print(f"  Query images: {query_names}")

    print("\n[2/3] Running A/B/C/D comparison...")
    results: Dict[str, Any] = {}
    for v in ["A", "B", "C", "D"]:
        print(f"\n  Variant {v}...")
        r = validate_variant(
            v,
            query_embs_arr,
            query_names,
            enrollment,
            quality if v in ("B", "C", "D") else None,
            liveness if v in ("C", "D") else None,
            amfr if v == "D" else None,
            num_queries=len(query_embs),
        )
        results[v] = r
        print(
            f"  Accuracy: {r.get('accuracy', 'N/A')}  |  Precision: {r.get('precision', 'N/A')}  |  "
            f"Recall: {r.get('recall', 'N/A')}  |  FAR: {r.get('far', 'N/A')}  |  FRR: {r.get('frr', 'N/A')}"
        )

    print("\n[3/3] Saving results...")
    output_path = ROOT / "outputs" / "amfr_validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"  Saved to: {output_path}")

    print(f"\n{'=' * 72}")
    print("  AMFR COMPARISON SUMMARY")
    print(f"{'=' * 72}")
    dash = "-" * 70
    print(f"  {'Var':<5} {'Acc':<8} {'Prec':<8} {'Rec':<8} {'F1':<8} {'FAR':<8} {'FRR':<8} {'P95ms':<8}")
    print(f"  {dash}")
    for v in ["A", "B", "C", "D"]:
        r = results.get(v, {})
        print(
            f"  {v:<5} {str(r.get('accuracy', 'N/A')):<8} {str(r.get('precision', 'N/A')):<8} "
            f"{str(r.get('recall', 'N/A')):<8} {str(r.get('f1_score', 'N/A')):<8} "
            f"{str(r.get('far', 'N/A')):<8} {str(r.get('frr', 'N/A')):<8} "
            f"{str(r.get('p95_latency_ms', 'N/A')):<8}"
        )
    print("\n  LEGEND:")
    print("  A: ArcFace + FAISS (baseline)")
    print("  B: Quality + ArcFace + FAISS")
    print("  C: Quality + Liveness + ArcFace + FAISS")
    print("  D: Full AMFR")
    print("\n  NOTE: Quality/liveness use synthetic face crops (RetinaFace not called).")
    print("  Real performance may differ from these numbers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
