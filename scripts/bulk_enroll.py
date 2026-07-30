#!/usr/bin/env python3
"""
Bulk Face Enrollment Script
============================
Enroll many students at once — either from real photos or synthetic
embeddings for scale testing.

Usage:
    # Real faces: scan a directory of student photos
    python scripts/bulk_enroll.py --mode real --image-dir dataset/students \\
        --pattern '*.jpg' --db

    # Synthetic: generate 5,000 random embeddings for FAISS benchmarking
    python scripts/bulk_enroll.py --mode synthetic --count 5000

    # Dry-run (don't save anything)
    python scripts/bulk_enroll.py --mode synthetic --count 1000 --dry-run

    # Clear the index first, then enroll
    python scripts/bulk_enroll.py --mode synthetic --count 5000 --clear-first

Image naming convention (real mode):
    dataset/students/Gokul_Krishana.jpg         -> name: "Gokul_Krishana"
    dataset/students/EMP001.jpg                 -> name: "EMP001"
    dataset/students/2021-CSE-001_Gokul.jpg     -> name: "2021-CSE-001_Gokul"
    dataset/students/rollno=101_name=Amit.jpg   -> name: "Amit"

Image requirements:
    - JPEG or PNG format
    - Face must be clearly visible (frontal preferred)
    - Minimum 100px face width
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import faiss
import numpy as np

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg
from app.enrollment import FaceEnrollment
from app.recognizer import FaceRecognizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bulk_enroll")


# ── Helper: parse student name from filename ───────────────────────

def parse_name_from_filename(filename: str) -> str:
    """Extract a clean student name from an image filename.

    Handles patterns like:
        - "Gokul_Krishana.jpg"       -> "Gokul_Krishana"
        - "EMP001.jpg"               -> "EMP001"
        - "2021-CSE-001_Gokul.jpg"   -> "2021-CSE-001_Gokul"
        - "rollno=101_name=Amit.jpg" -> "Amit"
    """
    stem = Path(filename).stem

    # Handle "rollno=..._name=..." format
    parts = stem.split("_")
    for p in parts:
        if p.lower().startswith("name="):
            return p.split("=", 1)[1]

    return stem


# ── Real face enrollment ───────────────────────────────────────────

def process_real_faces(
    image_dir: Path,
    pattern: str = "*.jpg",
    create_db_records: bool = False,
    dry_run: bool = False,
) -> Tuple[int, List[str], List[str]]:
    """Scan a directory of student photos and enroll each face.

    Returns:
        Tuple of (enrolled_count, enrolled_names, skipped_names).
    """
    recognizer = FaceRecognizer()
    enrollment = FaceEnrollment()

    image_files = sorted(image_dir.glob(pattern))
    if not image_files:
        # Also try other common extensions
        for ext in ("*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
            image_files = sorted(image_dir.glob(ext))
            if image_files:
                break

    if not image_files:
        logger.error(f"No images found in {image_dir}")
        return 0, [], []

    logger.info(f"Found {len(image_files)} images in {image_dir}")
    enrolled: List[str] = []
    skipped: List[str] = []

    for i, img_path in enumerate(image_files):
        name = parse_name_from_filename(img_path.name)
        logger.info(f"[{i+1}/{len(image_files)}] Processing {name} ({img_path.name})")

        # Read image
        image = cv2.imread(str(img_path))
        if image is None:
            logger.warning(f"  Cannot read image, skipping")
            skipped.append(name)
            continue

        # Detect face
        face = recognizer.detect_face(image)
        if face is None:
            logger.warning(f"  No face detected, skipping")
            skipped.append(name)
            continue

        # Extract embedding
        embedding = recognizer.extract_embedding(image)
        if embedding is None:
            logger.warning(f"  Embedding extraction failed, skipping")
            skipped.append(name)
            continue

        # Enroll
        if not dry_run:
            enrollment.enroll(name, embedding)
            if create_db_records:
                _create_employee_db_record(name)

        enrolled.append(name)

        percent = (i + 1) / len(image_files) * 100
        logger.info(f"  -> Enrolled ({percent:.0f}%)")

    return len(enrolled), enrolled, skipped


# ── Synthetic enrollment ───────────────────────────────────────────

def generate_synthetic(
    count: int,
    clear_first: bool = False,
    dry_run: bool = False,
    create_db_records: bool = False,
    batch_size: int = 10000,
    db_records: int = 0,
) -> int:
    """Generate *count* random 512-D embeddings and add them to FAISS.

    Uses batch ``index.add()`` for speed (not one-by-one ``enroll()``).

    Args:
        count: Number of embeddings to generate.
        clear_first: Clear the existing index before adding.
        dry_run: Validate without saving.
        create_db_records: Also create Employee/Student DB records.
        batch_size: Number of embeddings per batch (memory control).
        db_records: How many DB records to create (0 = all).

    Returns:
        The number of embeddings added.
    """
    enrollment = FaceEnrollment()

    if clear_first:
        logger.info("Clearing existing index...")
        if not dry_run:
            enrollment.clear()

    start_time = time.perf_counter()

    # Generate embeddings in batches to avoid excessive memory use
    batch_size = min(batch_size, count)
    dim = cfg.EMBEDDING_DIM
    total_added = 0
    all_metadata: List[Dict] = []
    total_batches = (count + batch_size - 1) // batch_size

    # Warn if index already has embeddings
    if enrollment.count() > 0 and not clear_first:
        logger.warning(f"Index already has {enrollment.count()} embeddings. "
                       f"New embeddings will be appended. Use --clear-first to reset.")

    logger.info(f"Generating {count} synthetic {dim}-D embeddings "
                f"(batch={batch_size}, {total_batches} batches)")

    for batch_num in range(total_batches):
        this_batch = min(batch_size, count - total_added)

        # Generate random vectors and L2-normalize them
        vectors = np.random.randn(this_batch, dim).astype(np.float32)
        faiss.normalize_L2(vectors)

        # Build metadata for this batch
        batch_meta = [
            {"name": f"student_{total_added + j:06d}", "id": total_added + j}
            for j in range(this_batch)
        ]

        if not dry_run:
            enrollment.index.add(vectors)
            all_metadata.extend(batch_meta)

        total_added += this_batch

        elapsed = time.perf_counter() - start_time
        rate = total_added / elapsed if elapsed > 0 else 0
        pct = total_added / count * 100
        logger.info(f"  Batch {batch_num + 1}/{total_batches}: "
                    f"{total_added}/{count} added ({pct:.0f}%) "
                    f"[{rate:.0f} emb/s]")

    # Save metadata and index once (batched)
    if not dry_run and all_metadata:
        existing_meta = list(enrollment.metadata)  # preserve old entries
        existing_meta.extend(all_metadata)
        enrollment.metadata = existing_meta
        enrollment._save()
        logger.info(f"Saved {len(all_metadata)} new metadata entries")

        # Create DB records (if requested)
        if create_db_records:
            n_db = db_records if db_records > 0 else len(all_metadata)
            n_db = min(n_db, len(all_metadata))
            logger.info(f"Creating {n_db} DB records...")
            _create_bulk_db_records(all_metadata[:n_db])

    elapsed = time.perf_counter() - start_time
    logger.info(f"Generated {total_added} embeddings in {elapsed:.1f}s "
                f"({total_added/elapsed:.0f} emb/s)")

    return total_added


# ── Database helpers ───────────────────────────────────────────────

def _create_employee_db_record(name: str) -> None:
    """Create an Employee record in SQLite."""
    try:
        from database.database import get_session
        from database.models import Employee

        with get_session() as session:
            exists = session.query(Employee).filter(
                Employee.employee_id == name
            ).first()
            if not exists:
                emp = Employee(
                    employee_id=name,
                    name=name,
                    department="Bulk Enrollment",
                )
                session.add(emp)
                session.commit()
    except Exception as e:
        logger.warning(f"Could not create DB record for {name}: {e}")


def _create_bulk_db_records(metadata: List[Dict]) -> None:
    """Create Employee records in SQLite for a list of metadata entries."""
    try:
        from database.database import get_session
        from database.models import Employee

        with get_session() as session:
            count = 0
            for entry in metadata:
                name = entry["name"]
                exists = session.query(Employee).filter(
                    Employee.employee_id == name
                ).first()
                if not exists:
                    emp = Employee(
                        employee_id=name,
                        name=name,
                        department="Bulk Enrollment",
                    )
                    session.add(emp)
                    count += 1
            session.commit()
            if count > 0:
                logger.info(f"  Created {count} new employee records")
    except Exception as e:
        logger.warning(f"Could not create DB records: {e}")


# ── CLI ────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk-enroll students into the face recognition system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode", choices=["real", "synthetic"], default="synthetic",
        help="Enrollment mode (default: synthetic)"
    )
    parser.add_argument(
        "--count", type=int, default=1000,
        help="Number of students to enroll (synthetic mode, default: 1000)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=10000,
        help="Batch size for synthetic embedding generation (default: 10000)"
    )
    parser.add_argument(
        "--db-records", type=int, default=0,
        help="Number of DB records to create in synthetic mode (0 = all records)"
    )
    parser.add_argument(
        "--image-dir", type=Path, default=None,
        help="Directory containing student photos (real mode)"
    )
    parser.add_argument(
        "--pattern", default="*.jpg",
        help="Glob pattern for image files (real mode, default: *.jpg)"
    )
    parser.add_argument(
        "--db", action="store_true",
        help="Also create database records for enrolled students"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run without saving anything (validate only)"
    )
    parser.add_argument(
        "--clear-first", action="store_true",
        help="Clear the existing FAISS index before enrolling"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show enrollment statistics after completion"
    )

    args = parser.parse_args()

    start_time = time.perf_counter()

    if args.mode == "real":
        image_dir = args.image_dir
        if image_dir is None:
            image_dir = cfg.DATASET_DIR
            logger.info(f"No --image-dir given, using default: {image_dir}")

        if not image_dir.exists():
            logger.error(f"Image directory not found: {image_dir}")
            return 1

        enrolled_count, enrolled, skipped = process_real_faces(
            image_dir=image_dir,
            pattern=args.pattern,
            create_db_records=args.db,
            dry_run=args.dry_run,
        )
    else:
        if args.count <= 0:
            logger.error("--count must be positive")
            return 1

        enrolled_count = generate_synthetic(
            count=args.count,
            clear_first=args.clear_first,
            dry_run=args.dry_run,
            create_db_records=args.db,
            batch_size=args.batch_size,
            db_records=args.db_records,
        )
        enrolled = []
        skipped = []

    elapsed = time.perf_counter() - start_time

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  BULK ENROLLMENT SUMMARY")
    print("=" * 60)
    print(f"  Mode:           {args.mode}")
    print(f"  Target:         {args.count if args.mode == 'synthetic' else 'auto'} students")
    print(f"  Enrolled:       {enrolled_count}")
    if skipped:
        print(f"  Skipped:        {len(skipped)}")
    print(f"  Dry run:        {args.dry_run}")
    print(f"  DB records:     {args.db}")
    print(f"  Time:           {elapsed:.1f}s")
    if enrolled:
        rate = enrolled_count / elapsed
        print(f"  Rate:           {rate:.0f} students/s")
    print("=" * 60)

    if args.stats:
        _show_stats()

    return 0


def _show_stats() -> None:
    """Display current enrollment statistics."""
    try:
        enrollment = FaceEnrollment()
        status = enrollment.status()
        print(f"\n  FAISS Status:")
        print(f"    Index type:     {status['index'].get('type', '?')}")
        if 'M' in status['index']:
            print(f"    HNSW M:         {status['index']['M']}")
        print(f"    Total vectors:  {status['total_embeddings']}")
        print(f"    Unique persons: {status['unique_persons']}")
        print(f"    Persons:        {status['persons'][:10]}..."
              if len(status['persons']) > 10
              else f"    Persons:        {status['persons']}")
    except Exception as e:
        logger.warning(f"Cannot show stats: {e}")


if __name__ == "__main__":
    sys.exit(main())
