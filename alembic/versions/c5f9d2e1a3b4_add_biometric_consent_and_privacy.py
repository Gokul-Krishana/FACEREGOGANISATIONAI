"""add biometric consent and privacy columns

Revision ID: c5f9d2e1a3b4
Revises: b4e8c1d2f3a0
Create Date: 2026-11-23

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5f9d2e1a3b4"
down_revision: Union[str, None] = "b4e8c1d2f3a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable biometric consent and data retention columns (idempotent)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    for tbl in ("employees", "students", "staff"):
        if tbl in table_names:
            cols = {c["name"] for c in inspector.get_columns(tbl)}
            if "consent_given" not in cols:
                op.add_column(
                    tbl,
                    sa.Column("consent_given", sa.Boolean(), nullable=True, server_default=sa.true()),
                )
            if "consent_date" not in cols:
                op.add_column(
                    tbl,
                    sa.Column("consent_date", sa.DateTime(), nullable=True),
                )
            if "retention_policy_days" not in cols:
                op.add_column(
                    tbl,
                    sa.Column("retention_policy_days", sa.Integer(), nullable=True, server_default="365"),
                )


def downgrade() -> None:
    """Remove biometric consent and data retention columns (idempotent)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    for tbl in ("employees", "students", "staff"):
        if tbl in table_names:
            cols = {c["name"] for c in inspector.get_columns(tbl)}
            if "retention_policy_days" in cols:
                op.drop_column(tbl, "retention_policy_days")
            if "consent_date" in cols:
                op.drop_column(tbl, "consent_date")
            if "consent_given" in cols:
                op.drop_column(tbl, "consent_given")
