"""Add an independently versioned road layer without regenerating geography.

Revision ID: d9a3b2c4e5f6
Revises: c8f2a1b3d4e5

Existing worlds deliberately remain NULL (not generated), not a misleading empty
network. Populate them explicitly with `fo-cli backfill world-roads` after upgrading.
Keeping procedural generation out of this migration avoids changing historical
migration output when a future road recipe ships.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d9a3b2c4e5f6"
down_revision = "c8f2a1b3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("worldsnapshot", sa.Column("roads", postgresql.JSONB(none_as_null=True), nullable=True))


def downgrade() -> None:
    op.drop_column("worldsnapshot", "roads")
