"""
Employee Enrollment — Multi-Camera Face Capture + AI Enroll
=============================================================

Captures a face from any camera source (webcam, Android, iPhone, IP camera),
extracts an ArcFace embedding, adds it to FAISS, and creates the employee record.

Workflow::

    Camera → Capture Frame → RetinaFace → ArcFace Embedding
        → FAISS Add → SQLite Employee Record → Done

Supports:
- 💻 Laptop Webcam (browser via st.camera_input)
- 📱 Android (USB / Wi-Fi)
- 📱 iPhone (USB / Wi-Fi)
- 🌐 IP Camera (RTSP / HTTP)
- 🔌 USB Auto (Plug & Play)
"""

from __future__ import annotations

from pathlib import Path
import sys
import io
import time

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st
import cv2
import numpy as np
from PIL import Image

from services.employee_service import EmployeeService
from app.enrollment import FaceEnrollment
from app.recognizer import FaceRecognizer
from camera.base import CameraSource
from camera.selector import create_camera, CAMERA_CHOICES, CAMERA_REGISTRY


def _process_enrollment(frame: np.ndarray, emp_id: str, name: str, dept: str | None) -> None:
    """Run the full enrollment pipeline on a captured frame.

    Steps:
        1. Detect face via RetinaFace (inside extract_embedding)
        2. Generate ArcFace 512-D embedding
        3. Add embedding to FAISS index
        4. Create employee record in SQLite
    """
    # Step 1 — Load models (lazy, first call is slow)
    try:
        recognizer = FaceRecognizer()
    except Exception as exc:
        st.error(f"Failed to load face recognition model: {exc}")
        return

    # Step 2 — Detect face and extract embedding
    embedding = recognizer.extract_embedding(frame)
    if embedding is None:
        st.error("No face detected in the captured image. Please try again with better lighting and face clearly visible.")
        return

    emb_norm = np.linalg.norm(embedding)
    st.info(f"Face detected. Embedding norm: {emb_norm:.2f} (should be ~1.0)")

    # Step 3 — Check if already enrolled in FAISS
    enrollment = FaceEnrollment()
    matches = enrollment.search(embedding, k=1, threshold=1.0)
    if matches:
        st.warning(f"This face is already enrolled as: **{matches[0]['name']}** (confidence: {matches[0]['confidence']:.1%})")
        return

    # Step 4 — Add to FAISS index
    try:
        enrollment.enroll(name, embedding)
        faiss_id = enrollment.count() - 1
    except Exception as exc:
        st.error(f"Failed to add to FAISS: {exc}")
        return

    # Step 5 — Create employee record in SQLite
    try:
        EmployeeService.create(
            employee_id=emp_id,
            name=name,
            department=dept,
            photo_path=None,
            faiss_id=faiss_id,
            operator="dashboard",
        )
    except ValueError as exc:
        # Rollback FAISS
        st.error(str(exc))
        st.warning("Rolling back FAISS...")
        enrollment.clear()
        # Re-add all other employees (simple approach: clear and re-add)
        # For now, just log the issue
        return
    except Exception as exc:
        st.error(f"Failed to create employee record: {exc}")
        return

    # Success
    st.session_state["enrolled_ok"] = True
    st.rerun()


st.set_page_config(page_title="Enroll", page_icon="📸", layout="wide")

# ── Session state initialization ─────────────────────────────
if "enroll_step" not in st.session_state:
    st.session_state["enroll_step"] = "form"  # form | preview | done
if "enrolled_ok" not in st.session_state:
    st.session_state["enrolled_ok"] = False
if "enroll_confirmed" not in st.session_state:
    st.session_state["enroll_confirmed"] = False

# ── Page Header ──────────────────────────────────────────────
st.title("📸 Enroll New Employee")
st.markdown("Capture a face via webcam and enroll them into the recognition system.")

# ── Camera Source Selector ───────────────────────────────────
camera_source_options = {}
for slug, label, desc in CAMERA_CHOICES:
    camera_source_options[label] = slug

# Default camera source from config
current_source = "💻 Laptop Webcam"
for label, slug in camera_source_options.items():
    if slug == "webcam":
        current_source = label
        break

st.markdown("### 📷 Camera Source")
selected_source_label = st.selectbox(
    "Select capture source",
    options=list(camera_source_options.keys()),
    index=list(camera_source_options.keys()).index(current_source),
    key="enroll_cam_source",
    help="Choose the camera to capture the face from",
)
camera_source_type = camera_source_options[selected_source_label]

# Extra URL/device fields for phone/IP cameras
enroll_cam_url = ""
enroll_cam_id = 0
if camera_source_type in ("android_wifi", "iphone_wifi", "ip_camera"):
    default_urls = {
        "android_wifi": "http://192.168.1.100:8080/video",
        "iphone_wifi": "http://192.168.1.101:8080/video",
        "ip_camera": "http://192.168.1.200:8080/video",
    }
    enroll_cam_url = st.text_input(
        "Camera URL",
        value=default_urls.get(camera_source_type, ""),
        help="Stream URL from the camera app",
    )
elif camera_source_type in ("android_usb", "iphone_usb"):
    default_ids = {"android_usb": 1, "iphone_usb": 2}
    enroll_cam_id = st.number_input(
        "Device Index",
        min_value=0, max_value=10,
        value=default_ids.get(camera_source_type, 0),
        step=1,
        help="Camera device index",
    )
elif camera_source_type == "usb_auto":
    enroll_cam_id = st.number_input(
        "Preferred Device Index (-1 = auto)",
        min_value=-1, max_value=10, value=-1, step=1,
        help="-1 = auto-scan all devices; 0+ = prefer a specific device",
    )

