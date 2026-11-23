import math
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import ClassVar

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerLocationRelationEnum, ExplorationStatus, LocationTypeEnum
from app.core.game_config import game_config
from app.crud import world_location as crud_world_location
from app.crud.vault_slot import vault_slot
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.exploration.dispatch_resolution import resolve_dispatch_arrival
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.services.world_snapshot_service import world_snapshot_service
from app.utils import world_terrain
from app.utils.place_groups import get_place_group
from app.utils.time import utcnow
from app.utils.vault_slots import slot_coords

STRONG_STATS = dict.fromkeys(
    ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"), 10
) | {"level": 30, "health": 100, "max_health": 100, "radiation": 0}


async def _save(db, *objs):
    for obj in objs:
        db.add(obj)
    await db.commit()


async def _nearby_clearable(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dx: float = 5.0, name: str = "Slice3a Depot"
):
    slot = await vault_slot.get_by_vault(async_session, vault.id)
    if slot is None:
        slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
        await async_session.commit()
    origin = slot_coords(slot.slot_index)
    snapshot = await world_snapshot_service.get_or_generate(async_session)
    x, y = world_terrain.nearest_land(snapshot, origin[0] + dx, origin[1])
    location = await crud_world_location.get_or_create_location(async_session, name, coords=(x, y))
    location.group_key = "gas_station"
    async_session.add(location)
    await async_session.flush()
    state = await crud_world_location.get_or_create_state(
        async_session, vault.id, location.id, LocationTypeEnum.DISCOVERY
    )
    await crud_world_location.link_dweller(
        async_session, dweller.id, location.id, DwellerLocationRelationEnum.VISITED, is_unlocked=True
    )
    await async_session.commit()
    await async_session.refresh(location)
    await async_session.refresh(state)
    return location, state, origin


async def _vanish(async_session: AsyncSession, location, state) -> None:
    await async_session.delete(state)
    await async_session.delete(location)
    await async_session.commit()


class TestSpatialClearing:
    pytestmark: ClassVar = [pytest.mark.asyncio, pytest.mark.usefixtures("default_world_snapshot")]

    async def test_dispatch_persists_movement_and_positional_arrival_clears(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        location, state, origin = await _nearby_clearable(async_session, vault, dweller)
        exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
        assert (exploration.target_location_id, exploration.origin_x, exploration.origin_y) == (location.id, *origin)
        assert (exploration.pos_x, exploration.pos_y) == origin
        expected = world_terrain.heading_to(origin, (location.coord_x, location.coord_y))
        assert exploration.heading_degrees == pytest.approx(expected, abs=1e-6)
        assert (exploration.world_version is not None, len(exploration.trail)) == (True, 1)

        for key, value in STRONG_STATS.items():
            setattr(dweller, key, value)
        await _save(async_session, dweller)
        distance = math.dist(origin, (location.coord_x, location.coord_y))
        exploration.start_time = utcnow() - timedelta(hours=distance / 10 + 0.05)
        await _save(async_session, exploration)

        stats = await process_explorations(async_session, vault.id)

        await async_session.refresh(exploration)
        await async_session.refresh(state)
        assert (stats["returning"], exploration.status, state.clear_count) == (1, ExplorationStatus.RETURNING, 1)

    async def test_fresh_clear_uses_the_archetype_cooldown_while_inflight_expiry_survives(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        location, state = (await _nearby_clearable(async_session, vault, dweller))[:2]
        other, other_state = (await _nearby_clearable(async_session, vault, dweller, dx=12.0, name="Slice3a Hold"))[:2]
        for key, value in STRONG_STATS.items():
            setattr(dweller, key, value)
        await _save(async_session, dweller)
        frozen_expiry = utcnow() + timedelta(hours=3)
        other_state.reclear_available_at = frozen_expiry
        await _save(async_session, other_state)
        exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)

        await resolve_dispatch_arrival(async_session, exploration.id, arrived=True)

        await async_session.refresh(state)
        await async_session.refresh(other_state)
        assert state.reclear_available_at is not None
        expected_hours = get_place_group(location.group_key)["reclear_hours"]
        wait_hours = (state.reclear_available_at - utcnow()).total_seconds() / 3600
        assert (expected_hours - 1 < wait_hours <= expected_hours, other_state.reclear_available_at) == (
            True,
            frozen_expiry,
        )

    async def test_missing_target_returns_without_resolving(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        location, state = (await _nearby_clearable(async_session, vault, dweller))[:2]
        exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
        await _vanish(async_session, location, state)
        stats = await process_explorations(async_session, vault.id)
        await async_session.refresh(exploration)
        # No target row: the party turns around on an empty trail and the zero-length
        # return completes immediately. Nothing resolves, nothing clears.
        assert (exploration.status, stats["returning"]) == (ExplorationStatus.COMPLETED, 1)

        location2, state2 = (await _nearby_clearable(async_session, vault, dweller, name="Slice3a Annex"))[:2]
        exploration2 = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location2.id)
        await _vanish(async_session, location2, state2)
        await resolve_dispatch_arrival(async_session, exploration2.id, arrived=True)
        await async_session.refresh(exploration2)
        assert exploration2.status == ExplorationStatus.RETURNING


def test_obstruction_time_reflects_distance_traveled() -> None:
    base = datetime(2026, 1, 1)
    speed = 1 / game_config.exploration.dispatch.travel_hours_per_unit
    obstruction = exploration_service._obstruction_time(base, (0.0, 0.0), (speed, 0.0))
    assert (obstruction, obstruction > base) == (base + timedelta(hours=1), True)


def test_path_clear_detects_water_walls() -> None:
    snap = SimpleNamespace(
        config={"width": 5, "height": 1}, terrain=["wasteland", "wasteland", "water", "wasteland", "wasteland"]
    )
    assert exploration_service._path_clear(snap, (10.0, 50.0), (90.0, 50.0)) is False
    assert exploration_service._path_clear(snap, (10.0, 50.0), (30.0, 50.0)) is True
