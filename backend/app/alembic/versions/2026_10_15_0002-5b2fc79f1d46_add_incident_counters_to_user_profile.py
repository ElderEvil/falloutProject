"""Add incident counters to user_profile (incident balance batch).

Revision ID: 5b2fc79f1d46
Revises: 8ea4b5cffb08
Create Date: 2026-10-15 00:00:00.000000

Lifetime per-user incident counters (spawned/won/lost), following the
existing total_* statistics pattern. Non-nullable with zero defaults, so no
backfill: every past incident simply predates counting.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b2fc79f1d46"
down_revision: str | None = "8ea4b5cffb08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("userprofile", sa.Column("total_incidents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("total_incidents_won", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("total_incidents_lost", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("userprofile", "total_incidents_lost")
    op.drop_column("userprofile", "total_incidents_won")
    op.drop_column("userprofile", "total_incidents")
