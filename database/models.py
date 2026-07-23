"""
SQLAlchemy ORM models for the Face Recognition AI database.

Tables:
    - employees: Registered employee records
    - attendance: Daily attendance marks
    - recognition_log: Every recognition event (known + unknown)
    - unknown_faces: Unknown face snapshots
    - cameras: Camera configuration
    - audit_log: System audit trail
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship


# ── Timezone-aware UTC helper (replaces deprecated datetime.utcnow) ──────
# Returns a naive datetime for backward compatibility with existing
# SQLite storage (which doesn't store timezone info). The value is
# computed from timezone-aware UTC then stripped of tzinfo.
def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (tzinfo=None).

    This avoids the ``datetime.utcnow()`` deprecation while producing
    the same naive-UTC value that SQLAlchemy's ``DateTime`` column
    (without ``timezone=True``) expects.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    photo_path = Column(String(500), nullable=True)
    faiss_id = Column(Integer, nullable=True)  # ID in the FAISS index
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    attendance_records = relationship("Attendance", back_populates="employee")
    recognition_logs = relationship(
        "RecognitionLog",
        back_populates="employee",
        foreign_keys="RecognitionLog.employee_id",
    )

    def __repr__(self) -> str:
        return f"<Employee {self.employee_id}: {self.name}>"


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=1.0)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)

    # Relationships
    employee = relationship("Employee", back_populates="attendance_records")
    camera = relationship("Camera", back_populates="attendance_records")

    def __repr__(self) -> str:
        return f"<Attendance {self.employee_id} @ {self.timestamp}>"


class RecognitionLog(Base):
    """Every recognition event — both known and unknown faces."""

    __tablename__ = "recognition_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_known = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    face_snapshot_path = Column(String(500), nullable=True)

    # Relationships
    employee = relationship(
        "Employee",
        back_populates="recognition_logs",
        foreign_keys=[employee_id],
    )
    camera = relationship("Camera", back_populates="recognition_logs")

    def __repr__(self) -> str:
        name = self.employee.name if self.employee else "Unknown"
        return f"<RecognitionLog {name} @ {self.timestamp}>"


class UnknownFace(Base):
    __tablename__ = "unknown_faces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(String(500), nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    confidence = Column(Float, nullable=True)
    reviewed = Column(Boolean, default=False)
    converted_to_employee = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    camera = relationship("Camera")

    def __repr__(self) -> str:
        return f"<UnknownFace {self.id} @ {self.timestamp}>"


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    camera_index = Column(Integer, nullable=False, unique=True)
    location = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    attendance_records = relationship("Attendance", back_populates="camera")
    recognition_logs = relationship("RecognitionLog", back_populates="camera")
    unknown_faces = relationship("UnknownFace", back_populates="camera")

    def __repr__(self) -> str:
        return f"<Camera {self.id}: {self.name} (idx={self.camera_index})>"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    operator = Column(String(100), default="system")
    timestamp = Column(DateTime, default=_utcnow, nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)

    employee = relationship("Employee")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.operator} @ {self.timestamp}>"
