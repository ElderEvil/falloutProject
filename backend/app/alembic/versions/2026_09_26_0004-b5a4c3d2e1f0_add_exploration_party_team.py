"""Add exploration party teams (issue 772, phase 3).

Revision ID: b5a4c3d2e1f0
Revises: a3b4c5d6e7f8
Create Date: 2026-09-26 00:04:00.000000

A dispatched party reuses the ``team``/``team_member`` roster: ``team`` gains
``exploration_id`` (a plain indexed UUID, deliberately NOT a foreign key — a
real FK would create a team -> exploration -> team cycle that breaks
``SQLModel.metadata.create_all`` on SQLite, which the test suite uses) and
``exploration`` gains ``team_id`` (a real FK, SET NULL so deleting the team at
finalize never orphans the run's history). ``ck_team_one_purpose`` widens from
three-way to four-way: exactly one of quest/incident/hazard/exploration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5a4c3d2e1f0"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Four-way purpose check: exactly one of quest/incident/hazard/exploration is set.
FOUR_WAY_PURPOSE_CHECK = (
    "(CASE WHEN quest_id IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN incident_id IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN hazard_team IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN exploration_id IS NOT NULL THEN 1 ELSE 0 END) = 1"
)
#: The three-way form restored on downgrade.
THREE_WAY_PURPOSE_CHECK = (
    "(CASE WHEN quest_id IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN incident_id IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN hazard_team IS NOT NULL THEN 1 ELSE 0 END) = 1"
)


def upgrade() -> None:
    op.add_column("team", sa.Column("exploration_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_team_exploration_id"), "team", ["exploration_id"], unique=False)
    op.create_unique_constraint("uq_team_vault_exploration", "team", ["vault_id", "exploration_id"])
    op.drop_constraint("ck_team_one_purpose", "team", type_="check")
    op.create_check_constraint("ck_team_one_purpose", "team", FOUR_WAY_PURPOSE_CHECK)

    op.add_column("exploration", sa.Column("team_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_exploration_team_id",
        "exploration",
        "team",
        ["team_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_exploration_team_id"), "exploration", ["team_id"], unique=False)


def downgrade() -> None:
    # Party rows would violate the restored three-way check, so drop them first.
    op.execute(sa.text("DELETE FROM team WHERE exploration_id IS NOT NULL"))

    op.drop_index(op.f("ix_exploration_team_id"), table_name="exploration")
    op.drop_constraint("fk_exploration_team_id", "exploration", type_="foreignkey")
    op.drop_column("exploration", "team_id")

    op.drop_constraint("uq_team_vault_exploration", "team", type_="unique")
    op.drop_constraint("ck_team_one_purpose", "team", type_="check")
    op.create_check_constraint("ck_team_one_purpose", "team", THREE_WAY_PURPOSE_CHECK)
    op.drop_index(op.f("ix_team_exploration_id"), table_name="team")
    op.drop_column("team", "exploration_id")