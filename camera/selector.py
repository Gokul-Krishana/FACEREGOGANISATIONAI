"""
Camera Selector — Camera Source Factory & CLI Prompt
=====================================================

Provides:

1. A **factory function** ``create_camera()`` that returns the correct
   ``CameraSource`` implementation based on a config string.

2. A **CLI prompt** ``select_camera_cli()`` that presents a numbered
   menu to the user at startup.

3. A **Streamlit UI helper** ``select_camera_ui()`` that renders a
   camera source selector in the dashboard.

4. A **probe function** ``get_available_cameras()`` that returns a list
   of all camera sources that can be offered to the user.

Mapping (matching the architecture diagram)::

    1. Laptop Webcam     →  ``webcam``
    2. Android (USB)     →  ``android_usb``
    3. Android (Wi-Fi)   →  ``android_wifi``
    4. iPhone (USB)      →  ``iphone_usb``
    5. iPhone (Wi-Fi)    →  ``iphone_wifi``
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import cv2

from camera.base import CameraSource
from camera.webcam import WebcamSource, USBAnySource
from utils.logging_setup import get_logger
from camera.phone import (
    AndroidUSBSource,
    AndroidWiFiSource,
    iPhoneUSBSource,
    iPhoneWiFiSource,
    IPCameraSource,
)

logger = get_logger(__name__)

# ── Registry ───────────────────────────────────────────────────
# Maps source type slugs to their class and a human label.
CAMERA_REGISTRY: Dict[str, Tuple[str, type]] = {
    "webcam": ("💻 Laptop Webcam", WebcamSource),
    "usb_auto": ("🔌 USB Auto", USBAnySource),
    "android_usb": ("📱 Android (USB)", AndroidUSBSource),
    "android_wifi": ("📱 Android (Wi-Fi)", AndroidWiFiSource),
    "iphone_usb": ("📱 iPhone (USB)", iPhoneUSBSource),
    "iphone_wifi": ("📱 iPhone (Wi-Fi)", iPhoneWiFiSource),
    "ip_camera": ("🌐 IP Camera", IPCameraSource),
}

# Ordered list for CLI / UI display
CAMERA_CHOICES: List[Tuple[str, str, str]] = [
    ("webcam", "💻 Laptop Webcam", "Built-in or USB webcam (default)"),
    (
        "usb_auto",
        "🔌 USB Auto (Plug & Play)",
        "Auto-detect any USB camera (Android UVC, webcam, DroidCam, EpocCam)",
    ),
    ("android_usb", "📱 Android (USB)", "DroidCam USB connection"),
    ("android_wifi", "📱 Android (Wi-Fi)", "IP Webcam app over Wi-Fi"),
    ("iphone_usb", "📱 iPhone (USB)", "EpocCam/DroidCam OBS USB connection"),
    ("iphone_wifi", "📱 iPhone (Wi-Fi)", "EpocCam Wi-Fi streaming"),
    ("ip_camera", "🌐 IP Camera", "Generic RTSP/HTTP network camera (Hikvision, Dahua, etc.)"),
]


# ── Factory ────────────────────────────────────────────────────


def create_camera(source_type: str, **kwargs) -> Optional[CameraSource]:
    """Create a camera source by type.

    Args:
        source_type: One of ``"webcam"``, ``"android_usb"``,
                     ``"android_wifi"``, ``"iphone_usb"``, ``"iphone_wifi"``.
        **kwargs: Arguments passed to the camera constructor.
                  Common: ``device_id``, ``url``, ``rtsp_url``.

    Returns:
        A ``CameraSource`` instance, or ``None`` if the type is unknown.
    """
    entry = CAMERA_REGISTRY.get(source_type)
    if entry is None:
        logger.warning("Unknown camera source type: %s", source_type)
        return None

    label, cls = entry

    # Map common kwargs names to constructor parameter names
    if source_type == "webcam":
        device_id = kwargs.get("device_id", kwargs.get("camera_id", 0))
        return cls(device_id=device_id)
    elif source_type == "usb_auto":
        prefer_index = kwargs.get("device_id", -1)
        return cls(prefer_index=prefer_index)
    elif source_type == "android_usb":
        return cls(
            droidcam_ip=kwargs.get("url", "192.168.1.100:4747"),
            device_id=kwargs.get("device_id", 1),
        )
    elif source_type == "android_wifi":
        return cls(url=kwargs.get("url", "http://192.168.1.100:8080/video"))
    elif source_type == "iphone_usb":
        return cls(device_id=kwargs.get("device_id", 2))
    elif source_type == "iphone_wifi":
        return cls(rtsp_url=kwargs.get("url", "http://192.168.1.101:8080/video"))
    elif source_type == "ip_camera":
        return cls(url=kwargs.get("url", "http://192.168.1.200:8080/video"))

    return cls(**kwargs)


# ── CLI Selector ───────────────────────────────────────────────


def select_camera_cli() -> CameraSource:
    """Interactive CLI camera selector.

    Presents a numbered menu of available camera options and returns the
    chosen ``CameraSource`` (already opened).

    Usage::

        cam = select_camera_cli()
        while True:
            ret, frame = cam.read()
            ...
    """
    print("\n" + "=" * 60)
    print("  Face Recognition AI — Camera Selection")
    print("=" * 60)
    print()

    # Build menu
    for i, (slug, label, desc) in enumerate(CAMERA_CHOICES, 1):
        print(f"  [{i}] {label}")
        print(f"      {desc}")

    print(f"  [{len(CAMERA_CHOICES) + 1}] Cancel")
    print()

    while True:
        try:
            choice = int(input("  Select camera source [1-6]: ").strip())
            if 1 <= choice <= len(CAMERA_CHOICES):
                slug, label, _ = CAMERA_CHOICES[choice - 1]
                cam = create_camera(slug)
                if cam is None:
                    print(f"  [FAIL] Could not create {label}")
                    continue

                # Ask for extra params if needed
                if slug == "android_wifi":
                    url = input("  IP Webcam URL [http://192.168.1.100:8080/video]: ").strip()
                    if url:
                        cam = create_camera("android_wifi", url=url)
                    if cam is None:
                        print("  [FAIL] Could not create Android Wi-Fi source")
                        continue

                if not cam.open():
                    print(f"  [FAIL] Could not connect to {label}")
                    print("  Check that the device is connected and try again.")
                    continue

                print(f"\n  ✅ Connected to {label}")
                print(f"     Resolution: {cam.get_resolution()}")
                return cam

            elif choice == len(CAMERA_CHOICES) + 1:
                print("  Cancelled.")
                raise SystemExit(0)
            else:
                print("  Invalid choice. Try again.")
        except ValueError:
            print("  Enter a number.")
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(0)


# ── Streamlit UI ───────────────────────────────────────────────


def select_camera_ui(st) -> Optional[CameraSource]:
    """Render a camera source selector in Streamlit.

    Args:
        st: The ``streamlit`` module (passed in to keep dependencies clean).

    Returns:
        A ``CameraSource`` if connected, ``None`` otherwise.

    Usage in a dashboard page::

        from camera.selector import select_camera_ui

        cam = select_camera_ui(st)
        if cam is not None:
            ret, frame = cam.read()
    """
    import streamlit as st

    st.markdown("### 📷 Camera Source")

    # Build a dict for the selectbox
    options = {f"{label}": slug for slug, label, _ in CAMERA_CHOICES}
    labels = list(options.keys())

    selected_label = st.selectbox(
        "Select camera type",
        options=labels,
        index=0,
        help="Choose the camera source for face recognition",
    )

    selected_slug = options[selected_label]

    # Extra configuration fields for specific cameras
    extra_kwargs: Dict = {}
    if selected_slug == "android_wifi":
        url = st.text_input(
            "IP Webcam URL",
            value="http://192.168.1.100:8080/video",
            help="Start IP Webcam on Android and enter the URL shown in the app",
        )
        extra_kwargs["url"] = url
    elif selected_slug == "android_usb":
        droidcam_ip = st.text_input(
            "DroidCam IP (Wi-Fi fallback)",
            value="192.168.1.100:4747",
            help="IP shown in DroidCam app when in Wi-Fi mode",
        )
        extra_kwargs["url"] = droidcam_ip
    elif selected_slug == "iphone_wifi":
        rtsp_url = st.text_input(
            "EpocCam RTSP URL",
            value="http://192.168.1.101:8080/video",
            help="IP/port shown in EpocCam app",
        )
        extra_kwargs["url"] = rtsp_url

    # Device index for direct camera sources
    if selected_slug in ("webcam", "android_usb", "iphone_usb"):
        device_id = st.number_input(
            "Device index",
            min_value=0,
            max_value=10,
            value={"webcam": 0, "android_usb": 1, "iphone_usb": 2}.get(selected_slug, 0),
            step=1,
            help="Camera device index (0 = default webcam, 1+ = USB cameras)",
        )
        extra_kwargs["device_id"] = int(device_id)

    if st.button("🔌 Connect Camera", type="primary", use_container_width=True):
        cam = create_camera(selected_slug, **extra_kwargs)
        if cam is None:
            st.error(f"❌ Could not create {selected_label}")
            return None

        with st.spinner(f"Connecting to {selected_label}..."):
            success = cam.open()

        if success:
            info = cam.info()
            st.success(f"✅ Connected to {selected_label}")
            st.info(f"Resolution: {info.get('resolution', 'N/A')}")
            return cam
        else:
            st.error(f"❌ Could not connect to {selected_label}")
            st.info(
                "Troubleshooting:\n"
                "1. Make sure the device is powered on\n"
                "2. Check Wi-Fi/USB connection\n"
                "3. Verify the IP address is correct\n"
                "4. Start the camera app first (IP Webcam / DroidCam / EpocCam)"
            )
            return None

    return None


# ── Probe ──────────────────────────────────────────────────────


def get_available_cameras() -> List[Dict]:
    """Probe the system and return a list of detectable camera sources.

    Returns:
        List of dicts with ``slug``, ``label``, ``available`` keys.
    """
    results: List[Dict] = []

    # Check OpenCV webcams
    available_indices = []
    for idx in range(5):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            available_indices.append(idx)
            cap.release()

    results.append(
        {
            "slug": "webcam",
            "label": "Laptop Webcam",
            "available": len(available_indices) > 0,
            "detail": f"Found {len(available_indices)} device(s): {available_indices}"
            if available_indices
            else "No webcam detected",
        }
    )

    # Other sources are assumed "maybe available" — they depend on external apps
    for slug, label, _ in CAMERA_CHOICES[1:]:
        results.append(
            {
                "slug": slug,
                "label": label.split(" ", 1)[1],  # Remove emoji
                "available": "unknown",  # Can't probe DroidCam / EpocCam without the app running
                "detail": "Connect and start the app on your phone to use this source",
            }
        )

    return results
