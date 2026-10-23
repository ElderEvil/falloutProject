"""Retire the Staff the Radio Studio starter objective.

Revision ID: d6e8f0a2b4c9
Revises: e2f4a6c8d0b1

Standard starts omit the Radio Studio. Stop fresh assignment of its lesson while
preserving existing objective links, progress and rewards.
"""

from alembic import op

revision = "d6e8f0a2b4c9"
down_revision = "e2f4a6c8d0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE objective SET assignable = false WHERE template_key = 'starter:staff the radio'")


def downgrade() -> None:
    op.execute("UPDATE objective SET assignable = true WHERE template_key = 'starter:staff the radio'")
