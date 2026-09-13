"""widen dweller bio for compiled life entries

Revision ID: b2c3d4e5f6a1
Revises: 9d2c4b6a8f1e
Create Date: 2026-09-13 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a1"
down_revision = "9d2c4b6a8f1e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "dweller",
        "bio",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "dweller",
        "bio",
        existing_type=sa.String(length=2048),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )
