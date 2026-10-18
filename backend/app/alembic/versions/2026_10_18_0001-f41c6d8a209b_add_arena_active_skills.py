"""Persist Arena skill charge and queued attacks.

Revision ID: f41c6d8a209b
Revises: b37d2a5f810c

Existing matches start at zero charge with no queued attack. NULL correctly
represents that initial state, so no semantic backfill is needed.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f41c6d8a209b"
down_revision = "b37d2a5f810c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("arena_state", sa.Column("skill_charge", postgresql.JSONB(), nullable=True))
    op.add_column("arena_state", sa.Column("queued_skill_ids", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("arena_state", "queued_skill_ids")
    op.drop_column("arena_state", "skill_charge")
