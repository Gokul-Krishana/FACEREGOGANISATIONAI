"""
Alert Service — SMTP email notifications
==========================================

Best-effort, throttled email alerts for operational events:

    - Spoof / security alerts
    - Camera offline
    - Low disk space
    - Database down
    - Backup failures

Design goals:
- **Never blocks** the calling thread: sends happen on a daemon thread.
- **Never raises** into the caller: all failures are logged, not thrown.
- **Throttled** per alert type: at most one email per type per
  ``ALERT_MIN_INTERVAL_SECONDS`` (default 900s = 15 min) so a flapping
  camera never floods the inbox.
- **No secrets in code**: SMTP credentials come from environment
  variables (``SMTP_*``, ``ALERT_EMAIL_TO``), matching the rest of the
  project's env-driven configuration.

Configuration (see ``.env.example``)::

    ALERT_EMAIL_ENABLED=true
    SMTP_HOST=smtp.college.edu
    SMTP_PORT=587
    SMTP_USERNAME=faceai-alerts@college.edu
    SMTP_PASSWORD=...
    SMTP_FROM=FaceAI Alerts <faceai-alerts@college.edu>
    ALERT_EMAIL_TO=admin@college.edu,security@college.edu
    ALERT_MIN_INTERVAL_SECONDS=900
"""

from __future__ import annotations

import logging
import os
import smtplib
import threading
import time
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── In-memory throttle state ─────────────────────────────────────────
# alert_type → last-sent epoch seconds. Guarded by _THROTTLE_LOCK.
_THROTTLE: Dict[str, float] = {}
_THROTTLE_LOCK = threading.Lock()


def is_enabled() -> bool:
    """Whether email alerting is configured and switched on."""
    return os.getenv("ALERT_EMAIL_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _recipients() -> List[str]:
    raw = os.getenv("ALERT_EMAIL_TO", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


def _throttle(alert_type: str) -> bool:
    """Return True if this alert should be sent (not throttled)."""
    min_interval = float(os.getenv("ALERT_MIN_INTERVAL_SECONDS", "900"))
    now = time.time()
    with _THROTTLE_LOCK:
        last = _THROTTLE.get(alert_type, 0.0)
        if now - last < min_interval:
            return False
        _THROTTLE[alert_type] = now
        return True


def _send_smtp(subject: str, body: str, severity: str = "INFO") -> bool:
    """Send one email synchronously. Never raises."""
    recipients = _recipients()
    if not recipients:
        logger.warning(
            "Alert email not sent: ALERT_EMAIL_TO is empty. Subject: %s",
            subject,
        )
        return False

    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", username or "faceai-alerts@localhost")

    if not host:
        logger.warning("Alert email not sent: SMTP_HOST is empty.")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[{severity}] {subject}"
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            if port == 587 or os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes", "on"):
                server.starttls()
                server.ehlo()
            if username:
                server.login(username, password)
            server.sendmail(from_addr, recipients, msg.as_string())
        logger.info("Alert email sent: %s → %s", subject, ", ".join(recipients))
        return True
    except Exception as exc:
        logger.error("Alert email FAILED (%s): %s", subject, exc)
        return False


def send_alert(
    alert_type: str,
    subject: str,
    body: str,
    severity: str = "WARNING",
    throttle_key: Optional[str] = None,
) -> bool:
    """Send a throttled alert asynchronously (daemon thread).

    Args:
        alert_type: Stable identifier for throttling (e.g. ``spoof``,
            ``camera_offline``, ``low_disk``, ``db_down``).
        subject: Email subject line (without severity prefix).
        body: Plain-text email body.
        severity: INFO / WARNING / ERROR / CRITICAL (added to subject).
        throttle_key: Optional finer-grained throttle key. Defaults to
            ``alert_type``. Use e.g. ``f"camera_offline:{camera_id}"``
            to throttle per camera instead of globally.

    Returns:
        ``True`` if the alert was queued for sending, ``False`` if
        disabled, throttled, or misconfigured.
    """
    if not is_enabled():
        return False

    key = throttle_key or alert_type
    if not _throttle(key):
        logger.debug("Alert throttled: %s", key)
        return False

    def _worker() -> None:
        _send_smtp(subject, body, severity)

    threading.Thread(target=_worker, name=f"Alert-{alert_type}", daemon=True).start()
    return True


# ── Semantic helpers ─────────────────────────────────────────────────

def send_security_alert(
    description: str,
    details: Optional[Dict] = None,
    severity: str = "WARNING",
) -> bool:
    """Send a security alert (spoof attempt, session revocation, etc.)."""
    body = description
    if details:
        body += "\n\nDetails:\n" + "\n".join(
            f"  {k}: {v}" for k, v in details.items()
        )
    return send_alert(
        "security",
        "Security Alert — Face Recognition AI",
        body,
        severity=severity,
        throttle_key="security",
    )


def send_operational_alert(
    alert_type: str,
    message: str,
    severity: str = "WARNING",
    throttle_key: Optional[str] = None,
) -> bool:
    """Send an operational alert (camera offline, low disk, DB down)."""
    return send_alert(
        alert_type,
        f"Operational Alert ({alert_type.replace('_', ' ').title()})",
        message,
        severity=severity,
        throttle_key=throttle_key or alert_type,
    )


def reset_throttle() -> None:
    """Clear throttle state (useful for tests / manual retries)."""
    with _THROTTLE_LOCK:
        _THROTTLE.clear()
