"""Barbershop API and appearance/AI gate tests."""

import pytest
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


async def test_read_barbershop_status(async_client, async_session, superuser_token_headers, vault) -> None:
    room = await _make_room(async_session, vault)
    response = await async_client.get(f"/rooms/{room.id}/barbershop", headers=superuser_token_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["room_id"] == str(room.id)
    assert body["built"] is True
    assert body["staffed"] is False
    assert body["fee"] == 350
    assert body["skin_fee"] == 200
    assert body["hair_fee"] == 150
    assert body["skin_tones"] == ["Pale", "Tan", "Brown", "Ebony"]
    assert body["hair_colors"] == ["blonde", "brunette", "black", "brown", "red", "gray"]


async def test_read_barbershop_status_rejects_other_rooms(
    async_client, async_session, superuser_token_headers, vault
) -> None:
    room = await _make_room(
        async_session, vault, name="Diner", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.AGILITY
    )
    response = await async_client.get(f"/rooms/{room.id}/barbershop", headers=superuser_token_headers)
    assert response.status_code == 400


async def test_change_appearance_endpoint(async_client, async_session, superuser_token_headers, vault, dweller) -> None:
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
    assert body["fee"] == 350
    assert body["remaining_caps"] == 150
    assert body["dweller"]["visual_attributes"]["skin_tone"] == "Tan"
    assert body["dweller"]["visual_attributes"]["hair_color"] == "black"
    assert "SkinTan_HairBlack" in body["dweller"]["image_url"]


async def test_change_appearance_endpoint_requires_staffed_room(
    async_client, async_session, superuser_token_headers, vault, dweller
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


APPEARANCE_CALLS = [
    ("put", "/dwellers/{id}", True, {"json": {"visual_attributes": {"skin_tone": "Tan"}}}),
    ("post", "/dwellers/{id}/generate_visual_attributes/", False, {}),
    ("post", "/dwellers/{id}/generate_photo/", False, {}),
    ("post", "/dwellers/{id}/generate_with_ai/", False, {}),
    (
        "post",
        "/dwellers/{id}/generate_avatar",
        False,
        {"params": {"dweller_first_name": "Test", "dweller_last_name": "User"}, "json": {"hair_color": "black"}},
    ),
]


@pytest.mark.parametrize(("method", "path", "human", "kwargs"), APPEARANCE_CALLS)
async def test_appearance_endpoints_require_barbershop(
    async_client, async_session, superuser_token_headers, dweller, method, path, human, kwargs
) -> None:
    if human:
        await _make_human(async_session, dweller)
    response = await getattr(async_client, method)(
        path.format(id=dweller.id), headers=superuser_token_headers, **kwargs
    )
    assert response.status_code == 403
    assert "Barbershop" in response.json()["detail"]


async def test_put_non_appearance_fields_still_work_without_barbershop(
    async_client, superuser_token_headers, dweller
) -> None:
    response = await async_client.put(
        f"/dwellers/{dweller.id}", json={"first_name": "Renamed"}, headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Renamed"
