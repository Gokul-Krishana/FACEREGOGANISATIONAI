"""
Settings — Edit and persist configuration to ``config/settings.yaml``
=====================================================================

Supports:
- Camera source selection (webcam / Android / iPhone)
- Recognition thresholds
- Unknown face retention
- Enrollment settings
- Logging configuration
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Dict, List

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import config.config as cfg

# ── Page config (must be first Streamlit command) ────────────
st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")

st.title("⚙️ Settings")
st.markdown("Edit configuration values below and save — changes persist to `config/settings.yaml`.")
st.caption("**Note:** Some settings (e.g. camera, logging) require a full app restart to take effect.")

# ── Load current values from the live settings dict ─────────
def _get_live(*keys: str, default):
    """Read a setting directly from the reloaded YAML dict."""
    val = cfg.get_settings()
    for key in keys:
        if isinstance(val, dict):
            val = val.get(key)
        else:
            return default
    return val if val is not None else default


# ── Form ─────────────────────────────────────────────────────
with st.form("settings_form", clear_on_submit=False):
    st.markdown("### 🎥 Camera")
    
    # Camera source type
    camera_source_options = {
        "💻 Laptop Webcam": "webcam",
        "🔌 USB Auto (Plug & Play)": "usb_auto",
        "📱 Android (USB)": "android_usb",
        "📱 Android (Wi-Fi)": "android_wifi",
        "📱 iPhone (USB)": "iphone_usb",
        "📱 iPhone (Wi-Fi)": "iphone_wifi",
        "🌐 IP Camera": "ip_camera",
    }
    current_source = _get_live("camera", "source_type", default="webcam")
    # Find the matching label
    current_source_label = "💻 Laptop Webcam"
    for label, slug in camera_source_options.items():
        if slug == current_source:
            current_source_label = label
            break
    
    selected_source_label = st.selectbox(
        "Camera Source",
        options=list(camera_source_options.keys()),
        index=list(camera_source_options.keys()).index(current_source_label),
        help="Select the camera source type for face recognition",
    )
    camera_source_type = camera_source_options[selected_source_label]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        camera_id = st.number_input(
            "Camera ID",
            value=_get_live("camera", "id", default=0),
            min_value=-1, max_value=10, step=1,
            help=cam_id_help.get(camera_source_type, "Camera device index"),
        )
    with col2:
        cam_width = st.number_input(
            "Width",
            value=_get_live("camera", "width", default=640),
            min_value=320, max_value=3840, step=10,
        )
    with col3:
        cam_height = st.number_input(
            "Height",
            value=_get_live("camera", "height", default=480),
            min_value=240, max_value=2160, step=10,
        )
    
    # Camera URL for phone camera sources
    camera_url_help = {
        "webcam": "Not used for webcam",
        "usb_auto": "Not used for USB Auto — auto-scans all device indices",
        "android_usb": "DroidCam IP:Port for Wi-Fi fallback (e.g., 192.168.1.100:4747)",
        "android_wifi": "IP Webcam video URL (e.g., http://192.168.1.100:8080/video)",
        "iphone_usb": "Not used for iPhone USB",
        "iphone_wifi": "EpocCam stream URL (e.g., http://192.168.1.101:8080/video)",
    }
    cam_id_help = {
        "webcam": "Camera device index (0 = default webcam)",
        "usb_auto": "-1 = auto-scan all; 0+ = prefer a specific device",
        "android_usb": "Camera device index for DroidCam (typically 1)",
        "android_wifi": "Not used for Android Wi-Fi",
        "iphone_usb": "Camera device index for EpocCam (typically 2)",
        "iphone_wifi": "Not used for iPhone Wi-Fi",
    }
    
    # Only show URL field for phone camera types
    if camera_source_type in ("android_wifi", "android_usb", "iphone_wifi"):
        camera_url = st.text_input(
            "Camera URL",
            value=_get_live("camera", "url", default="http://192.168.1.100:8080/video"),
            help=camera_url_help.get(camera_source_type, "URL for phone camera connection"),
        )
    else:
        camera_url = _get_live("camera", "url", default="http://192.168.1.100:8080/video")
        st.caption(f"🔗 Camera URL: {camera_url_help.get(camera_source_type, '')}")
    
    # Auto-connect toggle
    auto_connect = st.toggle(
        "Auto-connect camera at startup",
        value=_get_live("camera", "auto_connect", default=False),
        help="Automatically connect to the configured camera when the app starts",
    )

    st.divider()
    st.markdown("### 🧠 Recognition")

    col1, col2 = st.columns(2)
    with col1:
        yolo_conf = st.slider(
            "YOLO Confidence Threshold",
            min_value=0.0, max_value=1.0, step=0.05,
            value=_get_live("recognition", "yolo_confidence", default=0.5),
            help="Minimum confidence for YOLO person detection. Lower = more detections but more false positives.",
        )
        threshold = st.slider(
            "Recognition Threshold (L2 distance)",
            min_value=0.0, max_value=3.0, step=0.05,
            value=_get_live("recognition", "recognition_threshold", default=1.0),
            help="FAISS L2 distance threshold. Lower = stricter match. 1.0–1.5 is typical for same person under different conditions.",
        )
    with col2:
        frame_skip = st.number_input(
            "Frame Skip",
            min_value=0, max_value=10, step=1,
            value=_get_live("recognition", "frame_skip", default=2),
            help="Process every Nth frame. Higher = faster but may miss faces.",
        )
        cooldown = st.number_input(
            "Cooldown (seconds)",
            min_value=0, max_value=600, step=5,
            value=_get_live("recognition", "cooldown_seconds", default=60),
            help="Don't re-mark attendance within this window for the same person.",
        )

    st.divider()
    st.markdown("### 👤 Unknown Faces")
    retention = st.number_input(
        "Auto-delete unknown faces after (days)",
        min_value=0, max_value=365, step=1,
        value=_get_live("unknown_faces", "retention_days", default=30),
        help="0 = never auto-delete.",
    )

    st.divider()
    st.markdown("### 📝 Enrollment")
    col1, col2 = st.columns(2)
    with col1:
        min_face = st.number_input(
            "Min Face Size (pixels)",
            min_value=50, max_value=500, step=10,
            value=_get_live("enrollment", "min_face_size", default=100),
        )
    with col2:
        capture_count = st.number_input(
            "Capture Count",
            min_value=1, max_value=10, step=1,
            value=_get_live("enrollment", "capture_count", default=1),
        )

    st.divider()
    st.markdown("### 📋 Logging")
    col1, col2 = st.columns(2)
    with col1:
        log_level = st.selectbox(
            "Log Level",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                _get_live("logging", "level", default="INFO").upper()
            ),
        )
    with col2:
        log_max_mb = st.number_input(
            "Max Log Size (MB)",
            min_value=1, max_value=100, step=1,
            value=_get_live("logging", "max_size_mb", default=10),
        )

    # ── Submit ────────────────────────────────────────────────
    col1, col2 = st.columns([1, 4])
    with col1:
        saved = st.form_submit_button("💾 Save Settings", type="primary", use_container_width=True)

# ── Save handler ─────────────────────────────────────────────
if saved:
    updates = {
        "camera": {
            "source_type": camera_source_type,
            "id": int(camera_id),
            "url": str(camera_url),
            "width": int(cam_width),
            "height": int(cam_height),
            "auto_connect": bool(auto_connect),
        },
        "recognition": {
            "yolo_confidence": float(yolo_conf),
            "recognition_threshold": float(threshold),
            "frame_skip": int(frame_skip),
            "cooldown_seconds": int(cooldown),
        },
        "unknown_faces": {
            "retention_days": int(retention),
        },
        "enrollment": {
            "min_face_size": int(min_face),
            "capture_count": int(capture_count),
        },
        "logging": {
            "level": log_level,
            "max_size_mb": int(log_max_mb),
        },
    }

    try:
        cfg.save_settings(updates)
        st.success("✅ Settings saved to `config/settings.yaml`!")
        st.info("🔄 Restart the app for all changes to take effect.")
    except Exception as exc:
        st.error(f"❌ Failed to save settings: {exc}")

# ── Camera source guide ───────────────────────────────────────
st.divider()
with st.expander("📹 Camera Source Setup Guide"):
    st.markdown("""
    ### 🔌 USB Auto (Plug & Play)
    - **Setup:** No extra software needed!
    - **Android 14+:** Enable ``Developer Options`` → ``USB Webcam`` → connect USB cable
    - **Android (older):** Install [DroidCam](https://www.dev47apps.com/)
    - **iPhone on Windows:** Install [EpocCam](https://www.elgato.com/us/en/s/epoccam)
    - **Regular webcams:** Any USB webcam works too
    - **Device ID:** -1 = auto-scan; set to 0-10 to prefer a specific device
    
    ### 💻 Laptop Webcam
    - **Setup:** Plug & play. No additional software needed.
    - **Device ID:** 0 = built-in webcam, 1+ = external USB cameras.
    
    ### 📱 Android (USB) — DroidCam
    1. Install [DroidCam](https://www.dev47apps.com/) on your Android phone and computer
    2. Connect your phone via USB
    3. Enable **USB Debugging** on your Android (Developer Options)
    4. Open DroidCam on both devices and select **USB** mode
    
    ### 📱 Android (Wi-Fi) — IP Webcam
    1. Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) on your Android phone
    2. Connect your phone to the same Wi-Fi network as your computer
    3. Open IP Webcam and tap **Start Server**
    4. Enter the URL shown in the app (e.g., `http://192.168.1.100:8080/video`)
    
    ### 📱 iPhone (USB) — EpocCam
    1. Install [EpocCam](https://www.elgato.com/us/en/s/epoccam) on your iPhone and computer
    2. Connect your iPhone via USB
    3. Open EpocCam on your iPhone
    4. It appears as a DirectShow camera (device index 2 or 3)
    
    ### 📱 iPhone (Wi-Fi) — EpocCam
    1. Install EpocCam on your iPhone and computer
    2. Connect both to the same Wi-Fi network
    3. Open EpocCam on your iPhone
    4. Enter the stream URL shown in EpocCam
    """)

# ═══════════════════════════════════════════════════════════════
#  Camera Diagnostics — inline scanner
# ═══════════════════════════════════════════════════════════════

st.divider()
st.markdown("### 🔍 Camera Diagnostics")
st.caption("Scan for connected cameras (webcams, phone USB cameras, etc.)")

col1, col2 = st.columns([1, 3])
with col1:
    run_diag = st.button(
        "▶️ Run Diagnostics",
        type="primary",
        use_container_width=True,
    )
with col2:
    st.caption("Scans device indices 0..9. Takes 5-10 seconds.")

if run_diag:
    import cv2
    import time

    progress_bar = st.progress(0, text="Scanning cameras...")
    status_text = st.empty()

    found_cameras: List[Dict] = []
    max_idx = 10

    with st.spinner("Scanning camera ports..."):
        for idx in range(max_idx):
            progress_bar.progress(
                (idx + 1) / max_idx,
                text=f"Scanning device #{idx}..."
            )

            cam_info = None
            # Try DirectShow first, then default
            for backend in (cv2.CAP_DSHOW, None):
                try:
                    if backend is None:
                        cap = cv2.VideoCapture(idx)
                    else:
                        cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        w, h = frame.shape[:2][::-1] if ret and frame is not None else (0, 0)
                        cap.release()
                        cam_info = {
                            "index": idx,
                            "resolution": f"{w}x{h}" if w > 0 else "unknown",
                            "has_frame": ret and frame is not None,
                            "backend": "DirectShow" if backend == cv2.CAP_DSHOW else "Default",
                        }
                        break
                except Exception:
                    continue

            if cam_info:
                found_cameras.append(cam_info)
                status_text.info(f"Found: Device #{idx} ({cam_info['resolution']})")
            else:
                status_text.info(f"Device #{idx}: not found")

            time.sleep(0.1)

    progress_bar.empty()
    status_text.empty()

    if found_cameras:
        st.success(f"Found {len(found_cameras)} camera(s)")

        # Build results table
        table_data = []
        for cam in found_cameras:
            idx = cam["index"]
            label = "Built-in webcam" if idx == 0 else f"USB Camera #{idx}"
            table_data.append({
                "Device": f"#{idx}",
                "Type": label,
                "Resolution": cam["resolution"],
                "Backend": cam["backend"],
                "Frame OK": "Yes" if cam["has_frame"] else "No",
            })

        st.table(table_data)

        st.markdown("**Next steps:**")
        for cam in found_cameras:
            idx = cam["index"]
            if idx == 0:
                st.markdown(f"- Device **#{idx}** appears to be your built-in webcam. Select **Laptop Webcam** above.")
            else:
                st.markdown(f"- Device **#{idx}** is a USB camera. Select **USB Auto** or **Webcam** with device ID **{idx}**.")

        # Check for phone cameras
        if len(found_cameras) > 1:
            st.info("Multiple cameras found! Use **USB Auto (Plug and Play)** in settings to auto-detect.")
        elif len(found_cameras) == 1 and found_cameras[0]["index"] == 0:
            st.warning("Only built-in webcam found. To use your phone as a camera:")
            st.markdown("""
            1. **Android 14+:** Enable ``Developer Options`` → ``USB Webcam`` → connect USB
            2. **Android (older) / iPhone:** Install [DroidCam](https://www.dev47apps.com/) or [EpocCam](https://www.elgato.com/us/en/s/epoccam), connect via USB
            3. **Wi-Fi:** Use IP Webcam (Android) or EpocCam (iPhone) over Wi-Fi
            4. After connecting, click **Run Diagnostics** again
            """)
    else:
        st.error("No cameras found on any device index (0-9)")
        st.markdown("""
        **Troubleshooting:**
        1. Make sure no other app (Zoom, Teams) is using the camera
        2. Check Device Manager → Cameras for your device
        3. Try plugging into a different USB port
        4. For phone cameras, install DroidCam or EpocCam first
        """)

    st.divider()

# ── Footer ───────────────────────────────────────────────────
st.divider()
with st.expander("📄 Current settings.yaml contents"):
    try:
        st.code(cfg.SETTINGS_PATH.read_text(encoding="utf-8"), language="yaml")
    except Exception:
        st.info("Could not read settings file.")
