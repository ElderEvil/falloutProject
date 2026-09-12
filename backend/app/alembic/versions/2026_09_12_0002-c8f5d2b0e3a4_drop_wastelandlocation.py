"""drop_wastelandlocation_swap_dwellerlocation_fk

Phase 2 of the shared places registry (docs/WORLD_MAP_PLAN.md): point
``dwellerlocation.location_id`` at the canonical ``worldlocation`` table and
drop the retired per-vault ``wastelandlocation`` table.

Single transactional revision:
1. Re-run the phase-1 backfill idempotently, absorbing rows written to
   ``wastelandlocation`` after phase 1 was applied.
2. Guard: fail loudly if any foreign key other than
   ``dwellerlocation.location_id`` still references ``wastelandlocation``.
3. Swap the ``dwellerlocation.location_id`` FK to ``worldlocation(id)`` with
   ``ON DELETE CASCADE`` (the ``ix_dwellerlocation_location_id`` index stays).
4. Drop ``wastelandlocation``.

Downgrade recreates ``wastelandlocation`` and rebuilds it row-for-row from
states joined to the registry (state ids were preserved from the old rows, so
``dwellerlocation.location_id`` values keep resolving), restores the old FK,
then drops the registry tables. The ``placekind`` enum is left in place.

Revision ID: c8f5d2b0e3a4
Revises: b7e4c1a9f2d3
Create Date: 2026-09-12

"""

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c8f5d2b0e3a4"
down_revision: str | None = "b7e4c1a9f2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PHASE1_MODULE = "2026_09_12_0001-b7e4c1a9f2d3_add_world_place_registry.py"


def upgrade() -> None:
    _rerun_phase1_backfill()
    _assert_only_dwellerlocation_references_old_table()
    _swap_dwellerlocation_fk("wastelandlocation", "worldlocation")
    op.drop_table("wastelandlocation")


def downgrade() -> None:
    _create_wastelandlocation()
    _rebuild_wastelandlocation_rows()
    _swap_dwellerlocation_fk("worldlocation", "wastelandlocation")

    op.drop_index(op.f("ix_vaultlocationstate_location_id"), table_name="vaultlocationstate")
    op.drop_index(op.f("ix_vaultlocationstate_vault_id"), table_name="vaultlocationstate")
    op.drop_index(op.f("ix_vaultlocationstate_id"), table_name="vaultlocationstate")
    op.drop_table("vaultlocationstate")

    op.drop_index("uq_world_location_vault_number", table_name="worldlocation")
    op.drop_index("ix_worldlocation_normalized_name", table_name="worldlocation")
    op.drop_index(op.f("ix_worldlocation_id"), table_name="worldlocation")
    op.drop_table("worldlocation")


def _rerun_phase1_backfill() -> None:
    """Re-run the phase-1 registry backfill to absorb drift rows.

    Recreates the registry tables first when they are absent (downgrade then
    upgrade path); otherwise backfills into the existing tables.
    """
    import importlib.util

    path = Path(__file__).parent / _PHASE1_MODULE
    spec = importlib.util.spec_from_file_location("phase1_registry_migration", path)
    if spec is None or spec.loader is None:  # pragma: no cover - missing file is a packaging error
        raise RuntimeError(f"Phase-1 migration module not found at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    bind = op.get_bind()
    tables_present = sa.inspect(bind).get_table_names()
    missing = {"worldlocation", "vaultlocationstate"} - set(tables_present)
    if missing == {"worldlocation", "vaultlocationstate"}:
        # Post-downgrade state: drop the orphaned placekind type first, or the
        # table creates below fail re-creating it.
        bind.execute(sa.text("DROP TYPE IF EXISTS placekind"))
        module._create_tables()
    elif missing:  # pragma: no cover - defensive; a half-applied schema needs a human
        raise RuntimeError(f"Unexpected partial registry schema, missing: {sorted(missing)}")
    module._backfill_registry()


def _dwellerlocation_fk_names() -> list[tuple[str, str]]:
    """(constraint name, referenced table) for FKs on ``dwellerlocation.location_id``."""
    bind = op.get_bind()
    return [
        (conname, reftable)
        for conname, reftable in bind.execute(
            sa.text(
                """
                SELECT c.conname, confrelid::regclass::text
                FROM pg_constraint c
                WHERE c.conrelid = 'dwellerlocation'::regclass
                  AND c.contype = 'f'
                  AND c.conkey = ARRAY[
                      (SELECT attnum FROM pg_attribute
                       WHERE attrelid = 'dwellerlocation'::regclass AND attname = 'location_id')
                  ]
                """
            )
        ).all()
    ]


def _assert_only_dwellerlocation_references_old_table() -> None:
    """Fail loudly if anything besides the swapped FK references the old table."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT conrelid::regclass::text, conname
            FROM pg_constraint
            WHERE confrelid = 'wastelandlocation'::regclass AND contype = 'f'
            """
        )
    ).all()
    unexpected = [f"{table}.{name}" for table, name in rows if table != "dwellerlocation"]
    if unexpected:  # pragma: no cover - defensive; fail loudly rather than orphan data
        raise RuntimeError(f"Unexpected FKs reference wastelandlocation: {unexpected}")


