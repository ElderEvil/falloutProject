"""Service: own the world snapshot lifecycle (generate explicitly once, read thereafter).

The map renders the persisted snapshot; reads never regenerate. Generation is a
development/seed operation, not a request path.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING, cast

from sqlalchemy.exc import IntegrityError

from app.crud.world_location import world_location as location_crud
from app.crud.world_snapshot import world_snapshot as snapshot_crud
from app.models.world_snapshot import WorldSnapshot
from app.schemas.world_snapshot import WorldRoadConnectionsResult, WorldRoadsRead, WorldSlotRead, WorldSnapshotRead
from app.services.map.road_generation import ROAD_VERSION, generate_roads, place_access_road
from app.services.map.world_generation import (
    GENERATOR_VERSION,
    WORLD_ID,
    GeneratedWorld,
    TerrainType,
    WorldConfig,
    WorldRecipe,
    _largest_traversable_component,
    generate_world,
    snapshot_checksum,
)
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class WorldSnapshotService:
    async def connect_places(self, db_session: AsyncSession, *, refresh: bool = False) -> WorldRoadConnectionsResult:
        """Add public-place access roads atomically; preserve the existing network."""
        snapshot = await snapshot_crud.get_version(
            db_session, world_id=WORLD_ID, generator_version=GENERATOR_VERSION, for_update=True
        )
        if snapshot is None or snapshot.roads is None:
            raise ResourceConflictException("Generate the shared road network first")
        roads = WorldRoadsRead.model_validate(snapshot.roads)
        if roads.base_checksum != snapshot.snapshot_checksum:
            raise ResourceConflictException("Roads belong to a different terrain snapshot")
        if roads.version != ROAD_VERSION:
            raise ResourceConflictException(
                "Access roads require the current road recipe; upgrade the road layer first"
            )
        removed = 0
        if refresh:
            removed = sum(r.location_id is not None for r in roads.segments)
            roads.segments = [r for r in roads.segments if r.location_id is None]
        width, height = snapshot.config["width"], snapshot.config["height"]
        land = _largest_traversable_component(cast("list[TerrainType]", snapshot.terrain), width, height)
        vertices = {p for r in roads.segments if r.kind != "railroad" and r.location_id is None for p in r.points}
        connected = {r.location_id for r in roads.segments if r.location_id is not None}
        added = skipped = 0
        for place in await location_crud.get_public_road_places(db_session):
            if place.id in connected:
                continue
            access = place_access_road(
                terrain=snapshot.terrain,
                width=snapshot.config["width"],
                height=snapshot.config["height"],
                origin=(place.coord_x, place.coord_y),
                land=land,
                vertices=vertices,
                location_id=str(place.id),
            )
            if access is None:
                skipped += 1
                continue
            roads.segments.append(access)
            added += 1
        if added or removed:
            payload = roads.model_dump(mode="json", exclude={"checksum"}, exclude_none=True)
            roads.checksum = hashlib.blake2b(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), digest_size=16
            ).hexdigest()
            snapshot.roads = roads.model_dump(mode="json", exclude_none=True)
            db_session.add(snapshot)
            await db_session.commit()
        return WorldRoadConnectionsResult(
            added=added, off_road=skipped, already_connected=len(connected), removed=removed
        )

    async def read(self, db_session: AsyncSession) -> WorldSnapshotRead:
        """Read public cartography; never backfill an existing world during GET."""
        snapshot = await self.get_or_generate(db_session)
        roads = WorldRoadsRead.model_validate(snapshot.roads) if snapshot.roads is not None else None
        if roads is not None and roads.base_checksum != snapshot.snapshot_checksum:
            raise ResourceConflictException("Roads belong to a different terrain snapshot")
        return WorldSnapshotRead(
            world_id=snapshot.world_id,
            generator_version=snapshot.generator_version,
            recipe_fingerprint=snapshot.recipe_fingerprint,
            snapshot_checksum=snapshot.snapshot_checksum,
            width=snapshot.config["width"],
            height=snapshot.config["height"],
            terrain=snapshot.terrain,
            slots=[WorldSlotRead(**slot) for slot in snapshot.slots],
            roads=roads,
        )

    async def backfill_roads(
        self,
        db_session: AsyncSession,
        *,
        world_id: str = WORLD_ID,
        generator_version: int = GENERATOR_VERSION,
        expected_checksum: str | None = None,
        upgrade: bool = False,
    ) -> WorldSnapshot:
        """Own one locked, atomic road-payload write; existing geography is untouched."""
        snapshot = await snapshot_crud.get_version(
            db_session, world_id=world_id, generator_version=generator_version, for_update=True
        )
        if snapshot is None:
            raise ResourceNotFoundException(WorldSnapshot, f"{world_id}:{generator_version}", "world/version")
        if expected_checksum is not None and expected_checksum != snapshot.snapshot_checksum:
            raise ResourceConflictException("World changed since road generation was requested")
        if snapshot.roads is not None:
            roads = WorldRoadsRead.model_validate(snapshot.roads)
            if roads.base_checksum != snapshot.snapshot_checksum or roads.version > ROAD_VERSION:
                raise ResourceConflictException(
                    "Existing roads have a different base or recipe; explicit migration required"
                )
            if roads.version == ROAD_VERSION:
                return snapshot
            if not upgrade:
                raise ResourceConflictException("An older road recipe exists; rerun with --upgrade")
        snapshot.roads = generate_roads(
            terrain=snapshot.terrain,
            width=snapshot.config["width"],
            height=snapshot.config["height"],
            seed=snapshot.seed,
            base_checksum=snapshot.snapshot_checksum,
        ).model_dump(mode="json")
        db_session.add(snapshot)
        await db_session.commit()
        return snapshot

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

    @staticmethod
    def _to_model(recipe: WorldRecipe, world: GeneratedWorld) -> WorldSnapshot:
        checksum = snapshot_checksum(world)
        return WorldSnapshot(
            world_id=recipe.world_id,
            generator_version=recipe.generator_version,
            seed=recipe.seed,
            # The whole config, derived programmatically so new fields cannot
            # silently diverge from the fingerprint input.
            config=asdict(recipe.config),
            recipe_fingerprint=world.recipe_fingerprint,
            snapshot_checksum=checksum,
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
            roads=generate_roads(
                terrain=list(world.terrain),
                width=world.width,
                height=world.height,
                seed=recipe.seed,
                base_checksum=checksum,
            ).model_dump(mode="json"),
        )


world_snapshot_service = WorldSnapshotService()
