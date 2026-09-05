"""add incident event journal

Revision ID: a8c1d2e3f4b5
Revises: 7c2d9f1a4b3e
Create Date: 2026-09-05 00:45:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "a8c1d2e3f4b5"
down_revision = "7c2d9f1a4b3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incident_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("message", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incident.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incident_event_incident_id"), "incident_event", ["incident_id"], unique=False)
    op.create_index(op.f("ix_incident_event_kind"), "incident_event", ["kind"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_incident_event_kind"), table_name="incident_event")
    op.drop_index(op.f("ix_incident_event_incident_id"), table_name="incident_event")
    op.drop_table("incident_event")
