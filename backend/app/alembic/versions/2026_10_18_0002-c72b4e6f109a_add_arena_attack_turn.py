"""Persist the next attacking Arena team.

Revision ID: c72b4e6f109a
Revises: f41c6d8a209b

Existing matches had simultaneous attacks, so no previous team turn exists.
Starting them at Team A is the correct backfill and matches new match selection.
"""

import sqlalchemy as sa
from alembic import op

revision = "c72b4e6f109a"
down_revision = "f41c6d8a209b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("arena_state", sa.Column("next_attack_team", sa.String(1), nullable=False, server_default="A"))


def downgrade() -> None:
    op.drop_column("arena_state", "next_attack_team")
