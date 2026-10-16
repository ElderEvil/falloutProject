"""Clarify starter scrapping without changing progress or rewards.

Revision ID: d8e4c7a2b915
Revises: f1e2d3c4b5a6
"""

import sqlalchemy as sa
from alembic import op

revision = "d8e4c7a2b915"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    objective = sa.table(
        "objective", sa.column("template_key"), sa.column("challenge"), sa.column("description")
    )
    op.get_bind().execute(
        objective.update()
        .where(objective.c.template_key.in_(
            ["starter:reverse-engineer a schematic", "starter:reverse-engineer a schematic#v2"]
        ))
        .values(
            challenge="Scrap a rare weapon",
            description=(
                "Scrap a rare weapon from Storage to recover crafting materials. "
                "Only items with a locked recipe teach a new schematic."
            ),
        )
    )


def downgrade() -> None:
    """Keep corrected guidance; player progress and rewards were never changed."""
