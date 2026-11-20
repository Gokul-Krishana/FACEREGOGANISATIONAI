#!/usr/bin/env bash
# ==============================================================================
# Face Recognition Attendance System 2.0 - Linux Dashboard Startup
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

echo "[START] Launching Streamlit Dashboard on port 8501 ..."
exec streamlit run dashboard/app.py --server.port 8501 --server.headless true --server.address 0.0.0.0
