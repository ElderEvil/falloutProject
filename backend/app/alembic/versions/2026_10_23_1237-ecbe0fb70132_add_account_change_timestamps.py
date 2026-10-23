"""Add per-field account change timestamps.

Revision ID: ecbe0fb70132
Revises: c4e8f6a1b2d3
Create Date: 2026-10-23 12:37:48.232475
"""

import sqlalchemy as sa
from alembic import op

revision = "ecbe0fb70132"
down_revision = "c4e8f6a1b2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("username_changed_at", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("email_changed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "email_changed_at")
    op.drop_column("user", "username_changed_at")
