"""
Headless verification of all Streamlit dashboard pages.

Runs every page in dashboard/pages/ through Streamlit's AppTest
framework (same execution path the browser uses server-side) and
reports any exceptions raised during rendering.

Usage:
    python scripts/verify_dashboard_pages.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Ensure project root is on path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from streamlit.testing.v1 import AppTest  # noqa: E402  (needs sys.path setup above)

PAGES_DIR = Path(_project_root) / "dashboard" / "pages"

PAGE_LABELS = {
    "01_Dashboard.py": "Dashboard",
    "02_Employees.py": "Employees",
    "03_Enroll.py": "Enroll",
    "04_Live.py": "Live Recognition",
    "05_Attendance.py": "Attendance",
    "06_Unknown.py": "Unknown Faces",
    "07_Analytics.py": "Analytics",
    "08_Settings.py": "Settings",
    "09_Health.py": "System Health",
    "10_About.py": "About",
}


def verify_page(page_file: str) -> list[str]:
    """Run one page and return a list of exception messages (empty = pass)."""
    path = str(PAGES_DIR / page_file)
    try:
        at = AppTest.from_file(path, default_timeout=180)
        at.run()
    except Exception:
        return [traceback.format_exc()]
    return [str(exc) for exc in at.exception]


def main() -> int:
    results = []
    failures = 0
    for page_file, label in PAGE_LABELS.items():
        errors = verify_page(page_file)
        status = "PASS" if not errors else "FAIL"
        if errors:
            failures += 1
        results.append((label, page_file, status, errors))
        print(f"[{status}] {label:18s} ({page_file})")

    print()
    print("=" * 60)
    if failures == 0:
        print("ALL 10 PAGES PASS — no exceptions raised")
    else:
        print(f"{failures} page(s) FAILED:")
        for label, page_file, status, errors in results:
            if status == "FAIL":
                print(f"\n--- {label} ({page_file}) ---")
                for e in errors:
                    print(e)
    print("=" * 60)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
