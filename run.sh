#!/bin/bash
# ============================================================
# run.sh — Face Recognition AI Launcher
# ============================================================
# Launches the Streamlit dashboard (default) or runs the CLI
# with a specific camera source.
#
# Usage:
#   ./run.sh                        Start Streamlit dashboard
#   ./run.sh --no-cache             Skip cache clearing
#
#   ./run.sh cli                    Run laptop webcam (CLI)
#   ./run.sh cli --debug            Run diagnostic mode
#   ./run.sh cli webcam             Live with specific webcam
#
#   ./run.sh android-wifi URL       Android IP Webcam
#   ./run.sh android-usb DEVICE     Android DroidCam USB
#   ./run.sh iphone-wifi URL       iPhone EpocCam Wi-Fi
#   ./run.sh iphone-usb DEVICE     iPhone EpocCam USB
#   ./run.sh ip-camera URL         Generic IP/RTSP camera
#   ./run.sh usb-auto               USB Auto (plug & play)
#
# Examples — Phone Cameras:
#   ./run.sh android-wifi http://192.168.1.100:8080/video
#   ./run.sh iphone-wifi http://192.168.1.101:8080/video
#   ./run.sh ip-camera rtsp://admin:pass@192.168.1.200:554/stream1
#
# Examples — USB / Webcam:
#   ./run.sh android-usb 1
#   ./run.sh iphone-usb 2
#   ./run.sh cli webcam
#   ./run.sh usb-auto
#
# Other CLI commands:
#   ./run.sh test                   Pipeline test on dataset/
#   ./run.sh debug                  Run diagnostics
#
#   python3 main.py --help         Full CLI reference
# ============================================================

set -e

echo ""
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║    Face Recognition AI — Startup Script           ║"
echo "  ╚═══════════════════════════════════════════════════╝"
echo ""

# ── Parse arguments ──────────────────────────────────────────
SKIP_CACHE=0
MODE="dashboard"
CLI_ARGS=""

# Check for --no-cache flag first
if [ "$1" = "--no-cache" ]; then
    SKIP_CACHE=1
    shift
fi

# Parse sub-command
case "$1" in
    cli)
        MODE="cli"
        shift
        case "$1" in
            ""|webcam)    CLI_ARGS="--source-type webcam" ;;
            debug)        CLI_ARGS="--debug" ;;
            test)         CLI_ARGS="--test" ;;
            *)            CLI_ARGS="--source-type webcam" ;;
        esac
        ;;
    android-wifi)
        MODE="cli"
        CLI_ARGS="--source-type android_wifi --camera-url $2"
        ;;
    android-usb)
        MODE="cli"
        CLI_ARGS="--source-type android_usb --camera-id $2"
        ;;
    iphone-wifi)
        MODE="cli"
        CLI_ARGS="--source-type iphone_wifi --camera-url $2"
        ;;
    iphone-usb)
        MODE="cli"
        CLI_ARGS="--source-type iphone_usb --camera-id $2"
        ;;
    ip-camera)
        MODE="cli"
        CLI_ARGS="--source-type ip_camera --camera-url $2"
        ;;
    usb-auto)
        MODE="cli"
        CLI_ARGS="--source-type usb_auto"
        ;;
    debug)
        MODE="cli"
        CLI_ARGS="--debug"
        ;;
    test)
        MODE="cli"
        CLI_ARGS="--test"
        ;;
esac

# ── Cache clearing ────────────────────────────────────────────
if [ $SKIP_CACHE -eq 0 ]; then
    echo "  🧹 Clearing Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    echo "  ✅ Cache cleared!"
    echo ""
fi

# ── Dashboard Mode ────────────────────────────────────────────
if [ "$MODE" = "dashboard" ]; then
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo "  ❌ Python3 is not installed or not in PATH."
        echo "     Please install Python 3.8+."
        exit 1
    fi

    # Check Streamlit
    if ! python3 -c "import streamlit" &> /dev/null; then
        echo "  ❌ Streamlit is not installed."
        echo "     Run: pip install streamlit"
        exit 1
    fi

    echo "  🚀 Starting Face Recognition AI Dashboard..."
    echo "  📍 URL: http://localhost:8501"
    echo "  ⏹  Press Ctrl+C to stop"
    echo ""
    echo "─────────────────────────────────────────────────────"
    echo ""

    streamlit run dashboard/app.py --server.port 8501 --server.headless true

# ── CLI Mode ────────────────────────────────────────────────────
elif [ "$MODE" = "cli" ]; then
    echo "  🚀 Running CLI mode: python3 main.py $CLI_ARGS"
    echo ""
    echo "─────────────────────────────────────────────────────"
    echo ""

    python3 main.py $CLI_ARGS

    echo ""
    echo "  ✅ Done."
fi
