"""add magazine buffs and the site read clock

Revision ID: d9b3f7a1c4e8
Revises: c1a5e8b4d902
Create Date: 2026-11-24 00:01:00.000000

Magazines are read, not collected: ``dweller.magazine_buff`` holds the one timed +SPECIAL buff a
dweller is carrying, and ``vaultlocationstate.last_read_at`` is the fixed 24h site clock that lets
a magazine place be reread. Both are NULL for every existing row, which is the correct "nobody has
read a magazine yet" state, so no backfill. Both adds are metadata-only in PG.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9b3f7a1c4e8"
down_revision: str | None = "c1a5e8b4d902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dweller", sa.Column("magazine_buff", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("vaultlocationstate", sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("vaultlocationstate", "last_read_at")
    op.drop_column("dweller", "magazine_buff")
