"""add attendance idempotency key

Revision ID: b4e8c1d2f3a0
Revises: 9c4d2f6a7b11
Create Date: 2026-11-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4e8c1d2f3a0"
down_revision: Union[str, None] = "9c4d2f6a7b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable unique idempotency_key column on attendance (idempotent)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("attendance")}
    if "idempotency_key" not in cols:
        op.add_column(
            "attendance",
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )
    idxs = {i["name"] for i in inspector.get_indexes("attendance")}
    if "uq_attendance_idempotency_key" not in idxs:
        op.create_index(
            "uq_attendance_idempotency_key",
            "attendance",
            ["idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    """Remove attendance idempotency_key column and unique index (idempotent)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    idxs = {i["name"] for i in inspector.get_indexes("attendance")}
    if "uq_attendance_idempotency_key" in idxs:
        op.drop_index("uq_attendance_idempotency_key", table_name="attendance")
    cols = {c["name"] for c in inspector.get_columns("attendance")}
    if "idempotency_key" in cols:
        op.drop_column("attendance", "idempotency_key")
