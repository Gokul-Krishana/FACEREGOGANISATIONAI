"""add failed login attempts table

Revision ID: 2a7c9e4f1b3d
Revises: 1bf6aa4e001c
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a7c9e4f1b3d'
down_revision: Union[str, None] = '1bf6aa4e001c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the failed_login_attempts table for brute force protection."""
    op.create_table(
        'failed_login_attempts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(100), nullable=False, index=True),
        sa.Column('ip_address', sa.String(45), nullable=False, index=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='0'),
    )
    # Composite indexes for efficient lockout and rate-limit queries
    op.create_index(
        'idx_failed_login_username_time',
        'failed_login_attempts',
        ['username', 'attempted_at'],
    )
    op.create_index(
        'idx_failed_login_ip_time',
        'failed_login_attempts',
        ['ip_address', 'attempted_at'],
    )


def downgrade() -> None:
    """Drop the failed_login_attempts table."""
    op.drop_index('idx_failed_login_ip_time', table_name='failed_login_attempts')
    op.drop_index('idx_failed_login_username_time', table_name='failed_login_attempts')
    op.drop_table('failed_login_attempts')
