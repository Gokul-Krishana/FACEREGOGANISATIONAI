"""
Audit logging service for Face Recognition AI - College Deployment.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from database.models import AuditLog


class AuditAction(str, Enum):
    """Audit action types."""

    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    ATTENDANCE_MARKED = "ATTENDANCE_MARKED"
    ATTENDANCE_MODIFIED = "ATTENDANCE_MODIFIED"
    ATTENDANCE_DELETED = "ATTENDANCE_DELETED"
    STUDENT_ENROLLED = "STUDENT_ENROLLED"
    STUDENT_UPDATED = "STUDENT_UPDATED"
    STUDENT_DELETED = "STUDENT_DELETED"
    EMPLOYEE_ENROLLED = "EMPLOYEE_ENROLLED"
    EMPLOYEE_UPDATED = "EMPLOYEE_UPDATED"
    CAMERA_ADDED = "CAMERA_ADDED"
    CAMERA_REMOVED = "CAMERA_REMOVED"
    CAMERA_STATUS_CHANGED = "CAMERA_STATUS_CHANGED"
    UNKNOWN_FACE_REVIEWED = "UNKNOWN_FACE_REVIEWED"
    UNKNOWN_FACE_DELETED = "UNKNOWN_FACE_DELETED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REMOVED = "ROLE_REMOVED"
    SYSTEM_CONFIG_CHANGED = "SYSTEM_CONFIG_CHANGED"
    DATA_EXPORTED = "DATA_EXPORTED"
    DATA_DELETED = "DATA_DELETED"
    SECURITY_ALERT = "SECURITY_ALERT"
    RECOGNITION_EVENT = "RECOGNITION_EVENT"
    ATTENDANCE_SYNC = "ATTENDANCE_SYNC"


class AuditService:
    """Service for audit logging and compliance."""

    @staticmethod
    def log_event(
        session: Session,
        action: AuditAction,
        actor: str,
        actor_id: Optional[int] = None,
        actor_type: str = "USER",
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "INFO",
    ) -> AuditLog:
        """Create and save an audit log entry."""
        audit = AuditLog(
            action=action.value,
            actor=actor,
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            details=details,
            severity=severity,
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)
        return audit

    @staticmethod
    def log_recognition_event(
        session: Session,
        student_id: Optional[int],
        employee_id: Optional[int],
        confidence: float,
        liveness_score: Optional[float] = None,
        is_spoof: bool = False,
        camera_id: Optional[int] = None,
        classroom_id: Optional[int] = None,
        section_id: Optional[int] = None,
        track_id: Optional[str] = None,
        face_snapshot_path: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log a recognition event."""
        from database.models import RecognitionLog

        is_known = student_id is not None or employee_id is not None

        recognition = RecognitionLog(
            employee_id=employee_id,
            student_id=student_id,
            is_known=is_known,
            confidence=confidence,
            liveness_confidence=liveness_score,
            is_spoof=is_spoof,
            camera_id=camera_id,
            classroom_id=classroom_id,
            section_id=section_id,
            track_id=track_id,
            face_snapshot_path=face_snapshot_path,
        )
        session.add(recognition)
        session.commit()
        session.refresh(recognition)

        # Also create audit log
        audit = AuditService.log_event(
            session=session,
            action=AuditAction.RECOGNITION_EVENT,
            actor="SYSTEM",
            actor_type="SYSTEM",
            resource_type="RecognitionLog",
            resource_id=recognition.id,
            description=f"Recognition event for {'student' if student_id else 'employee' if employee_id else 'unknown'}",
            ip_address=ip_address,
            details={
                "student_id": student_id,
                "employee_id": employee_id,
                "confidence": confidence,
                "liveness_score": liveness_score,
                "is_spoof": is_spoof,
                "camera_id": camera_id,
            },
        )
        return audit

    @staticmethod
    def log_security_alert(
        session: Session,
        alert_type: str,
        description: str,
        severity: str = "WARNING",
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log a security alert."""
        return AuditService.log_event(
            session=session,
            action=AuditAction.SECURITY_ALERT,
            actor="SYSTEM",
            actor_type="SYSTEM",
            description=description,
            severity=severity,
            details={"alert_type": alert_type, **(details or {})},
            ip_address=ip_address,
        )

    @staticmethod
    def get_audit_logs(
        session: Session,
        action: Optional[AuditAction] = None,
        actor: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Query audit logs with filters."""
        query = session.query(AuditLog)

        if action:
            query = query.filter(AuditLog.action == action.value)
        if actor:
            query = query.filter(AuditLog.actor == actor)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if severity:
            query = query.filter(AuditLog.severity == severity)
        if date_from:
            query = query.filter(AuditLog.timestamp >= date_from)
        if date_to:
            query = query.filter(AuditLog.timestamp <= date_to)

        query = query.order_by(AuditLog.timestamp.desc()).limit(limit)
        return query.all()

    @staticmethod
    def export_logs(
        session: Session,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        """Export audit logs for compliance."""
        logs = (
            session.query(AuditLog)
            .filter(
                AuditLog.timestamp >= date_from,
                AuditLog.timestamp <= date_to,
            )
            .order_by(AuditLog.timestamp)
            .all()
        )

        return [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action,
                "actor": log.actor,
                "actor_type": log.actor_type,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "description": log.description,
                "ip_address": log.ip_address,
                "severity": log.severity,
                "details": log.details,
            }
            for log in logs
        ]
