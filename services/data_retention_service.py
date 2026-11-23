"""
Data Retention and Privacy Compliance Service
=============================================

Implements automated data retention policies and GDPR/BIPA compliance:
- Purges expired unknown face snapshots and shreds image files on disk.
- Enforces subject-level retention policies.
- Retains auditable deletion records for compliance verification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import and_

from database.database import get_session
from database.models import AuditAction, AuditLog, UnknownFace, _utcnow
from services.audit_service import AuditService
from utils.biometric_crypto import shred_file

logger = logging.getLogger(__name__)


class DataRetentionService:
    """Manages automated data retention, privacy policies, and GDPR compliance."""

    DEFAULT_UNKNOWN_RETENTION_DAYS = 30
    DEFAULT_AUDIT_RETENTION_DAYS = 365

    @classmethod
    def run_retention_purge(
        cls,
        unknown_days: int = DEFAULT_UNKNOWN_RETENTION_DAYS,
        audit_days: int = DEFAULT_AUDIT_RETENTION_DAYS,
        operator: str = "system",
    ) -> Dict[str, int]:
        """Execute automated retention cleanup.

        Returns:
            Dictionary with counts of deleted records.
        """
        now = _utcnow()
        unknown_cutoff = now - timedelta(days=unknown_days)
        audit_cutoff = now - timedelta(days=audit_days)

        unknown_deleted = 0
        audit_deleted = 0

        with get_session() as session:
            # 1. Purge expired unknown face records and shred their images
            query = session.query(UnknownFace).filter(
                (UnknownFace.retention_expires_at <= now)
                | (and_(UnknownFace.retention_expires_at.is_(None), UnknownFace.timestamp < unknown_cutoff))
            )
            expired_faces = query.all()

            for face in expired_faces:
                if face.image_path:
                    shred_file(face.image_path)
                if face.thumbnail_path:
                    shred_file(face.thumbnail_path)
                if face.embedding_path:
                    shred_file(face.embedding_path)
                session.delete(face)
                unknown_deleted += 1

            session.commit()

            # 2. Purge audit logs older than retention policy (except critical security alerts)
            old_logs = (
                session.query(AuditLog)
                .filter(
                    and_(
                        AuditLog.timestamp < audit_cutoff,
                        AuditLog.severity != "CRITICAL",
                    )
                )
                .all()
            )
            for log in old_logs:
                session.delete(log)
                audit_deleted += 1

            session.commit()

        if unknown_deleted > 0 or audit_deleted > 0:
            AuditService.log(
                "DATA_DELETED",
                f"Data retention purge completed: {unknown_deleted} unknown faces shredded, {audit_deleted} old audit logs pruned",
                operator=operator,
            )
            logger.info(
                "Retention purge completed: %d unknown faces shredded, %d audit logs pruned",
                unknown_deleted,
                audit_deleted,
            )

        return {
            "unknown_faces_deleted": unknown_deleted,
            "audit_logs_deleted": audit_deleted,
        }
