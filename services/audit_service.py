"""
Audit Service — records all system actions to the database.

Every important operation (enrollment, recognition, attendance marking,
configuration change, etc.) should be logged through this service.
"""

from __future__ import annotations

from typing import Optional

from database.database import get_session
from database.repository import AuditLogRepo


class AuditService:
    """Enterprise audit trail for all system actions.

    Usage::

        AuditService.log("ENROLL", "Enrolled employee Alice (EMP001)")
        AuditService.log(
            "MARK_ATTENDANCE",
            "Attendance marked for Alice",
            operator="admin",
            employee_id=1,
        )
    """

    @staticmethod
    def log(
        action: str,
        description: Optional[str] = None,
        operator: str = "system",
        employee_id: Optional[int] = None,
    ) -> None:
        """Record an audit log entry.

        Args:
            action: Short action name (e.g. ``ENROLL``, ``RECOGNIZE``,
                    ``MARK_ATTENDANCE``, ``DELETE``, ``CONFIG_CHANGE``).
            description: Human-readable description of what happened.
            operator: Who performed the action (default: ``"system"``).
            employee_id: Related employee, if applicable.
        """
        with get_session() as session:
            AuditLogRepo.create(
                session,
                action=action,
                description=description,
                operator=operator,
                employee_id=employee_id,
            )

    @staticmethod
    def get_recent(limit: int = 100) -> list:
        """Return the most recent audit log entries."""
        with get_session() as session:
            return AuditLogRepo.get_recent(session, limit=limit)

    @staticmethod
    def get_by_action(action: str) -> list:
        """Return audit log entries filtered by action type."""
        with get_session() as session:
            return AuditLogRepo.get_by_action(session, action)
