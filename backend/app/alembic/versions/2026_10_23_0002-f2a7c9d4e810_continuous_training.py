"""Add an opt-in, vault-wide continuous training setting.

Revision ID: f2a7c9d4e810
Revises: c8a4d6e2f901
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a7c9d4e810"
down_revision = "c8a4d6e2f901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing vaults keep single-round behavior until their owner opts in.
    op.add_column("vault", sa.Column("continuous_training", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("vault", "continuous_training")
