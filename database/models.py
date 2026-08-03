"""
SQLAlchemy ORM models for the Face Recognition AI database.

College Deployment Schema:
Tables:
    - institutions: College/University master records
    - departments: Academic departments
    - courses: Course catalog
    - sections: Course sections with timetables
    - classrooms: Physical locations
    - students: Student records
    - staff: Staff/Faculty records
    - employees: Employee records (for non-academic staff)
    - cameras: Multi-camera architecture with centralized credentials
    - enrollments: Student-course-section relationships
    - attendance: Timetable-aware attendance records
    - recognition_events: Detailed recognition logs
    - unknown_faces: Unknown face snapshots with retention policies
    - users: Authentication users
    - roles: RBAC roles
    - permissions: RBAC permissions
    - user_roles: User-to-role mappings
    - audit_logs: Comprehensive audit trail
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Table,
    JSON,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship, synonym


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


# ── Account Lockout Constants ────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30

# ── Association Tables ──────────────────────────────────────────────

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)


# ── RBAC Tables ─────────────────────────────────────────────────────


class RoleName(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    COLLEGE_ADMIN = "COLLEGE_ADMIN"
    HOD = "HOD"
    FACULTY = "FACULTY"
    SECURITY = "SECURITY"
    STUDENT = "STUDENT"
    STAFF = "STAFF"


class ActionType(str, Enum):
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    __table_args__ = (Index("idx_permission_resource_action", "resource", "action", unique=True),)

    def __repr__(self) -> str:
        return f"<Permission {self.resource}:{self.action}>"


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    permissions = relationship("Permission", secondary=role_permissions, backref="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # ── OIDC fields ────────────────────────────────────────────
    oidc_sub = Column(String(255), unique=True, nullable=True)  # OIDC subject identifier
    oidc_provider = Column(String(50), nullable=True)  # e.g. "azure", "keycloak", "google"
    auth_method = Column(String(20), default="local")  # "local" | "oidc" | "both"

    # ── MFA fields ─────────────────────────────────────────────
    is_mfa_enabled = Column(Boolean, default=False)
    mfa_totp_secret = Column(String(64), nullable=True)  # Base32-encoded TOTP secret
    mfa_backup_codes = Column(JSON, nullable=True)  # List of hashed backup codes
    mfa_last_verified = Column(DateTime, nullable=True)  # Last MFA verification time

    # ── Session tracking ───────────────────────────────────────
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    roles = relationship("Role", secondary=user_roles, back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class FailedLoginAttempt(Base):
    """Track failed login attempts for brute force protection."""

    __tablename__ = "failed_login_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    user_agent = Column(String(500), nullable=True)
    attempted_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
    success = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_failed_login_username_time", "username", "attempted_at"),
        Index("idx_failed_login_ip_time", "ip_address", "attempted_at"),
    )

    def __repr__(self) -> str:
        return f"<FailedLoginAttempt {self.username} from {self.ip_address} @ {self.attempted_at}>"


class RefreshToken(Base):
    """Persistent refresh tokens with rotation and revocation support."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by = Column(String(128), nullable=True)  # Token rotation chain
    device_info = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)

    user = relationship("User", foreign_keys=[user_id])

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return _utcnow() > self.expires_at  # type: ignore[return-value]

    __table_args__ = (Index("idx_refresh_token_user", "user_id", "revoked_at"),)

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} revoked={self.is_revoked}>"


