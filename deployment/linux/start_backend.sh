#!/usr/bin/env bash
# ==============================================================================
# Face Recognition Attendance System 2.0 - Linux Backend Startup
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "[START] Launching FastAPI Backend on http://0.0.0.0:8000 ..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
