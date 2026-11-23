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
from typing import Any, List, Optional

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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, synonym


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_permission_resource_action", "resource", "action", unique=True),)

    def __repr__(self) -> str:
        return f"<Permission {self.resource}:{self.action}>"


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    permissions: Mapped[List["Permission"]] = relationship(
        "Permission", secondary=role_permissions, backref="roles"
    )
    users: Mapped[List["User"]] = relationship("User", secondary=user_roles, back_populates="roles")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── OIDC fields ────────────────────────────────────────────
    oidc_sub: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )  # OIDC subject identifier
    oidc_provider: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # e.g. "azure", "keycloak", "google"
    auth_method: Mapped[str] = mapped_column(
        String(20), default="local", nullable=True
    )  # "local" | "oidc" | "both"

    # ── MFA fields ─────────────────────────────────────────────
    is_mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    mfa_totp_secret: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )  # Base32-encoded TOTP secret
    mfa_backup_codes: Mapped[Optional[Any]] = mapped_column(
        JSON, nullable=True
    )  # List of hashed backup codes
    mfa_last_verified: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )  # Last MFA verification time

    # ── Session tracking ───────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=True)

    roles: Mapped[List["Role"]] = relationship("Role", secondary=user_roles, back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class FailedLoginAttempt(Base):
    """Track failed login attempts for brute force protection."""

    __tablename__ = "failed_login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    __table_args__ = (
        Index("idx_failed_login_username_time", "username", "attempted_at"),
        Index("idx_failed_login_ip_time", "ip_address", "attempted_at"),
    )

    def __repr__(self) -> str:
        return f"<FailedLoginAttempt {self.username} from {self.ip_address} @ {self.attempted_at}>"


