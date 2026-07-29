"""
Upload Security — File Validation for Enrollment Images
=========================================================

Validates uploaded image files for enrollment: checks that the file
is actually an image (magic bytes), enforces size limits, generates
server-side filenames, and prevents path traversal.

Usage::

    from utils.upload_security import validate_image_upload

    try:
        filename, file_bytes = validate_image_upload(
            uploaded_file=uploaded_file,
            max_size_mb=5,
            allowed_formats={".jpg", ".jpeg", ".png"},
        )
        # Save to disk or process
    except UploadSecurityError as e:
        # Return 400 to user
        raise HTTPException(status_code=400, detail=str(e))
"""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path
from typing import Optional, Set, Tuple

# ── Constants ────────────────────────────────────────────────────────

# Magic bytes -> extension mapping (first few bytes of the file)
_MAGIC_BYTES: dict[bytes, str] = {
    b"\xff\xd8\xff": ".jpg",   # JPEG
    b"\x89PNG\r\n\x1a\n": ".png",   # PNG
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",  # WebP starts with RIFF
}

# Allowed MIME types (from libmagic)
_ALLOWED_MIME_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

# Max dimensions
_MAX_WIDTH = 4096
_MAX_HEIGHT = 4096
_MAX_MEGA_PIXELS = 8.0  # 8 MP


class UploadSecurityError(ValueError):
    """Raised when an uploaded file fails a validation check."""
    pass


def validate_image_upload(
    file_data: bytes,
    filename: str = "upload",
    max_size_mb: float = 5.0,
    allowed_formats: Optional[Set[str]] = None,
) -> Tuple[str, bytes]:
    """Validate an uploaded image file.

    Checks performed:
        1. File size within limit.
        2. Magic bytes identify it as a known image format.
        3. Optionally decode with Pillow to verify it's a valid image.
        4. Dimensions within limits.
        5. Server-side filename generation (no path traversal).

    Args:
        file_data: Raw bytes of the uploaded file.
        filename: Original filename (used only for extension detection).
        max_size_mb: Maximum file size in MB.
        allowed_formats: Set of allowed extensions (e.g. ``{".jpg", ".png"}``).
                         If ``None``, all detected image types are allowed.

    Returns:
        ``(safe_filename, file_bytes)`` tuple ready for storage.

    Raises:
        UploadSecurityError: If any validation check fails.
    """
    if allowed_formats is None:
        allowed_formats = {".jpg", ".jpeg", ".png"}

    # 1. Size check
    max_size_bytes = int(max_size_mb * 1024 * 1024)
    if len(file_data) > max_size_bytes:
        raise UploadSecurityError(
            f"File too large: {len(file_data) / 1024 / 1024:.1f} MB "
            f"(max {max_size_mb:.1f} MB)"
        )
    if len(file_data) == 0:
        raise UploadSecurityError("Uploaded file is empty")

    # 2. Magic bytes detection (content-based, not extension-based)
    detected_ext = _detect_format(file_data)
    if detected_ext is None:
        raise UploadSecurityError(
            "File type could not be detected. Only JPEG, PNG, and WebP images are accepted."
        )

    # 3. Check allowed formats
    ext_lower = detected_ext.lower()
    if ext_lower not in {f.lower() for f in allowed_formats}:
        raise UploadSecurityError(
            f"File format '{detected_ext}' is not allowed. "
            f"Allowed: {', '.join(sorted(allowed_formats))}"
        )

    # 4. Verify with Pillow (catches truncated/corrupt images)
    _verify_pillow(file_data)

    # 5. Check image dimensions
    _check_dimensions(file_data)

    # 6. Generate server-side filename
    safe_filename = _generate_safe_filename(ext_lower)

    return safe_filename, file_data


def _detect_format(file_data: bytes) -> Optional[str]:
    """Detect image format from magic bytes.

    Uses a direct magic-byte lookup (no libmagic dependency). The
    ``python-magic`` package was removed because it causes segfaults
    on Windows due to ``libmagic`` C-library conflicts. The magic-bytes
    dictionary combined with Pillow's ``Image.verify()`` provides
    sufficient validation for enrollment image uploads.
    """
    for magic_bytes, ext in _MAGIC_BYTES.items():
        if file_data[:len(magic_bytes)] == magic_bytes:
            return ext

    return None


def _verify_pillow(file_data: bytes) -> None:
    """Verify the file is a valid image using Pillow."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(file_data))
        img.verify()  # Verify it's a valid image
    except Exception as exc:
        raise UploadSecurityError(f"Invalid or corrupt image file: {exc}")


def _check_dimensions(file_data: bytes) -> None:
    """Check image dimensions are within limits."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(file_data))
        w, h = img.size

        if w > _MAX_WIDTH or h > _MAX_HEIGHT:
            raise UploadSecurityError(
                f"Image dimensions {w}x{h} exceed maximum {_MAX_WIDTH}x{_MAX_HEIGHT}"
            )

        megapixels = (w * h) / 1_000_000
        if megapixels > _MAX_MEGA_PIXELS:
            raise UploadSecurityError(
                f"Image too large: {megapixels:.1f} MP (max {_MAX_MEGA_PIXELS:.0f} MP)"
            )
    except UploadSecurityError:
        raise
    except Exception as exc:
        raise UploadSecurityError(f"Could not read image dimensions: {exc}")


def _generate_safe_filename(ext: str) -> str:
    """Generate a server-side filename that cannot be a path traversal.

    Format: ``enroll_{uuid}_{timestamp}{ext}``

    This prevents:
        - Path traversal (``../../etc/passwd``)
        - Special characters
        - Filename collisions
    """
    import time
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:12]
    return f"enroll_{timestamp}_{unique_id}{ext}"


def sanitize_filename(filename: str) -> str:
    """Remove path traversal and dangerous characters from a filename.

    Used for display/storage keys, NOT for actual file writes
    (use ``_generate_safe_filename`` for that).
    """
    # Remove any path components
    clean = Path(filename).name
    # Remove null bytes
    clean = clean.replace("\x00", "")
    # Limit length
    return clean[:255]
