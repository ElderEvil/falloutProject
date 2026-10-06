"""Service: own the world snapshot lifecycle (generate explicitly once, read thereafter).

The map renders the persisted snapshot; reads never regenerate. Generation is a
development/seed operation, not a request path.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from app.crud.world_snapshot import world_snapshot as snapshot_crud
from app.models.world_snapshot import WorldSnapshot
from app.services.world_generation_service import (
    WORLD_ID,
    GeneratedWorld,
    WorldConfig,
    WorldRecipe,
    generate_world,
    snapshot_checksum,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class WorldSnapshotService:
    async def get_or_generate(self, db_session: AsyncSession, recipe: WorldRecipe | None = None) -> WorldSnapshot:
        """Return the persisted snapshot, generating and persisting it once if absent.

        Idempotent on (world_id, generator_version): an existing row is returned
        unchanged, so terrain and slots never drift between reads.
        """
        recipe = recipe or WorldRecipe(seed="wasteland-atlas-v1", config=WorldConfig())
        existing = await snapshot_crud.get_version(
            db_session, world_id=recipe.world_id, generator_version=recipe.generator_version
        )
        if existing is not None:
            return existing

        world = generate_world(recipe)
        snapshot = self._to_model(recipe, world)
        try:
            await snapshot_crud.create(db_session, snapshot=snapshot)
            await db_session.commit()
        except IntegrityError:
            # Lost a creation race: another writer persisted this version first.
            # The unique constraint kept it to one row; return the winner.
            await db_session.rollback()
            winner = await snapshot_crud.get_version(
                db_session, world_id=recipe.world_id, generator_version=recipe.generator_version
            )
            if winner is None:
                raise
            return winner
        logger.info(
            "Generated world snapshot %s v%s (fingerprint=%s)",
            recipe.world_id,
            recipe.generator_version,
            world.recipe_fingerprint,
        )
        return snapshot

    async def active_slot_coord(
        self, db_session: AsyncSession, slot_index: int, *, world_id: str = WORLD_ID
    ) -> tuple[float, float] | None:
        """The active world's placement for *slot_index*, or None when unset.

        The activation workflow writes the approved placement into the active
        snapshot's slots; map/home consumers read it back here (falling back to the
        legacy slot grid when no world is active) so all coordinate sources agree
        after a transition.
        """
        placement = await self.active_slot_placement(db_session, slot_index, world_id=world_id)
        return (placement[0], placement[1]) if placement is not None else None

    async def active_slot_coords(
        self, db_session: AsyncSession, *, world_id: str = WORLD_ID
    ) -> dict[int, tuple[float, float]]:
        """The active world's placement for every slot, or an empty dict when unset."""
        snapshot = await snapshot_crud.get_active(db_session, world_id=world_id)
        return self._slot_coords(snapshot) if snapshot is not None else {}

    async def active_slot_placement(
        self, db_session: AsyncSession, slot_index: int, *, world_id: str = WORLD_ID
    ) -> tuple[float, float, int] | None:
        """The active world's placement for *slot_index* and the version that supplies it.

        Returned together so a spatial departure stores the terrain version matching
        the origin it departs from; a coordinate without its version could make
        movement check against a different snapshot's terrain.
        """
        snapshot = await snapshot_crud.get_active(db_session, world_id=world_id)
        if snapshot is None:
            return None
        coord = self._slot_coords(snapshot).get(slot_index)
        return (coord[0], coord[1], snapshot.generator_version) if coord is not None else None

    @staticmethod
    def _slot_coords(snapshot: WorldSnapshot) -> dict[int, tuple[float, float]]:
        placements: dict[int, tuple[float, float]] = {}
        for slot in snapshot.slots:
            index = slot.get("slot_index")
            coord_x = slot.get("coord_x")
            coord_y = slot.get("coord_y")
            if index is None or coord_x is None or coord_y is None:
                continue
            placements[index] = (float(coord_x), float(coord_y))
        return placements

    @staticmethod
    def _to_model(recipe: WorldRecipe, world: GeneratedWorld) -> WorldSnapshot:
        return WorldSnapshot(
            world_id=recipe.world_id,
            generator_version=recipe.generator_version,
            seed=recipe.seed,
            # The whole config, derived programmatically so new fields cannot
            # silently diverge from the fingerprint input.
            config=asdict(recipe.config),
            recipe_fingerprint=world.recipe_fingerprint,
            snapshot_checksum=snapshot_checksum(world),
            terrain=list(world.terrain),
            slots=[
                {
                    "slot_index": slot.slot_index,
                    "tile_x": slot.tile_x,
                    "tile_y": slot.tile_y,
                    "coord_x": slot.coord_x,
                    "coord_y": slot.coord_y,
                }
                for slot in world.slots
            ],
            anchors=[{"id": a.id, "coord_x": a.coord_x, "coord_y": a.coord_y} for a in recipe.anchors],
        )


world_snapshot_service = WorldSnapshotService()
