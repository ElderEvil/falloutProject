"""consolidate earned hazard teams onto the team roster primitive

Revision ID: c9d8e7f6a5b4
Revises: b7c8d9e0f1a2
Create Date: 2026-09-19 00:00:00.000000

The earned fire/radiation rosters lived on a parallel ``hazard_team_member``
table. This revision moves them onto the reusable ``team``/``team_member``
primitive: one ``team`` row per ``(vault_id, hazard_team)``, members copied
with ``slot_number`` 1-3 by seniority for living ``active`` members and NULL
for ``reserve``/fallen members, then drops the legacy table. The ``hazardteam``
enum type survives because ``team.hazard_team`` now uses it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d8e7f6a5b4"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Three-way purpose check: exactly one of quest/incident/hazard is set.
THREE_WAY_PURPOSE_CHECK = (
    "(CASE WHEN quest_id IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN incident_id IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN hazard_team IS NOT NULL THEN 1 ELSE 0 END) = 1"
)
#: The two-way form restored on downgrade.
TWO_WAY_PURPOSE_CHECK = (
    "(CASE WHEN quest_id IS NOT NULL THEN 1 ELSE 0 END + "
    "CASE WHEN incident_id IS NOT NULL THEN 1 ELSE 0 END) = 1"
)

TEAM_BACKFILL_SQL = sa.text(
    "INSERT INTO team (id, vault_id, hazard_team, created_at, updated_at) "
    "SELECT gen_random_uuid(), vault_id, team, MIN(created_at), MAX(updated_at) "
    "FROM hazard_team_member GROUP BY vault_id, team"
)

#: Roster size the team enforces: only the most senior living active members keep
#: a slot; any legacy excess becomes a bench place.
ACTIVE_SLOT_LIMIT = 3

#: Active members hold slots 1-3 in seniority order; reserve and fallen members
#: hold no slot (NULL), so a fallen member frees their place for the bench.
#: Legacy data can carry more than three living ``active`` rows (nothing forced a
#: revived member to vacate a place that had already been refilled), so ranks past
#: the limit become bench members rather than granting a fourth active place.
MEMBER_BACKFILL_SQL = sa.text(
    "WITH ranked AS ("
    "  SELECT htm2.id AS member_id, "
    "         ROW_NUMBER() OVER (PARTITION BY htm2.vault_id, htm2.team ORDER BY htm2.created_at, htm2.id) "
    "         AS slot_rank "
    "  FROM hazard_team_member htm2 "
    "  JOIN dweller d2 ON d2.id = htm2.dweller_id "
    "  WHERE htm2.status = 'active' AND d2.is_dead = FALSE AND d2.is_deleted = FALSE"
    ") "
    "INSERT INTO team_member (id, team_id, dweller_id, slot_number, status, created_at, updated_at) "
    "SELECT gen_random_uuid(), t.id, htm.dweller_id, "
    f"       CASE WHEN ranked.slot_rank <= {ACTIVE_SLOT_LIMIT} THEN ranked.slot_rank END, "
    f"       CASE WHEN ranked.slot_rank > {ACTIVE_SLOT_LIMIT} THEN 'reserve' ELSE htm.status END, "
    "       htm.created_at, htm.updated_at "
    "FROM hazard_team_member htm "
    "JOIN team t ON t.vault_id = htm.vault_id AND t.hazard_team = htm.team "
    "LEFT JOIN ranked ON ranked.member_id = htm.id"
)

MEMBER_RESTORE_SQL = sa.text(
    "INSERT INTO hazard_team_member (id, vault_id, dweller_id, team, status, created_at, updated_at) "
    "SELECT gen_random_uuid(), t.vault_id, tm.dweller_id, t.hazard_team, tm.status, tm.created_at, tm.updated_at "
    "FROM team_member tm JOIN team t ON t.id = tm.team_id "
    "WHERE t.hazard_team IS NOT NULL"
)


def upgrade() -> None:
    op.add_column(
        "team",
        sa.Column(
            "hazard_team",
            sa.Enum("FIRE", "RADIATION", name="hazardteam", create_type=False),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_team_hazard_team"), "team", ["hazard_team"], unique=False)
    op.drop_constraint("ck_team_one_purpose", "team", type_="check")
    op.create_check_constraint("ck_team_one_purpose", "team", THREE_WAY_PURPOSE_CHECK)
    op.create_unique_constraint("uq_team_vault_hazard", "team", ["vault_id", "hazard_team"])

    op.execute(TEAM_BACKFILL_SQL)
    op.execute(MEMBER_BACKFILL_SQL)

    op.drop_index(op.f("ix_hazard_team_member_team"), table_name="hazard_team_member")
    op.drop_index(op.f("ix_hazard_team_member_dweller_id"), table_name="hazard_team_member")
    op.drop_index(op.f("ix_hazard_team_member_vault_id"), table_name="hazard_team_member")
    op.drop_index(op.f("ix_hazard_team_member_id"), table_name="hazard_team_member")
    op.drop_table("hazard_team_member")


def downgrade() -> None:
    # Recreate hazard_team_member exactly as in 2026_09_18_0001. Raw SQL rather
    # than op.create_table: the hazardteam enum type already exists (team.hazard_team
    # still uses it), and SQLAlchemy's PG ENUM before_create event would emit a
    # duplicate CREATE TYPE.
    op.execute(
        sa.text(
            "CREATE TABLE hazard_team_member ("
            "created_at TIMESTAMP WITHOUT TIME ZONE, "
            "updated_at TIMESTAMP WITHOUT TIME ZONE, "
            "vault_id UUID NOT NULL, "
            "dweller_id UUID NOT NULL, "
            "team hazardteam NOT NULL, "
            "status VARCHAR NOT NULL, "
            "id UUID NOT NULL, "
            "CONSTRAINT hazard_team_member_pkey PRIMARY KEY (id), "
            "CONSTRAINT uq_hazard_team_dweller UNIQUE (vault_id, team, dweller_id), "
            "CONSTRAINT hazard_team_member_dweller_id_fkey "
            "FOREIGN KEY (dweller_id) REFERENCES dweller(id) ON DELETE CASCADE, "
            "CONSTRAINT hazard_team_member_vault_id_fkey "
            "FOREIGN KEY (vault_id) REFERENCES vault(id) ON DELETE CASCADE"
            ")"
        )
    )
    op.create_index(op.f("ix_hazard_team_member_id"), "hazard_team_member", ["id"], unique=False)
    op.create_index(op.f("ix_hazard_team_member_vault_id"), "hazard_team_member", ["vault_id"], unique=False)
    op.create_index(op.f("ix_hazard_team_member_dweller_id"), "hazard_team_member", ["dweller_id"], unique=False)
    op.create_index(op.f("ix_hazard_team_member_team"), "hazard_team_member", ["team"], unique=False)

    op.execute(MEMBER_RESTORE_SQL)

    op.execute(sa.text("DELETE FROM team_member WHERE team_id IN (SELECT id FROM team WHERE hazard_team IS NOT NULL)"))
    op.execute(sa.text("DELETE FROM team WHERE hazard_team IS NOT NULL"))

    op.drop_constraint("uq_team_vault_hazard", "team", type_="unique")
    op.drop_constraint("ck_team_one_purpose", "team", type_="check")
    op.create_check_constraint("ck_team_one_purpose", "team", TWO_WAY_PURPOSE_CHECK)
    op.drop_index(op.f("ix_team_hazard_team"), table_name="team")
    op.drop_column("team", "hazard_team")