# ── College Infrastructure Tables ───────────────────────────────────


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)

    departments = relationship("Department", back_populates="institution")

    def __repr__(self) -> str:
        return f"<Institution {self.name}>"


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(20), nullable=False)
    head_id = Column(
        Integer, ForeignKey("staff.id", name="fk_departments_head_id", use_alter=True), nullable=True
    )
    is_active = Column(Boolean, default=True)

    institution = relationship("Institution", back_populates="departments")
    head = relationship("Staff", foreign_keys=[head_id], primaryjoin="Department.head_id == Staff.id")
    courses = relationship("Course", back_populates="department")
    students = relationship("Student", back_populates="department")
    staff_members = relationship("Staff", back_populates="department", foreign_keys="Staff.department_id")

    __table_args__ = (Index("idx_department_inst_code", "institution_id", "code", unique=True),)

    def __repr__(self) -> str:
        return f"<Department {self.code}: {self.name}>"


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    credits = Column(Integer, default=3)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    department = relationship("Department", back_populates="courses", foreign_keys="Course.department_id")
    sections = relationship("Section", back_populates="course")
    # NOTE: Enrollments accessed via course.sections[*].enrollments (no direct FK on Enrollment)

    __table_args__ = (Index("idx_course_dept_code", "department_id", "code", unique=True),)

    def __repr__(self) -> str:
        return f"<Course {self.code}: {self.name}>"


class Classroom(Base):
    __tablename__ = "classrooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    building = Column(String(100), nullable=False)
    room_number = Column(String(20), nullable=False)
    capacity = Column(Integer, nullable=True)
    floor = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)

    institution = relationship("Institution")
    cameras = relationship("Camera", back_populates="classroom")
    attendance_records = relationship("Attendance", back_populates="classroom")
    # NOTE: Sections accessed via classroom.timetables[*].section (no direct FK on Section)

    __table_args__ = (Index("idx_classroom_building_room", "building", "room_number", unique=True),)

    def __repr__(self) -> str:
        return f"<Classroom {self.building}-{self.room_number}>"


class Timetable(Base):
    """Class schedule defining when and where courses are held."""

    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(String(8), nullable=False)  # HH:MM:SS
    end_time = Column(String(8), nullable=False)  # HH:MM:SS
    instructor_id = Column(Integer, ForeignKey("staff.id"), nullable=True)

    section = relationship("Section", back_populates="timetables")
    classroom = relationship("Classroom")
    instructor = relationship("Staff", foreign_keys=[instructor_id])

    __table_args__ = (
        Index("idx_timetable_section_day", "section_id", "day_of_week"),
        Index("idx_timetable_classroom_day_time", "classroom_id", "day_of_week", "start_time"),
    )

    def __repr__(self) -> str:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return f"<Timetable {self.section.code} @ {days[self.day_of_week]} {self.start_time}-{self.end_time}>"


