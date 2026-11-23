"""Snapshot lifecycle contract: a read must resolve an explicitly selected ``(world_id, generator_version)``
slice, and generating a later version must not change what an existing reader sees. There is deliberately no
"newest wins" path.
"""

from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import PlaceKindEnum
from app.crud.world_snapshot import world_snapshot as snapshot_crud
from app.models.world_location import WorldLocation
from app.services.map.road_generation import ROAD_VERSION, place_on_road
from app.services.map.world_generation import WorldConfig, WorldRecipe, _largest_traversable_component, generate_world
from app.services.world_snapshot_service import WorldSnapshotService
from app.services.world_snapshot_service import world_snapshot_service as svc
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException

pytestmark = pytest.mark.asyncio


def _recipe(seed: str, version: int = 1) -> WorldRecipe:
    return WorldRecipe(seed=seed, generator_version=version, config=WorldConfig())


def _place(name: str, x: float, y: float, source: str = "seed") -> WorldLocation:
    return WorldLocation(
        name=name,
        normalized_name=name.lower(),
        kind=PlaceKindEnum.PLACE,
        source=source,
        coord_x=x,
        coord_y=y,
    )


async def _reload(session: AsyncSession):
    return await snapshot_crud.get_version(session, world_id="wasteland-atlas", generator_version=1)


async def _raises_on_write(session: AsyncSession, phase: str, message: str, call) -> None:
    def boom(*_args: object) -> None:
        raise RuntimeError(message)

    event.listen(session.sync_session, phase, boom)
    try:
        with pytest.raises(RuntimeError, match=message):
            await call()
    finally:
        event.remove(session.sync_session, phase, boom)
        await session.rollback()


async def test_read_selects_explicit_version_not_newest(async_session: AsyncSession) -> None:
    v1, v2 = _recipe("activation-v1", 1), _recipe("activation-v2", 2)
    first, second = [await svc.get_or_generate(async_session, r) for r in (v1, v2)]
    assert (first.world_id, first.generator_version) == (v1.world_id, 1)
    assert (second.world_id, second.generator_version) == (v2.world_id, 2)
    reread = await svc.get_or_generate(async_session, v1)  # the newer v2 row must not shadow v1
    assert reread.id == first.id
    assert reread.generator_version == 1
    assert reread.snapshot_checksum == first.snapshot_checksum


async def test_generate_is_idempotent_per_version(async_session: AsyncSession) -> None:
    recipe = _recipe("idempotent")
    first = await svc.get_or_generate(async_session, recipe)
    second = await svc.get_or_generate(async_session, recipe)
    assert second.id == first.id
    assert second.snapshot_checksum == first.snapshot_checksum


async def test_duplicate_version_insert_is_rejected(async_session: AsyncSession) -> None:
    recipe = _recipe("dup")
    await svc.get_or_generate(async_session, recipe)
    snapshot = WorldSnapshotService._to_model(recipe, generate_world(recipe))
    with pytest.raises(IntegrityError):
        await snapshot_crud.create(async_session, snapshot=snapshot)
    await async_session.rollback()


