import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate

pytestmark = pytest.mark.asyncio(scope="module")


async def _vault(async_session: AsyncSession, number: int, **extra):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    return await crud.vault.create_with_user_id(
        db_session=async_session, obj_in={"number": number, **extra}, user_id=user.id
    )


async def _radio_room(async_session: AsyncSession, vault, *, ability=None, capacity=None):
    return await crud.room.create(
        async_session,
        RoomCreate(
            name="Radio Studio",
            vault_id=vault.id,
            tier=1,
            size=2,
            coordinate_x=1,
            coordinate_y=1,
            category="misc.",
            ability=ability,
            capacity=capacity,
            output=None,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=1,
            size_max=3,
        ),
    )


async def _staff(
    async_session: AsyncSession, vault, room, *, first_name="Test", last_name="DJ", gender=GenderEnum.MALE
):
    dweller = await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            vault_id=vault.id,
            room_id=room.id,
        ),
    )
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()
    return dweller


@pytest.mark.smoke
async def test_get_radio_stats_with_radio(async_client, async_session, superuser_token_headers):
    vault = await _vault(async_session, 998)
    await _radio_room(async_session, vault)
    response = await async_client.get(f"/radio/vault/{vault.id}/stats", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["has_radio"] is True
    assert data["radio_rooms_count"] == 1
    assert data["recruitment_rate"] >= 0.0
    assert "speedup_multipliers" not in data


@pytest.mark.smoke
@pytest.mark.parametrize("last_name", ["Jones", None])
async def test_manual_recruit_success(async_client, async_session, superuser_token_headers, last_name):
    vault = await _vault(async_session, 995, bottle_caps=1000, population_max=10)
    room = await _radio_room(async_session, vault)
    await _staff(async_session, vault, room)
    response = await async_client.post(
        f"/radio/vault/{vault.id}/recruit",
        headers=superuser_token_headers,
        json={"override": {"first_name": "Cass", "last_name": last_name}},
    )
    assert response.status_code == 200
    data = response.json()
    assert "dweller" in data
    assert data["dweller"]["last_name"] == last_name
    expected_name = f"Cass {last_name or ''}".strip()
    assert data["message"] == f"{expected_name} has joined your vault!"
    assert data["caps_spent"] == 500


async def test_set_radio_mode(async_client, async_session, superuser_token_headers):
    vault = await _vault(async_session, 994)
    response = await async_client.put(
        f"/radio/vault/{vault.id}/mode", headers=superuser_token_headers, params={"mode": "happiness"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["radio_mode"] == "happiness"
    assert "happiness" in data["message"].lower()


async def test_manual_recruit_does_not_break_subsequent_api_calls(async_client, async_session, superuser_token_headers):
    """Recruiting must not invalidate the caller's auth token for subsequent requests."""
    vault = await _vault(async_session, 990, bottle_caps=10000, population_max=10)
    room = await _radio_room(async_session, vault, ability="CHARISMA", capacity=2)
    await _staff(async_session, vault, room, first_name="Radio", last_name="Host", gender=GenderEnum.FEMALE)
    response = await async_client.get(f"/vaults/{vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200, "Pre-recruitment: Should access vault"
    initial_caps = response.json()["bottle_caps"]
    response = await async_client.get(f"/dwellers/vault/{vault.id}/", headers=superuser_token_headers)
    assert response.status_code == 200, "Pre-recruitment: Should fetch dwellers"
    initial_dweller_count = len(response.json())
    response = await async_client.post(f"/radio/vault/{vault.id}/recruit", headers=superuser_token_headers, json={})
    assert response.status_code == 200
    recruit_data = response.json()
    assert "dweller" in recruit_data
    assert recruit_data["caps_spent"] == 500
    response = await async_client.get(f"/vaults/{vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200, "Post-recruitment vault access must succeed"
    assert response.json()["bottle_caps"] == initial_caps - 500, "Caps should be deducted"
    response = await async_client.get(f"/dwellers/vault/{vault.id}/", headers=superuser_token_headers)
    assert response.status_code == 200, "Post-recruitment dweller fetch must succeed"
    assert len(response.json()) == initial_dweller_count + 1, "Should have one more dweller"
    response = await async_client.get("/users/me", headers=superuser_token_headers, follow_redirects=False)
    assert response.status_code == 200, "Auth token should still be valid"
