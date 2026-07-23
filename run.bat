@echo off
:: ============================================================
:: run.bat — Face Recognition AI Launcher
:: ============================================================
:: Launches the Streamlit dashboard (default) or runs the CLI
:: with a specific camera source.
::
:: Usage:
::   run.bat                        Start Streamlit dashboard
::   run.bat --no-cache             Skip cache clearing
::
::   run.bat cli                    Run laptop webcam (CLI)
::   run.bat cli --debug            Run diagnostic mode
::   run.bat cli webcam             Live with specific webcam
::
::   run.bat android-wifi URL      Android IP Webcam
::   run.bat android-usb DEVICE    Android DroidCam USB
::   run.bat iphone-wifi URL       iPhone EpocCam Wi-Fi
::   run.bat iphone-usb DEVICE     iPhone EpocCam USB
::   run.bat ip-camera URL         Generic IP/RTSP camera
::   run.bat usb-auto               USB Auto (plug & play)
::
:: Examples — Phone Cameras:
::   run.bat android-wifi http://192.168.1.100:8080/video
::   run.bat iphone-wifi http://192.168.1.101:8080/video
::   run.bat ip-camera rtsp://admin:pass@192.168.1.200:554/stream1
::
:: Examples — USB / Webcam:
::   run.bat android-usb 1
::   run.bat iphone-usb 2
::   run.bat cli webcam
::   run.bat usb-auto
::
:: Other CLI commands:
::   run.bat test                   Pipeline test on dataset/
::   run.bat debug                  Run diagnostics
::
::   python main.py --help         Full CLI reference
:: ============================================================

setlocal EnableDelayedExpansion

echo.
echo  ╔═══════════════════════════════════════════════════╗
echo  ║    Face Recognition AI — Startup Script           ║
echo  ╚═══════════════════════════════════════════════════╝
echo.

:: ── Parse arguments ──────────────────────────────────────────
set MODE=dashboard
set SKIP_CACHE=0
set CLI_ARGS=

:: Check for --no-cache flag (must be first argument)
if /i "%1"=="--no-cache" (
    set SKIP_CACHE=1
    shift
)

:: Parse the sub-command from the (possibly shifted) %1
if not "%1"=="" (
    if /i "%1"=="cli" (
        set MODE=cli
        set CLI_ARGS=--source-type webcam
        if /i "%2"=="debug"   set CLI_ARGS=--debug
        if /i "%2"=="test"    set CLI_ARGS=--test
        if /i "%2"=="webcam"  set CLI_ARGS=--source-type webcam
        goto :run_cli
    )
    if /i "%1"=="android-wifi" (
        set MODE=cli
        set CLI_ARGS=--source-type android_wifi --camera-url %2
        goto :run_cli
    )
    if /i "%1"=="android-usb" (
        set MODE=cli
        set CLI_ARGS=--source-type android_usb --camera-id %2
        goto :run_cli
    )
    if /i "%1"=="iphone-wifi" (
        set MODE=cli
        set CLI_ARGS=--source-type iphone_wifi --camera-url %2
        goto :run_cli
    )
    if /i "%1"=="iphone-usb" (
        set MODE=cli
        set CLI_ARGS=--source-type iphone_usb --camera-id %2
        goto :run_cli
    )
    if /i "%1"=="ip-camera" (
        set MODE=cli
        set CLI_ARGS=--source-type ip_camera --camera-url %2
        goto :run_cli
    )
    if /i "%1"=="usb-auto" (
        set MODE=cli
        set CLI_ARGS=--source-type usb_auto
        goto :run_cli
    )
    if /i "%1"=="debug" (
        set MODE=cli
        set CLI_ARGS=--debug
        goto :run_cli
    )
    if /i "%1"=="test" (
        set MODE=cli
        set CLI_ARGS=--test
        goto :run_cli
    )
)

:: ── Dashboard Mode (default) ─────────────────────────────────

:: Clear cache unless --no-cache
if %SKIP_CACHE%==0 (
    echo  🧹 Clearing Python cache...
    for /r %%i in (__pycache__) do @if exist "%%i" (
        echo     Removing: %%i
        rd /s /q "%%i" 2>nul
    )
    echo  ✅ Cache cleared!
    echo.
)

:: Check Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo  ❌ Python is not installed or not in PATH.
    echo     Please install Python 3.8+ and add it to PATH.
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
goto :end

:: ── CLI Mode ────────────────────────────────────────────────
:run_cli
:: Clear cache unless --no-cache
if %SKIP_CACHE%==0 (
    echo  🧹 Clearing Python cache...
    for /r %%i in (__pycache__) do @if exist "%%i" (
        echo     Removing: %%i
        rd /s /q "%%i" 2>nul
    )
    echo  ✅ Cache cleared!
    echo.
)

echo  🚀 Running CLI mode: python main.py %CLI_ARGS%
echo.
echo ─────────────────────────────────────────────────────
echo.

python main.py %CLI_ARGS%

goto :end

:end
echo.
echo  ✅ Done.
if not "%MODE%"=="cli" pause
endlocal
