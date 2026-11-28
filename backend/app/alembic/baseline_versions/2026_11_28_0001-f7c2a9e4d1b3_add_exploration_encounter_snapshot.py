"""add the danger encounter snapshot to explorations

Revision ID: f7c2a9e4d1b3
Revises: b9d4e2f7a1c6
Create Date: 2026-11-28 00:01:00.000000

Stores the departure-time danger profile, thresholds, band and per-member damage so a mid-run
tuning change cannot alter the outcome. Existing runs stay NULL and resolve under the old binary rule.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "f7c2a9e4d1b3"
down_revision: str | Sequence[str] | None = "b9d4e2f7a1c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exploration", sa.Column("encounter_snapshot", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("exploration", "encounter_snapshot")
