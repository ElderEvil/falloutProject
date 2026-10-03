"""move home markers to vault slots

Revision ID: f8b2c3d4e5f6
Revises: e7a1b2c3d4e5
Create Date: 2026-10-02 00:02:00.000000

Home-vault registry rows were pinned at the map centre (50, 50). Vaults now occupy
scattered slots, so each home marker moves to its vault's slot coordinates. Matches
rows by normalized name and skips any already at their slot, so it is idempotent.
``downgrade()`` is a documented no-op: the centre is no longer meaningful.

Self-contained by design: uses ``sa.table`` stubs (never live ORM models) and
grid constants fixed at this revision (count 100, 10 columns, seed 0x5EED), so a
replayed upgrade always produces the same coordinates even if the runtime config
or models change later.
"""

from collections.abc import Sequence
from random import Random

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8b2c3d4e5f6"
down_revision: str | None = "e7a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Grid geometry fixed at this revision (mirrors the runtime defaults, frozen so
# replays are stable). Do not read game_config here.
_SLOT_COUNT = 100
_SLOT_COLUMNS = 10
_SCATTER_SEED = 0x5EED


def _slot_permutation() -> tuple[int, ...]:
    order = list(range(_SLOT_COUNT))
    Random(_SCATTER_SEED).shuffle(order)
    return tuple(order)


def _slot_coords(slot_index: int, permutation: tuple[int, ...]) -> tuple[float, float]:
    cell = 100 / _SLOT_COLUMNS
    index = permutation[slot_index % _SLOT_COUNT]
    h = (slot_index * 2654435761) & 0xFFFFFFFF
    jx = ((h & 0xFFFF) / 0xFFFF - 0.5) * 0.6
    jy = (((h >> 16) & 0xFFFF) / 0xFFFF - 0.5) * 0.6
    return ((index % _SLOT_COLUMNS + 0.5 + jx) * cell, (index // _SLOT_COLUMNS + 0.5 + jy) * cell)


def _normalize_place_name(name: str) -> str:
    return " ".join(name.strip().casefold().split()).rstrip(".,!")


vaultslot = sa.table(
    "vaultslot",
    sa.column("slot_index", sa.Integer),
    sa.column("vault_id", sa.Uuid),
)

vault = sa.table(
    "vault",
    sa.column("id", sa.Uuid),
    sa.column("number", sa.Integer),
)

worldlocation = sa.table(
    "worldlocation",
    sa.column("id", sa.Uuid),
    sa.column("normalized_name", sa.String),
    sa.column("coord_x", sa.Float),
    sa.column("coord_y", sa.Float),
)


def upgrade() -> None:
    bind = op.get_bind()
    permutation = _slot_permutation()
    rows = bind.execute(
        sa.select(vaultslot.c.slot_index, vault.c.number).join(vault, vault.c.id == vaultslot.c.vault_id)
    ).all()
    for slot_index, number in rows:
        normalized = _normalize_place_name(f"Vault {number:03}")
        home_id, coord_x, coord_y = bind.execute(
            sa.select(worldlocation.c.id, worldlocation.c.coord_x, worldlocation.c.coord_y).where(
                worldlocation.c.normalized_name == normalized
            )
        ).one_or_none() or (None, None, None)
        if home_id is None:
            continue
        target_x, target_y = _slot_coords(slot_index, permutation)
        if (coord_x, coord_y) != (target_x, target_y):
            bind.execute(
                worldlocation.update()
                .where(worldlocation.c.id == home_id)
                .values(coord_x=target_x, coord_y=target_y)
            )


def downgrade() -> None:
    """No-op: the centre-pinned home marker is no longer meaningful."""
