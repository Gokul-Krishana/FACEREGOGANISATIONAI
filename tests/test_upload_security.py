"""
Tests for utils/upload_security — file validation for enrollment images.

Validates the Windows-safe magic-byte replacement for python-magic.
"""

from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest
from PIL import Image

from utils.upload_security import (
    UploadSecurityError,
    sanitize_filename,
    validate_image_upload,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_png_bytes(width: int = 32, height: int = 32) -> bytes:
    """Generate a minimal valid PNG in memory."""
    buf = io.BytesIO()
    # RGBA gives more reliable round-trip than '1' mode
    img = Image.new("RGBA", (width, height), (128, 200, 50, 255))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(width: int = 32, height: int = 32) -> bytes:
    """Generate a minimal valid JPEG in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), (128, 200, 50))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_webp_bytes(width: int = 32, height: int = 32) -> bytes:
    """Generate a minimal valid WebP in memory."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), (128, 200, 50))
    img.save(buf, format="WebP")
    return buf.getvalue()


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def valid_jpeg_bytes() -> bytes:
    return _make_jpeg_bytes()


@pytest.fixture()
def valid_png_bytes() -> bytes:
    return _make_png_bytes()


@pytest.fixture()
def valid_webp_bytes() -> bytes:
    return _make_webp_bytes()


# ── Tests ────────────────────────────────────────────────────────────


class TestValidateImageUpload:

    # ── Happy paths ────────────────────────────────────────────

    def test_valid_jpeg_passes(self, valid_jpeg_bytes):
        """Valid JPEG should pass validation and return a safe filename."""
        safe_name, data = validate_image_upload(
            valid_jpeg_bytes, filename="photo.jpg",
        )
        assert safe_name.endswith(".jpg")
        assert data == valid_jpeg_bytes

    def test_valid_png_passes(self, valid_png_bytes):
        """Valid PNG should pass validation."""
        safe_name, data = validate_image_upload(
            valid_png_bytes, filename="photo.png",
        )
        assert safe_name.endswith(".png")

    def test_valid_webp_passes(self, valid_webp_bytes):
        """Valid WebP should pass validation when format is allowed."""
        safe_name, data = validate_image_upload(
            valid_webp_bytes,
            filename="photo.webp",
            allowed_formats={".jpg", ".jpeg", ".png", ".webp"},
        )
        assert safe_name.endswith(".webp")

    def test_generated_filename_no_path_traversal(self, valid_jpeg_bytes):
        """Generated server-side filename should not contain path separators."""
        safe_name, _ = validate_image_upload(valid_jpeg_bytes)
        assert "/" not in safe_name
        assert "\\" not in safe_name
        assert ".." not in safe_name
        assert safe_name.startswith("enroll_")

    def test_generated_filename_is_unique(self, valid_png_bytes):
        """Generated filenames should be unique across calls."""
        names = set()
        for _ in range(10):
            name, _ = validate_image_upload(valid_png_bytes)
            names.add(name)
        assert len(names) == 10  # All unique

    def test_default_allowed_formats(self, valid_webp_bytes):
        """WebP should be rejected when allowed_formats only includes jpg/png."""
        with pytest.raises(UploadSecurityError, match="not allowed"):
            validate_image_upload(
                valid_webp_bytes,
                filename="photo.webp",
                allowed_formats={".jpg", ".jpeg", ".png"},
            )

    # ── Size checks ────────────────────────────────────────────

    def test_oversized_file_is_rejected(self):
        """File larger than max_size_mb should be rejected."""
        big_data = b"x" * (6 * 1024 * 1024)  # 6 MB
        with pytest.raises(UploadSecurityError, match="too large"):
            validate_image_upload(big_data, max_size_mb=5.0)

    def test_empty_file_is_rejected(self):
        """Zero-byte file should be rejected."""
        with pytest.raises(UploadSecurityError, match="empty"):
            validate_image_upload(b"")

    # ── Magic-byte / content-based rejection ───────────────────

    def test_text_file_is_rejected(self):
        """A plain-text file should be rejected (no image magic bytes)."""
        with pytest.raises(UploadSecurityError, match="could not be detected"):
            validate_image_upload(b"This is not an image file")

    def test_binary_non_image_is_rejected(self):
        """Arbitrary binary data (not an image) should be rejected."""
        with pytest.raises(UploadSecurityError, match="could not be detected"):
            validate_image_upload(bytes(range(256)))

    def test_exe_magic_bytes_are_rejected(self):
        """PE executable magic bytes (MZ) should be rejected."""
        with pytest.raises(UploadSecurityError, match="could not be detected"):
            validate_image_upload(b"MZ" + b"\x00" * 100)

    def test_renamed_non_image(self, valid_jpeg_bytes):
        """A file with a .jpg extension but PNG content should pass
        (the validator uses content, not extension). This is valid.
        But a file with .jpg extension and plain-text content should fail."""
        with pytest.raises(UploadSecurityError, match="could not be detected"):
            validate_image_upload(
                b"Not really an image",
                filename="innocent.jpg",
            )

    # ── Corrupted / truncated images ───────────────────────────

    def test_corrupted_image_is_rejected(self):
        """Truncated/corrupted image data should be caught by Pillow verify."""
        # Minimal PNG header is 8 bytes, but we need actual corrupt data
        png_header = b"\x89PNG\r\n\x1a\n"
        # A valid-looking but actually corrupted chunk
        corrupted = png_header + b"\x00" * 100
        with pytest.raises(UploadSecurityError, match="Invalid or corrupt"):
            validate_image_upload(corrupted, filename="corrupt.png")

    def test_truncated_jpeg_is_rejected(self):
        """A JPEG file that's been truncated should be caught."""
        full = _make_jpeg_bytes(64, 64)
        truncated = full[:len(full) // 4]  # Only first 25%
        with pytest.raises((UploadSecurityError, OSError)):
            validate_image_upload(truncated, filename="truncated.jpg")

    # ── Dimension checks ───────────────────────────────────────

    def test_oversized_dimensions_rejected(self, monkeypatch):
        """Image exceeding MAX_WIDTH or MAX_HEIGHT should be rejected."""
        # Generate a large (but 8 MP) image
        big = _make_jpeg_bytes(5000, 5000)  # 25 MP
        with pytest.raises(UploadSecurityError, match="exceed maximum|too large"):
            validate_image_upload(big, filename="huge.jpg")

    # ── Extension / format edge cases ──────────────────────────

    def test_no_extension_provided(self, valid_jpeg_bytes):
        """Even without a filename, detection should work via magic bytes."""
        safe_name, data = validate_image_upload(
            valid_jpeg_bytes, filename=""
        )
        assert safe_name.endswith(".jpg")

    def test_unsupported_format_in_allowed_list(self, valid_png_bytes):
        """PNG should be rejected if only jpg is in allowed_formats."""
        with pytest.raises(UploadSecurityError, match="not allowed"):
            validate_image_upload(
                valid_png_bytes,
                filename="photo.png",
                allowed_formats={".jpg", ".jpeg"},
            )

    # ── Allow-nobody edge case ─────────────────────────────────

    def test_empty_allowed_formats_rejects_all(self, valid_jpeg_bytes):
        """An empty allowed_formats set should reject everything."""
        with pytest.raises(UploadSecurityError):
            validate_image_upload(
                valid_jpeg_bytes,
                allowed_formats=set(),
            )


class TestSanitizeFilename:
    """Tests for the sanitize_filename helper."""

    def test_sanitize_removes_path_traversal(self):
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_sanitize_removes_backslash_paths(self):
        assert sanitize_filename("..\\..\\windows\\system32") == "system32"

    def test_sanitize_truncates_long_names(self):
        long_name = "a" * 500 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) == 255

    def test_sanitize_handles_normal_name(self):
        assert sanitize_filename("photo.jpg") == "photo.jpg"

    def test_sanitize_removes_null_bytes(self):
        assert sanitize_filename("photo\x00.jpg") == "photo.jpg"
