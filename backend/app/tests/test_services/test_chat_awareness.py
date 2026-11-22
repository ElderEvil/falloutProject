from datetime import timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentType
from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.services.chat.awareness import build_awareness_digest
from app.tests.factory.vaults import random_vault_number
from app.utils.time import utcnow


async def _incident(async_session: AsyncSession, vault: Vault, room: Room, message: str, at) -> Incident:
    incident = Incident(vault_id=vault.id, room_id=room.id, type=IncidentType.FIRE, difficulty=1, start_time=at)
    async_session.add(incident)
    await async_session.flush()
    async_session.add(IncidentEvent(incident_id=incident.id, kind="resolved", message=message, created_at=at))
    await async_session.flush()
    return incident


async def _other_vault(async_session: AsyncSession) -> Vault:
    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username="othervault", email="other@example.com", password="correct horse battery"),
    )
    return await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in=VaultCreate(number=random_vault_number(), population_max=50),
        user_id=user.id,
    )


async def test_none_since_returns_nothing(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    await _incident(async_session, vault, radio_room, "Fire contained", utcnow())

    assert await build_awareness_digest(async_session, vault_id=vault.id, since=None, max_lines=8) == []


async def test_incident_after_since_appears_once(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    since = utcnow() - timedelta(days=3)
    incident = await _incident(async_session, vault, radio_room, "Fire contained", since + timedelta(hours=1))
    async_session.add(
        IncidentEvent(
            incident_id=incident.id,
            kind="spread",
            message="Fire spread to the workshop",
            created_at=since + timedelta(hours=2),
        )
    )
    await async_session.flush()

    lines = await build_awareness_digest(async_session, vault_id=vault.id, since=since, max_lines=8)

    assert len(lines) == 1
    assert "Fire" in lines[0]
    assert lines[0].startswith("Fire spread to the workshop")


async def test_incident_before_since_is_ignored(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    since = utcnow()
    await _incident(async_session, vault, radio_room, "Fire contained", since - timedelta(days=1))

    assert await build_awareness_digest(async_session, vault_id=vault.id, since=since, max_lines=8) == []


async def test_another_vaults_incident_is_ignored(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    since = utcnow() - timedelta(days=1)
    other = await _other_vault(async_session)
    other_room = await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(
            name="Other studio",
            category=radio_room.category,
            ability=radio_room.ability,
            capacity=1,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=1,
            size_max=3,
            size=1,
            tier=1,
            coordinate_x=0,
            coordinate_y=0,
            vault_id=other.id,
        ),
    )
    await _incident(async_session, other, other_room, "Fire contained", since + timedelta(hours=1))

    assert await build_awareness_digest(async_session, vault_id=vault.id, since=since, max_lines=8) == []


async def test_dwellers_added_and_deceased_since(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    since = utcnow()
    newcomer_data: dict = dict(dweller_data)
    newcomer_data["first_name"] = "Newcomer"
    newcomer = await crud.dweller.create(async_session, obj_in=DwellerCreate(**newcomer_data, vault_id=vault.id))
    newcomer.created_at = since + timedelta(hours=1)
    dweller.death_timestamp = since + timedelta(hours=2)
    dweller.is_dead = True
    async_session.add(newcomer)
    async_session.add(dweller)
    await async_session.flush()

    lines = await build_awareness_digest(async_session, vault_id=vault.id, since=since, max_lines=8)

    assert len(lines) == 2
    assert any("Newcomer" in line and "joined" in line for line in lines)
    assert any(dweller.first_name in line and "died" in line for line in lines)


async def test_dweller_before_since_is_ignored(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    lines = await build_awareness_digest(async_session, vault_id=vault.id, since=utcnow(), max_lines=8)

    assert lines == []


async def test_cap_is_respected(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    since = utcnow() - timedelta(days=2)
    for hour in range(4):
        await _incident(
            async_session, vault, radio_room, f"Incident {hour} resolved", since + timedelta(hours=hour + 1)
        )

    lines = await build_awareness_digest(async_session, vault_id=vault.id, since=since, max_lines=2)

    assert len(lines) == 2
    # The most recent two survive, still told in the order they happened.
    assert lines == ["Incident 2 resolved.", "Incident 3 resolved."]


async def test_lines_are_clipped_to_ninety_chars(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    since = utcnow() - timedelta(days=1)
    await _incident(async_session, vault, radio_room, "Fire " + "spread " * 40, since + timedelta(hours=1))

    lines = await build_awareness_digest(async_session, vault_id=vault.id, since=since, max_lines=8)

    assert len(lines) == 1
    assert len(lines[0]) <= 90
    assert lines[0].startswith("Fire spread")


async def test_no_measurements_means_no_lines(async_session: AsyncSession, vault: Vault) -> None:
    lines = await build_awareness_digest(async_session, vault_id=vault.id, since=utcnow(), max_lines=8)

    assert lines == []
