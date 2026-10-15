"""Persist arena support bot selections and match HP.

Revision ID: e91c7a50b62d
Revises: d87f17395e24

NULL means an existing match has no support bots, so no backfill is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e91c7a50b62d"
down_revision: str | None = "d87f17395e24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("arena_state", sa.Column("support_bots", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("arena_state", "support_bots")
