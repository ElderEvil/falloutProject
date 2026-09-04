"""align incident event timestamp nullability

Revision ID: c0d1e2f3a4b5
Revises: b9d2e3f4a5b6
Create Date: 2026-09-05 02:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "b9d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("incident_event", "created_at", existing_type=sa.DateTime(), nullable=True)
    op.alter_column("incident_event", "updated_at", existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    op.alter_column("incident_event", "updated_at", existing_type=sa.DateTime(), nullable=False)
    op.alter_column("incident_event", "created_at", existing_type=sa.DateTime(), nullable=False)
