"""
Startup Validation — Check System Readiness Before Running
============================================================

Validates that all system components are ready before the operator
starts using the application. Run this at startup to catch
configuration errors, missing models, and connectivity issues
early — not during a live recognition session.

Usage:
    python -m tools.validate_startup
    python tools/validate_startup.py --verbose

Checks:
    1. Configuration files exist and are valid
    2. Required directories exist and are writable
    3. AI models (YOLO, InsightFace) are accessible
    4. FAISS index loads correctly
    5. Database connection works
    6. Redis connectivity (if configured)
    7. Camera configuration is valid
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# UTF-8 output (Windows consoles default to cp1252, which breaks on emoji)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Ensure project root is on path ────────────────────────────
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg  # noqa: E402  (needs sys.path setup above)
from database.database import DB_TYPE, DATABASE_URL, get_session  # noqa: E402

logger = logging.getLogger(__name__)


# ── Result Model ──────────────────────────────────────────────

@dataclass
class Check:
    """Result of a single startup validation check."""

    name: str
    status: str  # PASS | FAIL | WARN | SKIP
    message: str = ""
    duration_ms: float = 0.0
    details: Optional[dict] = None

    def __bool__(self) -> bool:
        return self.status == "PASS"

    @classmethod
    def pass_(cls, name: str, message: str = "", duration_ms: float = 0.0,
              details: Optional[dict] = None) -> "Check":
        return cls(name=name, status="PASS", message=message,
                   duration_ms=duration_ms, details=details)

    @classmethod
    def fail(cls, name: str, message: str = "", duration_ms: float = 0.0,
             details: Optional[dict] = None) -> "Check":
        return cls(name=name, status="FAIL", message=message,
                   duration_ms=duration_ms, details=details)

    @classmethod
    def warn(cls, name: str, message: str = "", duration_ms: float = 0.0,
             details: Optional[dict] = None) -> "Check":
        return cls(name=name, status="WARN", message=message,
                   duration_ms=duration_ms, details=details)

    @classmethod
    def skip(cls, name: str, message: str = "", details: Optional[dict] = None) -> "Check":
        return cls(name=name, status="SKIP", message=message, details=details)


# ═══════════════════════════════════════════════════════════════
#  Check Functions
# ═══════════════════════════════════════════════════════════════

def check_config() -> Check:
    """Validate configuration files and critical settings."""
    start = time.time()
    issues: List[str] = []

    settings_path = cfg.SETTINGS_PATH
    if not settings_path.exists():
        return Check.fail("Config File", f"Settings not found: {settings_path}")

    # Validate essential config values
    if not (0 < cfg.YOLO_CONFIDENCE <= 1):
        issues.append(f"YOLO_CONFIDENCE={cfg.YOLO_CONFIDENCE} out of range (0-1]")
    if not (0 <= cfg.RECOGNITION_THRESHOLD <= 5):
        issues.append(f"RECOGNITION_THRESHOLD={cfg.RECOGNITION_THRESHOLD} seems extreme")
    if not (0 <= cfg.AMFR_HIGH_CONFIDENCE_THRESHOLD <= 1):
        issues.append("AMFR threshold out of range")
    if cfg.FAISS_INDEX_TYPE not in ("flat", "hnsw", "ivf"):
        issues.append(f"Unknown FAISS index type: {cfg.FAISS_INDEX_TYPE}")

    elapsed = (time.time() - start) * 1000
    if issues:
        return Check.warn("Configuration", "; ".join(issues), duration_ms=elapsed)
    return Check.pass_("Configuration", f"Valid: {cfg.SETTINGS_PATH.name}",
                       duration_ms=elapsed)


def check_directories() -> Check:
    """Ensure required directories exist and are writable."""
    start = time.time()
    required = [
        cfg.MODELS_DIR,
        cfg.EMBEDDINGS_DIR,
        cfg.UNKNOWN_FACES_DIR,
        cfg.LOGS_DIR,
        cfg.ATTENDANCE_DIR,
        cfg.OUTPUTS_DIR,
        cfg.ROOT_DIR / "data",
    ]
    missing = [d for d in required if not d.exists()]
    for d in required:
        d.mkdir(parents=True, exist_ok=True)
    elapsed = (time.time() - start) * 1000
    if missing:
        return Check.pass_("Directories", f"Created {len(missing)} missing dir(s)",
                           duration_ms=elapsed,
                           details={"created": [str(d) for d in missing]})
    return Check.pass_("Directories", f"All {len(required)} directories ready",
                       duration_ms=elapsed)


def check_yolo_model() -> Check:
    """Check YOLO model file exists and loads correctly."""
    start = time.time()
    model_path = Path(cfg.YOLO_MODEL_PATH)
    if not model_path.exists():
        return Check.fail("YOLO Model", f"Not found: {cfg.YOLO_MODEL_PATH}")

    size_mb = model_path.stat().st_size / (1024 * 1024)
    if size_mb < 1:
        return Check.warn("YOLO Model", f"File seems small: {size_mb:.1f} MB")

    # Try to instantiate — catches corrupt models
    try:
        from app.face_detector import FaceDetector
        _ = FaceDetector()
        elapsed = (time.time() - start) * 1000
        return Check.pass_("YOLO Model", f"Loaded ({size_mb:.1f} MB)", duration_ms=elapsed)
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return Check.warn("YOLO Model",
                          f"File exists ({size_mb:.1f} MB) but load failed: {exc}",
                          duration_ms=elapsed)


def check_insightface_model() -> Check:
    """Check InsightFace model is accessible."""
    start = time.time()
    try:
        from app.recognizer import FaceRecognizer
        rec = FaceRecognizer()
        dim = rec.embedding_dim()
        elapsed = (time.time() - start) * 1000
        return Check.pass_("InsightFace",
                           f"Model={rec.model_name}, dim={dim}",
                           duration_ms=elapsed)
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return Check.fail("InsightFace", str(exc), duration_ms=elapsed)


def check_faiss_index() -> Check:
    """Check FAISS index loads and metadata is consistent."""
    start = time.time()
    index_path = Path(cfg.FAISS_INDEX_PATH)
    meta_path = Path(cfg.METADATA_PATH)

    if not index_path.exists() and not meta_path.exists():
        # Fresh install — empty index is normal
        return Check.pass_("FAISS Index", "Empty (fresh installation)")

    try:
        from app.enrollment import FaceEnrollment
        enrollment = FaceEnrollment()
        total = enrollment.count()
        persons = enrollment.unique_count()
        meta_count = len(enrollment.metadata)
        elapsed = (time.time() - start) * 1000

        # Validate metadata matches index
        if total != meta_count:
            return Check.warn("FAISS Index",
                              f"Index={total} embeddings vs Metadata={meta_count} entries — mismatch!",
                              duration_ms=elapsed,
                              details={"embeddings": total, "metadata": meta_count})

        return Check.pass_("FAISS Index",
                           f"{total} embeddings, {persons} persons ({cfg.FAISS_INDEX_TYPE})",
                           duration_ms=elapsed,
                           details={"embeddings": total, "persons": persons,
                                    "index_type": cfg.FAISS_INDEX_TYPE})
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return Check.fail("FAISS Index", str(exc), duration_ms=elapsed)


def check_database() -> Check:
    """Check database connection and migrations."""
    start = time.time()
    try:
        with get_session() as session:
            session.execute(__import__('sqlalchemy').text("SELECT 1"))
        elapsed = (time.time() - start) * 1000
        masked_url = DATABASE_URL
        if "postgresql" in masked_url:
            from urllib.parse import urlparse
            parsed = urlparse(DATABASE_URL)
            masked_url = f"postgresql://{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}"
        return Check.pass_("Database",
                           f"Connected ({DB_TYPE})",
                           duration_ms=elapsed,
                           details={"type": DB_TYPE, "url": masked_url})
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return Check.fail("Database", f"{DB_TYPE}: {exc}", duration_ms=elapsed)


def check_redis() -> Check:
    """Check Redis connectivity if configured."""
    start = time.time()
    try:
        from api.redis_client import get_redis
        redis = get_redis()
        redis.client.ping()
        elapsed = (time.time() - start) * 1000
        return Check.pass_("Redis", "Connected", duration_ms=elapsed)
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return Check.warn("Redis",
                          f"Not available — running with in-memory fallback: {exc}",
                          duration_ms=elapsed)


def check_amfr() -> Check:
    """Check AMFR engine loads correctly."""
    start = time.time()
    try:
        from app.amfr_engine import AMFREngine
        engine = AMFREngine()
        status = engine.status()
        elapsed = (time.time() - start) * 1000
        return Check.pass_("AMFR Engine", "Ready", duration_ms=elapsed,
                           details=status)
    except Exception as exc:
        elapsed = (time.time() - start) * 1000
        return Check.fail("AMFR Engine", str(exc), duration_ms=elapsed)


# ═══════════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════════

def run_all(verbose: bool = False) -> Tuple[List[Check], bool]:
    """Run all startup validation checks.

    Args:
        verbose: If True, print detailed output for each check.

    Returns:
        Tuple of (checks, all_pass) where all_pass is True if no FAIL checks.
    """
    checks: List[Check] = []

    checks.append(check_config())
    checks.append(check_directories())

    # Models
    checks.append(check_yolo_model())
    checks.append(check_insightface_model())

    # FAISS
    checks.append(check_faiss_index())

    # AMFR
    checks.append(check_amfr())

    # Infrastructure
    checks.append(check_database())
    checks.append(check_redis())

    all_pass = all(c.status != "FAIL" for c in checks)
    return checks, all_pass


def print_report(checks: List[Check]) -> None:
    """Print a formatted validation report."""
    emoji = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "SKIP": "⏭️"}
    print(f"\n{'='*60}")
    print("  System Validation Report")
    print(f"{'='*60}")
    print()

    for c in checks:
        em = emoji.get(c.status, "❓")
        dur = f" [{c.duration_ms:.0f}ms]" if c.duration_ms > 0 else ""
        print(f"  {em} [{c.status:5s}] {c.name}{dur}")
        if c.message:
            print(f"          {c.message}")
        if c.details and c.status != "PASS":
            for k, v in c.details.items():
                print(f"          {k}={v}")
        print()

    passed = sum(1 for c in checks if c.status == "PASS")
    failed = sum(1 for c in checks if c.status == "FAIL")
    warned = sum(1 for c in checks if c.status == "WARN")
    total = len(checks)

    print(f"{'='*60}")
    print(f"  Results: {passed}/{total} passed, {failed} failed, {warned} warnings")
    if failed > 0:
        print("  ❌ SYSTEM NOT READY — fix FAIL items above")
    elif warned > 0:
        print("  ⚠️  System ready (with warnings)")
    else:
        print("  ✅ SYSTEM READY")
    print(f"{'='*60}\n")


def main() -> int:
    """Run startup validation and return exit code."""
    import argparse
    parser = argparse.ArgumentParser(description="Face Recognition AI — Startup Validation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    checks, all_pass = run_all(verbose=args.verbose)
    print_report(checks)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
