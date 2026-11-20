@echo off
REM ============================================================================
REM Face Recognition Attendance System 2.0 - Windows Backend Startup
REM ============================================================================

cd /d "%~dp0..\..\"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo [START] Launching FastAPI Backend on http://127.0.0.1:8000 ...
uvicorn api.main:app --host 127.0.0.1 --port 8000
pause
