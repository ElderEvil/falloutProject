"""add the world event terminal transition clock

Revision ID: e0c4a1b7f3d2
Revises: d9b3f7a1c4e8
Create Date: 2026-11-25 00:02:00.000000

``ends_at`` is the nominal end of the event window, and an event that reaches its target completes
early — a relay target can be met on day two of seven. The quiet day before the next relay has to
be measured from the moment the event actually finished, so that instant gets its own column
instead of being inferred from ``ends_at`` or ``updated_at`` (which any later write moves).

NULL is the correct value for every pre-existing row: open events have not finished, and finished
rows from before this column existed fall back to ``ends_at`` — the cooldown query reads
``finished_at or ends_at``. A backfill would have to invent a transition time that was never
recorded, so there is none. The add is metadata-only in PostgreSQL.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0c4a1b7f3d2"
down_revision: str | None = "d9b3f7a1c4e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("worldevent", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("worldevent", "finished_at")
