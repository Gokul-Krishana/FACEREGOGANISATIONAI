"""initial_schema

Revision ID: 1bf6aa4e001c
Revises:
Create Date: 2026-07-13 22:40:02.151173

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1bf6aa4e001c"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Create initial database schema if tables are not yet present."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "permissions" not in existing_tables:
        op.create_table(
            "permissions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("resource", sa.String(100), nullable=False),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
        )
        op.create_index("idx_permission_resource_action", "permissions", ["resource", "action"], unique=True)

    if "roles" not in existing_tables:
        op.create_table(
            "roles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(50), unique=True, nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
        )

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(100), unique=True, nullable=False),
            sa.Column("email", sa.String(255), unique=True, nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("oidc_sub", sa.String(255), unique=True, nullable=True),
            sa.Column("oidc_provider", sa.String(50), nullable=True),
            sa.Column("auth_method", sa.String(20), nullable=True),
            sa.Column("is_mfa_enabled", sa.Boolean(), nullable=True),
            sa.Column("mfa_totp_secret", sa.String(64), nullable=True),
            sa.Column("mfa_backup_codes", sa.JSON(), nullable=True),
            sa.Column("mfa_last_verified", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    if "user_roles" not in existing_tables:
        op.create_table(
            "user_roles",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True),
        )

    if "role_permissions" not in existing_tables:
        op.create_table(
            "role_permissions",
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True),
            sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id"), primary_key=True),
        )

    if "refresh_tokens" not in existing_tables:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token_hash", sa.String(128), unique=True, nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("replaced_by", sa.String(128), nullable=True),
            sa.Column("device_info", sa.String(255), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
        op.create_index("idx_refresh_token_user", "refresh_tokens", ["user_id", "revoked_at"], unique=False)

    if "institutions" not in existing_tables:
        op.create_table(
            "institutions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(20), unique=True, nullable=False),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
        )

    if "departments" not in existing_tables:
        op.create_table(
            "departments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("code", sa.String(20), nullable=False),
            sa.Column("head_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
        )
        op.create_index("idx_department_inst_code", "departments", ["institution_id", "code"], unique=True)

    if "staff" not in existing_tables:
        op.create_table(
            "staff",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("employee_id", sa.String(20), unique=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
            sa.Column("position", sa.String(100), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_staff_employee_id", "staff", ["employee_id"], unique=True)
        # Defer circular FK departments.head_id -> staff.id until staff exists (PostgreSQL supports ALTER TABLE)
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_departments_head_id",
                "departments",
                "staff",
                ["head_id"],
                ["id"],
            )

    if "courses" not in existing_tables:
        op.create_table(
            "courses",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("credits", sa.Integer(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
        )
        op.create_index("idx_course_dept_code", "courses", ["department_id", "code"], unique=True)

    if "classrooms" not in existing_tables:
        op.create_table(
            "classrooms",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("institution_id", sa.Integer(), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("building", sa.String(100), nullable=False),
            sa.Column("room_number", sa.String(20), nullable=False),
            sa.Column("capacity", sa.Integer(), nullable=True),
            sa.Column("floor", sa.String(20), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
        )
        op.create_index("idx_classroom_building_room", "classrooms", ["building", "room_number"], unique=True)

    if "students" not in existing_tables:
        op.create_table(
            "students",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("student_id", sa.String(20), unique=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("phone", sa.String(20), nullable=True),
            sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True),
            sa.Column("enrollment_year", sa.Integer(), nullable=True),
            sa.Column("graduation_year", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_student_id", "students", ["student_id"], unique=True)

    if "employees" not in existing_tables:
        op.create_table(
            "employees",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("employee_id", sa.String(20), unique=True, nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("department", sa.String(100), nullable=True),
            sa.Column("photo_path", sa.String(500), nullable=True),
            sa.Column("faiss_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_employee_id", "employees", ["employee_id"], unique=True)

    if "sections" not in existing_tables:
        op.create_table(
            "sections",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
            sa.Column("section_name", sa.String(50), nullable=False),
            sa.Column("semester", sa.String(20), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("max_capacity", sa.Integer(), nullable=True),
        )
        op.create_index(
            "idx_section_course_semester", "sections", ["course_id", "semester", "year"], unique=False
        )

    if "timetables" not in existing_tables:
        op.create_table(
            "timetables",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.id"), nullable=False),
            sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=False),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.String(8), nullable=False),
            sa.Column("end_time", sa.String(8), nullable=False),
            sa.Column("instructor_id", sa.Integer(), sa.ForeignKey("staff.id"), nullable=True),
        )
        op.create_index(
            "idx_timetable_section_day", "timetables", ["section_id", "day_of_week"], unique=False
        )
        op.create_index(
            "idx_timetable_classroom_day_time",
            "timetables",
            ["classroom_id", "day_of_week", "start_time"],
            unique=False,
        )

    if "enrollments" not in existing_tables:
        op.create_table(
            "enrollments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.id"), nullable=False),
            sa.Column("enrollment_date", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(20), nullable=True),
        )
        op.create_index(
            "idx_enrollment_student_section", "enrollments", ["student_id", "section_id"], unique=True
        )

    if "cameras" not in existing_tables:
        op.create_table(
            "cameras",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("camera_index", sa.Integer(), nullable=True),
            sa.Column("camera_id", sa.String(50), unique=True, nullable=False),
            sa.Column("stream_url", sa.String(500), nullable=True),
            sa.Column("credential_ref", sa.String(255), nullable=True),
            sa.Column("location", sa.String(200), nullable=True),
            sa.Column("building", sa.String(100), nullable=True),
            sa.Column("room", sa.String(50), nullable=True),
            sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("status", sa.String(20), nullable=True),
            sa.Column("last_seen", sa.DateTime(), nullable=True),
            sa.Column("fps", sa.Integer(), nullable=True),
            sa.Column("resolution", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("idx_camera_id", "cameras", ["camera_id"], unique=True)
        op.create_index("idx_camera_status", "cameras", ["status"], unique=False)

    if "attendance" not in existing_tables:
        op.create_table(
            "attendance",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.id"), nullable=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=True),
            sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=True),
            sa.Column("instructor_id", sa.Integer(), sa.ForeignKey("staff.id"), nullable=True),
            sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id"), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("recognized_at", sa.DateTime(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("method", sa.String(50), nullable=True),
            sa.Column("status", sa.String(20), nullable=True),
            sa.Column("marked_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("marked_manually", sa.Boolean(), nullable=True),
            sa.Column("manual_notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_attendance_timestamp", "attendance", ["timestamp"], unique=False)
        op.create_index("idx_attendance_timestamp", "attendance", ["timestamp"], unique=False)
        op.create_index(
            "idx_attendance_student_section", "attendance", ["student_id", "section_id"], unique=False
        )
        op.create_index("idx_attendance_course_date", "attendance", ["course_id", "timestamp"], unique=False)

    if "recognition_log" not in existing_tables:
        op.create_table(
            "recognition_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("is_known", sa.Boolean(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("liveness_confidence", sa.Float(), nullable=True),
            sa.Column("is_spoof", sa.Boolean(), nullable=True),
            sa.Column("track_id", sa.String(50), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id"), nullable=True),
            sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=True),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("sections.id"), nullable=True),
            sa.Column("face_snapshot_path", sa.String(500), nullable=True),
            sa.Column("embedding_path", sa.String(500), nullable=True),
            sa.Column("frame_number", sa.Integer(), nullable=True),
            sa.Column("processing_time_ms", sa.Float(), nullable=True),
        )
        op.create_index("ix_recognition_log_timestamp", "recognition_log", ["timestamp"], unique=False)
        op.create_index("idx_recognition_timestamp", "recognition_log", ["timestamp"], unique=False)
        op.create_index("idx_recognition_is_known", "recognition_log", ["is_known"], unique=False)
        op.create_index("idx_recognition_employee", "recognition_log", ["employee_id"], unique=False)
        op.create_index("idx_recognition_student", "recognition_log", ["student_id"], unique=False)

    if "unknown_faces" not in existing_tables:
        op.create_table(
            "unknown_faces",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("image_path", sa.String(500), nullable=False),
            sa.Column("embedding_path", sa.String(500), nullable=True),
            sa.Column("thumbnail_path", sa.String(500), nullable=True),
            sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id"), nullable=True),
            sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id"), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("liveness_score", sa.Float(), nullable=True),
            sa.Column("track_id", sa.String(50), nullable=True),
            sa.Column("is_spoof", sa.Boolean(), nullable=True),
            sa.Column("reviewed", sa.Boolean(), nullable=True),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("converted_to_employee", sa.Boolean(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("retention_expires_at", sa.DateTime(), nullable=True),
            sa.Column("face_metadata", sa.JSON(), nullable=True),
        )
        op.create_index("idx_unknown_timestamp", "unknown_faces", ["timestamp"], unique=False)
        op.create_index("idx_unknown_reviewed", "unknown_faces", ["reviewed"], unique=False)
        op.create_index("idx_unknown_retention", "unknown_faces", ["retention_expires_at"], unique=False)

    # Refresh inspector after potential table creation
    inspector = sa.inspect(bind)
    if "unknown_faces" in set(inspector.get_table_names()) and not _has_index(
        inspector, "unknown_faces", op.f("ix_unknown_faces_timestamp")
    ):
        op.create_index(op.f("ix_unknown_faces_timestamp"), "unknown_faces", ["timestamp"], unique=False)

    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("actor", sa.String(100), nullable=False),
            sa.Column("actor_type", sa.String(20), nullable=True),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False),
            sa.Column("resource_type", sa.String(50), nullable=True),
            sa.Column("resource_id", sa.Integer(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.String(500), nullable=True),
            sa.Column("request_id", sa.String(100), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("severity", sa.String(20), nullable=True),
        )
        op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)
        op.create_index("idx_audit_timestamp", "audit_logs", ["timestamp"], unique=False)
        op.create_index("idx_audit_actor", "audit_logs", ["actor"], unique=False)
        op.create_index("idx_audit_action", "audit_logs", ["action"], unique=False)
        op.create_index("idx_audit_severity", "audit_logs", ["severity"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "unknown_faces" in existing_tables and _has_index(
        inspector, "unknown_faces", op.f("ix_unknown_faces_timestamp")
    ):
        op.drop_index(op.f("ix_unknown_faces_timestamp"), table_name="unknown_faces")

    if "departments" in existing_tables and bind.dialect.name != "sqlite":
        fk_names = {fk["name"] for fk in inspector.get_foreign_keys("departments") if fk.get("name")}
        if "fk_departments_head_id" in fk_names:
            op.drop_constraint("fk_departments_head_id", "departments", type_="foreignkey")

    for table in (
        "audit_logs",
        "unknown_faces",
        "recognition_log",
        "attendance",
        "cameras",
        "enrollments",
        "timetables",
        "sections",
        "employees",
        "students",
        "classrooms",
        "courses",
        "staff",
        "departments",
        "institutions",
        "refresh_tokens",
        "role_permissions",
        "user_roles",
        "users",
        "roles",
        "permissions",
    ):
        if table in existing_tables:
            op.drop_table(table)
