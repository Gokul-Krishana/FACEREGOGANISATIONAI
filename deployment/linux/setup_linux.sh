#!/usr/bin/env bash
# ==============================================================================
# Face Recognition Attendance System 2.0 - Linux Setup Script (Ubuntu/Debian)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

echo "[SETUP] Installing Linux System Libraries..."
sudo apt-get update && sudo apt-get install -y \
    build-essential \
    python3-dev \
    python3-venv \
    libgl1 \
    libglib2.0-0 \
    v4l-utils

echo "[VENV] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "[PIP] Installing Linux dependencies from requirements-linux.txt..."
pip install --upgrade pip setuptools wheel
pip install -r requirements-linux.txt

echo "[DB] Seeding database & RBAC roles..."
python scripts/seed_admin.py

echo "[DONE] Linux setup complete. You can now start backend and dashboard."
