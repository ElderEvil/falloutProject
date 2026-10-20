"""Retire the Staff the Radio Studio starter objective.

Revision ID: e4b8d2a6c1f9
Revises: c8a4d6e2f901
Create Date: 2026-10-23 00:00:00.000000

A standard vault no longer seeds a Radio Studio, and the room requires 20 dwellers
to build, so the objective was unachievable on a fresh vault. Existing links keep
their progress and rewards; only fresh assignment stops.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4b8d2a6c1f9"
down_revision: str | None = "c8a4d6e2f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEMPLATE_KEY = "starter:staff the radio"


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE objective SET assignable = false WHERE template_key = :key").bindparams(key=TEMPLATE_KEY)
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE objective SET assignable = true WHERE template_key = :key").bindparams(key=TEMPLATE_KEY)
    )
