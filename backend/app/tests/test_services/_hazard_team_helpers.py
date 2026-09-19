"""Shared helpers for the hazard-team service tests."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum, HazardTeam, OutfitTypeEnum, RarityEnum
from app.models.incident import IncidentType
from app.models.team import TeamMember
from app.services.hazard_team_service import hazard_team_service


async def raise_incident(session: AsyncSession, room, incident_type: IncidentType):
    return await crud.incident_crud.create(
        session, vault_id=room.vault_id, room_id=room.id, incident_type=incident_type, difficulty=2
    )


async def fight(session: AsyncSession, room, incident_type: IncidentType, dwellers: list):
    """Give each dweller one callout against the given hazard and persist it."""
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