st.divider()

# ── Side-by-side layout ──────────────────────────────────────
form_col, preview_col = st.columns([1, 1])

with form_col:
    st.markdown("### Employee Details")

    with st.form("enroll_form", clear_on_submit=False):
        emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP004",
                               help="Unique identifier, e.g. EMP004")
        name = st.text_input("Full Name *", placeholder="e.g. John Doe")
        dept = st.text_input("Department", placeholder="e.g. Engineering")
        submitted = st.form_submit_button("📸 Start Capture", type="primary", use_container_width=True)

    if submitted:
        if not emp_id or not name:
            st.error("Employee ID and Name are required.")
        else:
            st.session_state["enroll_emp_id"] = emp_id.strip()
            st.session_state["enroll_name"] = name.strip()
            st.session_state["enroll_dept"] = dept.strip() or None
            st.session_state["enroll_cam_source_type"] = camera_source_type
            st.session_state["enroll_cam_url"] = enroll_cam_url
            st.session_state["enroll_cam_id"] = enroll_cam_id
            st.session_state["enroll_step"] = "capture"
            st.session_state["enrolled_ok"] = False
            st.rerun()

# ── Capture & Process ────────────────────────────────────────
with preview_col:
    if st.session_state.get("enroll_step") in ("capture", "done"):
        emp_id = st.session_state["enroll_emp_id"]
        name = st.session_state["enroll_name"]
        dept = st.session_state.get("enroll_dept")
        cam_type = st.session_state.get("enroll_cam_source_type", "webcam")
        cam_url = st.session_state.get("enroll_cam_url", "")
        cam_id = st.session_state.get("enroll_cam_id", 0)

        st.markdown(f"### Capturing for: **{name}** ({emp_id})")

        # ── Initialize frame storage in session state ─────────
        if "enroll_captured_frame" not in st.session_state:
            st.session_state["enroll_captured_frame"] = None

        # ── Choose capture method based on camera type ─────────
        captured_frame = st.session_state["enroll_captured_frame"]

        if cam_type == "webcam":
            # Browser webcam via Streamlit's built-in camera input
            # The camera_input action itself IS the user's intent → auto-confirm
            img_file = st.camera_input("Take a photo", key="webcam_capture")

            if img_file is not None and not st.session_state["enrolled_ok"]:
                bytes_data = img_file.getvalue()
                np_arr = np.frombuffer(bytes_data, np.uint8)
                captured_frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                st.session_state["enroll_captured_frame"] = captured_frame
                st.session_state["enroll_confirmed"] = True  # Auto-confirm for webcam
                if captured_frame is None:
                    st.error("Could not read captured image.")
        else:
            # Phone / IP camera via CameraSource abstraction
            # Only capture fresh frame if we don't already have one stored
            if st.session_state["enroll_captured_frame"] is None:
                st.info(f"📷 Connecting to {selected_source_label}...")

                kwargs = {}
                if cam_type in ("android_wifi", "iphone_wifi", "ip_camera"):
                    kwargs["url"] = cam_url
                elif cam_type in ("android_usb", "iphone_usb"):
                    kwargs["device_id"] = cam_id
                elif cam_type == "usb_auto":
                    kwargs["device_id"] = cam_id

                cam = create_camera(cam_type, **kwargs)
                if cam is not None and cam.open():
                    cam.set_resolution(640, 480)
                    # Read a few frames to let auto-exposure settle
                    for _ in range(10):
                        ret, frame = cam.read()
                        if ret and frame is not None:
                            captured_frame = frame
                    cam.release()

                    if captured_frame is not None:
                        st.session_state["enroll_captured_frame"] = captured_frame
                        st.rerun()  # Rerun to show preview + confirm button
                    else:
                        st.error("❌ Could not capture frame from camera. Check connection.")
                else:
                    st.error(f"❌ Could not connect to {selected_source_label}. Check the URL/device.")

            if st.session_state["enroll_captured_frame"] is not None:
                captured_frame = st.session_state["enroll_captured_frame"]
                # Show preview of stored frame
                st.image(cv2.cvtColor(captured_frame, cv2.COLOR_BGR2RGB),
                         channels="RGB", caption="Captured frame from phone/IP camera",
                         use_container_width=True)

                st.caption("📸 Frame captured. Click the button below to process enrollment.")

                col_confirm, col_recapture = st.columns(2)
                with col_confirm:
                    if st.button("✅ Confirm & Enroll", type="primary", use_container_width=True):
                        st.session_state["enroll_confirmed"] = True
                        st.rerun()
                with col_recapture:
                    if st.button("🔄 Recapture", use_container_width=True):
                        st.session_state["enroll_captured_frame"] = None
                        st.session_state["enroll_confirmed"] = False
                        st.rerun()
            else:
                st.caption("🔄 Taking snapshot from connected camera...")

        # ── Process enrollment only when user confirms ────────
        confirmed = st.session_state.get("enroll_confirmed", False)
        if captured_frame is not None and confirmed and not st.session_state["enrolled_ok"]:
            with st.spinner("Processing face and generating embedding..."):
                _process_enrollment(captured_frame, emp_id, name, dept)

        # Show success state after enrollment
        if st.session_state["enrolled_ok"]:
            st.success(f"✅ **{name}** ({emp_id}) enrolled successfully!")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Enroll Another", use_container_width=True):
                    st.session_state["enroll_step"] = "form"
                    st.session_state["enrolled_ok"] = False
                    st.rerun()
            with col2:
                if st.button("👥 View Employees", use_container_width=True):
                    st.switch_page("pages/02_Employees.py")
