#!/bin/bash
# ============================================================
# run.sh — Start Face Recognition AI with cache clearing
# ============================================================
# This script clears stale __pycache__ before starting Streamlit,
# preventing issues like:
#   AttributeError: module 'config.config' has no attribute 'get_settings'
#
# Usage:
#   ./run.sh              Start with cache clearing
#   ./run.sh --no-cache   Skip cache clearing (faster startup)
# ============================================================

set -e

echo ""
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║    Face Recognition AI — Startup Script           ║"
echo "  ╚═══════════════════════════════════════════════════╝"
echo ""

# Check for --no-cache flag
SKIP_CACHE=0
if [ "$1" = "--no-cache" ]; then
    SKIP_CACHE=1
fi

# Clear cache unless --no-cache is specified
if [ $SKIP_CACHE -eq 0 ]; then
    echo "  🧹 Clearing Python cache..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    echo "  ✅ Cache cleared!"
    echo ""
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "  ❌ Python3 is not installed or not in PATH."
    echo "     Please install Python 3.8+."
    exit 1
fi

# Check if Streamlit is installed
if ! python3 -c "import streamlit" &> /dev/null; then
    echo "  ❌ Streamlit is not installed."
    echo "     Run: pip install streamlit"
    exit 1
fi

# Start Streamlit
echo "  🚀 Starting Face Recognition AI Dashboard..."
echo "  📍 URL: http://localhost:8501"
echo "  ⏹  Press Ctrl+C to stop"
echo ""
echo "─────────────────────────────────────────────────────"
echo ""

streamlit run dashboard/app.py --server.port 8501 --server.headless true
