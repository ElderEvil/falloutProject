"""Travel-backed clearing (slice 3a): dispatches move, arrive positionally, cool down 168h."""

import math
from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.vault_slot import vault_slot
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.vault import Vault
from app.services.exploration.dispatch_resolution import resolve_dispatch_arrival
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.services.map_service import map_service
from app.services.world_snapshot_service import world_snapshot_service
from app.utils import world_terrain
from app.utils.vault_slots import slot_coords

STRONG_STATS = {
    "strength": 10,
    "perception": 10,
    "endurance": 10,
    "charisma": 10,
    "intelligence": 10,
    "agility": 10,
    "luck": 10,
    "level": 30,
    "health": 100,
    "max_health": 100,
    "radiation": 0,
}


async def _boost_dweller(async_session: AsyncSession, dweller: Dweller) -> Dweller:
    for key, value in STRONG_STATS.items():
        setattr(dweller, key, value)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def _nearby_clearable(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dx: float = 5.0, name: str = "Slice3a Depot"
):
    """A clearable gas_station point due east of the vault's slot, snapped to land."""
    from app.core.enums import DwellerLocationRelationEnum
    from app.crud import world_location as crud_world_location
    from app.models.world_location import LocationTypeEnum

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


@pytest.mark.asyncio
async def test_dispatch_persists_movement_toward_its_target(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A dispatch departs with a heading aimed at its target, from the slot origin."""
    location, _state, origin = await _nearby_clearable(async_session, vault, dweller)

    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)

    assert exploration.target_location_id == location.id
    assert (exploration.origin_x, exploration.origin_y) == origin
    assert (exploration.pos_x, exploration.pos_y) == origin
    expected = world_terrain.heading_to(origin, (location.coord_x, location.coord_y))
    assert exploration.heading_degrees == pytest.approx(expected, abs=1e-6)
    assert exploration.world_version is not None
    assert len(exploration.trail) == 1


@pytest.mark.asyncio
async def test_arrival_resolves_positionally_before_timer_expiry(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Reaching the target resolves combat even with most of the travel time left."""
    location, state, origin = await _nearby_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller)
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    distance = math.dist(origin, (location.coord_x, location.coord_y))
    exploration.start_time = datetime.utcnow() - timedelta(hours=distance / 10 + 0.05)
    async_session.add(exploration)
    await async_session.commit()

    stats = await process_explorations(async_session, vault.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert stats["returning"] == 1
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.clear_count == 1


@pytest.mark.asyncio
async def test_fresh_clear_cools_down_168h_while_inflight_expiry_survives(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """New clears wait a week; a pre-existing expiry is never recalculated."""
    location, state = (await _nearby_clearable(async_session, vault, dweller))[:2]
    other, other_state = (await _nearby_clearable(async_session, vault, dweller, dx=12.0, name="Slice3a Hold"))[:2]
    await _boost_dweller(async_session, dweller)
    frozen_expiry = datetime.utcnow() + timedelta(hours=3)
    other_state.reclear_available_at = frozen_expiry
    async_session.add(other_state)
    await async_session.commit()
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)

    await resolve_dispatch_arrival(async_session, exploration.id, arrived=True)

    await async_session.refresh(state)
    await async_session.refresh(other_state)
    assert state.reclear_available_at is not None
    wait_hours = (state.reclear_available_at - datetime.utcnow()).total_seconds() / 3600
    assert 167 < wait_hours <= 168
    assert other_state.reclear_available_at == frozen_expiry


@pytest.mark.asyncio
async def test_missing_target_returns_without_resolving(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A dispatch whose target row vanished comes home; nothing resolves, nothing clears."""
    from app.models.world_location import VaultLocationState, WorldLocation

    location, state = (await _nearby_clearable(async_session, vault, dweller))[:2]
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    await async_session.delete(state)
    await async_session.delete(location)
    await async_session.commit()

    stats = await process_explorations(async_session, vault.id)

    await async_session.refresh(exploration)
    # No target row: the party turns around on an empty trail and the zero-length
    # return completes immediately. Nothing resolves, nothing clears.
    assert exploration.status == ExplorationStatus.COMPLETED
    assert stats["returning"] == 1