def _swap_dwellerlocation_fk(from_table: str, to_table: str) -> None:
    """Repoint ``dwellerlocation.location_id`` from one table to the other."""
    matches = _dwellerlocation_fk_names()
    if len(matches) != 1:  # pragma: no cover - defensive
        raise RuntimeError(f"Expected exactly one FK on dwellerlocation.location_id, found: {matches}")
    constraint_name, current_target = matches[0]
    if current_target != from_table:  # pragma: no cover - defensive
        raise RuntimeError(f"dwellerlocation.location_id references {current_target}, expected {from_table}")

    op.drop_constraint(constraint_name, "dwellerlocation", type_="foreignkey")
    op.create_foreign_key(
        f"fk_dwellerlocation_location_id_{to_table}",
        "dwellerlocation",
        to_table,
        ["location_id"],
        ["id"],
        ondelete="CASCADE",
    )


def _create_wastelandlocation() -> None:
    """Recreate the retired table with its original DDL (downgrade only)."""
    op.create_table(
        "wastelandlocation",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("normalized_name", sa.String(length=64), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "ORIGIN",
                "VISITED",
                "DISCOVERY",
                "HOME_VAULT",
                name="locationtypeenum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("coord_x", sa.Float(), nullable=False),
        sa.Column("coord_y", sa.Float(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("exploration_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vault_id", "normalized_name", name="uq_wasteland_location_vault_name"),
        sa.CheckConstraint("coord_x >= 0 AND coord_x <= 100", name="ck_wasteland_location_coord_x_range"),
        sa.CheckConstraint("coord_y >= 0 AND coord_y <= 100", name="ck_wasteland_location_coord_y_range"),
        sa.UniqueConstraint("vault_id", "coord_x", "coord_y", name="uq_wasteland_location_vault_coords"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exploration_id"], ["exploration.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_wastelandlocation_id"), "wastelandlocation", ["id"], unique=False)
    op.create_index(
        op.f("ix_wastelandlocation_normalized_name"), "wastelandlocation", ["normalized_name"], unique=False
    )
    op.create_index(op.f("ix_wastelandlocation_vault_id"), "wastelandlocation", ["vault_id"], unique=False)


def _rebuild_wastelandlocation_rows() -> None:
    """Restore old rows from states joined to the registry (downgrade only).

    Coordinates come from the registry (name-derived), not the original
    per-vault positions — the swap is lossy for marker positions only.
    """
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO wastelandlocation
                (id, name, normalized_name, type, coord_x, coord_y, description,
                 vault_id, exploration_id, created_at, updated_at)
            SELECT s.id, gl.name, gl.normalized_name, s.type, gl.coord_x, gl.coord_y,
                   s.description, s.vault_id, s.exploration_id, s.created_at, s.updated_at
            FROM vaultlocationstate s
            JOIN worldlocation gl ON gl.id = s.location_id
            """
        )
    )
