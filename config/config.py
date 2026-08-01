"""
Centralized configuration for the Face Recognition AI system.

Settings are loaded from ``config/settings.yaml`` with fallback
values defined here. This allows editing configuration without
touching Python code.
"""

from pathlib import Path
from typing import Any, Dict

import yaml
from ruamel.yaml import YAML

# Use ruamel.yaml for comment-preserving YAML round-trips
_yaml = YAML()
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 4096  # Don't wrap long lines

# ── Project Root ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent

# ── Load YAML settings ───────────────────────────────────────
_SETTINGS_PATH = ROOT_DIR / "config" / "settings.yaml"


def _load_yaml() -> Dict[str, Any]:
    """Load settings from YAML file, returning empty dict if missing."""
    if _SETTINGS_PATH.exists():
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_settings = _load_yaml()


# Helper to get nested keys:  _get("recognition", "yolo_confidence") -> 0.5
def _get(*keys: str, default: Any = None) -> Any:
    val = _settings
    for key in keys:
        if isinstance(val, dict):
            val = val.get(key)
        else:
            return default
    return val if val is not None else default


SETTINGS_PATH = _SETTINGS_PATH  # Public alias for external access


def get_settings() -> dict:
    """Return the current live settings dict (read-only copy)."""
    return dict(_settings)


def save_settings(updates: dict) -> None:
    """Update settings and persist them to settings.yaml.

    Comments in the YAML file are preserved via ruamel.yaml round-trip:
    the file is read as a ``CommentedMap``, updated in-place, then written back.

    Args:
        updates: Nested dict of settings to update.
                 E.g. {"recognition": {"recognition_threshold": 1.2}}
    """
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Read with ruamel.yaml so comment tokens are captured in the CommentedMap
    data = {}
    if _SETTINGS_PATH.exists() and _SETTINGS_PATH.stat().st_size > 0:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = _yaml.load(f)

    # Apply updates in-place on the CommentedMap (preserves comments!)
    for section, values in updates.items():
        if isinstance(values, dict):
            if section not in data or not isinstance(data[section], dict):
                data[section] = {}
            for key, val in values.items():
                data[section][key] = val
        else:
            data[section] = values

    # Write back — comments preserved because ``data`` is a CommentedMap
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        _yaml.dump(data, f)

    # Reload the in-memory dict via existing PyYAML load
    _settings.clear()
    _settings.update(_load_yaml())


# ── Model Paths ───────────────────────────────────────────────
MODELS_DIR = ROOT_DIR / "models"
YOLO_MODEL_PATH = str(MODELS_DIR / "yolo11n.pt")

# ── Face Recognition ──────────────────────────────────────────
INSIGHTFACE_MODEL = "buffalo_l"       # InsightFace model name
INSIGHTFACE_ROOT = str(ROOT_DIR / "models" / ".insightface")
EMBEDDING_DIM = 512                    # ArcFace embedding dimension

# ── Detection Thresholds (from YAML with fallback) ────────────
YOLO_CONFIDENCE: float = _get("recognition", "yolo_confidence", default=0.5)
RECOGNITION_THRESHOLD: float = _get("recognition", "recognition_threshold", default=1.0)
FRAME_SKIP: int = _get("recognition", "frame_skip", default=2)
COOLDOWN_SECONDS: int = _get("recognition", "cooldown_seconds", default=60)
IDENTITY_TTL: float = _get("recognition", "identity_ttl", default=3.0)

# ── Paths ─────────────────────────────────────────────────────
EMBEDDINGS_DIR = ROOT_DIR / "embeddings"
FAISS_INDEX_PATH = str(EMBEDDINGS_DIR / "faiss.index")
METADATA_PATH = str(EMBEDDINGS_DIR / "metadata.json")

ATTENDANCE_DIR = ROOT_DIR / "attendance"
LOGS_DIR = ROOT_DIR / "logs"
OUTPUTS_DIR = ROOT_DIR / "outputs"
UNKNOWN_FACES_DIR = ROOT_DIR / "unknown_faces"
DATASET_DIR = ROOT_DIR / "dataset"

