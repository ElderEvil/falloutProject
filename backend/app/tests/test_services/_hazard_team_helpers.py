"""Shared helpers for the hazard-team service tests."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum, HazardTeam, OutfitTypeEnum, RarityEnum
from app.models.hazard_team import HazardTeamMember
from app.models.incident import IncidentType
from app.services.contamination_team_service import contamination_team_service


async def raise_incident(session: AsyncSession, room, incident_type: IncidentType):
    return await crud.incident_crud.create(
        session, vault_id=room.vault_id, room_id=room.id, incident_type=incident_type, difficulty=2
    )


async def fight(session: AsyncSession, room, incident_type: IncidentType, dwellers: list):
    """Give each dweller one callout against the given hazard and persist it."""
    incident = await raise_incident(session, room, incident_type)
    await contamination_team_service.record_participation(session, incident, dwellers)
    await session.commit()
    return incident


async def make_member(session: AsyncSession, vault_id, dweller_id, team: HazardTeam, status: str):
    await crud.hazard_team_crud.add(
        session,
        HazardTeamMember(vault_id=vault_id, dweller_id=dweller_id, team=team, status=status),
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
