"""
Multi-Factor Authentication Service
=====================================

Provides TOTP-based MFA using ``pyotp`` with:
    - TOTP secret generation and validation
    - QR code provisioning URIs
    - Backup codes (one-time use, hashed storage)
    - MFA enrollment and verification flows

Usage::

    from services.mfa_service import MFAService

    # Enroll a user
    secret, qr_uri = MFAService.generate_secret("user@college.edu")
    backup_codes = MFAService.generate_backup_codes()

    # Verify
    is_valid = MFAService.verify_totp(secret, user_input_code)
    is_valid = MFAService.verify_backup_code(stored_hashes, user_input_code)
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from database.database import get_session
from database.models import RoleName, User


class MFAService:
    """TOTP-based MFA service.

    Uses ``pyotp`` for TOTP generation/validation and stores
    backup codes as SHA-256 hashes.
    """

    TOTP_ISSUER = "Face Recognition AI"
    BACKUP_CODE_COUNT = 8
    BACKUP_CODE_LENGTH = 10  # Characters per code

    # ── Secret Management ──────────────────────────────────────

    @staticmethod
    def generate_secret(email: str) -> Tuple[str, str]:
        """Generate a new TOTP secret and provisioning URI.

        Args:
            email: User's email (appears in the authenticator app).

        Returns:
            ``(base32_secret, provisioning_uri)``.
            The provisioning URI should be shown as a QR code.
        """
        import pyotp

        secret = pyotp.random_base32()
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name=MFAService.TOTP_ISSUER,
        )
        return secret, uri

    @staticmethod
    def verify_totp(secret: str, code: str, tolerance: int = 1) -> bool:
        """Verify a TOTP code against a secret.

        Args:
            secret: Base32-encoded TOTP secret.
            code: The 6-digit code from the authenticator app.
            tolerance: Allowed clock drift in 30-second windows (default 1).

        Returns:
            ``True`` if the code is valid.
        """
        import pyotp

        if not secret or not code:
            return False
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=tolerance)

    # ── Backup Codes ───────────────────────────────────────────

    @staticmethod
    def generate_backup_codes() -> Tuple[List[str], List[str]]:
        """Generate one-time backup codes.

        Returns:
            ``(plaintext_codes, hashed_codes)``.
            - Show ``plaintext_codes`` to the user exactly once.
            - Store ``hashed_codes`` in the database.
        """
        plaintext: List[str] = []
        hashed: List[str] = []

        for _ in range(MFAService.BACKUP_CODE_COUNT):
            code = MFAService._generate_backup_code()
            plaintext.append(code)
            hashed.append(MFAService._hash_backup_code(code))

        return plaintext, hashed

    @staticmethod
    def verify_backup_code(stored_hashes: List[str], user_code: str) -> Tuple[bool, Optional[str]]:
        """Verify a backup code against stored hashes.

        If valid, returns the matched hash so the caller can remove it
        (one-time use).

        Args:
            stored_hashes: List of SHA-256 hashed backup codes from DB.
            user_code: The code the user entered.

        Returns:
            ``(is_valid, matched_hash)``. If valid, the matched hash
            should be removed from the stored list (one-time use).
        """
        if not stored_hashes or not user_code:
            return False, None

        user_hash = MFAService._hash_backup_code(user_code.strip().upper())
        for i, stored_hash in enumerate(stored_hashes):
            if hmac.compare_digest(stored_hash, user_hash):
                return True, stored_hash
        return False, None

    @staticmethod
    def remove_used_backup_code(stored_hashes: List[str], used_hash: str) -> List[str]:
        """Remove a used backup code from the list."""
        return [h for h in stored_hashes if h != used_hash]

    # ── Enrollment ─────────────────────────────────────────────

    @staticmethod
    def enroll_user(user: User) -> Tuple[str, str, List[str]]:
        """Enable MFA for a user.

        Generates a TOTP secret and backup codes, stores them
        (backup codes hashed), and returns the display values.

        Args:
            user: The User ORM object.

        Returns:
            ``(secret, qr_uri, plaintext_backup_codes)``.
            Show these to the user exactly once.
        """
        secret, uri = MFAService.generate_secret(user.email or user.username)  # type: ignore[arg-type]
        plaintext_codes, hashed_codes = MFAService.generate_backup_codes()

        with get_session() as session:
            db_user = session.query(User).filter(User.id == user.id).first()
            if db_user:
                db_user.mfa_totp_secret = secret  # type: ignore[assignment]
                db_user.mfa_backup_codes = hashed_codes  # type: ignore[assignment]
                db_user.is_mfa_enabled = True  # type: ignore[assignment]
                session.commit()

        return secret, uri, plaintext_codes

    @staticmethod
    def disable_mfa(user: User) -> bool:
        """Disable MFA for a user, clearing all MFA data."""
        with get_session() as session:
            db_user = session.query(User).filter(User.id == user.id).first()
            if db_user:
                db_user.is_mfa_enabled = False  # type: ignore[assignment]
                db_user.mfa_totp_secret = None  # type: ignore[assignment]
                db_user.mfa_backup_codes = None  # type: ignore[assignment]
                db_user.mfa_last_verified = None  # type: ignore[assignment]
                session.commit()
                return True
        return False

    @staticmethod
    def verify_and_update(user: User, code: str, use_backup: bool = False) -> Tuple[bool, str]:
        """Verify MFA code and update verification timestamp.

        Args:
            user: The User ORM object.
            code: TOTP code or backup code.
            use_backup: If True, check backup codes instead of TOTP.

        Returns:
            ``(success, message)``.
        """
        now = datetime.now(timezone.utc)

        if use_backup:
            # Check backup codes
            hashes = user.mfa_backup_codes or []  # type: ignore[var-annotated]
            valid, matched_hash = MFAService.verify_backup_code(hashes, code)  # type: ignore[arg-type]
            if not valid:
                return False, "Invalid backup code"

            # Remove used code
            remaining = MFAService.remove_used_backup_code(hashes, matched_hash)  # type: ignore[arg-type]

            # Check if user has any backup codes left
            with get_session() as session:
                db_user = session.query(User).filter(User.id == user.id).first()
                if db_user:
                    db_user.mfa_backup_codes = remaining  # type: ignore[assignment]
                    db_user.mfa_last_verified = now  # type: ignore[assignment]
                    session.commit()

            return True, "Backup code accepted"

        # TOTP verification
        if not user.mfa_totp_secret:
            return False, "MFA not configured"

        if not MFAService.verify_totp(user.mfa_totp_secret, code):  # type: ignore[arg-type]
            return False, "Invalid TOTP code"

        # Update verification timestamp
        with get_session() as session:
            db_user = session.query(User).filter(User.id == user.id).first()
            if db_user:
                db_user.mfa_last_verified = now  # type: ignore[assignment]
                session.commit()

        return True, "TOTP code accepted"

    @staticmethod
    def requires_mfa(user: User) -> bool:
        """Check if a user needs to complete MFA for the current session."""
        if not user.is_mfa_enabled:
            return False

        # Super admin always requires MFA
        for role in user.roles:
            if role.name == RoleName.SUPER_ADMIN.value:
                return True

        # Other admin roles require MFA
        admin_roles = {
            RoleName.COLLEGE_ADMIN.value,
            RoleName.HOD.value,
            RoleName.SECURITY.value,
        }
        for role in user.roles:
            if role.name in admin_roles:
                return True

        return False

    # ── Internal ──────────────────────────────────────────────

    @staticmethod
    def _generate_backup_code() -> str:
        """Generate a human-readable backup code."""
        return secrets.token_hex(MFAService.BACKUP_CODE_LENGTH // 2).upper()

    @staticmethod
    def _hash_backup_code(code: str) -> str:
        """SHA-256 hash of a backup code (one-way, for storage)."""
        return hashlib.sha256(code.encode("utf-8")).hexdigest()
