@echo off
:: ============================================================
:: run.bat — Start Face Recognition AI with cache clearing
:: ============================================================
:: This script clears stale __pycache__ before starting Streamlit,
:: preventing issues like:
::   AttributeError: module 'config.config' has no attribute 'get_settings'
::
:: Usage:
::   run.bat              Start with cache clearing
::   run.bat --no-cache   Skip cache clearing (faster startup)
:: ============================================================

setlocal EnableDelayedExpansion

echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║    Face Recognition AI — Startup Script           ║
echo  ╚═══════════════════════════════════════════════════╝
echo.

:: Check for --no-cache flag
set SKIP_CACHE=0
if "%1"=="--no-cache" set SKIP_CACHE=1

:: Clear cache unless --no-cache is specified
if %SKIP_CACHE%==0 (
    echo  🧹 Clearing Python cache...
    for /r %%i in (__pycache__) do @if exist "%%i" (
        echo     Removing: %%i
        rd /s /q "%%i" 2>nul
    )
    echo  ✅ Cache cleared!
    echo.
)

:: Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo  ❌ Python is not installed or not in PATH.
    echo     Please install Python 3.8+ and add it to PATH.
    pause
    exit /b 1
)

:: Check if Streamlit is installed
python -c "import streamlit" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo  ❌ Streamlit is not installed.
    echo     Run: pip install streamlit
    pause
    exit /b 1
)

:: Start Streamlit
echo  🚀 Starting Face Recognition AI Dashboard...
echo  📍 URL: http://localhost:8501
echo  ⏹  Press Ctrl+C to stop
echo.
echo ─────────────────────────────────────────────────────
echo.

streamlit run dashboard/app.py --server.port 8501 --server.headless true

endlocal
