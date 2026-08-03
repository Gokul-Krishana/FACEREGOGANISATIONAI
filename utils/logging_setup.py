"""
Central logging setup for Face Recognition AI.

Single source of truth for log configuration across the whole project:

- ``configure_logging(...)`` installs console + rotating-file handlers
  (called once by ``config/config.py`` with production settings).
- ``get_logger(name)`` is safe to call from any module, even ones imported
  before ``config`` — it configures sensible console defaults when nothing
  has been configured yet (idempotent).
- ``redact_url(url)`` masks credentials embedded in stream URLs
  (``rtsp://admin:pass@host`` → ``rtsp://admin:****@host``) so camera
  credentials never reach the logs.

Security note: the pipeline logs recognition *decisions* (names, scores)
but never biometric data (embeddings, face crops, snapshots).
"""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_configured = False
_DEFAULT_LEVEL = "INFO"
_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter (one JSON object per line).

    Produces machine-readable logs suitable for shipping to a SIEM or log
    aggregator. Enable with ``LOG_FORMAT=json``.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)
        return json.dumps(payload, ensure_ascii=False)


def redact_url(url: str) -> str:
    """Mask userinfo (credentials) embedded in a URL.

    ``rtsp://admin:secret@192.168.1.50:554/stream`` becomes
    ``rtsp://admin:****@192.168.1.50:554/stream``. Non-credentialed URLs
    (e.g. ``http://192.168.1.100:8080/video``) are returned unchanged.
    """
    if not url or "://" not in url:
        return url
    try:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(url)
        if parts.password is None:
            return url
        hostname = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        username = parts.username or ""
        netloc = f"{username}:****@{hostname}{port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        # Malformed URL (e.g. bad port) — fall back to the raw string.
        return url


def configure_logging(
    level: str = _DEFAULT_LEVEL,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
    log_format: str = "plain",
    force: bool = False,
) -> None:
    """Install console + optional rotating-file log handlers.

    Idempotent: the second call is a no-op unless ``force=True`` (used by
    ``config/config.py`` to upgrade a default console-only config with the
    full production config, regardless of import order).
    """
    global _configured
    if _configured and not force:
        return

    root = logging.getLogger()
    # Replace any handlers installed earlier (e.g. console-only defaults).
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    level_no = getattr(logging, str(level).upper(), logging.INFO)

    if str(log_format).strip().lower() == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_path = str(log_file)
        try:
            from pathlib import Path

            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            handlers.append(
                logging.handlers.RotatingFileHandler(
                    log_path,
                    maxBytes=int(max_bytes),
                    backupCount=int(backup_count),
                    encoding="utf-8",
                )
            )
        except Exception:
            # File logging is best-effort — console still works.
            pass

    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(level_no)
    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger, configuring console defaults on first use.

    Safe to call from any module — including ones imported before
    ``config.config`` — because configuration is idempotent and the
    full production config later replaces it via ``force=True``.
    """
    configure_logging()  # No-op if already configured.
    return logging.getLogger(name)
