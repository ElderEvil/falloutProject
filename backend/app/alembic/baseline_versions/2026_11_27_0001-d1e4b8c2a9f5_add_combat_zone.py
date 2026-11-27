"""add combat zone party, match, and journal tables

Revision ID: d1e4b8c2a9f5
Revises: c3f5a7d9e1b2
Create Date: 2026-11-27 00:01:00.000000

Adds the Combat Zone backend spine (issue #1057, M1):

* three native enum types for party status, stance, and match status;
* a sent dweller reuses the existing ``FIGHTING`` status (no enum change);
* ``combat_zone_party`` (one reusable row per vault, unique ``vault_id``);
* ``combat_zone_match`` (two party rows, escrowed pot, alternating attacker);
* ``combat_zone_event`` (append-only journal keyed by ``sequence``);
* a per-vault toggle that ships off, matching the dark global switch.

No backfill beyond the vault flag: all three tables are new, and no existing row
can be in the Zone. Downgrade drops the new tables and enum types; no existing
enum is modified.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d1e4b8c2a9f5"
down_revision: str | Sequence[str] | None = "c3f5a7d9e1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMBAT_ZONE_STANCE = postgresql.ENUM(
    "AGGRESSIVE", "DEFENSIVE", "FOCUS", "RETREAT", name="combatzonestance", create_type=False
)
_COMBAT_ZONE_PARTY_STATUS = postgresql.ENUM(
    "TRAVELING",
    "QUEUED",
    "IN_MATCH",
    "RETURNING",
    "HOME",
    name="combatzonepartystatus",
    create_type=False,
)
_COMBAT_ZONE_MATCH_STATUS = postgresql.ENUM(
    "ACTIVE", "FINISHED", name="combatzonematchstatus", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    _COMBAT_ZONE_STANCE.create(bind, checkfirst=True)
    _COMBAT_ZONE_PARTY_STATUS.create(bind, checkfirst=True)
    _COMBAT_ZONE_MATCH_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "combat_zone_party",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=False),
        sa.Column("origin_room_id", sa.Uuid(), nullable=True),
        sa.Column("status", _COMBAT_ZONE_PARTY_STATUS, nullable=False, server_default="HOME"),
        sa.Column("stance", _COMBAT_ZONE_STANCE, nullable=False, server_default="DEFENSIVE"),
        sa.Column("stance_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrives_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escrow_caps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], name="fk_combat_zone_party_vault_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dweller_id"], ["dweller.id"], name="fk_combat_zone_party_dweller_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["origin_room_id"], ["room.id"], name="fk_combat_zone_party_origin_room_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_combat_zone_party"),
        sa.UniqueConstraint("vault_id", name="uq_combat_zone_party_vault"),
        sa.CheckConstraint("escrow_caps >= 0", name="ck_combat_zone_party_escrow_non_negative"),
    )
    op.create_index("ix_combat_zone_party_id", "combat_zone_party", ["id"])
    op.create_index("ix_combat_zone_party_vault_id", "combat_zone_party", ["vault_id"])
    op.create_index("ix_combat_zone_party_dweller_id", "combat_zone_party", ["dweller_id"])
    op.create_index("ix_combat_zone_party_status", "combat_zone_party", ["status"])

    op.create_table(
        "combat_zone_match",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("party_a_id", sa.Uuid(), nullable=False),
        sa.Column("party_b_id", sa.Uuid(), nullable=False),
        sa.Column("party_a_dweller_id", sa.Uuid(), nullable=True),
        sa.Column("party_b_dweller_id", sa.Uuid(), nullable=True),
        sa.Column("party_a_name", sa.String(length=64), nullable=False),
        sa.Column("party_b_name", sa.String(length=64), nullable=False),
        sa.Column("party_a_vault_number", sa.Integer(), nullable=False),
        sa.Column("party_b_vault_number", sa.Integer(), nullable=False),
        sa.Column("party_a_level", sa.Integer(), nullable=True),
        sa.Column("party_b_level", sa.Integer(), nullable=True),
        sa.Column("party_a_power", sa.Float(), nullable=True),
        sa.Column("party_b_power", sa.Float(), nullable=True),
        sa.Column("party_a_age_group", sa.String(length=16), nullable=True),
        sa.Column("party_b_age_group", sa.String(length=16), nullable=True),
        sa.Column("party_a_race", sa.String(length=32), nullable=True),
        sa.Column("party_b_race", sa.String(length=32), nullable=True),
        sa.Column("status", _COMBAT_ZONE_MATCH_STATUS, nullable=False, server_default="ACTIVE"),
        sa.Column("next_attack_party", sa.String(length=1), nullable=False, server_default="A"),
        sa.Column("round_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pot_caps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("winner_party_id", sa.Uuid(), nullable=True),
        sa.Column("finish_reason", sa.String(length=32), nullable=True),
        sa.Column("party_a_health", sa.Integer(), nullable=True),
        sa.Column("party_b_health", sa.Integer(), nullable=True),
        sa.Column("party_a_max_health", sa.Integer(), nullable=True),
        sa.Column("party_b_max_health", sa.Integer(), nullable=True),
        sa.Column("party_a_credited_caps", sa.Integer(), nullable=True),
        sa.Column("party_b_credited_caps", sa.Integer(), nullable=True),
        sa.Column("carry", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["party_a_id"], ["combat_zone_party.id"], name="fk_combat_zone_match_party_a_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["party_b_id"], ["combat_zone_party.id"], name="fk_combat_zone_match_party_b_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["winner_party_id"],
            ["combat_zone_party.id"],
            name="fk_combat_zone_match_winner_party_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["party_a_dweller_id"],
            ["dweller.id"],
            name="fk_combat_zone_match_party_a_dweller_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["party_b_dweller_id"],
            ["dweller.id"],
            name="fk_combat_zone_match_party_b_dweller_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_combat_zone_match"),
        sa.CheckConstraint("party_a_id <> party_b_id", name="ck_combat_zone_match_distinct_parties"),
        sa.CheckConstraint("round_seq >= 1", name="ck_combat_zone_match_round_positive"),
        sa.CheckConstraint("pot_caps >= 0", name="ck_combat_zone_match_pot_non_negative"),
    )
    op.create_index("ix_combat_zone_match_id", "combat_zone_match", ["id"])
    op.create_index("ix_combat_zone_match_party_a_id", "combat_zone_match", ["party_a_id"])
    op.create_index("ix_combat_zone_match_party_b_id", "combat_zone_match", ["party_b_id"])
    op.create_index("ix_combat_zone_match_party_a_dweller_id", "combat_zone_match", ["party_a_dweller_id"])
    op.create_index("ix_combat_zone_match_party_b_dweller_id", "combat_zone_match", ["party_b_dweller_id"])
    op.create_index("ix_combat_zone_match_status", "combat_zone_match", ["status"])

    op.create_table(
        "combat_zone_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("round_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=200), nullable=False),
        sa.Column("action", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"], ["combat_zone_match.id"], name="fk_combat_zone_event_match_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_combat_zone_event"),
        sa.UniqueConstraint("match_id", "sequence", name="uq_combat_zone_event_match_sequence"),
    )
    op.create_index("ix_combat_zone_event_id", "combat_zone_event", ["id"])
    op.create_index("ix_combat_zone_event_match_id", "combat_zone_event", ["match_id"])
    op.create_index("ix_combat_zone_event_kind", "combat_zone_event", ["kind"])

    # Canonical shared POI, so production reads never lazily create it.
    op.execute(
        """
        INSERT INTO worldlocation (
            id, name, normalized_name, coord_x, coord_y, description,
            group_key, source, kind, created_at, updated_at
        )
        VALUES (
            'c0b4a7e2-5d3f-4a91-8c6e-2f7b1d9a4e83',
            'The Combat Zone',
            'the_combat_zone',
            50.0,
            50.0,
            'A pre-war interchange where vaults send parties to fight for caps. '
            'The signal is open to every vault on the same frequency.',
            'combat_zone',
            'system',
            'PLACE',
            now(),
            now()
        )
        ON CONFLICT (normalized_name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM worldlocation WHERE normalized_name = 'the_combat_zone' AND source = 'system'")

    op.drop_index("ix_combat_zone_event_kind", table_name="combat_zone_event")
    op.drop_index("ix_combat_zone_event_match_id", table_name="combat_zone_event")
    op.drop_index("ix_combat_zone_event_id", table_name="combat_zone_event")
    op.drop_table("combat_zone_event")

    op.drop_index("ix_combat_zone_match_status", table_name="combat_zone_match")
    op.drop_index("ix_combat_zone_match_party_b_dweller_id", table_name="combat_zone_match")
    op.drop_index("ix_combat_zone_match_party_a_dweller_id", table_name="combat_zone_match")
    op.drop_index("ix_combat_zone_match_party_b_id", table_name="combat_zone_match")
    op.drop_index("ix_combat_zone_match_party_a_id", table_name="combat_zone_match")
    op.drop_index("ix_combat_zone_match_id", table_name="combat_zone_match")
    op.drop_table("combat_zone_match")

    op.drop_index("ix_combat_zone_party_status", table_name="combat_zone_party")
    op.drop_index("ix_combat_zone_party_dweller_id", table_name="combat_zone_party")
    op.drop_index("ix_combat_zone_party_vault_id", table_name="combat_zone_party")
    op.drop_index("ix_combat_zone_party_id", table_name="combat_zone_party")
    op.drop_table("combat_zone_party")

    bind = op.get_bind()
    _COMBAT_ZONE_MATCH_STATUS.drop(bind, checkfirst=True)
    _COMBAT_ZONE_PARTY_STATUS.drop(bind, checkfirst=True)
    _COMBAT_ZONE_STANCE.drop(bind, checkfirst=True)
