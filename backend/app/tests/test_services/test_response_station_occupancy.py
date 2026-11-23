"""Response Station occupancy and hazard-team independence (issue #997).

Occupancy follows the station's footprint (3/6/9 -> 2/4/6 slots) through the REAL
dweller-assignment path, and assignment never touches hazard-team membership.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    SPECIAL_STATS,
    AgeGroupEnum,
    GenderEnum,
    HazardTeam,
    IncidentType,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.dweller_service import dweller_service
from app.services.hazard_team_service import QUALIFYING_INCIDENTS, HazardTeamService
from app.services.room_assignment_policy import calculate_room_capacity
from app.services.room_service import room_service
from app.tests.test_services._hazard_team_helpers import fight, make_member, outfit_data
from app.utils.exceptions import ResourceConflictException

pytestmark = pytest.mark.asyncio

STATION = {
    "name": "Response Station",
    "category": RoomTypeEnum.RESPONSE,
    "ability": SPECIALEnum.ENDURANCE,
    "base_cost": 600,
    "incremental_cost": None,
    "t2_upgrade_cost": None,
    "t3_upgrade_cost": None,
    "size_min": 3,
    "size_max": 9,
    "tier": 1,
    "coordinate_y": 1,
}


def _station_create(vault_id: UUID, *, coordinate_x: int = 1, size: int = 3) -> RoomCreate:
    return RoomCreate(**STATION, vault_id=vault_id, size=size, coordinate_x=coordinate_x)


async def _create_station(session: AsyncSession, vault_id: UUID, *, coordinate_x: int = 1, size: int = 3) -> Room:
    return await crud.room.create(session, obj_in=_station_create(vault_id, coordinate_x=coordinate_x, size=size))


async def _ensure_elevator(session: AsyncSession, vault_id: UUID, coordinate_y: int) -> None:
    """Place the level-1 access the build-placement rules require before growing the station."""
    existing = await crud.room.get_room_by_coordinates(
        db_session=session, vault_id=vault_id, x_coord=0, y_coord=coordinate_y
    )
    if existing is None:
        await crud.room.create(
            session,
            obj_in=RoomCreate(
                vault_id=vault_id,
                name="Elevator",
                category=RoomTypeEnum.MISC,
                ability=None,
                base_cost=100,
                t2_upgrade_cost=None,
                t3_upgrade_cost=None,
                size_min=1,
                size_max=1,
                size=1,
                tier=1,
                coordinate_x=0,
                coordinate_y=coordinate_y,
            ),
        )


async def _grow_station(session: AsyncSession, vault_id: UUID, station_id: UUID) -> Room:
    """Grow the station one segment by building an adjacent segment through the real service path."""
    station = await crud.room.get(session, station_id)
    assert station.coordinate_x is not None
    assert station.coordinate_y is not None
    await _ensure_elevator(session, vault_id, station.coordinate_y)
    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        grown, _created = await room_service._build(
            db_session=session,
            obj_in=_station_create(vault_id, coordinate_x=station.coordinate_x + (station.size or station.size_min)),
        )
    return grown


async def _create_non_unique_room(session: AsyncSession, vault_id: UUID, *, coordinate_x: int = 1) -> Room:
    """A mergeable production room; worker capacity follows its footprint like any room."""
    return await crud.room.create(
        session,
        obj_in=RoomCreate(
            vault_id=vault_id,
            name="Power Generator",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            incremental_cost=25,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=9,
            size=3,
            tier=1,
            coordinate_x=coordinate_x,
            coordinate_y=1,
        ),
    )


async def _create_adult(session: AsyncSession, vault_id: UUID, surname: str) -> Dweller:
    return await crud.dweller.create(
        session,
        obj_in=DwellerCreate(
            vault_id=vault_id,
            first_name="Occupant",
            last_name=surname,
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=1,
            experience=0,
            max_health=100,
            health=100,
            radiation=0,
            happiness=50,
            **dict.fromkeys(SPECIAL_STATS, 5),
        ),
    )


@pytest.fixture
async def rich_vault(vault: Vault, async_session: AsyncSession) -> Vault:
    """Vault with enough caps to pay for every expansion in these tests."""
    vault.bottle_caps = 1_000_000
    async_session.add(vault)
    await async_session.commit()
    await async_session.refresh(vault)
    return vault


async def _occupants(session: AsyncSession, room: Room) -> int:
    return await crud.dweller.count_in_room(session, room.id)


async def test_station_size_three_holds_two_then_rejects_third(async_session: AsyncSession, rich_vault: Vault) -> None:
    station = await crud.room.get(async_session, (await _create_station(async_session, rich_vault.id)).id)
    assert station.size == 3
    assert calculate_room_capacity(station.size) == 2

    first = await _create_adult(async_session, rich_vault.id, "First")
    second = await _create_adult(async_session, rich_vault.id, "Second")
    third = await _create_adult(async_session, rich_vault.id, "Third")
    await dweller_service.move_to_room(async_session, first.id, station.id)
    await dweller_service.move_to_room(async_session, second.id, station.id)
    assert await _occupants(async_session, station) == 2

    with pytest.raises(ResourceConflictException, match="full capacity"):
        await dweller_service.move_to_room(async_session, third.id, station.id)
    assert await _occupants(async_session, station) == 2


async def test_station_grown_to_six_holds_four_then_rejects_fifth(
    async_session: AsyncSession, rich_vault: Vault
) -> None:
    station = await _create_station(async_session, rich_vault.id)
    await _grow_station(async_session, rich_vault.id, station.id)
    # Re-read the row so the assertion runs against committed state, not the stale instance.
    grown = await crud.room.get(async_session, station.id)
    assert (grown.id, grown.size, calculate_room_capacity(grown.size)) == (station.id, 6, 4)

    for index in range(4):
        await dweller_service.move_to_room(
            async_session, (await _create_adult(async_session, rich_vault.id, f"Occupant{index}")).id, grown.id
        )
    assert await _occupants(async_session, grown) == 4

    extra = await _create_adult(async_session, rich_vault.id, "Overflow")
    with pytest.raises(ResourceConflictException, match="full capacity"):
        await dweller_service.move_to_room(async_session, extra.id, grown.id)
    assert await _occupants(async_session, grown) == 4


async def test_station_grows_three_six_nine_through_assignment_path(
    async_session: AsyncSession, rich_vault: Vault
) -> None:
    station = await _create_station(async_session, rich_vault.id)
    adults = [await _create_adult(async_session, rich_vault.id, f"Person{i}") for i in range(7)]
    assigned: list[Dweller] = []

    async def assign_next() -> None:
        dweller = adults[len(assigned)]
        await dweller_service.move_to_room(async_session, dweller.id, station.id)
        assigned.append(dweller)

    async def expect_overflow_rejected() -> None:
        intruder = adults[len(assigned)]
        with pytest.raises(ResourceConflictException, match="full capacity"):
            await dweller_service.move_to_room(async_session, intruder.id, station.id)

    for size, slots in ((3, 2), (6, 4), (9, 6)):
        if size > 3:
            assert (await _grow_station(async_session, rich_vault.id, station.id)).size == size
        assert calculate_room_capacity(size) == slots
        for _ in range(2):
            await assign_next()
        assert await _occupants(async_session, station) == slots
        await expect_overflow_rejected()


async def test_assigning_dweller_to_station_creates_no_team_membership(
    async_session: AsyncSession, rich_vault: Vault
) -> None:
    """Moving a dweller into the station never joins them to a hazard team."""
    station = await _create_station(async_session, rich_vault.id)
    dweller = await _create_adult(async_session, rich_vault.id, "Newcomer")

    await dweller_service.move_to_room(async_session, dweller.id, station.id)

    for team in HazardTeam:
        assert await crud.team_crud.get_hazard_member(async_session, rich_vault.id, team, dweller.id) is None
    assert await crud.team_crud.get_hazard_team(async_session, rich_vault.id, HazardTeam.FIRE) == []
    assert await crud.team_crud.get_hazard_reserve(async_session, rich_vault.id, HazardTeam.RADIATION) == []


async def test_station_assignment_leaves_existing_roster_and_active_places_unchanged(
    async_session: AsyncSession, rich_vault: Vault
) -> None:
    station = await _create_station(async_session, rich_vault.id)
    veteran = await _create_adult(async_session, rich_vault.id, "Veteran")
    newcomer = await _create_adult(async_session, rich_vault.id, "Newcomer")
    await make_member(async_session, rich_vault.id, veteran.id, HazardTeam.FIRE, ACTIVE_STATUS)

    members = [veteran.id, newcomer.id]
    before = await crud.team_crud.get_active_hazard_member_ids(async_session, rich_vault.id, HazardTeam.FIRE, members)
    assert before == {veteran.id}

    await dweller_service.move_to_room(async_session, newcomer.id, station.id)

    after = await crud.team_crud.get_active_hazard_member_ids(async_session, rich_vault.id, HazardTeam.FIRE, members)
    assert after == {veteran.id}
    assert await crud.team_crud.get_hazard_member(async_session, rich_vault.id, HazardTeam.FIRE, newcomer.id) is None

    # Moving the veteran themselves into the station must not cost them their place.
    await dweller_service.move_to_room(async_session, veteran.id, station.id)
    veteran_place = await crud.team_crud.get_hazard_member(async_session, rich_vault.id, HazardTeam.FIRE, veteran.id)
    assert veteran_place is not None
    assert veteran_place.status == ACTIVE_STATUS


async def test_eligibility_and_active_place_do_not_depend_on_room_id(
    async_session: AsyncSession, rich_vault: Vault
) -> None:
    incident_room = await _create_non_unique_room(async_session, rich_vault.id)
    nomad = await _create_adult(async_session, rich_vault.id, "Nomad")
    assert nomad.room_id is None

    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, incident_room, IncidentType.FIRE, [nomad])

    place = await crud.team_crud.get_hazard_member(async_session, rich_vault.id, HazardTeam.FIRE, nomad.id)
    assert place is not None
    assert place.status == ACTIVE_STATUS

    station = await _create_station(async_session, rich_vault.id, coordinate_x=4)
    await dweller_service.move_to_room(async_session, nomad.id, station.id)

    place_after = await crud.team_crud.get_hazard_member(async_session, rich_vault.id, HazardTeam.FIRE, nomad.id)
    assert place_after is not None
    assert place_after.status == ACTIVE_STATUS
    active_ids = await crud.team_crud.get_active_hazard_member_ids(
        async_session, rich_vault.id, HazardTeam.FIRE, [nomad.id]
    )
    assert active_ids == {nomad.id}


async def _equip_catalog_named_outfit(async_session: AsyncSession, vault: Vault, dweller: Dweller, name: str):
    """Equip a stored outfit through the real equip path, returning (outfit_id, name)."""
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    outfit = await crud.outfit.create(async_session, outfit_data(name, storage_id=storage.id))
    await crud.outfit.equip(db_session=async_session, item_id=outfit.id, dweller_id=dweller.id)
    return outfit.id, outfit.name


async def test_demolish_and_rebuild_station_leaves_teams_ledger_and_gear_unchanged(
    async_session: AsyncSession, vault: Vault
) -> None:
    """Demolishing the Response Station and rebuilding it changes no roster state.

    Two members are stationed when it comes down, so the demolish also runs
    with occupants in the room being destroyed.
    """
    incident_room = await _create_non_unique_room(async_session, vault.id)
    station = await _create_station(async_session, vault.id, coordinate_x=5)
    fighters = [await _create_adult(async_session, vault.id, f"Fighter{i}") for i in range(4)]
    for _ in range(QUALIFYING_INCIDENTS):
        await fight(async_session, incident_room, IncidentType.FIRE, fighters)

    roster = await crud.team_crud.get_hazard_team(async_session, vault.id, HazardTeam.FIRE)
    active_before = {place.dweller_id: place.slot_number for place in roster if place.status == ACTIVE_STATUS}
    reserve_before = {place.dweller_id for place in roster if place.status == RESERVE_STATUS}
    assert (len(active_before), len(reserve_before)) == (3, 1)

    service_before = {
        dweller.id: await crud.incident_participant_crud.count_incidents(
            async_session, dweller.id, frozenset({IncidentType.FIRE})
        )
        for dweller in fighters
    }
    assert set(service_before.values()) == {QUALIFYING_INCIDENTS}
    gear_before = {
        dweller.id: await _equip_catalog_named_outfit(async_session, vault, dweller, "Firefighter suit")
        for dweller in fighters[:2]
    }

    await dweller_service.move_to_room(async_session, fighters[0].id, station.id)
    await dweller_service.move_to_room(async_session, fighters[1].id, station.id)
    assert await _occupants(async_session, station) == 2

    async def assert_roster_state_unchanged() -> None:
        current = await crud.team_crud.get_hazard_team(async_session, vault.id, HazardTeam.FIRE)
        assert {place.dweller_id: place.slot_number for place in current if place.status == ACTIVE_STATUS} == (
            active_before
        )
        assert {place.dweller_id for place in current if place.status == RESERVE_STATUS} == reserve_before
        for dweller in fighters:
            count = await crud.incident_participant_crud.count_incidents(
                async_session, dweller.id, frozenset({IncidentType.FIRE})
            )
            assert count == service_before[dweller.id]
        for dweller_id, (outfit_id, name) in gear_before.items():
            worn = await crud.outfit.get_equipped(async_session, dweller_id)
            assert worn is not None
            assert (worn.id, worn.name) == (outfit_id, name)

    await room_service.destroy_room(async_session, station.id)
    assert await crud.room.get_or_none(async_session, station.id) is None
    await assert_roster_state_unchanged()

    rebuilt = await _create_station(async_session, vault.id, coordinate_x=5)
    assert rebuilt.id != station.id
    assert rebuilt.size == 3
    await assert_roster_state_unchanged()


def test_hazard_team_eligibility_source_never_reads_room_id() -> None:
    """Structural guard: eligibility/roster methods and the roster CRUD never touch room_id."""
    for name in ("record_participation", "_join_if_qualified", "get_roster", "set_place"):
        source = inspect.getsource(getattr(HazardTeamService, name))
        assert "room_id" not in source, f"HazardTeamService.{name} must not read room_id"

    assert "room_id" not in inspect.getsource(type(crud.team_crud)), "the team roster CRUD must not read room_id"
