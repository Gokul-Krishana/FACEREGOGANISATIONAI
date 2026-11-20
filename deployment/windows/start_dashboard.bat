@echo off
REM ============================================================================
REM Face Recognition Attendance System 2.0 - Windows Dashboard Startup
REM ============================================================================

cd /d "%~dp0..\..\"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo [START] Launching Streamlit Dashboard on http://localhost:8501 ...
streamlit run dashboard/app.py --server.port 8501 --server.headless true
pause
