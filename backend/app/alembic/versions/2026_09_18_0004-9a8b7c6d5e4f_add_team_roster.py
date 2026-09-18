"""add team roster primitive and backfill quest parties

Revision ID: 9a8b7c6d5e4f
Revises: c3d4e5f6a7b8
Create Date: 2026-09-18 00:00:00.000000

Expand/contract slice 1: create the reusable ``team``/``team_member`` roster and
copy every ``quest_party`` row into it. The legacy ``quest_party`` table is left
untouched for a later release to drop.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "9a8b7c6d5e4f"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Uuid(), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incident.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quest_id"], ["quest.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vault_id", "quest_id", name="uq_team_vault_quest"),
        sa.UniqueConstraint("vault_id", "incident_id", name="uq_team_vault_incident"),
        sa.CheckConstraint(
            "(CASE WHEN quest_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN incident_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_team_one_purpose",
        ),
    )
    op.create_index(op.f("ix_team_id"), "team", ["id"], unique=False)
    op.create_index(op.f("ix_team_vault_id"), "team", ["vault_id"], unique=False)
    op.create_index(op.f("ix_team_quest_id"), "team", ["quest_id"], unique=False)
    op.create_index(op.f("ix_team_incident_id"), "team", ["incident_id"], unique=False)

    op.create_table(
        "team_member",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "dweller_id", name="uq_team_member_dweller"),
        sa.UniqueConstraint("team_id", "slot_number", name="uq_team_member_slot"),
    )
    op.create_index(op.f("ix_team_member_id"), "team_member", ["id"], unique=False)
    op.create_index(op.f("ix_team_member_team_id"), "team_member", ["team_id"], unique=False)
    op.create_index(op.f("ix_team_member_dweller_id"), "team_member", ["dweller_id"], unique=False)

    # Backfill one team per (vault, quest), then its members. quest_party is NOT dropped.
    op.execute(
        sa.text(
            "INSERT INTO team (id, vault_id, quest_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), vault_id, quest_id, MIN(created_at), MAX(updated_at) "
            "FROM quest_party GROUP BY vault_id, quest_id"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO team_member (id, team_id, dweller_id, slot_number, status, created_at, updated_at) "
            "SELECT gen_random_uuid(), t.id, qp.dweller_id, qp.slot_number, qp.status, qp.created_at, qp.updated_at "
            "FROM quest_party qp "
            "JOIN team t ON t.vault_id = qp.vault_id AND t.quest_id = qp.quest_id"
        )
    )


def downgrade() -> None:
    # Rebuild the legacy quest_party table from the current quest teams so
    # assignments made after the cutover survive a rollback. No-op when the
    # table is absent (e.g. a fresh DB that never ran the legacy migration).
    if op.get_bind().dialect.has_table(op.get_bind(), "quest_party"):
        op.execute(sa.text("DELETE FROM quest_party"))
        op.execute(
            sa.text(
                "INSERT INTO quest_party (id, quest_id, vault_id, dweller_id, slot_number, status, created_at, updated_at) "
                "SELECT gen_random_uuid(), t.quest_id, t.vault_id, tm.dweller_id, tm.slot_number, tm.status, "
                "tm.created_at, tm.updated_at "
                "FROM team_member tm JOIN team t ON t.id = tm.team_id "
                "WHERE t.quest_id IS NOT NULL"
            )
        )

    op.drop_index(op.f("ix_team_member_dweller_id"), table_name="team_member")
    op.drop_index(op.f("ix_team_member_team_id"), table_name="team_member")
    op.drop_index(op.f("ix_team_member_id"), table_name="team_member")
    op.drop_table("team_member")

    op.drop_index(op.f("ix_team_incident_id"), table_name="team")
    op.drop_index(op.f("ix_team_quest_id"), table_name="team")
    op.drop_index(op.f("ix_team_vault_id"), table_name="team")
    op.drop_index(op.f("ix_team_id"), table_name="team")
    op.drop_table("team")