# ── Camera (from YAML with fallback) ──────────────────────────
CAMERA_ID: int = _get("camera", "id", default=0)
# Camera source type: webcam | android_usb | android_wifi | iphone_usb | iphone_wifi
CAMERA_SOURCE_TYPE: str = _get("camera", "source_type", default="webcam")
# URL for phone cameras (IP Webcam, DroidCam, EpocCam)
CAMERA_URL: str = _get("camera", "url", default="http://192.168.1.100:8080/video")
# Auto-connect to the configured camera at startup
CAMERA_AUTO_CONNECT: bool = _get("camera", "auto_connect", default=False)

# ── AMFR (Adaptive Multi-Factor Recognition) ──────────────────
FACE_QUALITY_MIN_SCORE: float = _get("amfr", "face_quality_min_score", default=0.35)
LIVENESS_MIN_SCORE: float = _get("amfr", "liveness_min_score", default=0.30)
LIVENESS_SPOOF_THRESHOLD: float = _get("amfr", "liveness_spoof_threshold", default=0.15)

AMFR_HIGH_CONFIDENCE_THRESHOLD: float = _get("amfr", "high_confidence_threshold", default=0.70)
AMFR_BORDERLINE_THRESHOLD: float = _get("amfr", "borderline_threshold", default=0.40)

AMFR_WEIGHT_ARCFACE: float = _get("amfr", "weight_arcface", default=0.45)
AMFR_WEIGHT_LIVENESS: float = _get("amfr", "weight_liveness", default=0.35)
AMFR_WEIGHT_QUALITY: float = _get("amfr", "weight_quality", default=0.20)

# ── Deep Liveness (CNN-based anti-spoofing) ────────────────────
DEEP_LIVENESS_ENABLED: bool = _get("deep_liveness", "enabled", default=True)
DEEP_LIVENESS_THRESHOLD: float = _get("deep_liveness", "threshold", default=0.50)
DEEP_LIVENESS_FALLBACK: bool = _get("deep_liveness", "use_fallback", default=True)
DEEP_LIVENESS_AUTO_DOWNLOAD: bool = _get("deep_liveness", "auto_download", default=True)

# ── FAISS Vector Search (tuned from benchmarks) ────────────────
FAISS_INDEX_TYPE: str = _get("faiss", "index_type", default="hnsw")
FAISS_HNSW_M: int = _get("faiss", "hnsw", "M", default=64)
FAISS_HNSW_EF_CONSTRUCTION: int = _get("faiss", "hnsw", "ef_construction", default=200)
FAISS_HNSW_EF_SEARCH: int = _get("faiss", "hnsw", "ef_search", default=128)
FAISS_IVF_NLIST: int = _get("faiss", "ivf", "nlist", default=200)
FAISS_IVF_NPROBE: int = _get("faiss", "ivf", "nprobe", default=256)

# ── Unknown Face Retention ───────────────────────────────────
UNKNOWN_FACE_RETENTION_DAYS: int = _get("unknown_faces", "retention_days", default=30)

# ── Ensure required directories exist ────────────────────────
_REQUIRED_DIRS = [
    EMBEDDINGS_DIR,
    ATTENDANCE_DIR,
    LOGS_DIR,
    OUTPUTS_DIR,
    UNKNOWN_FACES_DIR,
    ROOT_DIR / "data",  # SQLite database directory
]

for _d in _REQUIRED_DIRS:
    _d.mkdir(parents=True, exist_ok=True)

# ── Logging Configuration ────────────────────────────────────
import logging
import logging.handlers

_LOG_LEVEL = _get("logging", "level", default="INFO").upper()
_LOG_FILE = ROOT_DIR / (_get("logging", "file", default="logs/app.log"))
_LOG_MAX_BYTES = _get("logging", "max_size_mb", default=10) * 1024 * 1024
_LOG_BACKUP_COUNT = _get("logging", "backup_count", default=3)

# Ensure log directory exists
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),               # Console output
        logging.handlers.RotatingFileHandler(   # File output with rotation
            str(_LOG_FILE),
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
        ),
    ],
)
