@echo off
REM ============================================================================
REM Face Recognition Attendance System 2.0 - Windows Setup & Dependency Check
REM ============================================================================

cd /d "%~dp0..\..\"

echo [SETUP] Initializing Windows Python Virtual Environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [INSTALL] Installing Windows Dependencies from requirements-windows.txt...
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-windows.txt

echo [DB] Initializing Database & Seeding RBAC...
python scripts/seed_admin.py

echo [READY] Windows setup complete.
pause
