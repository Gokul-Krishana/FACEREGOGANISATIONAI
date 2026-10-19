"""Attendance-page verification for the current stack.

The old Streamlit Attendance page no longer exists. The current backend exposes
attendance data through REST and can export it as CSV:

    GET  /attendance?limit=N&skip=N&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    GET  /bulk/attendance/export?date_from=...&date_to=...

This script validates those endpoints directly (backend must be running).
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def _api_url(path: str, port: int = 8000) -> str:
    return f"http://localhost:{port}{path}"


def main() -> int:
    failures = 0
    base = _api_url("/attendance")
    params = urllib.parse.urlencode({"limit": "1", "skip": "0"})
    url = f"{base}?{params}"

    print("Backend attendance endpoint verification")
    print("-" * 60)

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", "replace")
        print(f"[{status}] GET /attendance?limit=1&skip=0")
        print(f"   {body[:400]}")
    except urllib.error.HTTPError as exc:
        print(f"[HTTP {exc.code}] GET /attendance - {exc.reason}")
        failures += 1
    except Exception as exc:
        print(f"[ERROR] GET /attendance: {exc}")
        failures += 1

    export_url = _api_url("/bulk/attendance/export")
    try:
        req = urllib.request.Request(export_url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", "replace")
        print()
        print(f"[{status}] GET /bulk/attendance/export")
        print(f"   {body[:200]!r}")
        if not body.strip():
            print("   (empty export is OK when there is no attendance data)")
    except urllib.error.HTTPError as exc:
        print()
        print(f"[HTTP {exc.code}] GET /bulk/attendance/export - {exc.reason}")
        failures += 1
    except Exception as exc:
        print()
        print(f"[ERROR] GET /bulk/attendance/export: {exc}")
        failures += 1

    print()
    if failures:
        print("Attendance endpoint check failed.")
    else:
        print("Attendance endpoints are reachable (backend must be running on port 8000).")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
