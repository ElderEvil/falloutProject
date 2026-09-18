"""add outfit hazard resistance

Revision ID: 7b2c4d9e1f30
Revises: 3f8a1c7d9e20
Create Date: 2026-09-18 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "7b2c4d9e1f30"
down_revision = "3f8a1c7d9e20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outfit",
        sa.Column("fire_resist", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "outfit",
        sa.Column("radiation_resist", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outfit", "radiation_resist")
    op.drop_column("outfit", "fire_resist")