class RefreshToken(Base):
    """Persistent refresh tokens with rotation and revocation support."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    replaced_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # Token rotation chain
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return _utcnow() > self.expires_at

    __table_args__ = (Index("idx_refresh_token_user", "user_id", "revoked_at"),)

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} revoked={self.is_revoked}>"


# ── College Infrastructure Tables ───────────────────────────────────


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    departments: Mapped[List["Department"]] = relationship("Department", back_populates="institution")

    def __repr__(self) -> str:
        return f"<Institution {self.name}>"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    institution_id: Mapped[int] = mapped_column(Integer, ForeignKey("institutions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    head_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("staff.id", name="fk_departments_head_id", use_alter=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    institution: Mapped["Institution"] = relationship("Institution", back_populates="departments")
    head: Mapped[Optional["Staff"]] = relationship(
        "Staff", foreign_keys=[head_id], primaryjoin="Department.head_id == Staff.id"
    )
    courses: Mapped[List["Course"]] = relationship("Course", back_populates="department")
    students: Mapped[List["Student"]] = relationship("Student", back_populates="department")
    staff_members: Mapped[List["Staff"]] = relationship(
        "Staff", back_populates="department", foreign_keys="Staff.department_id"
    )

    __table_args__ = (Index("idx_department_inst_code", "institution_id", "code", unique=True),)

    def __repr__(self) -> str:
        return f"<Department {self.code}: {self.name}>"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=3, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    department: Mapped["Department"] = relationship(
        "Department", back_populates="courses", foreign_keys="Course.department_id"
    )
    sections: Mapped[List["Section"]] = relationship("Section", back_populates="course")
    # NOTE: Enrollments accessed via course.sections[*].enrollments (no direct FK on Enrollment)

    __table_args__ = (Index("idx_course_dept_code", "department_id", "code", unique=True),)

    def __repr__(self) -> str:
        return f"<Course {self.code}: {self.name}>"


class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    institution_id: Mapped[int] = mapped_column(Integer, ForeignKey("institutions.id"), nullable=False)
    building: Mapped[str] = mapped_column(String(100), nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    floor: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)

    institution: Mapped["Institution"] = relationship("Institution")
    cameras: Mapped[List["Camera"]] = relationship("Camera", back_populates="classroom")
    attendance_records: Mapped[List["Attendance"]] = relationship("Attendance", back_populates="classroom")
    # NOTE: Sections accessed via classroom.timetables[*].section (no direct FK on Section)

    __table_args__ = (Index("idx_classroom_building_room", "building", "room_number", unique=True),)

    def __repr__(self) -> str:
        return f"<Classroom {self.building}-{self.room_number}>"


class Timetable(Base):
    """Class schedule defining when and where courses are held."""

    __tablename__ = "timetables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("sections.id"), nullable=False)
    classroom_id: Mapped[int] = mapped_column(Integer, ForeignKey("classrooms.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)  # HH:MM:SS
    end_time: Mapped[str] = mapped_column(String(8), nullable=False)  # HH:MM:SS
    instructor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    section: Mapped["Section"] = relationship("Section", back_populates="timetables")
    classroom: Mapped["Classroom"] = relationship("Classroom")
    instructor: Mapped[Optional["Staff"]] = relationship("Staff", foreign_keys=[instructor_id])

    __table_args__ = (
        Index("idx_timetable_section_day", "section_id", "day_of_week"),
        Index("idx_timetable_classroom_day_time", "classroom_id", "day_of_week", "start_time"),
    )

    def __repr__(self) -> str:
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return f"<Timetable section={self.section_id} @ {days[self.day_of_week]} {self.start_time}-{self.end_time}>"


# ── Student & Staff Tables ───────────────────────────────────────────────


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)
    enrollment_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    graduation_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    consent_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=_utcnow, nullable=True)
    retention_policy_days: Mapped[Optional[int]] = mapped_column(Integer, default=365, nullable=True)

    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="students", foreign_keys="Student.department_id"
    )
    enrollments: Mapped[List["Enrollment"]] = relationship("Enrollment", back_populates="student")
    attendances: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="student", foreign_keys="Attendance.student_id"
    )

    __table_args__ = (
        Index("idx_student_id", "student_id", unique=True),
        Index("idx_student_name", "name"),
        Index("idx_student_department_active", "department_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Student {self.student_id}: {self.name}>"


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    consent_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=_utcnow, nullable=True)
    retention_policy_days: Mapped[Optional[int]] = mapped_column(Integer, default=365, nullable=True)

    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="staff_members", foreign_keys="Staff.department_id"
    )
    attendances: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="instructor", foreign_keys="Attendance.instructor_id"
    )

    __table_args__ = (Index("idx_staff_employee_id", "employee_id", unique=True),)

    def __repr__(self) -> str:
        return f"<Staff {self.employee_id}: {self.name}>"


class Employee(Base):
    """Legacy employee table - kept for backward compatibility."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    photo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    faiss_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    consent_date: Mapped[Optional[datetime]] = mapped_column(DateTime, default=_utcnow, nullable=True)
    retention_policy_days: Mapped[Optional[int]] = mapped_column(Integer, default=365, nullable=True)

    attendance_records: Mapped[List["Attendance"]] = relationship("Attendance", back_populates="employee")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="employee")
    recognition_logs: Mapped[List["RecognitionLog"]] = relationship(
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    section_name: Mapped[str] = mapped_column(String(50), nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    max_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    course: Mapped["Course"] = relationship("Course", back_populates="sections")
    timetables: Mapped[List["Timetable"]] = relationship("Timetable", back_populates="section")
    enrollments: Mapped[List["Enrollment"]] = relationship(
        "Enrollment", back_populates="section", foreign_keys="Enrollment.section_id"
    )
    attendances: Mapped[List["Attendance"]] = relationship(
        "Attendance", back_populates="section", foreign_keys="Attendance.section_id"
    )

    __table_args__ = (Index("idx_section_course_semester", "course_id", "semester", "year"),)

    def __repr__(self) -> str:
        return f"<Section {self.course.code}-{self.section_name} {self.year}/{self.semester}>"


class Enrollment(Base):
    """Student enrollment in a course section."""

    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("sections.id"), nullable=False)
    enrollment_date: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="enrollments")
    section: Mapped["Section"] = relationship("Section", back_populates="enrollments")

    __table_args__ = (Index("idx_enrollment_student_section", "student_id", "section_id", unique=True),)

    def __repr__(self) -> str:
        return f"<Enrollment {self.student.student_id} in {self.section.id}>"


# ── Multi-Camera Architecture Tables ───────────────────────────────────


