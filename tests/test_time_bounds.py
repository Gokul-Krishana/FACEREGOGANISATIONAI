"""
Regression tests for local-day ↔ UTC bounds conversion.

Root cause covered: attendance timestamps are stored as naive UTC
(``_utcnow``) while "today" queries used ``date.today()`` (host-local)
interpreted as a naive-UTC range. In any non-UTC timezone that mismatch
made every day-scoped attendance query silently return empty results
between local midnight and UTC midnight (reproduced on a UTC+5:30 host
just after local midnight: ``AttendanceRepo.get_statistics`` reported
``today_count == 0`` right after creating records).

These tests verify the invariant directly, independent of the host
timezone: a record written "now" must always fall inside today's bounds,
and bounds must be naive (matching stored timestamps).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from database.models import _utcnow, local_day_bounds_utc


class TestLocalDayBoundsUtc:
    def test_now_always_inside_today_bounds(self) -> None:
        """A timestamp written now must fall inside today's day bounds.

        This holds in every host timezone — it was exactly the property
        that broke when naive-local ranges were compared to UTC storage.
        """
        start, end = local_day_bounds_utc()
        now_utc = _utcnow()
        assert start <= now_utc <= end

    def test_bounds_are_naive(self) -> None:
        """Bounds must be naive datetimes to match stored timestamps."""
        start, end = local_day_bounds_utc()
        assert start.tzinfo is None
        assert end.tzinfo is None

    def test_bounds_span_a_full_day(self) -> None:
        start, end = local_day_bounds_utc()
        # A local day is always >= 23h (DST can shorten it by 1h)
        assert timedelta(hours=23) <= (end - start) <= timedelta(hours=24)

    def test_explicit_target_date(self) -> None:
        """Bounds for a past date must precede today's bounds."""
        yesterday = date.today() - timedelta(days=1)
        y_start, y_end = local_day_bounds_utc(yesterday)
        t_start, _ = local_day_bounds_utc()
        assert y_end < t_start
        assert y_start < y_end

    def test_record_created_now_is_counted_today(self) -> None:
        """End-to-end: a record created now must appear in 'today' queries."""
        from database.database import get_session
        from database.repository import AttendanceRepo, EmployeeRepo

        with get_session() as session:
            emp = EmployeeRepo.create(session, employee_id="TZ_T001", name="TZ Test")
            AttendanceRepo.create(session, employee_id=emp.id, confidence=0.99)
            stats = AttendanceRepo.get_statistics(session)
            assert stats["today_count"] >= 1
            today_records = AttendanceRepo.get_today(session)
            assert any(r.employee_id == emp.id for r in today_records)
            # Cleanup (rollback-safe: commits are required by repos)
            from database.models import Attendance

            session.query(Attendance).filter(Attendance.employee_id == emp.id).delete()
            session.query(type(emp)).filter(type(emp).id == emp.id).delete()
            session.commit()

    def test_bounds_contain_local_now_converted_to_utc(self) -> None:
        """The local 'now' (converted to UTC) falls inside today's bounds."""
        local_now = datetime.now()
        local_now_as_utc = local_now.astimezone(timezone.utc).replace(tzinfo=None)
        start, end = local_day_bounds_utc()
        assert start <= local_now_as_utc <= end

    def test_utc_host_degenerates_to_naive_utc_day(self) -> None:
        """When the host runs UTC, bounds equal the naive-UTC calendar day."""
        if datetime.now().astimezone().utcoffset() != timedelta(0):
            import pytest

            pytest.skip("Host timezone is not UTC")
        now_utc = _utcnow()
        start, end = local_day_bounds_utc(now_utc.date())
        assert start == datetime.combine(now_utc.date(), datetime.min.time())
        assert end == datetime.combine(now_utc.date(), datetime.max.time())
