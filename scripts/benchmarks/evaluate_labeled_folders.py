"""Evaluate ArcFace + FAISS using a labeled folder dataset.

Expected layout:
    dataset_root/person_name/image.jpg

The script uses a deterministic per-class split, builds a temporary FAISS
gallery from the training portion, and evaluates only unseen test images.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config.config as cfg  # noqa: E402
from app.enrollment import FaceEnrollment  # noqa: E402
from app.recognizer import FaceRecognizer  # noqa: E402


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def image_fingerprint(path: Path) -> Tuple[str, np.ndarray] | None:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    small = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA)
    return digest, (small >= small.mean()).astype(np.uint8)


def collect_images(
    source: Path,
    test_fraction: float,
    class_names: set[str] | None = None,
    seed: int = 42,
    minimum_images: int = 2,
) -> Tuple[List[Tuple[Path, str]], List[Tuple[Path, str]], List[Dict[str, object]]]:
    train: List[Tuple[Path, str]] = []
    test: List[Tuple[Path, str]] = []
    duplicate_groups: List[Dict[str, object]] = []
    fingerprints: List[Tuple[Path, str, str, np.ndarray]] = []
    class_dirs = (path for path in source.iterdir() if path.is_dir() and (class_names is None or path.name in class_names))
    for class_dir in sorted(class_dirs):
        files = sorted(path for path in class_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
        if len(files) < minimum_images:
            print(f"[WARN] Skipping {class_dir.name}: fewer than {minimum_images} images")
            continue
        usable = []
        for path in files:
            fingerprint = image_fingerprint(path)
            if fingerprint is None:
                continue
            digest, perceptual = fingerprint
            usable.append(path)
            fingerprints.append((path, class_dir.name, digest, perceptual))
        test_count = max(1, math.ceil(len(usable) * test_fraction))
        shuffled = list(usable)
        class_seed = int(hashlib.sha256(class_dir.name.encode("utf-8")).hexdigest()[:8], 16)
        random.Random(seed + class_seed).shuffle(shuffled)
        train.extend((path, class_dir.name) for path in shuffled[:-test_count])
        test.extend((path, class_dir.name) for path in shuffled[-test_count:])

    for index, (path, label, digest, perceptual) in enumerate(fingerprints):
        matches = [
            str(other)
            for other, other_label, other_digest, other_perceptual in fingerprints[index + 1 :]
            if label == other_label and (
                digest == other_digest
                or int(np.count_nonzero(perceptual != other_perceptual)) <= 8
            )
        ]
        if matches:
            duplicate_groups.append({"label": label, "files": [str(path), *matches]})
    train_paths = {path for path, _ in train}
    filtered_test: List[Tuple[Path, str]] = []
    for path, label in test:
        fingerprint = image_fingerprint(path)
        leaks = False
        if fingerprint is not None:
            digest, perceptual = fingerprint
            leaks = any(
                train_label == label
                and (
                    digest == train_digest
                    or int(np.count_nonzero(perceptual != train_perceptual)) <= 8
                )
                for train_path, train_label, train_digest, train_perceptual in fingerprints
                if train_path in train_paths
            )
        if leaks:
            train.append((path, label))
        else:
            filtered_test.append((path, label))
    return train, filtered_test, duplicate_groups


def extract(recognizer: FaceRecognizer, entries: List[Tuple[Path, str]]) -> Tuple[List[Tuple[np.ndarray, str]], List[str]]:
    embeddings: List[Tuple[np.ndarray, str]] = []
    failed: List[str] = []
    for path, label in entries:
        image = cv2.imread(str(path))
        embedding = recognizer.extract_embedding(image) if image is not None else None
        if embedding is None:
            failed.append(str(path))
            continue
        embeddings.append((embedding, label))
    return embeddings, failed


def metrics(actual: List[str], predicted: List[str], top_three_hits: int) -> Dict[str, float]:
    labels = sorted(set(actual) | set(predicted))
    weighted = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    for label in labels:
        support = sum(value == label for value in actual)
        true_positive = sum(a == label and p == label for a, p in zip(actual, predicted))
        predicted_count = sum(value == label for value in predicted)
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        weighted["precision"] += precision * support
        weighted["recall"] += recall * support
        weighted["f1"] += f1 * support
    total = max(len(actual), 1)
    return {
        "overall_accuracy": sum(a == p for a, p in zip(actual, predicted)) / total,
        "weighted_precision": weighted["precision"] / total,
        "weighted_recall": weighted["recall"] / total,
        "weighted_f1_score": weighted["f1"] / total,
        "correct_classifications": sum(a == p for a, p in zip(actual, predicted)),
        "test_images": len(actual),
        "top_three_hit_rate": top_three_hits / total,
    }


def distinct_names(matches: List[Dict[str, object]], limit: int = 3) -> List[str]:
    names: List[str] = []
    for match in matches:
        name = str(match["name"])
        if name not in names:
            names.append(name)
        if len(names) == limit:
            break
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Labeled class-folder root.")
    parser.add_argument("--class", dest="classes", action="append", help="Class folder name; may be repeated.")
    parser.add_argument("--unknown-source", type=Path, help="Optional folder of identities absent from the gallery.")
    parser.add_argument("--unknown-class", dest="unknown_classes", action="append", help="Unknown class folder; may be repeated.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-fraction", type=float, default=0.30)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "labeled_dataset_evaluation.json")
    args = parser.parse_args()

    if not args.source.is_dir():
        print(f"[ERROR] Dataset folder not found: {args.source}")
        return 2
    if not 0.1 <= args.test_fraction <= 0.5:
        print("[ERROR] --test-fraction must be between 0.1 and 0.5")
        return 2

    train_entries, test_entries, duplicate_groups = collect_images(
        args.source, args.test_fraction, set(args.classes) if args.classes else None, args.seed
    )
    print(f"Classes: {len({label for _, label in train_entries})}")
    print(f"Training candidates: {len(train_entries)} | Test candidates: {len(test_entries)}")

    recognizer = FaceRecognizer()
    train_embeddings, train_failed = extract(recognizer, train_entries)
    test_embeddings, test_failed = extract(recognizer, test_entries)
    if not train_embeddings or not test_embeddings:
        print("[ERROR] Could not extract embeddings for both splits.")
        return 1

    index_path = args.output.with_suffix(".faiss")
    metadata_path = args.output.with_suffix(".metadata.json")
    enrollment = FaceEnrollment(index_path=str(index_path), metadata_path=str(metadata_path))
    for embedding, label in train_embeddings:
        enrollment.enroll(label, embedding)

    actual: List[str] = []
    predicted: List[str] = []
    top_three_hits = 0
    predictions: List[Dict[str, object]] = []
    for embedding, label in test_embeddings:
        matches = enrollment.search(embedding, k=enrollment.count(), threshold=cfg.RECOGNITION_THRESHOLD)
        names = distinct_names(matches)
        prediction = names[0] if names else "Unknown"
        actual.append(label)
        predicted.append(prediction)
        top_three_hits += int(label in names)
        predictions.append(
            {"expected": label, "predicted": prediction, "top_three": names, "confidence": matches[0]["confidence"] if matches else 0.0}
        )

    unknown_result = None
    if args.unknown_source:
        _, unknown_entries, unknown_duplicates = collect_images(
            args.unknown_source,
            1.0,
            set(args.unknown_classes) if args.unknown_classes else None,
            args.seed,
            minimum_images=1,
        )
        unknown_embeddings, unknown_failed = extract(recognizer, unknown_entries)
        accepted = 0
        unknown_predictions = []
        for embedding, label in unknown_embeddings:
            matches = enrollment.search(embedding, k=enrollment.count(), threshold=cfg.RECOGNITION_THRESHOLD)
            names = distinct_names(matches)
            accepted += int(bool(names))
            unknown_predictions.append({"expected": label, "predicted": names[0] if names else "Unknown", "top_three": names})
        unknown_total = len(unknown_embeddings)
        unknown_result = {
            "images": unknown_total,
            "accepted_as_known": accepted,
            "false_acceptance_rate": accepted / max(unknown_total, 1),
            "unknown_rejection_rate": 1 - accepted / max(unknown_total, 1),
            "failed": unknown_failed,
            "duplicate_groups": unknown_duplicates,
            "predictions": unknown_predictions,
        }

    result = {
        "source": str(args.source),
        "split": {"test_fraction": args.test_fraction, "seed": args.seed, "train_candidates": len(train_entries), "test_candidates": len(test_entries), "duplicate_groups": duplicate_groups},
        "extraction": {"train_embeddings": len(train_embeddings), "test_embeddings": len(test_embeddings), "train_failed": train_failed, "test_failed": test_failed},
        "enrollment": {"embeddings": enrollment.count(), "persons": enrollment.all_persons()},
        "metrics": metrics(actual, predicted, top_three_hits),
        "unknown_evaluation": unknown_result,
        "predictions": predictions,
        "index": str(index_path),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], indent=2))
    print(f"Saved report: {args.output}")
    print(f"Saved evaluation index: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
