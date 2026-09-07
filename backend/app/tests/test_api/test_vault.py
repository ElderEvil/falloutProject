import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.smoke
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


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_read_vault_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(db_session=async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_1_data, vault_2_data = create_fake_vault(), create_fake_vault()
    # Ensure unique numbers so the disambiguation swap (number-based) is deterministic
    while vault_2_data["number"] == vault_1_data["number"]:
        vault_2_data = create_fake_vault()
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
async def test_auto_assign_respects_age_group_filter(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Auto-assign with age_group=adult must leave teen dwellers unassigned."""
    from app.models.room import RoomTypeEnum, SPECIALEnum
    from app.schemas.common import DwellerStatusEnum
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    room = await crud.room.create(
        async_session,
        RoomCreate(
            name="Power Generator",
            vault_id=vault.id,
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            population_required=12,
            base_cost=100,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            tier=1,
            size=3,
            size_min=3,
            size_max=9,
        ),
    )

    adult = await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name="Adult",
            last_name="Worker",
            vault_id=vault.id,
            gender="male",
            rarity="common",
            strength=5,
            perception=3,
            endurance=3,
            charisma=3,
            intelligence=3,
            agility=3,
            luck=3,
            status=DwellerStatusEnum.IDLE,
        ),
    )
    teen = await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name="Teen",
            last_name="Worker",
            vault_id=vault.id,
            gender="female",
            rarity="common",
            strength=5,
            perception=3,
            endurance=3,
            charisma=3,
            intelligence=3,
            agility=3,
            luck=3,
            status=DwellerStatusEnum.IDLE,
            age_group="teen",
            is_adult=False,
        ),
    )

    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-all",
        params={"age_group": "adult"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["assignments"] == [
        {"dweller_id": str(adult.id), "room_id": str(room.id), "room_name": room.name}
    ]
    await async_session.refresh(teen)
    assert teen.room_id is None
    assert teen.status == DwellerStatusEnum.IDLE


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

    # Verify dwellers assigned to training room have status "training" and active sessions.
    for dweller_id in dweller_ids:
        dweller = await crud.dweller.get(async_session, dweller_id)
        if dweller.room_id == training_room.id:
            assert dweller.status == DwellerStatusEnum.TRAINING, (
                f"Dweller {dweller_id} assigned to training room but has status {dweller.status}, "
                f"expected {DwellerStatusEnum.TRAINING}"
            )
            training = await crud.training.training.get_active_by_dweller(async_session, dweller_id)
            assert training is not None, "Training dwellers must have sessions for the training queue"
            assert training.room_id == training_room.id


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_vault_initiate_superuser_creates_25_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test that superuser vault initialization creates 25 dwellers (parity with boosted)."""
    from uuid import UUID

    vault_number = {"number": 202}
    response = await async_client.post("/vaults/initiate", headers=superuser_token_headers, json=vault_number)
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    vault_with_counts = await crud.vault.get_vault_with_room_and_dweller_count(
        db_session=async_session, vault_id=vault_id
    )
    assert vault_with_counts.dweller_count == 25, (
        f"Expected 25 dwellers for superuser, got {vault_with_counts.dweller_count}"
    )
