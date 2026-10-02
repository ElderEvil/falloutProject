"""Service: own the world snapshot lifecycle (generate explicitly once, read thereafter).

The map renders the persisted snapshot; reads never regenerate. Generation is a
development/seed operation, not a request path.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.crud.world_snapshot import world_snapshot as snapshot_crud
from app.models.world_snapshot import WorldSnapshot
from app.services.world_generation_service import (
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
        await snapshot_crud.create(db_session, snapshot=snapshot)
        await db_session.commit()
        logger.info(
            "Generated world snapshot %s v%s (fingerprint=%s)",
            recipe.world_id,
            recipe.generator_version,
            world.recipe_fingerprint,
        )
        return snapshot

    @staticmethod
    def _to_model(recipe: WorldRecipe, world: GeneratedWorld) -> WorldSnapshot:
        return WorldSnapshot(
            world_id=recipe.world_id,
            generator_version=recipe.generator_version,
            seed=recipe.seed,
            config={
                "width": recipe.config.width,
                "height": recipe.config.height,
                "location_count": recipe.config.location_count,
                "slot_count": recipe.config.slot_count,
                "slot_columns": recipe.config.slot_columns,
                "slot_min_spacing": recipe.config.slot_min_spacing,
            },
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
