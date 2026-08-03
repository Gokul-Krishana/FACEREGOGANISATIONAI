"""
Unknown Face Service — manages the unknown face lifecycle.

Workflow::

    Camera → Unknown Person → Save Face → Unknown Gallery
        → Admin Reviews
            → Register as Employee (generate embedding → FAISS → SQLite)
            → Ignore (mark reviewed)
            → Delete (remove image + record)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

import cv2

import config.config as cfg
from database.database import get_session
from database.models import UnknownFace
from database.repository import UnknownFaceRepo
from services.employee_service import EmployeeService
from services.audit_service import AuditService

logger = logging.getLogger(__name__)


class UnknownFaceService:
    """High-level API for managing unknown faces."""

    @staticmethod
    def get_statistics() -> dict:
        """Return aggregate statistics about unknown faces."""
        with get_session() as session:
            return UnknownFaceRepo.get_statistics(session)

    @staticmethod
    def get_all() -> List[UnknownFace]:
        """Return all unknown faces, newest first."""
        with get_session() as session:
            return UnknownFaceRepo.get_all(session)

    @staticmethod
    def get_filtered(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        camera_id: Optional[int] = None,
        reviewed: Optional[bool] = None,
        min_confidence: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[UnknownFace]:
        """Query unknown faces with optional filters."""
        with get_session() as session:
            return UnknownFaceRepo.get_filtered(
                session,
                start_date=start_date,
                end_date=end_date,
                camera_id=camera_id,
                reviewed=reviewed,
                min_confidence=min_confidence,
                limit=limit,
                offset=offset,
            )

    @staticmethod
    def get_by_id(face_id: int) -> Optional[UnknownFace]:
        """Return a single unknown face by ID."""
        with get_session() as session:
            return UnknownFaceRepo.get_by_id(session, face_id)

    @staticmethod
    def mark_reviewed(face_id: int) -> bool:
        """Mark an unknown face as reviewed (ignored)."""
        with get_session() as session:
            result = UnknownFaceRepo.mark_reviewed(session, face_id)
        if result:
            AuditService.log(
                "IGNORE_UNKNOWN",
                f"Ignored unknown face #{face_id}",
            )
        return result

    @staticmethod
    def delete(face_id: int) -> bool:
        """Delete an unknown face record and its image file."""
        with get_session() as session:
            result = UnknownFaceRepo.delete(session, face_id, delete_image=True)
        if result:
            AuditService.log(
                "DELETE_UNKNOWN",
                f"Deleted unknown face #{face_id}",
            )
        return result

    @staticmethod
    def update_notes(face_id: int, notes: str) -> bool:
        """Add or update notes for an unknown face."""
        with get_session() as session:
            return UnknownFaceRepo.update_notes(session, face_id, notes)

    @staticmethod
    def convert_to_employee(
        face_id: int,
        employee_id: str,
        name: str,
        department: Optional[str] = None,
    ) -> bool:
        """Convert an unknown face into a registered employee.

        The full workflow:
        1. Load the saved unknown face image
        2. Generate an ArcFace embedding from it
        3. Add the embedding to the FAISS index
        4. Create the employee record in SQLite
        5. Mark the unknown face as converted
        6. Log the audit trail

        Args:
            face_id: Database ID of the unknown face record.
            employee_id: Unique employee identifier (e.g. ``EMP004``).
            name: Display name for the new employee.
            department: Optional department name.

        Returns:
            ``True`` if conversion succeeded.
        """
        from app.enrollment import FaceEnrollment
        from app.recognizer import FaceRecognizer

        # Step 1 — Fetch the unknown face record
        with get_session() as session:
            uf = UnknownFaceRepo.get_by_id(session, face_id)
            if not uf:
                logger.warning("Unknown face #%d not found", face_id)
                return False
            image_path = uf.image_path

        # Step 2 — Load and verify the image
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error("Could not read image: %s", image_path)
            return False

        # Step 3 — Generate ArcFace embedding
        try:
            recognizer = FaceRecognizer()
            embedding = recognizer.extract_embedding(img)
            if embedding is None:
                logger.error("No face detected in the saved unknown image")
                return False
        except Exception as exc:
            logger.error("Failed to generate embedding: %s", exc)
            return False

        # Step 4 — Create employee record in SQLite FIRST
        # so we fail fast if the employee_id already exists (no FAISS pollution)
        try:
            emp = EmployeeService.create(
                employee_id=employee_id,
                name=name,
                department=department,
                photo_path=image_path,  # type: ignore[arg-type]
                operator="dashboard",
            )
            _emp_db_id = emp.id
        except ValueError as exc:
            logger.warning("Employee creation failed: %s", exc)
            return False

        # Step 5 — Add to FAISS index (after DB success)
        try:
            enrollment = FaceEnrollment()
            enrollment.enroll(name, embedding)
            _faiss_id = enrollment.count() - 1  # 0-based index of the new entry
        except Exception as exc:
            logger.error("Failed to add to FAISS: %s", exc)
            # Clean up the employee record since FAISS failed
            EmployeeService.delete(employee_id, operator="dashboard")
            return False

        # Step 6 — Mark unknown face as converted
        with get_session() as session:
            UnknownFaceRepo.mark_converted(session, face_id)

        AuditService.log(
            "CONVERT_UNKNOWN",
            f"Converted unknown face #{face_id} to employee '{name}' ({employee_id})",
        )
        logger.info(
            "Converted unknown face #%d → %s (%s)",
            face_id,
            name,
            employee_id,
        )
        return True

    @staticmethod
    def delete_all() -> int:
        """Delete ALL unknown face records and image files in one batch.

        Much faster than calling ``delete()`` in a loop when there are
        hundreds of records — uses a single SQL ``DELETE`` and removes
        all image files in one pass.

        Returns:
            Number of records deleted.
        """
        with get_session() as session:
            count = UnknownFaceRepo.delete_all(session, delete_images=True)
        if count > 0:
            AuditService.log(
                "DELETE_ALL_UNKNOWN",
                f"Deleted ALL {count} unknown face records and images",
            )
            logger.info("Batch deleted all %d unknown face records", count)
        return count

    @staticmethod
    def auto_cleanup(days: int = cfg.UNKNOWN_FACE_RETENTION_DAYS) -> int:
        """Delete unknown face records older than the specified days.

        This is called automatically at startup and can also be triggered
        from the Settings page.

        Args:
            days: Delete records older than this many days.

        Returns:
            Number of records deleted.
        """
        with get_session() as session:
            deleted = UnknownFaceRepo.delete_older_than(session, days)
        if deleted > 0:
            logger.info("Auto-cleanup: deleted %d unknown faces older than %d days", deleted, days)
        return deleted
