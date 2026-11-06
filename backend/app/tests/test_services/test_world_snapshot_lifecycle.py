"""Snapshot lifecycle contract: generating a version never activates it.

The requirement under test: a read must resolve an *explicitly selected*
``(world_id, generator_version)`` slice, and generating a later version must not
change what an existing reader sees. There is deliberately no "newest wins" path.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.world_snapshot import world_snapshot as snapshot_crud
from app.services.map.world_generation import WorldConfig, WorldRecipe, generate_world
from app.services.world_snapshot_service import WorldSnapshotService, world_snapshot_service

pytestmark = pytest.mark.asyncio


async def test_read_selects_explicit_version_not_newest(async_session: AsyncSession) -> None:
    """Generating v2 leaves reads for v1 unchanged: no implicit activation."""
    v1 = WorldRecipe(seed="activation-v1", generator_version=1, config=WorldConfig())
    v2 = WorldRecipe(seed="activation-v2", generator_version=2, config=WorldConfig())

    first = await world_snapshot_service.get_or_generate(async_session, v1)
    second = await world_snapshot_service.get_or_generate(async_session, v2)

    assert (first.world_id, first.generator_version) == (v1.world_id, 1)
    assert (second.world_id, second.generator_version) == (v2.world_id, 2)

    # Re-reading v1 still returns the v1 row — the newer v2 row does not shadow it.
    reread_v1 = await world_snapshot_service.get_or_generate(async_session, v1)
    assert reread_v1.id == first.id
    assert reread_v1.generator_version == 1
    assert reread_v1.snapshot_checksum == first.snapshot_checksum


async def test_generate_is_idempotent_per_version(async_session: AsyncSession) -> None:
    """A second generate for the same version returns the same row (no duplicate write)."""
    recipe = WorldRecipe(seed="idempotent", generator_version=1, config=WorldConfig())
    first = await world_snapshot_service.get_or_generate(async_session, recipe)
    second = await world_snapshot_service.get_or_generate(async_session, recipe)
    assert second.id == first.id
    assert second.snapshot_checksum == first.snapshot_checksum


async def test_duplicate_version_insert_is_rejected(async_session: AsyncSession) -> None:
    """The (world_id, generator_version) uniqueness holds at the database level."""
    recipe = WorldRecipe(seed="dup", generator_version=1, config=WorldConfig())
    await world_snapshot_service.get_or_generate(async_session, recipe)
    with pytest.raises(IntegrityError):
        await snapshot_crud.create(
            async_session,
            snapshot=WorldSnapshotService._to_model(recipe, generate_world(recipe)),
        )
    await async_session.rollback()


async def test_creation_race_returns_existing_row(async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """A lost creation race returns the winner instead of failing.

    Simulates check-then-insert interleaving: the initial read misses, a
    competitor persists, our insert hits the unique constraint.
    """
    recipe = WorldRecipe(seed="race", generator_version=1, config=WorldConfig())
    winner = await world_snapshot_service.get_or_generate(async_session, recipe)

    real_get_version = snapshot_crud.get_version
    calls = 0

    async def stale_check(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return await real_get_version(*args, **kwargs)

    monkeypatch.setattr(snapshot_crud, "get_version", stale_check)
    result = await world_snapshot_service.get_or_generate(async_session, recipe)
    assert result.id == winner.id


async def test_persisted_config_matches_generation_input(async_session: AsyncSession) -> None:
    """The stored config is the full generation input, not a subset."""
    recipe = WorldRecipe(seed="cfg", generator_version=1, config=WorldConfig())
    snapshot = await world_snapshot_service.get_or_generate(async_session, recipe)
    assert snapshot.config == asdict(recipe.config)


async def test_road_backfill_preserves_world_and_is_idempotent(async_session: AsyncSession) -> None:
    snapshot = await world_snapshot_service.get_or_generate(async_session)
    snapshot.roads = None
    await async_session.commit()
    original = (snapshot.terrain.copy(), snapshot.slots.copy(), snapshot.recipe_fingerprint, snapshot.snapshot_checksum)
    assert (await world_snapshot_service.read(async_session)).roads is None
    updated = await world_snapshot_service.backfill_roads(async_session, expected_checksum=snapshot.snapshot_checksum)
    assert updated.roads
    assert updated.roads["segments"]
    roads = updated.roads.copy()
    await async_session.refresh(updated)
    assert (updated.terrain, updated.slots, updated.recipe_fingerprint, updated.snapshot_checksum) == original
    repeated = await world_snapshot_service.backfill_roads(async_session)
    assert repeated.roads == roads
    assert (await world_snapshot_service.read(async_session)).roads.model_dump(mode="json") == roads


async def test_stale_road_backfill_rejects_without_writing(async_session: AsyncSession) -> None:
    from app.utils.exceptions import ResourceConflictException

    snapshot = await world_snapshot_service.get_or_generate(async_session)
    snapshot.roads = None
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="World changed"):
        await world_snapshot_service.backfill_roads(async_session, expected_checksum="old-base")
    await async_session.rollback()
    reloaded = await snapshot_crud.get_version(async_session, world_id="wasteland-atlas", generator_version=1)
    assert reloaded.roads is None


async def test_road_backfill_requires_an_existing_world(async_session: AsyncSession) -> None:
    from app.utils.exceptions import ResourceNotFoundException

    with pytest.raises(ResourceNotFoundException):
        await world_snapshot_service.backfill_roads(async_session, world_id="missing-world")
    assert await snapshot_crud.get_version(async_session, world_id="missing-world", generator_version=1) is None


async def test_roads_from_a_different_base_are_neither_served_nor_overwritten(async_session: AsyncSession) -> None:
    from app.utils.exceptions import ResourceConflictException

    snapshot = await world_snapshot_service.get_or_generate(async_session)
    incompatible = {**snapshot.roads, "base_checksum": "another-base"}
    snapshot.roads = incompatible
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="different terrain"):
        await world_snapshot_service.read(async_session)
    with pytest.raises(ResourceConflictException, match="different base"):
        await world_snapshot_service.backfill_roads(async_session)
    await async_session.rollback()
    reloaded = await snapshot_crud.get_version(async_session, world_id="wasteland-atlas", generator_version=1)
    assert reloaded.roads == incompatible


@pytest.mark.parametrize("legacy_roads", [False, True])
async def test_failed_road_write_rolls_back_without_altering_geography(
    async_session: AsyncSession, legacy_roads: bool
) -> None:
    from sqlalchemy import event

    snapshot = await world_snapshot_service.get_or_generate(async_session)
    original_roads = {**snapshot.roads, "version": 1} if legacy_roads else None
    snapshot.roads = original_roads
    await async_session.commit()
    original = (snapshot.terrain.copy(), snapshot.slots.copy(), snapshot.snapshot_checksum)

    def reject_commit(session, flush_context):
        raise RuntimeError("late road persistence failure")

    event.listen(async_session.sync_session, "after_flush_postexec", reject_commit)
    try:
        with pytest.raises(RuntimeError, match="late road persistence failure"):
            await world_snapshot_service.backfill_roads(async_session, upgrade=legacy_roads)
    finally:
        event.remove(async_session.sync_session, "after_flush_postexec", reject_commit)
        await async_session.rollback()
    reloaded = await snapshot_crud.get_version(async_session, world_id="wasteland-atlas", generator_version=1)
    assert reloaded.roads == original_roads
    assert (reloaded.terrain, reloaded.slots, reloaded.snapshot_checksum) == original


async def test_explicit_road_upgrade_replaces_only_the_older_layer(async_session: AsyncSession) -> None:
    from app.services.map.road_generation import ROAD_VERSION
    from app.utils.exceptions import ResourceConflictException

    snapshot = await world_snapshot_service.get_or_generate(async_session)
    snapshot.roads = {**snapshot.roads, "version": 1, "segments": []}
    await async_session.commit()
    original = (snapshot.terrain.copy(), snapshot.slots.copy(), snapshot.snapshot_checksum, snapshot.generator_version)
    with pytest.raises(ResourceConflictException, match="--upgrade"):
        await world_snapshot_service.backfill_roads(async_session)
    await async_session.rollback()
    updated = await world_snapshot_service.backfill_roads(async_session, upgrade=True)
    assert updated.roads["version"] == ROAD_VERSION
    assert len(updated.roads["segments"]) >= 30
    assert any(segment["kind"] == "railroad" for segment in updated.roads["segments"])
    assert (updated.terrain, updated.slots, updated.snapshot_checksum, updated.generator_version) == original
    payload = updated.roads.copy()
    assert (await world_snapshot_service.backfill_roads(async_session, upgrade=True)).roads == payload
