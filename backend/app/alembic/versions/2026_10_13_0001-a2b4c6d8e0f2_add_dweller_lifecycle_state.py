"""add dweller lifecycle and availability state

Canonical lifecycle/availability for #831 slice 1. Autogenerate cannot detect enum
values, so the types and columns are written by hand (AGENTS.md "DB Enums & Alembic
Migrations"). Existing rows are classified from the legacy death/soft-delete flags in the
SAME migration: a legacy EXILE tombstone (cause EXILE, no room, permanently dead, not
soft-deleted) becomes wasteland/departure with its former vault retained as
previous_vault_id; genuine deaths are never overwritten and an inconsistent EXILE row
stays unclassified for review. Content provenance is backfilled by name from a frozen
curated-template snapshot; unknown provenance stays NULL (private), never invented.

downgrade() is a documented no-op: exile-as-death cannot be safely reproduced once a
departure has been recruited, so operational rollback requires a backup restore (spec
"Migration and API compatibility" item 7).

Revision ID: a2b4c6d8e0f2
Revises: 862c04111ec1
Create Date: 2026-10-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a2b4c6d8e0f2"
down_revision: str | None = "862c04111ec1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIFECYCLE_TYPE = postgresql.ENUM(
    "ALIVE", "DEAD_REVIVABLE", "DEAD_PERMANENT", "WASTELAND", name="lifecycleenum", create_type=False
)
AVAILABILITY_TYPE = postgresql.ENUM(
    "VAULT", "DEPARTURE", "POOL", "MARKET", "ARCHIVE", name="availabilityenum", create_type=False
)

# Frozen curated dweller template names ("first last", lowercased, trimmed) taken when this
# revision was written. A later catalog edit must not change what this revision backfills.
CURATED_DWELLER_NAMES: tuple[str, ...] = (
    "76 overseer",
    "abraham washington",
    "akira katana",
    "alexander miller",
    "allistair tenpenny",
    "amata",
    "ameritus jones",
    "amy chandler",
    "andre grande",
    "benjamin price",
    "betty",
    "bittercup",
    "brandy valentino",
    "brian drake",
    "butch",
    "carlos the great",
    "chet",
    "colonel autumn",
    "confessor cromwell",
    "conrad kellogg",
    "cooper howard",
    "danielle hart",
    "desdemona",
    "dr. henry",
    "dr. li",
    "ed the ghoul",
    "elder lyons",
    "eulogy jones",
    "frank blitzer",
    "galahad swingsalot",
    "hank",
    "harkness",
    "heywood yalaff",
    "james",
    "jericho",
    "laurel divinitus",
    "legate",
    "luc the human",
    "lucas simms",
    "lucy maclean",
    "ma june",
    "martha dewey",
    "max throttle",
    "maximus",
    "moira brown",
    "moldaver",
    "mr. burke",
    "mr. house",
    "nick valentine",
    "norm",
    "old longfellow",
    "oscar blood",
    "paladin",
    "paladin danse",
    "piper",
    "preston garvey",
    "prospero leonard",
    "regs",
    "rex chessman",
    "rock hardscrabble",
    "sarah lyons",
    "scribe rothchild",
    "scribe valdez",
    "shamus rumple",
    "snake oil salesman",
    "snip snip",
    "star paladin cross",
    "stephanie",
    "tenderloin fauntleroy",
    "the ghoul",
    "three dog",
    "tina wrenchley",
    "vera majors",
    "wilzig",
)

# Identity state first (mutually exclusive, guarded by lifecycle IS NULL), then the
# name-keyed content-provenance enrichment kept separate from membership.
EXILE_TO_DEPARTURE_SQL = sa.text(
    "UPDATE dweller SET lifecycle = 'WASTELAND', availability = 'DEPARTURE', "
    "previous_vault_id = vault_id, vault_id = NULL, departed_at = death_timestamp "
    "WHERE lifecycle IS NULL AND death_cause = 'EXILE'::deathcauseenum AND room_id IS NULL "
    "AND is_permanently_dead = TRUE AND is_deleted = FALSE"
)
PERMANENT_DEATH_SQL = sa.text(
    "UPDATE dweller SET lifecycle = 'DEAD_PERMANENT', availability = 'ARCHIVE' "
    "WHERE lifecycle IS NULL AND is_dead = TRUE AND is_permanently_dead = TRUE "
    "AND death_cause IS DISTINCT FROM 'EXILE'::deathcauseenum"
)
REVIVABLE_DEATH_SQL = sa.text(
    "UPDATE dweller SET lifecycle = 'DEAD_REVIVABLE', availability = 'VAULT' "
    "WHERE lifecycle IS NULL AND is_dead = TRUE AND is_permanently_dead = FALSE"
)
MARKET_LISTING_SQL = sa.text(
    "UPDATE dweller SET lifecycle = 'ALIVE', availability = 'MARKET' "
    "WHERE lifecycle IS NULL AND is_dead = FALSE AND is_deleted = TRUE"
)
ACTIVE_DWELLER_SQL = sa.text(
    "UPDATE dweller SET lifecycle = 'ALIVE', availability = 'VAULT' "
    "WHERE lifecycle IS NULL AND is_dead = FALSE AND is_deleted = FALSE"
)
CONTENT_PROVENANCE_SQL = sa.text(
    "UPDATE dweller SET content_provenance = 'curated' "
    "WHERE content_provenance IS NULL "
    "AND LOWER(TRIM(first_name || ' ' || COALESCE(last_name, ''))) = :name"
)


def upgrade() -> None:
    op.execute("CREATE TYPE lifecycleenum AS ENUM ('ALIVE', 'DEAD_REVIVABLE', 'DEAD_PERMANENT', 'WASTELAND')")
    op.execute("CREATE TYPE availabilityenum AS ENUM ('VAULT', 'DEPARTURE', 'POOL', 'MARKET', 'ARCHIVE')")
    op.add_column("dweller", sa.Column("lifecycle", LIFECYCLE_TYPE, nullable=True))
    op.add_column("dweller", sa.Column("availability", AVAILABILITY_TYPE, nullable=True))
    op.create_index(op.f("ix_dweller_lifecycle"), "dweller", ["lifecycle"], unique=False)
    op.create_index(op.f("ix_dweller_availability"), "dweller", ["availability"], unique=False)
    op.add_column(
        "dweller",
        sa.Column("previous_vault_id", sa.UUID(), sa.ForeignKey("vault.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("dweller", sa.Column("content_provenance", sa.String(length=16), nullable=True))
    op.add_column("dweller", sa.Column("sharing_consent", sa.Boolean(), nullable=True))
    op.add_column("dweller", sa.Column("departed_at", sa.DateTime(), nullable=True))
    op.add_column("dweller", sa.Column("departure_eligible_at", sa.DateTime(), nullable=True))

    # A departure has no active vault (previous_vault_id carries provenance), so the
    # membership column must allow NULL before the reclassification below.
    op.alter_column("dweller", "vault_id", existing_type=sa.Uuid(), nullable=True)

    conn = op.get_bind()
    conn.execute(EXILE_TO_DEPARTURE_SQL)
    conn.execute(PERMANENT_DEATH_SQL)
    conn.execute(REVIVABLE_DEATH_SQL)
    conn.execute(MARKET_LISTING_SQL)
    conn.execute(ACTIVE_DWELLER_SQL)
    for name in CURATED_DWELLER_NAMES:
        conn.execute(CONTENT_PROVENANCE_SQL, {"name": name})


def downgrade() -> None:
    """No-op — see the module docstring; rollback requires a backup restore."""
