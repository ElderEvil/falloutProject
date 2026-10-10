"""Manual Active/Reserve moves on the earned hazard roster."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.schemas.dweller import DwellerCreate
from app.services.hazard_team_service import TEAM_SIZE, hazard_team_service
from app.tests.test_services._hazard_team_helpers import make_member
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


async def _dwellers_for_team(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict, count: int
) -> list:
    """The room's dwellers plus enough fresh ones to reach ``count``."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) < count:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )
    return dwellers


@pytest.mark.asyncio
async def test_activate_reserve_member_takes_lowest_free_slot(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A benched member activated by hand fills the lowest free slot and the roster reflects it."""
    room = room_with_dwellers["room"]
    dwellers = await _dwellers_for_team(async_session, room_with_dwellers, dweller_data, TEAM_SIZE + 1)
    for dweller in dwellers[:2]:
        await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    await make_member(async_session, room.vault_id, dwellers[2].id, HazardTeam.FIRE, RESERVE_STATUS)

    roster = await hazard_team_service.set_place(
        async_session, room.vault_id, HazardTeam.FIRE, dwellers[2].id, active=True
    )

    fire = next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)
    assert {place.dweller_id for place in fire.active} == {dwellers[0].id, dwellers[1].id, dwellers[2].id}
    assert dwellers[2].id not in {place.dweller_id for place in fire.reserve}
    active_by_id = {place.dweller_id: place for place in fire.active}
    assert active_by_id[dwellers[2].id].name == dwellers[2].display_name
    assert active_by_id[dwellers[2].id].level == dwellers[2].level
    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dwellers[2].id)
    assert place.status == ACTIVE_STATUS
    assert place.slot_number == 3

    await async_session.refresh(dwellers[2])
    service_entries = [entry for entry in dwellers[2].bio_entries if entry["source"] == "hazard"]
    assert any("Took an active place on the vault's fire team" in entry["text"] for entry in service_entries)


@pytest.mark.asyncio
async def test_activate_when_team_full_raises_conflict(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """Activating a fourth member while three hold active places is refused."""
    room = room_with_dwellers["room"]
    dwellers = await _dwellers_for_team(async_session, room_with_dwellers, dweller_data, TEAM_SIZE + 1)
    for dweller in dwellers[:TEAM_SIZE]:
        await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    await make_member(async_session, room.vault_id, dwellers[TEAM_SIZE].id, HazardTeam.FIRE, RESERVE_STATUS)

    with pytest.raises(ResourceConflictException):
        await hazard_team_service.set_place(
            async_session, room.vault_id, HazardTeam.FIRE, dwellers[TEAM_SIZE].id, active=True
        )


@pytest.mark.asyncio
async def test_bench_active_member_leaves_slot_open(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A voluntary stand-down drops to reserve with no slot and no auto-promotion."""
    room = room_with_dwellers["room"]
    dwellers = await _dwellers_for_team(async_session, room_with_dwellers, dweller_data, TEAM_SIZE + 1)
    for dweller in dwellers[:TEAM_SIZE]:
        await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    await make_member(async_session, room.vault_id, dwellers[TEAM_SIZE].id, HazardTeam.FIRE, RESERVE_STATUS)

    roster = await hazard_team_service.set_place(
        async_session, room.vault_id, HazardTeam.FIRE, dwellers[0].id, active=False
    )

    fire = next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)
    assert dwellers[0].id not in {place.dweller_id for place in fire.active}
    assert dwellers[0].id in {place.dweller_id for place in fire.reserve}
    # The bench member is NOT auto-promoted into the freed slot.
    assert dwellers[TEAM_SIZE].id not in {place.dweller_id for place in fire.active}
    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dwellers[0].id)
    assert place.status == RESERVE_STATUS
    assert place.slot_number is None


@pytest.mark.asyncio
async def test_activate_already_active_is_idempotent(async_session: AsyncSession, room_with_dwellers: dict):
    """Activating an already-active member changes nothing and raises nothing."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    roster = await hazard_team_service.set_place(async_session, room.vault_id, HazardTeam.FIRE, dweller.id, active=True)

    fire = next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)
    assert [place.dweller_id for place in fire.active] == [dweller.id]
    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place.status == ACTIVE_STATUS


@pytest.mark.asyncio
async def test_bench_already_reserve_is_idempotent(async_session: AsyncSession, room_with_dwellers: dict):
    """Benching an already-reserve member changes nothing and raises nothing."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)

    roster = await hazard_team_service.set_place(
        async_session, room.vault_id, HazardTeam.FIRE, dweller.id, active=False
    )

    fire = next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)
    assert [place.dweller_id for place in fire.reserve] == [dweller.id]
    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place.status == RESERVE_STATUS
    assert place.slot_number is None


@pytest.mark.asyncio
async def test_set_place_without_a_place_raises_not_found(async_session: AsyncSession, room_with_dwellers: dict):
    """A dweller holding no place on the team cannot be moved."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    with pytest.raises(ResourceNotFoundException):
        await hazard_team_service.set_place(async_session, room.vault_id, HazardTeam.FIRE, dweller.id, active=True)
