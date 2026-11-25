"""add the permanent magazine boon

Revision ID: d9b3f7a1c4e8
Revises: c1a5e8b4d902
Create Date: 2026-11-24 00:01:00.000000

A magazine is a one-time find, not a repeatable read: ``dweller.magazine_boon`` holds the permanent
+SPECIAL point its finder keeps (``{"key", "stat", "amount"}``, no expiry) and the site closes on the
claim exactly like a bobblehead or comic, so there is no read clock to add. NULL is the correct
"no magazine found yet" state for every existing row, so no backfill. The add is metadata-only in PG.
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
    op.add_column("dweller", sa.Column("magazine_boon", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("dweller", "magazine_boon")
