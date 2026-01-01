import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.room import Room
from app.schemas.room import RoomCreate
from app.tests.factory.rooms import create_fake_room


@pytest.mark.asyncio
async def test_read_room_list(async_client: AsyncClient, async_session: AsyncSession, room: Room):
    room_2_data = create_fake_room()
    room_2 = RoomCreate(**room_2_data, vault_id=room.vault_id)
    await crud.room.create(async_session, room_2)
    response = await async_client.get("/rooms/")
    rooms = response.json()
    assert response.status_code == 200
    assert len(rooms) == 2
    for r in rooms:
        assert "id" in r
        assert "name" in r
        assert "category" in r
        assert "ability" in r
        assert "population_required" in r
        assert "base_cost" in r
        assert "incremental_cost" in r
        assert "tier" in r
        assert "t2_upgrade_cost" in r
        assert "t3_upgrade_cost" in r
        assert "output" in r
        assert "size_min" in r
        assert "size_max" in r


@pytest.mark.asyncio
async def test_read_room(async_client: AsyncClient, superuser_token_headers: dict[str, str], room: Room):
    response = await async_client.get(f"/rooms/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    response_room = response.json()
    assert response_room["name"] == room.name
    assert response_room["category"] == room.category
    assert response_room["ability"] == room.ability
    assert response_room["population_required"] == room.population_required
    assert response_room["base_cost"] == room.base_cost
    assert response_room["incremental_cost"] == room.incremental_cost
    assert response_room["tier"] == room.tier
    assert response_room["t2_upgrade_cost"] == room.t2_upgrade_cost
    assert response_room["t3_upgrade_cost"] == room.t3_upgrade_cost
    assert response_room["output"] == room.output
    assert response_room["size_min"] == room.size_min
    assert response_room["size_max"] == room.size_max


@pytest.mark.asyncio
async def test_update_room(async_client: AsyncClient, superuser_token_headers: dict[str, str], room: Room):
    room_new_data = create_fake_room()
    update_response = await async_client.put(f"/rooms/{room.id}", json=room_new_data, headers=superuser_token_headers)
    updated_room = update_response.json()
    assert update_response.status_code == 200
    assert updated_room["id"] == str(room.id)
    assert updated_room["name"] == room_new_data["name"]
    assert updated_room["category"] == room_new_data["category"]
    assert updated_room["ability"] == room_new_data["ability"]
    assert updated_room["population_required"] == room_new_data["population_required"]
    assert updated_room["base_cost"] == room_new_data["base_cost"]
    assert updated_room["incremental_cost"] == room_new_data["incremental_cost"]
    assert updated_room["tier"] == room_new_data["tier"]
    assert updated_room["t2_upgrade_cost"] == room_new_data["t2_upgrade_cost"]
    assert updated_room["t3_upgrade_cost"] == room_new_data["t3_upgrade_cost"]
    assert updated_room["output"] == room_new_data["output"]
    assert updated_room["size_min"] == room_new_data["size_min"]
    assert updated_room["size_max"] == room_new_data["size_max"]


@pytest.mark.asyncio
async def test_delete_room(async_client: AsyncClient, superuser_token_headers: dict[str, str], room: Room):
    delete_response = await async_client.delete(f"/rooms/{room.id}", headers=superuser_token_headers)
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/rooms/{room.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_upgrade_room_tier_1_to_2(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test upgrading a room from tier 1 to tier 2."""
    # Create room with specific upgrade costs and capacity
    room_data.update(
        {
            "tier": 1,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
            "capacity": 10,
            "output": 20,
        }
    )

    # Ensure vault has enough caps
    vault.bottle_caps = 1000
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    initial_caps = vault.bottle_caps
    initial_capacity = room.capacity
    initial_output = room.output

    # Upgrade room
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200

    upgraded_room = response.json()
    assert upgraded_room["tier"] == 2
    assert upgraded_room["id"] == str(room.id)

    # Check capacity and output increased (tier ratio: (2+4)/(1+4) = 1.2)
    assert upgraded_room["capacity"] > initial_capacity
    assert upgraded_room["output"] > initial_output

    # Verify vault caps were deducted
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps - 500


@pytest.mark.asyncio
async def test_upgrade_room_tier_2_to_3(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test upgrading a room from tier 2 to tier 3."""
    # Start with tier 1 room
    room_data.update(
        {
            "tier": 1,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
            "capacity": 10,
            "output": 20,
        }
    )

    vault.bottle_caps = 2500
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # First upgrade to tier 2
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    tier2_room = response.json()
    assert tier2_room["tier"] == 2

    # Refresh vault to get updated caps
    await async_session.refresh(vault)
    caps_after_first_upgrade = vault.bottle_caps

    # Now upgrade from tier 2 to tier 3
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200

    upgraded_room = response.json()
    assert upgraded_room["tier"] == 3

    # Verify vault caps were deducted for tier 3 upgrade
    await async_session.refresh(vault)
    assert vault.bottle_caps == caps_after_first_upgrade - 1500


@pytest.mark.asyncio
async def test_upgrade_room_insufficient_caps(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test that upgrading fails when vault doesn't have enough caps."""
    room_data.update(
        {
            "tier": 1,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
        }
    )

    # Set vault caps below upgrade cost
    vault.bottle_caps = 100
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # Attempt to upgrade room
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 422 or response.status_code == 400  # noqa: PLR1714


@pytest.mark.asyncio
async def test_upgrade_room_already_max_tier(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test that upgrading fails when room is already at max tier."""
    room_data.update(
        {
            "tier": 3,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
        }
    )

    vault.bottle_caps = 10000
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # Attempt to upgrade room beyond max tier
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 422 or response.status_code == 400  # noqa: PLR1714
    assert "maximum tier" in response.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_upgrade_room_no_t2_cost(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test that upgrading fails when room has no t2_upgrade_cost defined."""
    room_data.update(
        {
            "tier": 1,
            "t2_upgrade_cost": None,
            "t3_upgrade_cost": None,
        }
    )

    vault.bottle_caps = 10000
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # Attempt to upgrade room with no upgrade cost
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 422 or response.status_code == 400  # noqa: PLR1714


@pytest.mark.asyncio
async def test_upgrade_room_capacity_calculation(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault,
    room_data: dict,
):
    """Test that capacity is calculated correctly after upgrade."""
    room_data.update(
        {
            "tier": 1,
            "t2_upgrade_cost": 500,
            "t3_upgrade_cost": 1500,
            "capacity": 15,  # Known starting capacity
            "output": 30,
        }
    )

    vault.bottle_caps = 1000
    await crud.vault.update(async_session, vault.id, vault)

    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # Upgrade room
    response = await async_client.post(f"/rooms/upgrade/{room.id}", headers=superuser_token_headers)
    assert response.status_code == 200

    upgraded_room = response.json()

    # Expected tier ratio: (2+4)/(1+4) = 6/5 = 1.2
    expected_capacity = int(15 * 1.2)  # 18
    expected_output = int(30 * 1.2)  # 36

    assert upgraded_room["capacity"] == expected_capacity
    assert upgraded_room["output"] == expected_output