async def test_creation_race_returns_existing_row(async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    recipe = _recipe("race")
    winner = await svc.get_or_generate(async_session, recipe)
    real_get_version, calls = snapshot_crud.get_version, 0

    async def stale_check(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return None if calls == 1 else await real_get_version(*args, **kwargs)

    monkeypatch.setattr(snapshot_crud, "get_version", stale_check)
    assert (await svc.get_or_generate(async_session, recipe)).id == winner.id


async def test_persisted_config_matches_generation_input(async_session: AsyncSession) -> None:
    recipe = _recipe("cfg")
    assert (await svc.get_or_generate(async_session, recipe)).config == asdict(recipe.config)


async def test_road_backfill_preserves_world_and_is_idempotent(async_session: AsyncSession) -> None:
    snapshot = await svc.get_or_generate(async_session)
    snapshot.roads = None
    await async_session.commit()
    original = (snapshot.terrain.copy(), snapshot.slots.copy(), snapshot.recipe_fingerprint, snapshot.snapshot_checksum)
    assert (await svc.read(async_session)).roads is None
    updated = await svc.backfill_roads(async_session, expected_checksum=snapshot.snapshot_checksum)
    assert updated.roads
    assert updated.roads["segments"]
    roads = updated.roads.copy()
    await async_session.refresh(updated)
    assert (updated.terrain, updated.slots, updated.recipe_fingerprint, updated.snapshot_checksum) == original
    assert (await svc.backfill_roads(async_session)).roads == roads
    assert (await svc.read(async_session)).roads.model_dump(mode="json") == roads


async def test_stale_road_backfill_rejects_without_writing(async_session: AsyncSession) -> None:
    snapshot = await svc.get_or_generate(async_session)
    snapshot.roads = None
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="World changed"):
        await svc.backfill_roads(async_session, expected_checksum="old-base")
    await async_session.rollback()
    assert (await _reload(async_session)).roads is None


async def test_road_backfill_requires_an_existing_world(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException):
        await svc.backfill_roads(async_session, world_id="missing-world")
    assert await snapshot_crud.get_version(async_session, world_id="missing-world", generator_version=1) is None


async def test_roads_from_a_different_base_are_neither_served_nor_overwritten(async_session: AsyncSession) -> None:
    snapshot = await svc.get_or_generate(async_session)
    incompatible = {**snapshot.roads, "base_checksum": "another-base"}
    snapshot.roads = incompatible
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="different terrain"):
        await svc.read(async_session)
    with pytest.raises(ResourceConflictException, match="different base"):
        await svc.backfill_roads(async_session)
    await async_session.rollback()
    assert (await _reload(async_session)).roads == incompatible


@pytest.mark.parametrize("legacy_roads", [False, True])
async def test_failed_road_write_rolls_back_without_altering_geography(
    async_session: AsyncSession, legacy_roads: bool
) -> None:
    snapshot = await svc.get_or_generate(async_session)
    original_roads = {**snapshot.roads, "version": 1} if legacy_roads else None
    snapshot.roads = original_roads
    await async_session.commit()
    original = (snapshot.terrain.copy(), snapshot.slots.copy(), snapshot.snapshot_checksum)
    await _raises_on_write(
        async_session,
        "after_flush_postexec",
        "late road persistence failure",
        lambda: svc.backfill_roads(async_session, upgrade=legacy_roads),
    )
    reloaded = await _reload(async_session)
    assert reloaded.roads == original_roads
    assert (reloaded.terrain, reloaded.slots, reloaded.snapshot_checksum) == original


async def test_explicit_road_upgrade_replaces_only_the_older_layer(async_session: AsyncSession) -> None:
    snapshot = await svc.get_or_generate(async_session)
    snapshot.roads = {**snapshot.roads, "version": 1, "segments": []}
    await async_session.commit()
    original = (snapshot.terrain.copy(), snapshot.slots.copy(), snapshot.snapshot_checksum, snapshot.generator_version)
    with pytest.raises(ResourceConflictException, match="--upgrade"):
        await svc.backfill_roads(async_session)
    await async_session.rollback()
    updated = await svc.backfill_roads(async_session, upgrade=True)
    assert updated.roads["version"] == ROAD_VERSION
    assert len(updated.roads["segments"]) >= 30
    assert any(segment["kind"] == "railroad" for segment in updated.roads["segments"])
    assert (updated.terrain, updated.slots, updated.snapshot_checksum, updated.generator_version) == original
    payload = updated.roads.copy()
    assert (await svc.backfill_roads(async_session, upgrade=True)).roads == payload