# ── Student & Staff Tables ───────────────────────────────────────────────


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    enrollment_year = Column(Integer, nullable=True)
    graduation_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    department = relationship("Department", back_populates="students", foreign_keys="Student.department_id")
    enrollments = relationship("Enrollment", back_populates="student")
    attendances = relationship("Attendance", back_populates="student", foreign_keys="Attendance.student_id")

    __table_args__ = (
        Index("idx_student_id", "student_id", unique=True),
        Index("idx_student_name", "name"),
        Index("idx_student_department_active", "department_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Student {self.student_id}: {self.name}>"


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    position = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    department = relationship(
        "Department", back_populates="staff_members", foreign_keys="Staff.department_id"
    )
    attendances = relationship(
        "Attendance", back_populates="instructor", foreign_keys="Attendance.instructor_id"
    )

    __table_args__ = (Index("idx_staff_employee_id", "employee_id", unique=True),)

    def __repr__(self) -> str:
        return f"<Staff {self.employee_id}: {self.name}>"


class Employee(Base):
    """Legacy employee table - kept for backward compatibility."""

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    photo_path = Column(String(500), nullable=True)
    faiss_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    attendance_records = relationship("Attendance", back_populates="employee")
    audit_logs = relationship("AuditLog", back_populates="employee")
    recognition_logs = relationship(
        "RecognitionLog",
        back_populates="employee",
    )
    # NOTE: AuditLog.actor_id is not a direct FK to employees.id

    __table_args__ = (Index("idx_employee_id", "employee_id", unique=True),)

    def __repr__(self) -> str:
        return f"<Employee {self.employee_id}: {self.name}>"


# ── Section & Enrollment Tables ────────────────────────────────────────


class Section(Base):
    """Course section with timetable association."""

    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    section_name = Column(String(50), nullable=False)
    semester = Column(String(20), nullable=False)
    year = Column(Integer, nullable=False)
    max_capacity = Column(Integer, nullable=True)

    course = relationship("Course", back_populates="sections")
    timetables = relationship("Timetable", back_populates="section")
    enrollments = relationship("Enrollment", back_populates="section", foreign_keys="Enrollment.section_id")
    attendances = relationship("Attendance", back_populates="section", foreign_keys="Attendance.section_id")

    __table_args__ = (Index("idx_section_course_semester", "course_id", "semester", "year"),)

    def __repr__(self) -> str:
        return f"<Section {self.course.code}-{self.section_name} {self.year}/{self.semester}>"


class Enrollment(Base):
    """Student enrollment in a course section."""

    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    enrollment_date = Column(DateTime, default=_utcnow)
    status = Column(String(20), default="ACTIVE")

    student = relationship("Student", back_populates="enrollments")
    section = relationship("Section", back_populates="enrollments")

    __table_args__ = (Index("idx_enrollment_student_section", "student_id", "section_id", unique=True),)

    def __repr__(self) -> str:
        return f"<Enrollment {self.student.student_id} in {self.section.id}>"


# ── Multi-Camera Architecture Tables ───────────────────────────────────


class Camera(Base):
    """Camera configuration with centralized credential management."""

    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    camera_index = Column(Integer, nullable=True)
    camera_id = Column(String(50), unique=True, nullable=False)  # UUID or custom ID
    stream_url = Column(String(500), nullable=True)
    credential_ref = Column(String(255), nullable=True)  # Reference to secrets manager
    location = Column(String(200), nullable=True)
    building = Column(String(100), nullable=True)
    room = Column(String(50), nullable=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default="OFFLINE")
    last_seen = Column(DateTime, nullable=True)
    fps = Column(Integer, nullable=True)
    resolution = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    classroom = relationship("Classroom", back_populates="cameras")
    attendance_records = relationship("Attendance", back_populates="camera")
    recognition_logs = relationship("RecognitionLog", back_populates="camera")
    unknown_faces = relationship("UnknownFace", back_populates="camera")

    __table_args__ = (
        Index("idx_camera_id", "camera_id", unique=True),
        Index("idx_camera_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Camera {self.camera_id}: {self.name} ({self.status})>"


# ── Timetable-Aware Attendance Tables ─────────────────────────────────


class Attendance(Base):
    """Timetable-aware attendance record."""

    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Student recognition (primary source)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)

    # Timetable context
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    instructor_id = Column(Integer, ForeignKey("staff.id"), nullable=True)

    # Camera context
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)

    # Timing
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    recognized_at = Column(DateTime, nullable=True)

    # Recognition details
    confidence = Column(Float, nullable=False, default=1.0)
    method = Column(String(50), default="FACE_RECOGNITION")
    status = Column(String(20), default="PRESENT")

    # Manual override tracking
    marked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    marked_manually = Column(Boolean, default=False)
    manual_notes = Column(Text, nullable=True)

    # Relationships
    student = relationship("Student", back_populates="attendances")
    employee = relationship("Employee", back_populates="attendance_records")
    section = relationship("Section", back_populates="attendances")
    course = relationship("Course")
    classroom = relationship("Classroom", back_populates="attendance_records")
    instructor = relationship("Staff", foreign_keys=[instructor_id], back_populates="attendances")
    camera = relationship("Camera", back_populates="attendance_records")
    marked_by_user = relationship("User", foreign_keys=[marked_by_user_id])

    __table_args__ = (
        Index("idx_attendance_timestamp", "timestamp"),
        Index("idx_attendance_student_timestamp", "student_id", "timestamp"),
        Index("idx_attendance_student_section", "student_id", "section_id"),
        Index("idx_attendance_course_date", "course_id", "timestamp"),
        Index("idx_attendance_camera_timestamp", "camera_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Attendance {self.student_id or self.employee_id} @ {self.timestamp}>"


# ── Recognition & Unknown Face Tables ─────────────────────────────────


class RecognitionLog(Base):
    """Every recognition event - detailed log for analytics."""

    __tablename__ = "recognition_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    is_known = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=True)
    liveness_confidence = Column(Float, nullable=True)
    is_spoof = Column(Boolean, default=False)
    track_id = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=True)
    face_snapshot_path = Column(String(500), nullable=True)
    embedding_path = Column(String(500), nullable=True)
    frame_number = Column(Integer, nullable=True)
    processing_time_ms = Column(Float, nullable=True)

    employee = relationship(
        "Employee",
        back_populates="recognition_logs",
        foreign_keys=[employee_id],
    )
    student = relationship("Student", foreign_keys=[student_id])
    camera = relationship("Camera", back_populates="recognition_logs")
    classroom = relationship("Classroom")
    section = relationship("Section")

    __table_args__ = (
        Index("idx_recognition_timestamp", "timestamp"),
        Index("idx_recognition_is_known", "is_known"),
        Index("idx_recognition_employee", "employee_id"),
        Index("idx_recognition_student", "student_id"),
        Index("idx_recognition_camera_timestamp", "camera_id", "timestamp"),
    )

    def __repr__(self) -> str:
        if self.employee:
            name = self.employee.name
        elif self.student:
            name = self.student.name
        else:
            name = "Unknown"
        return f"<RecognitionLog {name} @ {self.timestamp}>"


class UnknownFace(Base):
    """Unknown face snapshots with retention policies."""

    __tablename__ = "unknown_faces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(String(500), nullable=False)
    embedding_path = Column(String(500), nullable=True)
    thumbnail_path = Column(String(500), nullable=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    liveness_score = Column(Float, nullable=True)
    track_id = Column(String(50), nullable=True)
    is_spoof = Column(Boolean, default=False)
    reviewed = Column(Boolean, default=False)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    converted_to_employee = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    retention_expires_at = Column(DateTime, nullable=True)
    face_metadata = Column(JSON, nullable=True)

    camera = relationship("Camera", back_populates="unknown_faces")
    classroom = relationship("Classroom")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    __table_args__ = (
        Index("idx_unknown_timestamp", "timestamp"),
        Index("idx_unknown_reviewed", "reviewed"),
        Index("idx_unknown_retention", "retention_expires_at"),
        Index("idx_unknown_camera_timestamp", "camera_id", "timestamp"),
        Index("idx_unknown_camera_reviewed", "camera_id", "reviewed"),
    )

    def __repr__(self) -> str:
        return f"<UnknownFace {self.id} @ {self.timestamp}>"


# ── Audit Logging Table ───────────────────────────────────────────────


class AuditAction(str, Enum):
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
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_CHANGE_FAILED = "PASSWORD_CHANGE_FAILED"
    RECOGNITION_EVENT = "RECOGNITION_EVENT"
    ATTENDANCE_SYNC = "ATTENDANCE_SYNC"


class AuditLog(Base):
    """Comprehensive audit trail for security and compliance."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=False)
    operator = synonym("actor")
    actor_type = Column(String(20), default="USER")  # USER, SYSTEM, SERVICE
    actor_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    employee_id = synonym("actor_id")
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    severity = Column(String(20), default="INFO")  # INFO, WARNING, ERROR, CRITICAL

    employee = relationship("Employee", foreign_keys=[actor_id], back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_actor", "actor"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_severity", "severity"),
        Index("idx_audit_actor_timestamp", "actor", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.actor} @ {self.timestamp}>"
