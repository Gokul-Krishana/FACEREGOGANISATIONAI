"""
Brute Force Protection Service
================================

Tracks failed login attempts and implements account lockout
to prevent brute force attacks.

Features:
    - Per-username lockout after N failed attempts
    - Per-IP rate limiting
    - Automatic lockout duration (30 minutes default)
    - Successful login resets failed attempt counter
    - Audit trail for all login attempts

Usage::

    from services.brute_force_protection import BruteForceProtection

    # Before checking credentials
    if BruteForceProtection.is_locked_out(username, ip_address):
        raise HTTPException(status_code=429, detail="Account temporarily locked")

    # After failed attempt
    BruteForceProtection.record_failed_attempt(username, ip_address, user_agent)

    # After successful login
    BruteForceProtection.record_successful_login(username, ip_address)
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional, Tuple

from sqlalchemy import and_, func

from database.database import get_session
from database.models import FailedLoginAttempt, _utcnow

logger = logging.getLogger(__name__)


class BruteForceProtection:
    """Brute force protection for login attempts."""

    # Configuration (can be overridden via env vars)
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    IP_RATE_LIMIT_PER_MINUTE = 20
    CLEANUP_DAYS = 7  # Delete attempts older than 7 days

    @staticmethod
    def _last_success_at(session, username: str):
        """Return the most recent successful login time for a user."""
        return (
            session.query(func.max(FailedLoginAttempt.attempted_at))
            .filter(
                and_(
                    FailedLoginAttempt.username == username.lower(),
                    FailedLoginAttempt.success.is_(True),
                )
            )
            .scalar()
        )

    @staticmethod
    def is_locked_out(username: str, ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a username or IP address is currently locked out.

        Returns:
            Tuple of (is_locked, reason_message)
        """
        now = _utcnow()
        lockout_threshold = now - timedelta(minutes=BruteForceProtection.LOCKOUT_DURATION_MINUTES)

        with get_session() as session:
            last_success = BruteForceProtection._last_success_at(session, username)

            # Check username-based lockout
            query = session.query(func.count(FailedLoginAttempt.id)).filter(
                and_(
                    FailedLoginAttempt.username == username.lower(),
                    FailedLoginAttempt.success.is_(False),
                    FailedLoginAttempt.attempted_at >= lockout_threshold,
                )
            )
            if last_success is not None:
                query = query.filter(FailedLoginAttempt.attempted_at > last_success)
            username_failures = query.scalar()

            if username_failures >= BruteForceProtection.MAX_FAILED_ATTEMPTS:
                remaining = BruteForceProtection.LOCKOUT_DURATION_MINUTES
                return (
                    True,
                    f"Account locked due to too many failed attempts. Try again in {remaining} minutes.",
                )

            # Check IP-based rate limiting
            ip_attempts = (
                session.query(func.count(FailedLoginAttempt.id))
                .filter(
                    and_(
                        FailedLoginAttempt.ip_address == ip_address,
                        FailedLoginAttempt.attempted_at >= now - timedelta(minutes=1),
                    )
                )
                .scalar()
            )

            if ip_attempts >= BruteForceProtection.IP_RATE_LIMIT_PER_MINUTE:
                return True, "Too many requests from your IP. Please wait a moment."

            # Check if user has any failed attempts (for progressive delay warning)
            total_failures_query = session.query(func.count(FailedLoginAttempt.id)).filter(
                and_(
                    FailedLoginAttempt.username == username.lower(),
                    FailedLoginAttempt.success.is_(False),
                    FailedLoginAttempt.attempted_at >= lockout_threshold,
                )
            )
            if last_success is not None:
                total_failures_query = total_failures_query.filter(
                    FailedLoginAttempt.attempted_at > last_success
                )
            total_failures = total_failures_query.scalar()

            if total_failures >= 3:
                remaining_attempts = BruteForceProtection.MAX_FAILED_ATTEMPTS - total_failures
                return False, f"Warning: {remaining_attempts} attempts remaining before lockout."

            return False, None

    @staticmethod
    def record_failed_attempt(username: str, ip_address: str, user_agent: Optional[str] = None) -> None:
        """
        Record a failed login attempt.

        Args:
            username: The username that was attempted
            ip_address: IP address of the request
            user_agent: User-Agent header value
        """
        with get_session() as session:
            attempt = FailedLoginAttempt(
                username=username.lower(),
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
                success=False,
            )
            session.add(attempt)
            session.commit()

            # Check if this triggers a lockout
            lockout_threshold = _utcnow() - timedelta(minutes=BruteForceProtection.LOCKOUT_DURATION_MINUTES)
            failure_count = (
                session.query(func.count(FailedLoginAttempt.id))
                .filter(
                    and_(
                        FailedLoginAttempt.username == username.lower(),
                        FailedLoginAttempt.success.is_(False),
                        FailedLoginAttempt.attempted_at >= lockout_threshold,
                    )
                )
                .scalar()
            )

            if failure_count >= BruteForceProtection.MAX_FAILED_ATTEMPTS:
                logger.warning(
                    "Account locked: %s from %s after %d failed attempts", username, ip_address, failure_count
                )

    @staticmethod
    def record_successful_login(username: str, ip_address: str) -> None:
        """
        Record a successful login and clear failed attempts.

        Args:
            username: The successful username
            ip_address: IP address of the request
        """
        with get_session() as session:
            # Record successful attempt
            attempt = FailedLoginAttempt(username=username.lower(), ip_address=ip_address, success=True)
            session.add(attempt)
            session.commit()

    @staticmethod
    def get_lockout_info(username: str) -> dict:
        """
        Get lockout information for a username.

        Returns:
            Dict with lockout status and remaining time
        """
        now = _utcnow()
        lockout_threshold = now - timedelta(minutes=BruteForceProtection.LOCKOUT_DURATION_MINUTES)

        with get_session() as session:
            last_success = BruteForceProtection._last_success_at(session, username)
            # Get recent failed attempts for display purposes
            all_recent_failures = (
                session.query(FailedLoginAttempt)
                .filter(
                    and_(
                        FailedLoginAttempt.username == username.lower(),
                        FailedLoginAttempt.success.is_(False),
                        FailedLoginAttempt.attempted_at >= lockout_threshold,
                    )
                )
                .order_by(FailedLoginAttempt.attempted_at.desc())
                .all()
            )

            # Failures that still count toward an active lockout
            active_failures_query = session.query(FailedLoginAttempt).filter(
                and_(
                    FailedLoginAttempt.username == username.lower(),
                    FailedLoginAttempt.success.is_(False),
                    FailedLoginAttempt.attempted_at >= lockout_threshold,
                )
            )
            if last_success is not None:
                active_failures_query = active_failures_query.filter(
                    FailedLoginAttempt.attempted_at > last_success
                )
            active_failures = active_failures_query.order_by(FailedLoginAttempt.attempted_at.desc()).all()

            if not all_recent_failures:
                return {
                    "locked_out": False,
                    "failed_attempts": 0,
                    "remaining_attempts": BruteForceProtection.MAX_FAILED_ATTEMPTS,
                    "lockout_remaining_seconds": 0,
                }

            # Find the most recent failure
            most_recent = active_failures[0] if active_failures else all_recent_failures[0]
            lockout_end = most_recent.attempted_at + timedelta(
                minutes=BruteForceProtection.LOCKOUT_DURATION_MINUTES
            )
            if len(active_failures) >= BruteForceProtection.MAX_FAILED_ATTEMPTS and now < lockout_end:
                remaining_seconds = int((lockout_end - now).total_seconds())
                return {
                    "locked_out": True,
                    "failed_attempts": len(all_recent_failures),
                    "remaining_attempts": 0,
                    "lockout_remaining_seconds": remaining_seconds,
                    "lockout_end": lockout_end.isoformat(),
                }

            return {
                "locked_out": False,
                "failed_attempts": len(all_recent_failures),
                "remaining_attempts": max(0, BruteForceProtection.MAX_FAILED_ATTEMPTS - len(active_failures)),
                "lockout_remaining_seconds": 0,
            }

    @staticmethod
    def cleanup_old_attempts() -> int:
        """
        Delete failed login attempts older than CLEANUP_DAYS.

        Returns:
            Number of records deleted
        """
        cutoff = _utcnow() - timedelta(days=BruteForceProtection.CLEANUP_DAYS)

        with get_session() as session:
            deleted = (
                session.query(FailedLoginAttempt).filter(FailedLoginAttempt.attempted_at < cutoff).delete()
            )
            session.commit()

            if deleted > 0:
                logger.info("Cleaned up %d old login attempts", deleted)

            return deleted
