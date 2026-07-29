"""add scalability indexes

Revision ID: 9c4d2f6a7b11
Revises: 2a7c9e4f1b3d
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9c4d2f6a7b11"
down_revision: Union[str, None] = "2a7c9e4f1b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add read-path indexes for high-volume college workloads."""
    op.create_index("idx_student_name", "students", ["name"], unique=False)
    op.create_index(
        "idx_student_department_active",
        "students",
        ["department_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_attendance_student_timestamp",
        "attendance",
        ["student_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_attendance_camera_timestamp",
        "attendance",
        ["camera_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_recognition_camera_timestamp",
        "recognition_log",
        ["camera_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_unknown_camera_timestamp",
        "unknown_faces",
        ["camera_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_unknown_camera_reviewed",
        "unknown_faces",
        ["camera_id", "reviewed"],
        unique=False,
    )
    op.create_index(
        "idx_audit_actor_timestamp",
        "audit_logs",
        ["actor", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the added scalability indexes."""
    op.drop_index("idx_audit_actor_timestamp", table_name="audit_logs")
    op.drop_index("idx_unknown_camera_reviewed", table_name="unknown_faces")
    op.drop_index("idx_unknown_camera_timestamp", table_name="unknown_faces")
    op.drop_index("idx_recognition_camera_timestamp", table_name="recognition_log")
    op.drop_index("idx_attendance_camera_timestamp", table_name="attendance")
    op.drop_index("idx_attendance_student_timestamp", table_name="attendance")
    op.drop_index("idx_student_department_active", table_name="students")
    op.drop_index("idx_student_name", table_name="students")
