"""add exit request state

Revision ID: b1c2d3e4f5a6
Revises: 9f0a1b2c3d4e
Create Date: 2026-09-29 00:00:00.000000

Refusal becomes a real decision (see ``.omo/plans/exit-request-refusal.md``):
``vault.last_exit_request_at`` throttles asks to the daily cap, and
``dweller.despair_since`` records when a dweller first fell to the despair
threshold so they must stay unhappy for a grace period before asking.

Both columns are nullable and ``NULL`` is the correct "never" state for every
existing row — it is distinguishable from real data, so no backfill is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "9f0a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vault", sa.Column("last_exit_request_at", sa.DateTime(), nullable=True))
    op.add_column("dweller", sa.Column("despair_since", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("dweller", "despair_since")
    op.drop_column("vault", "last_exit_request_at")
