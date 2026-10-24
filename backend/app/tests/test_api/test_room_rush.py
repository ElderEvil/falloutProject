from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.crud.incident import incident_crud
from app.models.incident import IncidentType
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultCreate
from app.tests.factory.vaults import random_vault_number
from app.tests.utils.user import authentication_token_from_email


async def _owned_vault(async_client: AsyncClient, async_session: AsyncSession) -> tuple[Any, dict[str, str]]:
    email = "room-rush@example.com"
    headers = await authentication_token_from_email(client=async_client, email=email, db_session=async_session)
    user = await crud.user.get_by_email(async_session, email=email)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in=VaultCreate(
            number=random_vault_number(),
            power=50,
            power_max=100,
        ),
        user_id=user.id,
    )
    return vault, headers


async def _room(
    async_session: AsyncSession,
    vault: Vault,
    *,
    name: str = "Power Generator",
    category: RoomTypeEnum = RoomTypeEnum.PRODUCTION,
    ability: SPECIALEnum | None = SPECIALEnum.STRENGTH,
    capacity: int | None = None,
) -> Room:
    return await crud.room.create(
        async_session,
        RoomCreate(
            vault_id=vault.id,
            name=name,
            category=category,
            ability=ability,
            capacity=capacity,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            output=100 if category == RoomTypeEnum.PRODUCTION else None,
            size_min=1,
            size_max=3,
            size=1,
            tier=1,
        ),
    )


async def _staff(async_session: AsyncSession, vault: Vault, room: Room) -> None:
    worker = await crud.dweller.create(
        async_session,
        DwellerCreate(
            vault_id=vault.id,
            first_name="Rush",
            last_name="Worker",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            max_health=100,
            health=100,
            strength=10,
            luck=10,
        ),
    )
    worker.room_id = room.id
    async_session.add(worker)
    await async_session.commit()


@pytest.mark.asyncio
async def test_rush_quote_and_blocked_action(async_client: AsyncClient, async_session: AsyncSession) -> None:
    vault, headers = await _owned_vault(async_client, async_session)
    room = await _room(async_session, vault)

    quote_response = await async_client.get(f"/rooms/{room.id}/rush", headers=headers)
    assert quote_response.status_code == 200
    quote = quote_response.json()
    assert quote["can_rush"] is False
    assert quote["blocked_reason"] == "no_workers"

    rush_response = await async_client.post(f"/rooms/{room.id}/rush", headers=headers)
    assert rush_response.status_code == 409


@pytest.mark.asyncio
async def test_rush_rejects_non_production_room(async_client: AsyncClient, async_session: AsyncSession) -> None:
    vault, headers = await _owned_vault(async_client, async_session)
    room = await _room(
        async_session,
        vault,
        name="Living Quarters",
        category=RoomTypeEnum.CAPACITY,
        ability=None,
        capacity=2,
    )

    response = await async_client.post(f"/rooms/{room.id}/rush", headers=headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rush_quote_and_action_shape(async_client: AsyncClient, async_session: AsyncSession) -> None:
    vault, headers = await _owned_vault(async_client, async_session)
    room = await _room(async_session, vault)
    await _staff(async_session, vault, room)

    quote_response = await async_client.get(f"/rooms/{room.id}/rush", headers=headers)
    assert quote_response.status_code == 200
    quote = quote_response.json()
    assert set(quote) == {
        "can_rush",
        "blocked_reason",
        "fail_chance",
        "success_chance",
        "stacks",
        "max_stacks",
        "avg_ability",
        "avg_luck",
        "worker_count",
        "payout",
        "caps_chance",
        "eligible_incidents",
        "next_stack_penalty",
    }
    assert quote["can_rush"] is True
    assert 0 <= quote["fail_chance"] <= 100
    assert 0 <= quote["caps_chance"] <= 100

    with patch("random.random", return_value=0.99):
        rush_response = await async_client.post(f"/rooms/{room.id}/rush", headers=headers)

    assert rush_response.status_code == 200
    result = rush_response.json()
    assert set(result) == {
        "outcome",
        "payout",
        "caps",
        "xp_per_worker",
        "happiness_delta",
        "incident_id",
        "incident_type",
        "stacks_after",
        "next_fail_chance",
        "message",
    }
    assert result["outcome"] == "success"
    assert result["stacks_after"] == 1


@pytest.mark.asyncio
async def test_rush_requires_authentication(async_client: AsyncClient, async_session: AsyncSession) -> None:
    vault, _ = await _owned_vault(async_client, async_session)
    room = await _room(async_session, vault)

    quote_response = await async_client.get(f"/rooms/{room.id}/rush")
    rush_response = await async_client.post(f"/rooms/{room.id}/rush")

    assert quote_response.status_code in (401, 403)
    assert rush_response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_rush_requires_room_ownership(async_client: AsyncClient, async_session: AsyncSession) -> None:
    vault, _ = await _owned_vault(async_client, async_session)
    room = await _room(async_session, vault)
    await _staff(async_session, vault, room)
    visitor_headers = await authentication_token_from_email(
        client=async_client, email="room-rush-visitor@example.com", db_session=async_session
    )

    response = await async_client.post(f"/rooms/{room.id}/rush", headers=visitor_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rush_rejects_unpowered_non_strength_room(async_client: AsyncClient, async_session: AsyncSession) -> None:
    vault, headers = await _owned_vault(async_client, async_session)
    vault.power = 0
    async_session.add(vault)
    await async_session.commit()
    room = await _room(async_session, vault, name="Diner", ability=SPECIALEnum.AGILITY)
    await _staff(async_session, vault, room)

    response = await async_client.post(f"/rooms/{room.id}/rush", headers=headers)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_rush_rejects_active_incident(async_client: AsyncClient, async_session: AsyncSession) -> None:
    vault, headers = await _owned_vault(async_client, async_session)
    room = await _room(async_session, vault)
    await _staff(async_session, vault, room)
    await incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=1,
    )

    response = await async_client.post(f"/rooms/{room.id}/rush", headers=headers)

    assert response.status_code == 409