class Camera(Base):
    """Camera configuration with centralized credential management."""

    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    camera_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    camera_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # UUID or custom ID
    stream_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    credential_ref: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Reference to secrets manager
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    building: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    classroom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("classrooms.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="OFFLINE", nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=True)

    classroom: Mapped[Optional["Classroom"]] = relationship("Classroom", back_populates="cameras")
    attendance_records: Mapped[List["Attendance"]] = relationship("Attendance", back_populates="camera")
    recognition_logs: Mapped[List["RecognitionLog"]] = relationship("RecognitionLog", back_populates="camera")
    unknown_faces: Mapped[List["UnknownFace"]] = relationship("UnknownFace", back_populates="camera")

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Student recognition (primary source)
    student_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("students.id"), nullable=True)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id"), nullable=True)

    # Timetable context
    section_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sections.id"), nullable=True)
    course_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("courses.id"), nullable=True)
    classroom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("classrooms.id"), nullable=True)
    instructor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("staff.id"), nullable=True)

    # Camera context
    camera_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=True)

    # Timing
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    recognized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Recognition details
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    method: Mapped[str] = mapped_column(String(50), default="FACE_RECOGNITION", nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PRESENT", nullable=True)
    # Nullable unique key used by atomic daily attendance marking so concurrent
    # cameras cannot insert duplicate rows for the same person on the same day.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Manual override tracking
    marked_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    marked_manually: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    manual_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped[Optional["Student"]] = relationship("Student", back_populates="attendances")
    employee: Mapped[Optional["Employee"]] = relationship("Employee", back_populates="attendance_records")
    section: Mapped[Optional["Section"]] = relationship("Section", back_populates="attendances")
    course: Mapped[Optional["Course"]] = relationship("Course")
    classroom: Mapped[Optional["Classroom"]] = relationship("Classroom", back_populates="attendance_records")
    instructor: Mapped[Optional["Staff"]] = relationship(
        "Staff", foreign_keys=[instructor_id], back_populates="attendances"
    )
    camera: Mapped[Optional["Camera"]] = relationship("Camera", back_populates="attendance_records")
    marked_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[marked_by_user_id])

    __table_args__ = (
        Index("idx_attendance_timestamp", "timestamp"),
        Index("idx_attendance_student_timestamp", "student_id", "timestamp"),
        Index("idx_attendance_student_section", "student_id", "section_id"),
        Index("idx_attendance_course_date", "course_id", "timestamp"),
        Index("idx_attendance_camera_timestamp", "camera_id", "timestamp"),
        Index("uq_attendance_idempotency_key", "idempotency_key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Attendance {self.student_id or self.employee_id} @ {self.timestamp}>"


# ── Recognition & Unknown Face Tables ─────────────────────────────────


class RecognitionLog(Base):
    """Every recognition event - detailed log for analytics."""

    __tablename__ = "recognition_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id"), nullable=True)
    student_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("students.id"), nullable=True)
    is_known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liveness_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_spoof: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    track_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    camera_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=True)
    classroom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("classrooms.id"), nullable=True)
    section_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sections.id"), nullable=True)
    face_snapshot_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    embedding_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    frame_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processing_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        back_populates="recognition_logs",
        foreign_keys=[employee_id],
    )
    student: Mapped[Optional["Student"]] = relationship("Student", foreign_keys=[student_id])
    camera: Mapped[Optional["Camera"]] = relationship("Camera", back_populates="recognition_logs")
    classroom: Mapped[Optional["Classroom"]] = relationship("Classroom")
    section: Mapped[Optional["Section"]] = relationship("Section")

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    embedding_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    camera_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=True)
    classroom_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("classrooms.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    track_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_spoof: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    converted_to_employee: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retention_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    face_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    camera: Mapped[Optional["Camera"]] = relationship("Camera", back_populates="unknown_faces")
    classroom: Mapped[Optional["Classroom"]] = relationship("Classroom")
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])

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
    CONSENT_UPDATED = "CONSENT_UPDATED"
    BIOMETRIC_SHREDDED = "BIOMETRIC_SHREDDED"


class AuditLog(Base):
    """Comprehensive audit trail for security and compliance."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = synonym("actor")
    actor_type: Mapped[str] = mapped_column(
        String(20), default="USER", nullable=True
    )  # USER, SYSTEM, SERVICE
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id"), nullable=True)
    employee_id: Mapped[Optional[int]] = synonym("actor_id")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(20), default="INFO", nullable=True
    )  # INFO, WARNING, ERROR, CRITICAL

    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee", foreign_keys=[actor_id], back_populates="audit_logs"
    )

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_actor", "actor"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_severity", "severity"),
        Index("idx_audit_actor_timestamp", "actor", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.actor} @ {self.timestamp}>"
