"""add_world_place_registry

Phase 1 of the shared places registry (docs/WORLD_MAP_PLAN.md): create the
canonical ``worldlocation`` table plus per-vault ``vaultlocationstate`` and
backfill both from ``wastelandlocation``.

This revision is deliberately additive: the old table and the
``dwellerlocation.location_id`` FK are untouched, and no service is rewired yet,
so the application stays green. The FK swap and the drop of ``wastelandlocation``
ship in the phase 2 revision together with the service rewire.

The backfill is idempotent (``ON CONFLICT DO NOTHING`` + a registry rebuilt from
existing rows), so phase 2's revision re-runs it to absorb rows written between
the two releases.

Revision ID: b7e4c1a9f2d3
Revises: f7a21c9d4e03
Create Date: 2026-09-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7e4c1a9f2d3"
down_revision: str | None = "f7a21c9d4e03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Home-vault markers are pinned so every vault keeps its own centre.
_HOME_COORD = (50.0, 50.0)


def upgrade() -> None:
    _create_tables()
    _backfill_registry()


def downgrade() -> None:
    op.drop_index(op.f("ix_vaultlocationstate_location_id"), table_name="vaultlocationstate")
    op.drop_index(op.f("ix_vaultlocationstate_vault_id"), table_name="vaultlocationstate")
    op.drop_index(op.f("ix_vaultlocationstate_id"), table_name="vaultlocationstate")
    op.drop_table("vaultlocationstate")

    op.drop_index("uq_world_location_vault_number", table_name="worldlocation")
    op.drop_index("ix_worldlocation_normalized_name", table_name="worldlocation")
    op.drop_index(op.f("ix_worldlocation_id"), table_name="worldlocation")
    op.drop_table("worldlocation")

    # Only the new enum is dropped; ``locationtypeenum`` is shared with the
    # still-present ``wastelandlocation`` table.
    sa.Enum(name="placekind").drop(op.get_bind(), checkfirst=True)


def _create_tables() -> None:
    op.create_table(
        "worldlocation",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("normalized_name", sa.String(length=64), nullable=False),
        sa.Column("vault_number", sa.Integer(), nullable=True),
        sa.Column("coord_x", sa.Float(), nullable=False),
        sa.Column("coord_y", sa.Float(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Enum("PLACE", "VAULT", name="placekind"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("coord_x >= 0 AND coord_x <= 100", name="ck_world_location_coord_x_range"),
        sa.CheckConstraint("coord_y >= 0 AND coord_y <= 100", name="ck_world_location_coord_y_range"),
    )
    op.create_index(op.f("ix_worldlocation_id"), "worldlocation", ["id"], unique=False)
    op.create_index("ix_worldlocation_normalized_name", "worldlocation", ["normalized_name"], unique=True)
    op.create_index(
        "uq_world_location_vault_number",
        "worldlocation",
        ["vault_number"],
        unique=True,
        postgresql_where=sa.text("kind = 'VAULT'"),
    )

    op.create_table(
        "vaultlocationstate",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
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
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("exploration_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["worldlocation.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exploration_id"], ["exploration.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("vault_id", "location_id", name="uq_vault_location_state"),
    )
    op.create_index(op.f("ix_vaultlocationstate_id"), "vaultlocationstate", ["id"], unique=False)
    op.create_index(op.f("ix_vaultlocationstate_vault_id"), "vaultlocationstate", ["vault_id"], unique=False)
    op.create_index(op.f("ix_vaultlocationstate_location_id"), "vaultlocationstate", ["location_id"], unique=False)


def _backfill_registry() -> None:
    """Copy ``wastelandlocation`` into the registry, deduped by normalized name.

    Winner per name is the first row by ``(created_at, id)``; it supplies the
    canonical display name, description, coordinates and row id. Coordinates are
    name-derived (never carried over) so the registry stays deterministic for
    every viewer. Every old row becomes exactly one ``VaultLocationState``.
    """
    from app.utils.places import collision_nudge, schematic_coords

    bind = op.get_bind()

    registry: dict[str, str] = {
        normalized: str(row_id)
        for normalized, row_id in bind.execute(sa.text("SELECT normalized_name, id FROM worldlocation")).all()
    }
    occupied: set[tuple[float, float]] = {
        (round(x, 1), round(y, 1))
        for x, y in bind.execute(sa.text("SELECT coord_x, coord_y FROM worldlocation")).all()
    }
    existing_states: set[tuple[str, str]] = {
        (str(vault_id), str(location_id))
        for vault_id, location_id in bind.execute(
            sa.text("SELECT vault_id, location_id FROM vaultlocationstate")
        ).all()
    }

    rows = (
        bind.execute(
            sa.text(
                """
                SELECT wl.id, wl.vault_id, wl.name, wl.normalized_name, wl.type,
                       wl.description, wl.exploration_id, wl.created_at, wl.updated_at,
                       v.number AS vault_number
                FROM wastelandlocation wl
                LEFT JOIN vault v ON v.id = wl.vault_id
                ORDER BY wl.created_at ASC NULLS FIRST, wl.id ASC
                """
            )
        )
        .mappings()
        .all()
    )

    for row in rows:
        normalized = row["normalized_name"]
        is_home = row["type"] == "HOME_VAULT"

        if normalized not in registry:
            coord_x, coord_y = _HOME_COORD if is_home else collision_nudge(schematic_coords(normalized), occupied)
            occupied.add((round(coord_x, 1), round(coord_y, 1)))
            bind.execute(
                sa.text(
                    """
                    INSERT INTO worldlocation
                        (id, name, normalized_name, kind, vault_number, coord_x, coord_y,
                         description, source, created_at, updated_at)
                    VALUES
                        (:id, :name, :normalized_name, :kind, :vault_number, :coord_x, :coord_y,
                         :description, :source, :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": row["id"],
                    "name": row["name"][:64],
                    "normalized_name": normalized,
                    "kind": "VAULT" if is_home else "PLACE",
                    "vault_number": row["vault_number"] if is_home else None,
                    "coord_x": coord_x,
                    "coord_y": coord_y,
                    "description": row["description"],
                    "source": "emergent",
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                },
            )
            registry[normalized] = str(row["id"])

        location_id = registry[normalized]
        if (str(row["vault_id"]), location_id) in existing_states:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO vaultlocationstate
                    (id, vault_id, location_id, type, description, exploration_id, created_at, updated_at)
                VALUES
                    (:id, :vault_id, :location_id, :type, :description, :exploration_id, :created_at, :updated_at)
                ON CONFLICT (vault_id, location_id) DO NOTHING
                """
            ),
            {
                "id": row["id"],
                "vault_id": row["vault_id"],
                "location_id": location_id,
                "type": row["type"],
                "description": row["description"],
                "exploration_id": row["exploration_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )
