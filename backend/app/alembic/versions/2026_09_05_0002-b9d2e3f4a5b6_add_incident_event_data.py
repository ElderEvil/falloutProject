"""add incident event data

Revision ID: b9d2e3f4a5b6
Revises: a8c1d2e3f4b5
Create Date: 2026-09-05 01:15:00.000000
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b9d2e3f4a5b6"
down_revision = "a8c1d2e3f4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("incident_event", sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("incident_event", "data")
