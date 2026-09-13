"""add bio_entries to dweller for living biographies

Revision ID: 9d2c4b6a8f1e
Revises: c8f5d2b0e3a4
Create Date: 2026-09-13 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "9d2c4b6a8f1e"
down_revision = "c8f5d2b0e3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dweller",
        sa.Column("bio_entries", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("dweller", "bio_entries")
