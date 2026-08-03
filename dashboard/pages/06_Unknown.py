"""
Unknown Face Management — Gallery, Review, Convert to Employee
================================================================

Layout::

    ┌─────────────────────────────────────────────────────────────┐
    │  🔴 Unknown Face Gallery                                    │
    │  ┌──────┐ ┌──────┐ ┌──────┐                                │
    │  │ 001  │ │ 002  │ │ 003  │  ← thumbnail grid              │
    │  └──────┘ └──────┘ └──────┘                                │
    │                                                             │
    │  ┌──────────────────────────────────────────────────────┐   │
    │  │ 📷 unknown_001.jpg                                   │   │
    │  │ Time: 13 Jul 2026, 10:15 AM                          │   │
    │  │ Camera: Main Gate | Confidence: 41%                  │   │
    │  │                                                      │   │
    │  │ [Register Employee]  [Ignore]  [Delete]  📝 Notes   │   │
    │  └──────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from pathlib import Path
import sys

_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st  # noqa: E402

from services.unknown_face_service import UnknownFaceService  # noqa: E402
from database.database import get_session  # noqa: E402
from database.repository import CameraRepo  # noqa: E402

st.set_page_config(page_title="Unknown Faces", page_icon="🔴", layout="wide")

# ── Page Header ──────────────────────────────────────────────
st.title("🔴 Unknown Face Gallery")
st.markdown("Review unrecognised faces, register them as employees, or dismiss them.")

# ── Statistics Cards ─────────────────────────────────────────
try:
    stats = UnknownFaceService.get_statistics()
except Exception as _exc:
    st.error(f"⚠️ Could not load unknown-face statistics: {_exc}")
    stats = {"today": 0, "this_week": 0, "pending_review": 0, "converted": 0, "total": 0}

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Unknown Faces Today", stats["today"])
with col2:
    st.metric("This Week", stats["this_week"])
with col3:
    st.metric("Pending Review", stats["pending_review"])
with col4:
    st.metric("Converted to Employee", stats["converted"])

# ── Bulk Actions ─────────────────────────────────────────────
with st.expander("🗑️ Bulk Actions", expanded=False):
    bulk_col1, bulk_col2 = st.columns([1, 3])
    with bulk_col1:
        total_count = stats["total"]
        if total_count > 0:
            if st.button(f"🗑️ Delete All ({total_count})", type="primary", use_container_width=True):
                with st.spinner(f"Deleting all {total_count} unknown faces..."):
                    deleted_count = UnknownFaceService.delete_all()
                st.success(f"✅ Successfully deleted all {deleted_count} unknown face records and images!")
                st.rerun()
        else:
            st.button("🗑️ Delete All (0)", disabled=True, use_container_width=True)
    with bulk_col2:
        st.caption(
            "⚠️ This will permanently delete **ALL** unknown face records "
            "and their associated images from disk. This action cannot be undone."
        )

st.markdown("---")

# ── Filters ──────────────────────────────────────────────────
with st.expander("🔍 Search & Filter", expanded=True):
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        filter_start = st.date_input("From", value=None)
    with fcol2:
        filter_end = st.date_input("To", value=None)
    with fcol3:
        filter_reviewed = st.selectbox("Status", ["All", "Not Reviewed", "Reviewed", "Converted"])
    with fcol4:
        filter_limit = st.number_input("Max Results", min_value=10, max_value=500, value=50, step=10)

# Build filter params
reviewed_filter = None
if filter_reviewed == "Not Reviewed":
    reviewed_filter = False
elif filter_reviewed == "Reviewed":
    reviewed_filter = True
elif filter_reviewed == "Converted":
    reviewed_filter = True  # We'll handle this separately below

# ── Fetch Data ───────────────────────────────────────────────
try:
    if filter_reviewed == "Converted":
        # For converted, we get all and filter client-side
        faces = UnknownFaceService.get_filtered(
            start_date=filter_start or None,
            end_date=filter_end or None,
            limit=filter_limit,
        )
        faces = [f for f in faces if f.converted_to_employee]
    else:
        faces = UnknownFaceService.get_filtered(
            start_date=filter_start or None,
            end_date=filter_end or None,
            reviewed=reviewed_filter,
            limit=filter_limit,
        )
except Exception as _exc:
    st.error(f"⚠️ Could not load unknown faces: {_exc}")
    faces = []

# ── Helper Functions (defined before use for Streamlit rerun safety) ──


@st.cache_data(ttl=60)
def _get_camera_name(camera_id):
    """Look up camera name from ID."""
    if camera_id is None:
        return "Default"
    with get_session() as s:
        cam = CameraRepo.get_by_id(s, camera_id)
        if cam:
            return f"{cam.name} ({cam.location or 'No location'})"
    return f"Camera #{camera_id}"


def _render_face_card(face):
    """Render a single unknown face card with image preview and actions."""
    image_path = Path(face.image_path) if face.image_path else None
    image_exists = image_path and image_path.exists()

    # Status badge
    if face.converted_to_employee:
        status = "Converted"
        border = "2px solid #00cc00"
    elif face.reviewed:
        status = "Ignored"
        border = "2px solid #ffaa00"
    else:
        status = "Unreviewed"
        border = "2px solid #ff4444"

    st.markdown(
        f"""
        <div style="border: {border}; border-radius: 8px; padding: 10px; margin-bottom: 10px; background: #1a1a1a;">
        """,
        unsafe_allow_html=True,
    )

    # Image preview
    if image_exists:
        st.image(str(image_path), use_container_width=True)
    else:
        st.markdown("*Image file not found*")
        st.caption(f"Path: {face.image_path}")

    # Info
    st.caption(f"**{status}**")
    st.caption(f"{face.timestamp.strftime('%d %b %Y, %I:%M %p')}")
    cam_name = _get_camera_name(face.camera_id)
    st.caption(f"{cam_name}")

    if face.confidence is not None:
        conf_pct = face.confidence * 100 if face.confidence < 1 else face.confidence
        st.caption(f"Confidence: {conf_pct:.1f}%")

    if face.notes:
        st.caption(f"Notes: {face.notes[:100]}")

    # Action buttons
    col_a, col_b, col_c = st.columns(3)

    if not face.converted_to_employee:
        with col_a:
            if st.button("Register", key=f"reg_{face.id}", use_container_width=True):
                st.session_state["register_face_id"] = face.id
                st.session_state["register_image_path"] = str(image_path) if image_exists else ""
                st.rerun()

        with col_b:
            if not face.reviewed:
                if st.button("Ignore", key=f"ign_{face.id}", use_container_width=True):
                    UnknownFaceService.mark_reviewed(face.id)
                    st.rerun()

        with col_c:
            if st.button("Delete", key=f"del_{face.id}", use_container_width=True):
                UnknownFaceService.delete(face.id)
                st.rerun()
    else:
        with col_a:
            st.caption("Converted")

    st.markdown("</div>", unsafe_allow_html=True)


# ── Face Gallery Grid ───────────────────────────────────────
if not faces:
    st.info("No unknown faces match your filters.")
else:
    st.markdown(f"**{len(faces)}** face(s) found")

    # Show faces in a grid of cards
    for i in range(0, len(faces), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(faces):
                break
            face = faces[idx]
            with col:
                _render_face_card(face)


# ── Convert to Employee Modal ────────────────────────────────
if "register_face_id" in st.session_state and st.session_state["register_face_id"]:
    st.markdown("---")
    st.markdown("### 📝 Register Unknown Face as Employee")

    face_id = st.session_state["register_face_id"]
    image_path = st.session_state.get("register_image_path", "")

    if image_path and Path(image_path).exists():
        st.image(image_path, width=200)
    else:
        st.warning("Original image not available — enrollment will use webcam.")

    with st.form("register_form"):
        emp_name = st.text_input("Name *", placeholder="e.g. John Doe")
        emp_id = st.text_input("Employee ID *", placeholder="e.g. EMP004")
        emp_dept = st.text_input("Department", placeholder="e.g. Engineering")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            submitted = st.form_submit_button(
                "✅ Register Employee", type="primary", use_container_width=True
            )
        with col_s2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

        if submitted:
            if not emp_name or not emp_id:
                st.error("Name and Employee ID are required.")
            else:
                with st.spinner("Generating embedding and enrolling..."):
                    success = UnknownFaceService.convert_to_employee(
                        face_id=face_id,
                        employee_id=emp_id.strip(),
                        name=emp_name.strip(),
                        department=emp_dept.strip() or None,
                    )
                if success:
                    st.success(
                        f"✅ {emp_name} ({emp_id}) has been enrolled and will be recognized automatically!"
                    )
                    # Clear session state
                    del st.session_state["register_face_id"]
                    del st.session_state["register_image_path"]
                    st.rerun()
                else:
                    st.error("Failed to convert. Check the image has a clear face and try again.")

        if cancelled:
            del st.session_state["register_face_id"]
            del st.session_state["register_image_path"]
            st.rerun()
