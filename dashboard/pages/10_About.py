"""
About — Project Information & Credits
========================================

Displays:
- Project name, version, and description
- AI models used (YOLO11, RetinaFace, ArcFace, FAISS)
- Team / author info
- Technology stack
- Supported camera types guide
- License information
"""

from __future__ import annotations

from pathlib import Path
import sys

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

import config.config as cfg

st.set_page_config(page_title="About", page_icon="ℹ️", layout="wide")


# ── Helper ─────────────────────────────────────────────────────

def _pill(label: str, items: list[str]) -> None:
    """Render a label with clickable-looking pill badges."""
    badges = " ".join(
        f'<span style="display: inline-block; background: #2d2d2d; '
        f'border: 1px solid #555; border-radius: 12px; padding: 2px 10px; '
        f'margin: 2px 4px 2px 0; font-size: 0.85em;">{item}</span>'
        for item in items
    )
    st.markdown(f"**{label}**  \n{badges}", unsafe_allow_html=True)


# ── Page Header ────────────────────────────────────────────────

st.title("ℹ️ About Face Recognition AI")

st.markdown(
    """
    <div style="
        text-align: center;
        padding: 30px;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border-radius: 12px;
        margin-bottom: 24px;
    ">
        <h1 style="font-size: 3rem; margin: 0;">🟢</h1>
        <h2 style="margin: 8px 0 4px 0;">Face Recognition AI</h2>
        <p style="color: #aaaaaa; margin: 0;">Version 1.0 — Real-time face recognition & attendance system</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Main Content ───────────────────────────────────────────────

left_col, right_col = st.columns([3, 2], gap="large")

with left_col:
    st.markdown("### 📖 Overview")
    st.markdown(
        """
        Face Recognition AI is a production-ready, real-time face recognition system 
        that combines **YOLO11** for person detection, **RetinaFace** for face detection, 
        **ArcFace** for generating face embeddings, and **FAISS** for fast similarity search.

        The system supports **multiple camera sources** including laptop webcams, 
        USB cameras, Android phones (Wi-Fi/USB), iPhones (Wi-Fi/USB), and IP/RTSP 
        security cameras. It runs entirely **offline** — no cloud services required.

        **Key Features:**
        - 🎯 Real-time face recognition at 15-30 FPS
        - 📱 Dual camera support (Android + iPhone simultaneously)
        - 📸 Face enrollment with automatic FAISS indexing
        - 📋 Automatic attendance marking
        - 🔴 Unknown face detection & gallery management
        - 📊 Rich analytics with interactive charts
        - 🩺 Built-in health monitoring & diagnostics
        """
    )

    st.divider()

    st.markdown("### 🧠 AI Pipeline")
    st.markdown(
        """
        ```
        ┌──────────┐     ┌───────────┐     ┌─────────┐     ┌─────────┐
        │  YOLO11  │ →  │ RetinaFace │ →  │ ArcFace │ →  │  FAISS  │
        │  Person  │     │   Face     │     │  512-D  │     │ Nearest  │
        │ Detection│     │ Detection  │     │Embedding │     │Neighbor  │
        └──────────┘     └───────────┘     └─────────┘     └─────────┘
        """
    )

    st.divider()

    st.markdown("### 🛠️ Technology Stack")
    _pill("AI / ML", ["YOLO11", "RetinaFace", "ArcFace", "FAISS", "InsightFace", "PyTorch"])
    _pill("Backend", ["Python 3.10+", "OpenCV", "NumPy", "SQLAlchemy", "SQLite", "Alembic"])
    _pill("Frontend", ["Streamlit", "Pandas", "Plotly", "WebRTC"])
    _pill("Camera", ["OpenCV DirectShow", "DroidCam", "EpocCam", "IP Webcam", "RTSP"])
    _pill("Tools", ["pytest", "ruamel.yaml", "Git"])

with right_col:
    st.markdown("### 📱 Supported Cameras")

    cam_html = """
    <table style="width: 100%; border-collapse: collapse;">
        <tr style="border-bottom: 1px solid #333;">
            <th style="text-align: left; padding: 8px;">Type</th>
            <th style="text-align: left; padding: 8px;">Connection</th>
            <th style="text-align: left; padding: 8px;">App</th>
        </tr>
        <tr style="border-bottom: 1px solid #222;">
            <td style="padding: 8px;">💻 Laptop Webcam</td>
            <td style="padding: 8px;">Built-in</td>
            <td style="padding: 8px;">None</td>
        </tr>
        <tr style="border-bottom: 1px solid #222;">
            <td style="padding: 8px;">🔌 USB Auto</td>
            <td style="padding: 8px;">Plug & Play</td>
            <td style="padding: 8px;">None (UVC)</td>
        </tr>
        <tr style="border-bottom: 1px solid #222;">
            <td style="padding: 8px;">📱 Android (Wi-Fi)</td>
            <td style="padding: 8px;">HTTP MJPEG</td>
            <td style="padding: 8px;">IP Webcam</td>
        </tr>
        <tr style="border-bottom: 1px solid #222;">
            <td style="padding: 8px;">📱 Android (USB)</td>
            <td style="padding: 8px;">USB</td>
            <td style="padding: 8px;">DroidCam</td>
        </tr>
        <tr style="border-bottom: 1px solid #222;">
            <td style="padding: 8px;">📱 iPhone (Wi-Fi)</td>
            <td style="padding: 8px;">RTSP/HTTP</td>
            <td style="padding: 8px;">EpocCam</td>
        </tr>
        <tr style="border-bottom: 1px solid #222;">
            <td style="padding: 8px;">📱 iPhone (USB)</td>
            <td style="padding: 8px;">DirectShow</td>
            <td style="padding: 8px;">EpocCam</td>
        </tr>
        <tr>
            <td style="padding: 8px;">🌐 IP Camera</td>
            <td style="padding: 8px;">RTSP/HTTP</td>
            <td style="padding: 8px;">Any</td>
        </tr>
    </table>
    """
    st.markdown(cam_html, unsafe_allow_html=True)

    st.divider()

    st.markdown("### 📊 Version Information")

    import importlib.metadata as md

    version_info = {
        "Face Recognition AI": "1.0.0",
        "Python": sys.version.split()[0],
    }

    for pkg in ["streamlit", "opencv-python", "numpy", "pandas", "torch", "sqlalchemy", "faiss-cpu"]:
        try:
            version_info[pkg] = md.version(pkg.replace("-", "-"))
        except Exception:
            version_info[pkg] = "?"

    ver_df_data = [{"Component": k, "Version": v} for k, v in version_info.items()]
    import pandas as pd
    st.dataframe(
        pd.DataFrame(ver_df_data),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.markdown("### 📄 License")
    st.info(
        "This project is licensed under the **MIT License**. "
        "You are free to use, modify, and distribute this software "
        "for personal or commercial purposes."
    )

# ── Project Structure ──────────────────────────────────────────
st.divider()
st.markdown("### 📁 Project Structure")

st.code("""
FaceRecognitionAI/
│
├── app/                  # Core pipeline modules
│   ├── face_detector.py  # YOLO11 person detection
│   ├── recognizer.py     # RetinaFace + ArcFace embedding
│   ├── enrollment.py     # FAISS index management
│   ├── attendance.py     # CSV attendance tracking
│   └── live_detection.py # Integrated live pipeline
│
├── camera/               # Camera abstraction layer
│   ├── base.py           # CameraSource interface
│   ├── webcam.py         # Webcam / USB camera
│   ├── phone.py          # Phone camera (Android/iPhone)
│   ├── selector.py       # Camera factory
│   └── discovery.py      # Network auto-discovery
│
├── config/               # Configuration
│   ├── config.py         # Python config module
│   └── settings.yaml     # User-editable settings
│
├── dashboard/            # Streamlit web UI
│   ├── app.py            # Main entry + navigation
│   └── pages/            # 10 dashboard pages
│       ├── 01_Dashboard.py
│       ├── 02_Employees.py
│       ├── 03_Enroll.py
│       ├── 04_Live.py
│       ├── 05_Attendance.py
│       ├── 06_Unknown.py
│       ├── 07_Analytics.py
│       ├── 08_Settings.py
│       ├── 09_Health.py      # ← New: System Monitoring
│       └── 10_About.py       # ← New: Project Info
│
├── database/             # ORM + migrations
│   ├── database.py       # Session management
│   ├── models.py         # SQLAlchemy models
│   └── repository.py     # CRUD operations
│
├── services/             # Business logic layer
│   ├── attendance_service.py
│   ├── employee_service.py
│   ├── recognition_service.py
│   ├── unknown_face_service.py
│   └── audit_service.py
│
├── embeddings/           # FAISS index + metadata
├── models/               # YOLO model weights
├── tests/                # 137+ pytest tests
│
├── main.py               # CLI entry point
├── requirements.txt      # Python dependencies
├── LICENSE               # MIT License
└── README.md             # This file
""")

# ── Credits ────────────────────────────────────────────────────
st.divider()
st.markdown("### 👥 Credits")

credit_col1, credit_col2, credit_col3 = st.columns(3)
with credit_col1:
    st.markdown("**AI Models**")
    st.caption("""
    - YOLO11 by Ultralytics
    - InsightFace by DeepInsight
    - FAISS by Meta AI
    - ArcFace by Deng et al.
    """)
with credit_col2:
    st.markdown("**Frameworks**")
    st.caption("""
    - Streamlit by Snowflake
    - PyTorch by Meta AI
    - OpenCV by Intel
    - SQLAlchemy by Mike Bayer
    """)
with credit_col3:
    st.markdown("**Special Thanks**")
    st.caption("""
    - DroidCam by Dev47Apps
    - IP Webcam by Pavel Khlebovich
    - EpocCam by Elgato
    - Open source community
    """)

st.divider()
st.caption(
    "© 2026 Face Recognition AI. Built with ❤️ using open-source software. "
    f"Configuration: {cfg.SETTINGS_PATH}"
)
