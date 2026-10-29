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
from app.services.world_generation_service import (
    MAP_V3_GENERATOR_VERSION,
    WorldConfig,
    WorldRecipe,
    generate_world,
)
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


async def test_pinned_v1_row_reloads_masks(async_session: AsyncSession) -> None:
    """An explicitly pinned v1 row reloads its persisted roads and rivers masks, version unchanged."""
    recipe = WorldRecipe(seed="legacy-v1", generator_version=1, config=WorldConfig())
    created = await world_snapshot_service.get_or_generate(async_session, recipe)
    reloaded = await snapshot_crud.get_version(async_session, world_id=recipe.world_id, generator_version=1)
    assert reloaded is not None
    assert reloaded.generator_version == 1
    assert reloaded.roads == created.roads
    assert reloaded.rivers == created.rivers
    assert reloaded.rivers


async def test_generated_snapshot_carries_empty_v3_payload(async_session: AsyncSession) -> None:
    """A v2 generator run leaves the additive v3 payload empty and reloadable."""
    recipe = WorldRecipe(seed="v3-empty", config=WorldConfig())
    created = await world_snapshot_service.get_or_generate(async_session, recipe)
    reloaded = await snapshot_crud.get_version(
        async_session, world_id=recipe.world_id, generator_version=recipe.generator_version
    )

    assert reloaded is not None
    for snapshot in (created, reloaded):
        assert snapshot.regions == []
        assert snapshot.region_map == []
        assert snapshot.places == []
        assert snapshot.road_edges == []
        assert snapshot.validation == {}
        assert snapshot.blueprint == {}
        assert snapshot.blueprint_hash == ""
        assert snapshot.blueprint_version == 0


async def test_map_v3_flag_selects_the_v3_recipe(async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Flipping the flag changes which canonical recipe the default read generates."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "map_v3", True)
    snapshot = await world_snapshot_service.get_or_generate(async_session)

    assert snapshot.generator_version == MAP_V3_GENERATOR_VERSION
    assert snapshot.regions
    assert len(snapshot.region_map) == snapshot.config["width"] * snapshot.config["height"]
    assert snapshot.validation["reachable_slot_tiles"] == 100


async def test_map_v3_flag_off_keeps_the_v2_recipe(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the flag dark, the default read still resolves the legacy v2 world."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "map_v3", False)
    snapshot = await world_snapshot_service.get_or_generate(async_session)

    assert snapshot.generator_version == 2
    assert snapshot.regions == []
    assert snapshot.region_map == []


async def test_v3_snapshot_round_trips_road_edges(async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Generated vector road edges persist and reload unchanged for the map renderer."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "map_v3", True)
    created = await world_snapshot_service.get_or_generate(async_session)
    reloaded = await snapshot_crud.get_version(
        async_session, world_id=created.world_id, generator_version=created.generator_version
    )

    assert created.road_edges
    assert created.rivers == []
    assert reloaded is not None
    assert reloaded.road_edges == created.road_edges
    assert reloaded.validation["roads"]["slots_with_road"] == 100
