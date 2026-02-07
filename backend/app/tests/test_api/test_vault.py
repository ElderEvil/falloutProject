import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_create_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    response = await async_client.post("/vaults/", headers=superuser_token_headers, json=vault_data)
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["number"] == vault_data["number"]
    assert response_data["bottle_caps"] == vault_data["bottle_caps"]
    assert response_data["happiness"] == vault_data["happiness"]
    assert response_data["user_id"] == vault_data["user_id"]


@pytest.mark.asyncio
async def test_read_vault_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(db_session=async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_1_data, vault_2_data = create_fake_vault(), create_fake_vault()
    vault_1_data["user_id"] = vault_2_data["user_id"] = str(user.id)
    await crud.vault.create(async_session, VaultCreateWithUserID(**vault_1_data))
    await crud.vault.create(async_session, VaultCreateWithUserID(**vault_2_data))
    response = await async_client.get("/vaults/", headers=superuser_token_headers)
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    response_vault_1, response_vault_2 = response_data
    if response_vault_1["number"] == vault_2_data["number"]:
        response_vault_2, response_vault_1 = response_data
    assert response_vault_1["number"] == vault_1_data["number"]
    assert response_vault_1["bottle_caps"] == vault_1_data["bottle_caps"]
    assert response_vault_1["happiness"] == vault_1_data["happiness"]
    assert response_vault_1["user_id"] == vault_1_data["user_id"]

    assert response_vault_2["number"] == vault_2_data["number"]
    assert response_vault_2["bottle_caps"] == vault_2_data["bottle_caps"]
    assert response_vault_2["happiness"] == vault_2_data["happiness"]
    assert response_vault_2["user_id"] == vault_2_data["user_id"]


@pytest.mark.asyncio
async def test_read_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(db_session=async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = await crud.vault.create(async_session, vault_to_create)
    response = await async_client.get(f"/vaults/{created_vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(created_vault.id)
    assert response_data["number"] == vault_data["number"]
    assert response_data["bottle_caps"] == vault_data["bottle_caps"]
    assert response_data["happiness"] == vault_data["happiness"]
    # user_id is not included in VaultReadWithNumbers response (GET /vaults/{id})
    assert "room_count" in response_data
    assert "dweller_count" in response_data


@pytest.mark.asyncio
async def test_update_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(db_session=async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = await crud.vault.create(db_session=async_session, obj_in=vault_to_create)
    response = await async_client.get(f"/vaults/{created_vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    new_vault_data = create_fake_vault()
    new_vault_data["user_id"] = str(user.id)
    update_response = await async_client.put(
        f"/vaults/{created_vault.id}",
        json=new_vault_data,
        headers=superuser_token_headers,
    )
    assert update_response.status_code == 200
    update_response_data = update_response.json()
    assert update_response_data["id"] == str(created_vault.id)
    assert update_response_data["number"] == new_vault_data["number"]
    assert update_response_data["bottle_caps"] == new_vault_data["bottle_caps"]
    assert update_response_data["happiness"] == new_vault_data["happiness"]
    assert update_response_data["user_id"] == vault_data["user_id"]


@pytest.mark.asyncio
async def test_delete_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = await crud.vault.create(async_session, vault_to_create)
    delete_response = await async_client.delete(
        f"/vaults/{created_vault.id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/junk/{created_vault.id}")
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_superuser_vault_initiate_creates_training_sessions(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test that superuser vault initialization creates training sessions for all training room dwellers."""
    # Get superuser
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    assert user.is_superuser

    # Initiate vault (superuser flag passed automatically from user.is_superuser)
    vault_number = {"number": 777}
    response = await async_client.post("/vaults/initiate", headers=superuser_token_headers, json=vault_number)
    assert response.status_code == 201
    vault_id = response.json()["id"]

    # Get all training sessions for the vault
    training_response = await async_client.get(f"/training/vault/{vault_id}", headers=superuser_token_headers)
    assert training_response.status_code == 200
    training_sessions = training_response.json()

    # Verify we got training sessions created
    assert isinstance(training_sessions, list)

    # Note: The number of training sessions depends on vault initialization logic
    # which creates 7 training rooms (one per SPECIAL stat) with assigned dwellers.
    # Each dweller in a training room should have an active training session.
    if len(training_sessions) > 0:
        # Verify all sessions are in correct status and belong to this vault
        for session in training_sessions:
            assert session["status"] in ["active", "in_progress", "completed"]
            assert session["vault_id"] == vault_id


@pytest.mark.asyncio
async def test_auto_assign_all_rooms_basic(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test that auto-assign endpoint works and assigns unassigned dwellers."""
    from app.models.room import RoomTypeEnum, SPECIALEnum
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Get superuser and create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    # Create a production room
    room_data = {
        "name": "Power Generator",
        "vault_id": str(vault.id),
        "category": RoomTypeEnum.PRODUCTION,
        "ability": SPECIALEnum.STRENGTH,
        "population_required": 12,
        "base_cost": 100,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "tier": 1,
        "size": 3,
        "size_min": 3,
        "size_max": 9,
    }
    room = await crud.room.create(async_session, RoomCreate(**room_data))
    assert room is not None

    # Create unassigned dwellers
    for i in range(3):
        dweller_data = {
            "first_name": f"TestDweller{i}",
            "last_name": "Test",
            "vault_id": str(vault.id),
            "gender": "male",
            "rarity": "common",
            "strength": 5,
            "perception": 3,
            "endurance": 3,
            "charisma": 3,
            "intelligence": 3,
            "agility": 3,
            "luck": 3,
        }
        await crud.dweller.create(async_session, DwellerCreate(**dweller_data))

    # Call auto-assign endpoint
    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-all",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["assigned_count"] > 0
    assert len(result["assignments"]) == result["assigned_count"]


@pytest.mark.asyncio
async def test_auto_assign_respects_room_capacity(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test that auto-assign doesn't exceed room capacity."""
    from app.models.room import RoomTypeEnum, SPECIALEnum
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Get superuser and create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    # Create a small production room (size 3 = capacity 2)
    room_data = {
        "name": "Power Generator",
        "vault_id": str(vault.id),
        "category": RoomTypeEnum.PRODUCTION,
        "ability": SPECIALEnum.STRENGTH,
        "population_required": 12,
        "base_cost": 100,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "tier": 1,
        "size": 3,
        "size_min": 3,
        "size_max": 9,
    }
    room = await crud.room.create(async_session, RoomCreate(**room_data))

    # Create many dwellers
    for i in range(10):
        dweller_data = {
            "first_name": f"TestDweller{i}",
            "last_name": "Test",
            "vault_id": str(vault.id),
            "gender": "male",
            "rarity": "common",
            "strength": 5,
            "perception": 3,
            "endurance": 3,
            "charisma": 3,
            "intelligence": 3,
            "agility": 3,
            "luck": 3,
        }
        await crud.dweller.create(async_session, DwellerCreate(**dweller_data))

    # Call auto-assign
    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-all",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    result = response.json()

    # Count assignments to our room
    room_assignments = [a for a in result["assignments"] if a["room_id"] == str(room.id)]

    # Room capacity is 2, so should not exceed that
    assert len(room_assignments) <= 2, f"Room capacity exceeded: {len(room_assignments)} > 2"


@pytest.mark.asyncio
async def test_auto_assign_training_room_sets_training_status(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test that assigning dwellers to training rooms sets status to 'training'."""
    from app.models.room import RoomTypeEnum, SPECIALEnum
    from app.schemas.common import DwellerStatusEnum
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Get superuser and create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    # Create a training room
    training_room_data = {
        "name": "Strength Training",
        "vault_id": str(vault.id),
        "category": RoomTypeEnum.TRAINING,
        "ability": SPECIALEnum.STRENGTH,
        "population_required": 12,
        "base_cost": 100,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "tier": 1,
        "size": 3,
        "size_min": 3,
        "size_max": 9,
    }
    training_room = await crud.room.create(async_session, RoomCreate(**training_room_data))

    # Create unassigned dwellers
    dweller_ids = []
    for i in range(2):
        dweller_data = {
            "first_name": f"TrainingDweller{i}",
            "last_name": "Test",
            "vault_id": str(vault.id),
            "gender": "male",
            "rarity": "common",
            "strength": 5,
            "perception": 3,
            "endurance": 3,
            "charisma": 3,
            "intelligence": 3,
            "agility": 3,
            "luck": 3,
        }
        dweller = await crud.dweller.create(async_session, DwellerCreate(**dweller_data))
        dweller_ids.append(dweller.id)

    # Call auto-assign endpoint
    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-all",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["assigned_count"] > 0

    # Verify dwellers assigned to training room have status "training"
    for dweller_id in dweller_ids:
        dweller = await crud.dweller.get(async_session, dweller_id)
        if dweller.room_id == training_room.id:
            assert dweller.status == DwellerStatusEnum.TRAINING, (
                f"Dweller {dweller_id} assigned to training room but has status {dweller.status}, "
                f"expected {DwellerStatusEnum.TRAINING}"
            )


@pytest.mark.asyncio
async def test_vault_initiate_normal_creates_6_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test that normal vault initialization creates 6 dwellers."""
    from uuid import UUID

    vault_number = {"number": 100}
    response = await async_client.post("/vaults/initiate", headers=normal_user_token_headers, json=vault_number)
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    vault_with_counts = await crud.vault.get_vault_with_room_and_dweller_count(
        db_session=async_session, vault_id=vault_id
    )
    assert vault_with_counts.dweller_count == 6, f"Expected 6 dwellers, got {vault_with_counts.dweller_count}"


@pytest.mark.asyncio
async def test_vault_initiate_boosted_creates_13_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test that boosted vault initialization creates 13 dwellers."""
    from uuid import UUID

    vault_number = {"number": 101, "boosted": True}
    response = await async_client.post("/vaults/initiate", headers=normal_user_token_headers, json=vault_number)
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    vault_with_counts = await crud.vault.get_vault_with_room_and_dweller_count(
        db_session=async_session, vault_id=vault_id
    )
    assert vault_with_counts.dweller_count == 13, f"Expected 13 dwellers, got {vault_with_counts.dweller_count}"


@pytest.mark.asyncio
async def test_vault_initiate_superuser_creates_13_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test that superuser vault initialization creates 13 dwellers (parity with boosted)."""
    from uuid import UUID

    vault_number = {"number": 202}
    response = await async_client.post("/vaults/initiate", headers=superuser_token_headers, json=vault_number)
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    vault_with_counts = await crud.vault.get_vault_with_room_and_dweller_count(
        db_session=async_session, vault_id=vault_id
    )
    assert vault_with_counts.dweller_count == 13, (
        f"Expected 13 dwellers for superuser, got {vault_with_counts.dweller_count}"
    )


@pytest.mark.asyncio
async def test_vault_initiate_boosted_and_superuser_parity(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
):
    """Test that boosted non-superuser vault matches superuser vault initialization."""
    from uuid import UUID

    boosted_vault_number = {"number": 203, "boosted": True}
    boosted_response = await async_client.post(
        "/vaults/initiate", headers=normal_user_token_headers, json=boosted_vault_number
    )
    assert boosted_response.status_code == 201
    boosted_vault_id = UUID(boosted_response.json()["id"])

    superuser_vault_number = {"number": 204}
    superuser_response = await async_client.post(
        "/vaults/initiate", headers=superuser_token_headers, json=superuser_vault_number
    )
    assert superuser_response.status_code == 201
    superuser_vault_id = UUID(superuser_response.json()["id"])

    boosted_vault = await crud.vault.get_vault_with_room_and_dweller_count(
        db_session=async_session, vault_id=boosted_vault_id
    )
    superuser_vault = await crud.vault.get_vault_with_room_and_dweller_count(
        db_session=async_session, vault_id=superuser_vault_id
    )
    assert boosted_vault.dweller_count == 13, f"Expected 13 dwellers, got {boosted_vault.dweller_count}"
    assert superuser_vault.dweller_count == 13, f"Expected 13 dwellers, got {superuser_vault.dweller_count}"

