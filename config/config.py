"""
Centralized configuration for the Face Recognition AI system.

Settings are loaded from ``config/settings.yaml`` with fallback
values defined here. This allows editing configuration without
touching Python code.
"""

import os
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
            val = val.get(key)  # type: ignore[assignment]
        else:
            return default
    return val if val is not None else default


def _env(name: str, default: Any = None) -> Any:
    """Environment-variable override for a setting.

    Precedence: environment variable > settings.yaml > fallback default.
    The env var name matches the config constant, e.g. ``RECOGNITION_THRESHOLD``
    overrides ``recognition.recognition_threshold`` in ``settings.yaml``.
    See ``.env.example`` for the full list of supported overrides.
    """
    value = os.getenv(name)
    if value is None:
        return default
    if isinstance(default, bool):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        try:
            return int(value)
        except ValueError:
            return default
    if isinstance(default, float):
        try:
            return float(value)
        except ValueError:
            return default
    return value


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
INSIGHTFACE_MODEL = "buffalo_l"  # InsightFace model name
INSIGHTFACE_ROOT = str(ROOT_DIR / "models" / ".insightface")
EMBEDDING_DIM = 512  # ArcFace embedding dimension

# ── Detection Thresholds (from YAML with fallback) ────────────
YOLO_CONFIDENCE: float = _env("YOLO_CONFIDENCE", _get("recognition", "yolo_confidence", default=0.5))
RECOGNITION_THRESHOLD: float = _env(
    "RECOGNITION_THRESHOLD", _get("recognition", "recognition_threshold", default=1.0)
)
FRAME_SKIP: int = _env("FRAME_SKIP", _get("recognition", "frame_skip", default=2))
COOLDOWN_SECONDS: int = _env("COOLDOWN_SECONDS", _get("recognition", "cooldown_seconds", default=60))
IDENTITY_TTL: float = _env("IDENTITY_TTL", _get("recognition", "identity_ttl", default=3.0))

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
CAMERA_ID: int = _env("CAMERA_ID", _get("camera", "id", default=0))
# Camera source type: webcam | android_usb | android_wifi | iphone_usb | iphone_wifi
CAMERA_SOURCE_TYPE: str = _env("CAMERA_SOURCE_TYPE", _get("camera", "source_type", default="webcam"))
# URL for phone cameras (IP Webcam, DroidCam, EpocCam)
CAMERA_URL: str = _env("CAMERA_URL", _get("camera", "url", default="http://192.168.1.100:8080/video"))
# Auto-connect to the configured camera at startup
CAMERA_AUTO_CONNECT: bool = _env("CAMERA_AUTO_CONNECT", _get("camera", "auto_connect", default=False))

# ── AMFR (Adaptive Multi-Factor Recognition) ──────────────────
FACE_QUALITY_MIN_SCORE: float = _env(
    "FACE_QUALITY_MIN_SCORE", _get("amfr", "face_quality_min_score", default=0.35)
)
LIVENESS_MIN_SCORE: float = _env("LIVENESS_MIN_SCORE", _get("amfr", "liveness_min_score", default=0.30))
LIVENESS_SPOOF_THRESHOLD: float = _env(
    "LIVENESS_SPOOF_THRESHOLD", _get("amfr", "liveness_spoof_threshold", default=0.15)
)

AMFR_HIGH_CONFIDENCE_THRESHOLD: float = _env(
    "AMFR_HIGH_CONFIDENCE_THRESHOLD", _get("amfr", "high_confidence_threshold", default=0.70)
)
AMFR_BORDERLINE_THRESHOLD: float = _env(
    "AMFR_BORDERLINE_THRESHOLD", _get("amfr", "borderline_threshold", default=0.40)
)

AMFR_WEIGHT_ARCFACE: float = _env("AMFR_WEIGHT_ARCFACE", _get("amfr", "weight_arcface", default=0.45))
AMFR_WEIGHT_LIVENESS: float = _env("AMFR_WEIGHT_LIVENESS", _get("amfr", "weight_liveness", default=0.35))
AMFR_WEIGHT_QUALITY: float = _env("AMFR_WEIGHT_QUALITY", _get("amfr", "weight_quality", default=0.20))

# ── Deep Liveness (CNN-based anti-spoofing) ────────────────────
DEEP_LIVENESS_ENABLED: bool = _env("DEEP_LIVENESS_ENABLED", _get("deep_liveness", "enabled", default=True))
DEEP_LIVENESS_THRESHOLD: float = _env(
    "DEEP_LIVENESS_THRESHOLD", _get("deep_liveness", "threshold", default=0.50)
)
DEEP_LIVENESS_FALLBACK: bool = _env(
    "DEEP_LIVENESS_FALLBACK", _get("deep_liveness", "use_fallback", default=True)
)
DEEP_LIVENESS_AUTO_DOWNLOAD: bool = _env(
    "DEEP_LIVENESS_AUTO_DOWNLOAD", _get("deep_liveness", "auto_download", default=True)
)

# ── FAISS Vector Search (tuned from benchmarks) ────────────────
FAISS_INDEX_TYPE: str = _env("FAISS_INDEX_TYPE", _get("faiss", "index_type", default="hnsw"))
FAISS_HNSW_M: int = _env("FAISS_HNSW_M", _get("faiss", "hnsw", "M", default=64))
FAISS_HNSW_EF_CONSTRUCTION: int = _env(
    "FAISS_HNSW_EF_CONSTRUCTION", _get("faiss", "hnsw", "ef_construction", default=200)
)
FAISS_HNSW_EF_SEARCH: int = _env("FAISS_HNSW_EF_SEARCH", _get("faiss", "hnsw", "ef_search", default=128))
FAISS_IVF_NLIST: int = _env("FAISS_IVF_NLIST", _get("faiss", "ivf", "nlist", default=200))
FAISS_IVF_NPROBE: int = _env("FAISS_IVF_NPROBE", _get("faiss", "ivf", "nprobe", default=256))

# ── Unknown Face Retention ───────────────────────────────────
UNKNOWN_FACE_RETENTION_DAYS: int = _env(
    "UNKNOWN_FACE_RETENTION_DAYS", _get("unknown_faces", "retention_days", default=30)
)

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
# Uses the shared setup in utils/logging_setup.py: console + rotating file,
# with optional JSON format (LOG_FORMAT=json) for SIEM/log-shipper ingestion.
_LOG_LEVEL: str = _env("LOG_LEVEL", _get("logging", "level", default="INFO")).upper()
_LOG_FORMAT: str = _env("LOG_FORMAT", _get("logging", "format", default="plain")).lower()
_LOG_FILE = ROOT_DIR / (_get("logging", "file", default="logs/app.log"))
_LOG_MAX_BYTES = _env("LOG_MAX_SIZE_MB", _get("logging", "max_size_mb", default=10)) * 1024 * 1024
_LOG_BACKUP_COUNT = _env("LOG_BACKUP_COUNT", _get("logging", "backup_count", default=3))

from utils.logging_setup import configure_logging  # noqa: E402  (after dir setup)

configure_logging(
    level=_LOG_LEVEL,
    log_file=str(_LOG_FILE),
    max_bytes=_LOG_MAX_BYTES,
    backup_count=_LOG_BACKUP_COUNT,
    log_format=_LOG_FORMAT,
    force=True,
)
