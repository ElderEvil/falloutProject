"""move home markers to vault slots

Revision ID: f8b2c3d4e5f6
Revises: e7a1b2c3d4e5
Create Date: 2026-10-02 00:02:00.000000

Home-vault registry rows were pinned at the map centre (50, 50). Vaults now occupy
scattered slots, so each home marker moves to its vault's slot coordinates. Matches
rows by normalized name and skips any already at their slot, so it is idempotent.
``downgrade()`` is a documented no-op: the centre is no longer meaningful.
"""

from collections.abc import Sequence

from alembic import op
from sqlmodel import Session, select

from app.models.vault import Vault
from app.models.vault_slot import VaultSlot
from app.models.world_location import WorldLocation
from app.utils.places import normalize_place_name
from app.utils.vault_slots import slot_coords

# revision identifiers, used by Alembic.
revision: str = "f8b2c3d4e5f6"
down_revision: str | None = "e7a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    rows = session.execute(
        select(VaultSlot.slot_index, Vault.number).join(Vault, Vault.id == VaultSlot.vault_id)
    ).all()
    for slot_index, number in rows:
        normalized = normalize_place_name(f"Vault {number:03}")
        home = session.execute(
            select(WorldLocation).where(WorldLocation.normalized_name == normalized)
        ).scalar_one_or_none()
        if home is None:
            continue
        coord_x, coord_y = slot_coords(slot_index)
        if (home.coord_x, home.coord_y) != (coord_x, coord_y):
            home.coord_x = coord_x
            home.coord_y = coord_y
            session.add(home)
    session.commit()


def downgrade() -> None:
    """No-op: the centre-pinned home marker is no longer meaningful."""
