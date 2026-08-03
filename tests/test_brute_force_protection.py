"""
Tests for BruteForceProtection service.

Covers account lockout, failed attempt recording, successful login
recording, lockout info retrieval, and cleanup of old attempts.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from database.database import get_session
from database.models import FailedLoginAttempt, _utcnow
from services.brute_force_protection import BruteForceProtection


class TestBruteForceProtection:
    """Tests for BruteForceProtection brute force defense logic."""

    @pytest.fixture(autouse=True)
    def _clean_db(self, reset_db):
        """Reset database before each test."""
        pass

    # ── is_locked_out ─────────────────────────────────────────────

    def test_not_locked_initially(self):
        """New username should not be locked out."""
        is_locked, msg = BruteForceProtection.is_locked_out("alice", "192.168.1.1")
        assert is_locked is False

    def test_locked_after_max_attempts(self):
        """Username should be locked after 5 failed attempts."""
        for i in range(BruteForceProtection.MAX_FAILED_ATTEMPTS):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        is_locked, msg = BruteForceProtection.is_locked_out("alice", "192.168.1.1")
        assert is_locked is True
        assert "locked" in msg.lower() or "too many" in msg.lower()

    def test_lockout_is_per_username(self):
        """Locking out alice should not affect bob."""
        for i in range(BruteForceProtection.MAX_FAILED_ATTEMPTS):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        is_locked_alice, _ = BruteForceProtection.is_locked_out("alice", "192.168.1.1")
        is_locked_bob, _ = BruteForceProtection.is_locked_out("bob", "192.168.1.1")
        assert is_locked_alice is True
        assert is_locked_bob is False

    def test_lockout_is_per_ip(self):
        """Excessive attempts from same IP should trigger IP-based lockout."""
        for i in range(BruteForceProtection.IP_RATE_LIMIT_PER_MINUTE):
            BruteForceProtection.record_failed_attempt(f"user{i}", "192.168.1.1")

        is_locked, msg = BruteForceProtection.is_locked_out("newuser", "192.168.1.1")
        assert is_locked is True

    def test_different_ip_not_affected(self):
        """Lockout from one IP should not affect another IP."""
        for i in range(BruteForceProtection.IP_RATE_LIMIT_PER_MINUTE):
            BruteForceProtection.record_failed_attempt(f"user{i}", "192.168.1.1")

        is_locked, _ = BruteForceProtection.is_locked_out("alice", "10.0.0.1")
        assert is_locked is False

    # ── record_failed_attempt ─────────────────────────────────────

    def test_record_failed_attempt_creates_record(self):
        """Failed attempt should be recorded in the database."""
        BruteForceProtection.record_failed_attempt("alice", "192.168.1.1", "Mozilla/5.0")

        with get_session() as session:
            records = session.query(FailedLoginAttempt).filter(FailedLoginAttempt.username == "alice").all()
            assert len(records) == 1
            assert records[0].ip_address == "192.168.1.1"
            assert records[0].success is False
            assert records[0].user_agent == "Mozilla/5.0"

    def test_record_multiple_failed_attempts(self):
        """Multiple failed attempts should all be recorded."""
        for i in range(3):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        with get_session() as session:
            count = session.query(FailedLoginAttempt).filter(FailedLoginAttempt.username == "alice").count()
            assert count == 3

    def test_record_failed_attempt_username_lowercase(self):
        """Username should be stored in lowercase for consistency."""
        BruteForceProtection.record_failed_attempt("Alice", "192.168.1.1")

        with get_session() as session:
            record = session.query(FailedLoginAttempt).first()
            assert record.username == "alice"

    def test_record_failed_attempt_truncates_user_agent(self):
        """User agent should be truncated to 500 chars."""
        long_ua = "A" * 1000
        BruteForceProtection.record_failed_attempt("alice", "192.168.1.1", long_ua)

        with get_session() as session:
            record = session.query(FailedLoginAttempt).first()
            assert len(record.user_agent) <= 500

    # ── record_successful_login ───────────────────────────────────

    def test_record_successful_login(self):
        """Successful login should be recorded."""
        BruteForceProtection.record_successful_login("alice", "192.168.1.1")

        with get_session() as session:
            record = session.query(FailedLoginAttempt).first()
            assert record.username == "alice"
            assert record.success is True

    def test_successful_login_resets_lockout(self):
        """Successful login should allow future logins (resets counter)."""
        # Record 3 failed attempts (below threshold)
        for i in range(3):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        # Successful login
        BruteForceProtection.record_successful_login("alice", "192.168.1.1")

        # Should not be locked out
        is_locked, _ = BruteForceProtection.is_locked_out("alice", "192.168.1.1")
        assert is_locked is False

    # ── get_lockout_info ──────────────────────────────────────────

    def test_lockout_info_clean_user(self):
        """Clean user should show no failures and full remaining attempts."""
        info = BruteForceProtection.get_lockout_info("alice")
        assert info["locked_out"] is False
        assert info["failed_attempts"] == 0
        assert info["remaining_attempts"] == BruteForceProtection.MAX_FAILED_ATTEMPTS

    def test_lockout_info_after_failures(self):
        """After failures, should show correct remaining attempts."""
        for i in range(3):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        info = BruteForceProtection.get_lockout_info("alice")
        assert info["failed_attempts"] == 3
        assert info["remaining_attempts"] == BruteForceProtection.MAX_FAILED_ATTEMPTS - 3

    def test_lockout_info_when_locked(self):
        """When locked, should show lockout_remaining_seconds > 0."""
        for i in range(BruteForceProtection.MAX_FAILED_ATTEMPTS):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        info = BruteForceProtection.get_lockout_info("alice")
        assert info["locked_out"] is True
        assert info["lockout_remaining_seconds"] > 0
        assert info["remaining_attempts"] == 0

    def test_lockout_info_after_successful_login(self):
        """Successful login should reset the lockout info."""
        for i in range(3):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        BruteForceProtection.record_successful_login("alice", "192.168.1.1")

        info = BruteForceProtection.get_lockout_info("alice")
        assert info["failed_attempts"] >= 3  # Still records exist, but recent success resets
        assert info["locked_out"] is False

    # ── cleanup_old_attempts ──────────────────────────────────────

    def test_cleanup_old_attempts(self):
        """Old attempts should be cleaned up."""
        # Create an old record by directly inserting with old timestamp
        with get_session() as session:
            old_attempt = FailedLoginAttempt(
                username="alice",
                ip_address="192.168.1.1",
                success=False,
            )
            # Set attempted_at to 8 days ago (older than CLEANUP_DAYS=7)
            old_attempt.attempted_at = _utcnow() - timedelta(days=8)
            session.add(old_attempt)
            session.commit()

        deleted = BruteForceProtection.cleanup_old_attempts()
        assert deleted >= 1

        with get_session() as session:
            remaining = session.query(FailedLoginAttempt).count()
            assert remaining == 0

    def test_cleanup_keeps_recent(self):
        """Recent attempts should not be cleaned up."""
        BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        deleted = BruteForceProtection.cleanup_old_attempts()
        assert deleted == 0

        with get_session() as session:
            count = session.query(FailedLoginAttempt).count()
            assert count == 1

    # ── Edge Cases ────────────────────────────────────────────────

    def test_empty_username(self):
        """Empty username should not crash."""
        is_locked, _ = BruteForceProtection.is_locked_out("", "192.168.1.1")
        assert is_locked is False

    def test_empty_ip(self):
        """Empty IP should not crash."""
        BruteForceProtection.record_failed_attempt("alice", "")
        is_locked, _ = BruteForceProtection.is_locked_out("alice", "")
        assert is_locked is False

    def test_special_characters_in_username(self):
        """Usernames with special characters should work."""
        BruteForceProtection.record_failed_attempt("admin@college.edu", "192.168.1.1")

        with get_session() as session:
            record = session.query(FailedLoginAttempt).first()
            assert record.username == "admin@college.edu"

    def test_ipv6_address(self):
        """IPv6 addresses should be supported."""
        BruteForceProtection.record_failed_attempt("alice", "::1")

        with get_session() as session:
            record = session.query(FailedLoginAttempt).first()
            assert record.ip_address == "::1"

    def test_warning_at_threshold_minus_one(self):
        """Should get a warning message when close to lockout."""
        for i in range(3):
            BruteForceProtection.record_failed_attempt("alice", "192.168.1.1")

        is_locked, msg = BruteForceProtection.is_locked_out("alice", "192.168.1.1")
        assert is_locked is False
        assert msg is not None  # Should have a warning
        assert "remaining" in msg.lower() or "warning" in msg.lower()
