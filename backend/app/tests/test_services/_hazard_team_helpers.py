"""Shared helpers for the hazard-team service tests."""

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum, HazardTeam, IncidentType, OutfitTypeEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.models.room import Room
from app.models.team import TeamMember
from app.schemas.room import RoomCreate
from app.services.hazard_team_service import hazard_team_service


async def raise_incident(session: AsyncSession, room, incident_type: IncidentType):
    return await crud.incident_crud.create(
        session, vault_id=room.vault_id, room_id=room.id, incident_type=incident_type, difficulty=2
    )


async def empty_room(session: AsyncSession, vault_id: UUID4, *, name: str = "Diner", x: int = 7) -> Room:
    """A room with no dwellers in it — nobody to respond to an incident there."""
    return await crud.room.create(
        session,
        RoomCreate(
            name=name,
            category=RoomTypeEnum.PRODUCTION,
            ability=None,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=6,
            size=3,
            tier=1,
            coordinate_x=x,
            coordinate_y=0,
            vault_id=vault_id,
        ),
    )


async def ensure_station(session: AsyncSession, vault_id: UUID4) -> Room:
    """Give the vault a Response Station — the precondition for any hazard-team place.

    Idempotent: a station already standing is returned as-is, so a test that builds
    or demolishes its own station keeps its intent. Tests that only care about
    qualification call this first instead of restating the unique-room payload.
    """
    existing = await crud.room.get_by_category(session, vault_id, RoomTypeEnum.RESPONSE)
    if existing:
        return existing[0]
    station = RoomCreate(
        vault_id=vault_id,
        name="Response Station",
        category=RoomTypeEnum.RESPONSE,
        ability=SPECIALEnum.ENDURANCE,
        population_required=None,
        base_cost=600,
        incremental_cost=None,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        capacity=None,
        output=None,
        size_min=3,
        size_max=9,
        size=3,
        tier=1,
        coordinate_x=1,
        coordinate_y=1,
        image_url=None,
        capacity_formula=None,
        output_formula=None,
    )
    return await crud.room.create(session, obj_in=station)


async def fight(session: AsyncSession, room, incident_type: IncidentType, dwellers: list):
    """Give each dweller one callout against the given hazard and persist it."""
    await ensure_station(session, room.vault_id)
    incident = await raise_incident(session, room, incident_type)
    await hazard_team_service.record_participation(session, incident, dwellers)
    await session.commit()
    return incident


async def make_member(session: AsyncSession, vault_id, dweller_id, team: HazardTeam, status: str):
    team_row = await crud.team_crud.get_or_create_hazard_team(session, vault_id, team)
    slot_number = None
    if status == "active":
        active = await crud.team_crud.get_hazard_team(session, vault_id, team)
        taken = {place.slot_number for place in active if place.slot_number is not None}
        slot_number = next((slot for slot in (1, 2, 3) if slot not in taken), None)
    await crud.team_crud.add_member(
        session,
        TeamMember(team_id=team_row.id, dweller_id=dweller_id, status=status, slot_number=slot_number),
    )
    await session.commit()


def outfit_data(name: str, *, storage_id=None, dweller_id=None) -> dict:
    data = {
        "name": name,
        "rarity": RarityEnum.COMMON,
        "value": 10,
        "outfit_type": OutfitTypeEnum.COMMON,
        "gender": GenderEnum.MALE,
    }
    if storage_id:
        data["storage_id"] = storage_id
    if dweller_id:
        data["dweller_id"] = dweller_id
    return data


async def full_health(session: AsyncSession, dwellers: list) -> None:
    for dweller in dwellers:
        dweller.health = 100
        dweller.max_health = 100
        dweller.radiation = 0
        session.add(dweller)
    await session.commit()
