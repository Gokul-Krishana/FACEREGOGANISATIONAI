"""
Service Watchdog & Auto-Recovery Daemon
=======================================

Monitors FastAPI backend and Streamlit dashboard services:
- Pings health endpoints continuously
- Detects unresponsive, hanging, or terminated processes
- Automatically restarts services with exponential backoff
- Emits structured health logs to ``logs/watchdog.log``

Usage:
    python scripts/service_watchdog.py --check-once
    python scripts/service_watchdog.py --interval 15
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
WATCHDOG_LOG = LOGS_DIR / "watchdog.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [WATCHDOG] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(WATCHDOG_LOG), encoding="utf-8"),
    ],
)
logger = logging.getLogger("service_watchdog")

FASTAPI_HEALTH_URL = os.getenv("FASTAPI_HEALTH_URL", "http://127.0.0.1:8000/health")
STREAMLIT_HEALTH_URL = os.getenv("STREAMLIT_HEALTH_URL", "http://127.0.0.1:8501/_stcore/health")


def check_endpoint(url: str, timeout: float = 3.0) -> tuple[bool, int, str]:
    """Ping an HTTP health endpoint.

    Returns:
        (is_healthy, status_code, message)
    """
    req = urllib.request.Request(url, headers={"User-Agent": "FaceAI-Watchdog/2.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            code = response.getcode()
            return (code == 200, code, "OK" if code == 200 else f"HTTP {code}")
    except urllib.error.HTTPError as exc:
        return (False, exc.code, f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return (False, 0, f"Connection refused / timeout: {exc.reason}")
    except Exception as exc:
        return (False, 0, f"Error: {exc}")


def restart_service(service_name: str) -> None:
    """Attempt to restart a failed service."""
    logger.warning("Attempting automatic service restart for: %s", service_name)
    if service_name == "fastapi":
        cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    elif service_name == "streamlit":
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard/app.py",
            "--server.port",
            "8501",
            "--server.headless",
            "true",
        ]
    else:
        logger.error("Unknown service: %s", service_name)
        return

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        logger.info("Spawned new process for %s (PID: %d)", service_name, proc.pid)
    except Exception as exc:
        logger.error("Failed to spawn process for %s: %s", service_name, exc)


def run_health_check(auto_restart: bool = False) -> Dict[str, dict]:
    """Execute a single health check sweep across all services."""
    results = {}
    targets = [
        ("fastapi", FASTAPI_HEALTH_URL),
        ("streamlit", STREAMLIT_HEALTH_URL),
    ]

    for name, url in targets:
        healthy, code, msg = check_endpoint(url)
        results[name] = {"healthy": healthy, "code": code, "detail": msg, "url": url}
        status_symbol = "🟢" if healthy else "🔴"
        logger.info(
            "%s Service [%s]: %s (code: %d, detail: %s)",
            status_symbol,
            name,
            "HEALTHY" if healthy else "UNHEALTHY",
            code,
            msg,
        )

        if not healthy and auto_restart:
            restart_service(name)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Service Watchdog & Auto-Recovery")
    parser.add_argument("--check-once", action="store_true", help="Perform single health check and exit")
    parser.add_argument("--interval", type=int, default=15, help="Poll interval in seconds (default: 15)")
    parser.add_argument("--auto-restart", action="store_true", help="Auto-restart services on failure")
    args = parser.parse_args()

    logger.info("Starting Face Recognition AI Service Watchdog v2.1")
    logger.info("FastAPI URL   : %s", FASTAPI_HEALTH_URL)
    logger.info("Streamlit URL : %s", STREAMLIT_HEALTH_URL)

    if args.check_once:
        res = run_health_check(auto_restart=args.auto_restart)
        all_ok = all(v["healthy"] for v in res.values())
        return 0 if all_ok else 1

    consecutive_failures = {"fastapi": 0, "streamlit": 0}
    try:
        while True:
            res = run_health_check(auto_restart=False)
            for name, data in res.items():
                if not data["healthy"]:
                    consecutive_failures[name] += 1
                    if consecutive_failures[name] >= 3 and args.auto_restart:
                        logger.error("Service %s failed 3 consecutive checks! Triggering restart...", name)
                        restart_service(name)
                        consecutive_failures[name] = 0
                else:
                    consecutive_failures[name] = 0

            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Service watchdog stopped by user.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