def _roadside_slot(terrain: list[str], spine: list[tuple[float, float]]) -> tuple[float, float]:
    """A land coordinate far enough from every road vertex that connect_places owes it a genuine spur."""
    land, vertices = _largest_traversable_component(terrain, 80, 80), set(spine)

    def cell(point: tuple[float, float]) -> int:
        return min(79, int(point[1] * 0.8)) * 80 + min(79, int(point[0] * 0.8))

    offsets = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (1.0, 1.0), (-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0))
    for vertex in sorted(vertices):
        for dx, dy in offsets:
            point = (vertex[0] + dx, vertex[1] + dy)
            if all(0.0 <= c < 100 for c in point) and cell(point) in land and not place_on_road(point, vertices):
                return point
    pytest.fail("no roadside slot near the backbone")


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize("fail_write", [False, True])
async def test_public_place_connections_preserve_network_and_privacy(
    async_session: AsyncSession, fail_write: bool, refresh: bool
) -> None:
    snapshot = await svc.get_or_generate(async_session)
    if refresh:
        snapshot.roads = {
            **snapshot.roads,
            "segments": [
                *snapshot.roads["segments"],
                {
                    "id": "orphan",
                    "kind": "country",
                    "location_id": str(uuid4()),
                    "points": [[10.0, 10.0], [90.0, 90.0]],
                },
            ],
        }
        await async_session.commit()
    original = snapshot.roads.copy()
    point = original["segments"][0]["points"][0]
    water = snapshot.terrain.index("water")
    spine = [
        tuple(p)
        for road in original["segments"]
        if road["kind"] != "railroad" and not road.get("location_id")
        for p in road["points"]
    ]
    roadside_slot = _roadside_slot(snapshot.terrain, spine)
    public = _place("Public depot", point[0], point[1])
    private = _place("Private discovery", point[0], point[1], source="emergent")
    blocked = _place("Water landmark", (water % 80 + 0.5) * 1.25, (water // 80 + 0.5) * 1.25)
    roadside = _place("Roadside depot", roadside_slot[0], roadside_slot[1])
    async_session.add_all([public, private, blocked, roadside])
    await async_session.commit()
    public_id, private_id, roadside_id = str(public.id), str(private.id), str(roadside.id)
    if fail_write:
        await _raises_on_write(
            async_session,
            "after_flush_postexec",
            "connection write failed",
            lambda: svc.connect_places(async_session, refresh=refresh),
        )
        assert (await _reload(async_session)).roads == original
        return
    result = await svc.connect_places(async_session, refresh=refresh)
    assert result.added == 1
    assert result.off_road == 1
    assert result.already_connected == 1
    await async_session.refresh(snapshot)
    segments = snapshot.roads["segments"]
    access = [r for r in segments if r.get("location_id")]
    backbone = [{k: v for k, v in r.items() if v is not None} for r in original["segments"] if not r.get("location_id")]
    assert [r for r in segments if not r.get("location_id")] == backbone
    assert len(access) == 1
    assert access[0]["location_id"] == roadside_id
    assert access[0]["location_id"] != private_id
    assert access[0]["points"][0] == [roadside_slot[0], roadside_slot[1]]
    assert access[0]["points"][-1] in [
        p for r in original["segments"] if r["kind"] != "railroad" and not r.get("location_id") for p in r["points"]
    ]
    assert not any(r.get("location_id") == public_id for r in segments)
    assert result.removed == int(refresh)
    payload = snapshot.roads.copy()
    assert (await svc.connect_places(async_session)).added == 0
    await svc.connect_places(async_session, refresh=True)
    await async_session.refresh(snapshot)
    assert snapshot.roads == payload


@pytest.mark.parametrize("state", ["missing", "no_roads", "base", "old", "new"])
async def test_place_connections_reject_invalid_snapshot(async_session: AsyncSession, state: str) -> None:
    if state != "missing":
        snapshot = await svc.get_or_generate(async_session)
        if state == "no_roads":
            snapshot.roads = None
        elif state == "base":
            snapshot.roads = {**snapshot.roads, "base_checksum": "stale"}
        else:
            snapshot.roads = {**snapshot.roads, "version": ROAD_VERSION + (1 if state == "new" else -1)}
        await async_session.commit()
        original = snapshot.roads
    with pytest.raises(ResourceConflictException):
        await svc.connect_places(async_session)
    await async_session.rollback()
    if state != "missing":
        await async_session.refresh(snapshot)
        assert snapshot.roads == original
