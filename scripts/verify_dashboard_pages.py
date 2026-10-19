"""Frontend coverage verification for the current stack.

The repository no longer uses a Streamlit dashboard. The primary UI is the
Next.js frontend in ``frontend/``, and the backend is FastAPI in ``api/``.

This script verifies the parts that can be checked headlessly without a
browser GPU/screen:

    1. The Next.js app type-checks/builds (optional, controlled by flags).
    2. The FastAPI app imports and exposes the expected public routes.
    3. The live-video session routes exist and are wired correctly.

Run it from the project root::

    python scripts/verify_dashboard_pages.py

Notes:
    - Full Next.js build is optional because it is slow and depends on node.
    - Backend verification is the default because it is deterministic and
      does not require a camera or browser.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def run_backend_check() -> int:
    """Verify the FastAPI app starts up enough to list its routes."""
    print("Backend route verification")
    print("-" * 60)

    try:
        from api.main import app
    except Exception as exc:
        print(f"[FAIL] Could not import api.main.app:\n{exc}")
        return 1

    routes = sorted(
        {
            r.path.rstrip("/") or "/"
            for r in app.routes
            if getattr(r, "path", None) is not None or getattr(r, "routes", None) is not None
        }
    )

    expected_prefixes = [
        "/auth/login",
        "/auth/me",
        "/auth/logout",
        "/auth/refresh",
        "/video/sessions/start",
        "/video/sessions",
        "/video/sessions/{session_key}/stop",
        "/video/sessions/{session_key}/status",
        "/video/sessions/{session_key}/mjpeg",
        "/ws/live",
        "/health",
        "/health/ready",
        "/students",
        "/employees",
        "/cameras",
        "/attendance",
        "/analytics/attendance-summary",
        "/jobs",
    ]

    missing = []
    for prefix in expected_prefixes:
        if not any(p == prefix or p.startswith(prefix) for p in routes):
            missing.append(prefix)

    print(f"Found {len(routes)} routes in the FastAPI app.")
    if missing:
        print("Missing expected route prefixes:")
        for p in missing:
            print(f"  - {p}")
        return 1

    print("Expected backend routes are present.")
    return 0


def run_frontend_check(perform_build: bool = False) -> int:
    """Optionally run a headless frontend sanity check."""
    print("Frontend verification")
    print("-" * 60)

    frontend_dir = Path(_project_root) / "frontend"
    if not frontend_dir.is_dir():
        print("[SKIP] No frontend/ directory found.")
        return 0

    node_paths = ["node", "npm", "npx"]
    if not any(Path(p).exists() or any(_cmd_exists(c) for c in node_paths) for p in [None]):
        # Fall back to a lightweight check of whether node is available.
        import shutil

        node_ok = shutil.which("node") is not None
        npm_ok = shutil.which("npm") is not None
        if not node_ok or not npm_ok:
            print("[SKIP] Node/npm not available; skipping frontend checks.")
            return 0

    pkg = frontend_dir / "package.json"
    if not pkg.exists():
        print("[SKIP] No frontend/package.json found.")
        return 0

    try:
        manifest = importlib.import_module("json").loads(pkg.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[FAIL] Could not read frontend/package.json:\n{exc}")
        return 1

    scripts = manifest.get("scripts", {})
    has_dev = bool(scripts.get("dev"))
    has_build = bool(scripts.get("build"))
    print(f"Next.js app detected. dev={has_dev}, build={has_build}.")

    if perform_build:
        import subprocess

        print("Running frontend production build (this may take a while)...")
        try:
            proc = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(frontend_dir),
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            print("[FAIL] Frontend build timed out.")
            return 1
        except Exception as exc:
            print(f"[FAIL] Could not run frontend build:\n{exc}")
            return 1

        if proc.returncode != 0:
            print("[FAIL] Frontend build failed.")
            print(proc.stdout[-4000:])
            print(proc.stderr[-4000:])
            return 1

        print("Frontend production build succeeded.")
    else:
        print("Frontend build skipped (use --build to run it).")

    return 0


def _cmd_exists(name: str) -> bool:
    import shutil

    return shutil.which(name) is not None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the current FaceRecognitionAI frontend/backend stack."
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Also run the Next.js production build (optional).",
    )
    args = parser.parse_args()

    failures = 0

    backend_rc = run_backend_check()
    if backend_rc != 0:
        failures += 1

    frontend_rc = run_frontend_check(perform_build=args.build)
    if frontend_rc != 0:
        failures += 1

    print()
    if failures == 0:
        print("Verification passed for the current stack.")
    else:
        print(f"Verification failed in {failures} area(s).")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
