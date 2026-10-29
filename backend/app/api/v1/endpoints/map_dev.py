"""Dev-only map lab API: generate an ephemeral v3 world for inspection."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.config import settings
from app.schemas.world_snapshot import WorldSlotRead, WorldSnapshotRead
from app.services.world_generation_service import (
    MAP_V3_GENERATOR_VERSION,
    MAP_V3_SEED_EPOCH,
    WORLD_ID,
    WorldConfig,
    WorldRecipe,
    generate_world,
    snapshot_checksum,
)
from app.utils.exceptions import NotFoundException

router = APIRouter(prefix="/map/dev", tags=["Map dev"])


@router.get("/world", response_model=WorldSnapshotRead)
async def preview_world(
    seed: Annotated[str, Query(min_length=1, max_length=64)] = "wasteland-atlas-v1",
) -> WorldSnapshotRead:
    """Generate an ephemeral v3 world for the local map lab; never persisted.

    The route is only mounted when ``ENVIRONMENT=local`` and also returns 404 if reached in
    any other environment, so production can never expose an arbitrary-seed generator.
    """
    if settings.ENVIRONMENT != "local":
        raise NotFoundException

    recipe = WorldRecipe(
        seed=seed,
        config=WorldConfig(),
        generator_version=MAP_V3_GENERATOR_VERSION,
        seed_epoch=MAP_V3_SEED_EPOCH,
    )
    world = generate_world(recipe)
    return WorldSnapshotRead(
        world_id=WORLD_ID,
        generator_version=world.generator_version,
        recipe_fingerprint=world.recipe_fingerprint,
        snapshot_checksum=snapshot_checksum(world),
        width=world.width,
        height=world.height,
        terrain=world.terrain,
        slots=[
            WorldSlotRead(slot_index=slot.slot_index, coord_x=slot.coord_x, coord_y=slot.coord_y)
            for slot in world.slots
        ],
        roads=world.roads,
        rivers=world.rivers,
        road_edges=world.road_edges,
        road_anchors=world.road_anchors,
        towns=world.towns,
        regions=world.regions,
        region_map=world.region_map,
        places=[],
        validation=world.validation,
    )
