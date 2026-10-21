"""Barbershop API and appearance/AI gate tests."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.room import RoomCreate


async def _make_room(
    db_session: AsyncSession,
    vault: Vault,
    *,
    name: str = "Barbershop",
    category: RoomTypeEnum = RoomTypeEnum.MISC,
    ability: SPECIALEnum = SPECIALEnum.CHARISMA,
) -> Room:
    return await crud.room.create(
        db_session,
        obj_in=RoomCreate(
            name=name,
            category=category,
            ability=ability,
            population_required=50,
            base_cost=10000,
            incremental_cost=None,
            t2_upgrade_cost=50000,
            t3_upgrade_cost=None,
            size_min=6,
            size_max=6,
            size=6,
            tier=1,
            vault_id=vault.id,
        ),
    )


async def _staff(db_session: AsyncSession, room: Room, dweller: Dweller) -> None:
    dweller.room_id = room.id
    db_session.add(dweller)
    await db_session.commit()
    await db_session.refresh(dweller)


async def _make_human(db_session: AsyncSession, dweller: Dweller) -> None:
    dweller.visual_attributes = {
        "race": "human",
        "faction": "vault_dweller",
        "skin_tone": "Pale",
        "hair_color": "blonde",
    }
    db_session.add(dweller)
    await db_session.commit()
    await db_session.refresh(dweller)


async def test_read_barbershop_status(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault: Vault,
) -> None:
    room = await _make_room(async_session, vault)

    response = await async_client.get(f"/rooms/{room.id}/barbershop", headers=superuser_token_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["room_id"] == str(room.id)
    assert body["built"] is True
    assert body["staffed"] is False
    assert body["fee"] == 100
    assert body["skin_tones"] == ["Pale", "Tan", "Brown", "Ebony"]
    assert body["hair_colors"] == ["blonde", "brunette", "black", "brown", "red", "gray"]


async def test_read_barbershop_status_rejects_other_rooms(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault: Vault,
) -> None:
    room = await _make_room(
        async_session,
        vault,
        name="Diner",
        category=RoomTypeEnum.PRODUCTION,
        ability=SPECIALEnum.AGILITY,
    )

    response = await async_client.get(f"/rooms/{room.id}/barbershop", headers=superuser_token_headers)

    assert response.status_code == 400


async def test_change_appearance_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault: Vault,
    dweller: Dweller,
) -> None:
    room = await _make_room(async_session, vault)
    await _staff(async_session, room, dweller)
    await _make_human(async_session, dweller)
    vault.bottle_caps = 500
    async_session.add(vault)
    await async_session.commit()

    response = await async_client.post(
        f"/rooms/{room.id}/barbershop/dwellers/{dweller.id}",
        json={"skin_tone": "Tan", "hair_color": "black"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["portrait_updated"] is True
    assert body["fee"] == 100
    assert body["remaining_caps"] == 400
    assert body["dweller"]["visual_attributes"]["skin_tone"] == "Tan"
    assert body["dweller"]["visual_attributes"]["hair_color"] == "black"
    assert "SkinTan_HairBlack" in body["dweller"]["image_url"]


async def test_change_appearance_endpoint_requires_staffed_room(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault: Vault,
    dweller: Dweller,
) -> None:
    room = await _make_room(async_session, vault)
    await _make_human(async_session, dweller)

    response = await async_client.post(
        f"/rooms/{room.id}/barbershop/dwellers/{dweller.id}",
        json={"skin_tone": "Tan", "hair_color": "black"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 403
    assert "Barbershop" in response.json()["detail"]


async def test_put_appearance_change_requires_barbershop(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    await _make_human(async_session, dweller)

    response = await async_client.put(
        f"/dwellers/{dweller.id}",
        json={"visual_attributes": {"skin_tone": "Tan"}},
        headers=superuser_token_headers,
    )

    assert response.status_code == 403
    assert "Barbershop" in response.json()["detail"]


async def test_put_non_appearance_fields_still_work_without_barbershop(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    response = await async_client.put(
        f"/dwellers/{dweller.id}",
        json={"first_name": "Renamed"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Renamed"


@pytest.mark.parametrize("path", ["generate_visual_attributes", "generate_photo", "generate_with_ai"])
async def test_ai_appearance_endpoints_require_barbershop(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
    path: str,
) -> None:
    response = await async_client.post(
        f"/dwellers/{dweller.id}/{path}/",
        headers=superuser_token_headers,
    )

    assert response.status_code == 403
    assert "Barbershop" in response.json()["detail"]


async def test_generate_avatar_requires_barbershop(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    response = await async_client.post(
        f"/dwellers/{dweller.id}/generate_avatar",
        params={"dweller_first_name": "Test", "dweller_last_name": "User"},
        json={"hair_color": "black"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 403
    assert "Barbershop" in response.json()["detail"]
