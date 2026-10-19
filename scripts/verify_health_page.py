"""Health-page verification for the current stack.

The old Streamlit System Health page no longer exists. The current backend
exposes machine-readable health endpoints:

    GET /health          - status summary
    GET /health/ready    - readiness checks
    GET /health/live     - liveness probe

This script validates those endpoints directly.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def _api_url(path: str, port: int = 8000) -> str:
    return f"http://localhost:{port}{path}"


def main() -> int:
    failures = 0
    base = _api_url("/health")
    ready = _api_url("/health/ready")
    liveness = _api_url("/health/live")

    print("Backend health endpoint verification")
    print("-" * 60)

    for label, url in [("/health", base), ("/health/ready", ready), ("/health/live", liveness)]:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body = resp.read().decode("utf-8", "replace")
            print(f"[{status}] {label}")
            print(f"   {body[:300]}")
        except urllib.error.HTTPError as exc:
            print(f"[HTTP {exc.code}] {label} - {exc.reason}")
            failures += 1
        except Exception as exc:
            print(f"[ERROR] {label}: {exc}")
            failures += 1

    print()
    if failures:
        print("Health endpoint check failed.")
    else:
        print("Health endpoints are reachable (backend must be running on port 8000).")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
