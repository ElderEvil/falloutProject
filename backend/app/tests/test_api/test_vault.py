from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import GenderEnum, ObjectiveCategoryEnum
from app.crud.objective import objective_crud
from app.schemas.vault import VaultCreateWithUserID
from app.services.exploration.expedition import expedition_service
from app.services.vault_service import vault_service
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
    read_response = await async_client.get(f"/vaults/{created_vault.id}", headers=superuser_token_headers)
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


@pytest.mark.asyncio
async def test_auto_assign_crafting_rooms_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Crafting auto-assign endpoint fills workshops with highest-total-SPECIAL adults."""
    from app.models.room import RoomTypeEnum
    from app.schemas.common import DwellerStatusEnum
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    workshop = await crud.room.create(
        async_session,
        RoomCreate(
            name="Weapon workshop",
            vault_id=vault.id,
            category=RoomTypeEnum.CRAFTING,
            ability=None,
            population_required=12,
            base_cost=100,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            tier=1,
            size=9,
            size_min=9,
            size_max=9,
        ),
    )

    high = await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name="High",
            last_name="Crafter",
            vault_id=vault.id,
            gender="male",
            rarity="common",
            strength=7,
            perception=7,
            endurance=7,
            charisma=7,
            intelligence=7,
            agility=7,
            luck=7,
            status=DwellerStatusEnum.IDLE,
        ),
    )
    low = await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name="Low",
            last_name="Crafter",
            vault_id=vault.id,
            gender="female",
            rarity="common",
            strength=1,
            perception=1,
            endurance=1,
            charisma=1,
            intelligence=1,
            agility=1,
            luck=1,
            status=DwellerStatusEnum.IDLE,
        ),
    )

    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-crafting",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["assigned_count"] == 2
    assert [a["dweller_id"] for a in result["assignments"]] == [str(high.id), str(low.id)]
    assert all(a["room_id"] == str(workshop.id) for a in result["assignments"])


@pytest.mark.asyncio
async def test_auto_assign_crafting_rejects_foreign_vault(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
    vault,
):
    """An authenticated user cannot auto-assign crafting in another user's vault."""
    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-crafting",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_vault_initiate_does_not_boost_superusers_by_default(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """A superuser is only boosted when the request asks for it, like any other user."""
    from uuid import UUID

    response = await async_client.post("/vaults/initiate", headers=superuser_token_headers, json={"number": 202})
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    vault_with_counts = await vault_service.get_vault_with_room_and_dweller_count(
        db_session=async_session, vault_id=vault_id
    )
    assert vault_with_counts.dweller_count <= 32, (
        f"Superuser was boosted without requesting it: {vault_with_counts.dweller_count} dwellers"
    )
    rooms = await crud.room.get_all_by_vault(async_session, vault_id)
    # Crafting workshops are seeded only for boosted vaults.
    assert not any(room.category.value == "crafting" for room in rooms)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_vault_initiate_boosted_seeds_crafting_and_capacity(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Boosted vaults seed staffed workshops, merged living space, and capacity to match."""
    from uuid import UUID

    response = await async_client.post(
        "/vaults/initiate", headers=superuser_token_headers, json={"number": 203, "boosted": True}
    )
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    vault = await crud.vault.get(async_session, vault_id)
    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id)
    storage = await crud.storage.storage.get_by_vault(async_session, vault_id)
    rooms = await crud.room.get_all_by_vault(async_session, vault_id)
    junk = await crud.junk.get_in_storage(async_session, storage.id)

    workshops = [room for room in rooms if room.category.value == "crafting"]
    assert {room.name for room in workshops} == {"Weapon workshop", "Outfit workshop"}
    # Each workshop is staffed so orders get the crew speed-up.
    assert all(sum(1 for dweller in dwellers if dweller.room_id == room.id) >= 2 for room in workshops)

    # Living space is a merged (size 9) room plus the base room.
    assert [room.size for room in rooms if room.name == "Living room"].count(9) == 1

    # Adjacent seed storage rooms fuse into one merged room at seed time.
    storages = [room for room in rooms if room.name == "Storage room"]
    assert len(storages) == 1
    assert storages[0].size == 9

    # More than 32 dwellers, with room to spare.
    assert len(dwellers) > 32
    assert vault.population_max >= len(dwellers)

    # Every junk type the craftable catalog accepts, across all three rarities.
    assert {(item.junk_type.value, item.rarity.value) for item in junk} >= {
        ("steel", "common"),
        ("leather", "common"),
        ("circuitry", "common"),
        ("cloth", "common"),
        ("steel", "rare"),
        ("leather", "rare"),
        ("circuitry", "rare"),
        ("cloth", "rare"),
        ("steel", "legendary"),
        ("circuitry", "legendary"),
    }

    used_space = await crud.storage.storage.count_items(async_session, storage.id)
    assert storage.max_space > used_space


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_vault_initiate_survival_mode(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    """A survival vault is created and reports its mode back through the vault API."""
    response = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 211, "vault_mode": "survival"},
    )
    assert response.status_code == 201
    assert response.json()["vault_mode"] == "survival"

    read = await async_client.get(f"/vaults/{response.json()['id']}", headers=superuser_token_headers)
    assert read.status_code == 200
    assert read.json()["vault_mode"] == "survival"


@pytest.mark.asyncio
async def test_vault_initiate_defaults_to_standard_mode(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    response = await async_client.post("/vaults/initiate", headers=superuser_token_headers, json={"number": 212})
    assert response.status_code == 201
    assert response.json()["vault_mode"] == "standard"


@pytest.mark.asyncio
async def test_vault_initiate_rejects_unknown_mode(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    response = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 213, "vault_mode": "nightmare"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_vault_initiate_rejects_boosted_survival(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    """Boosted Start is incompatible with survival mode and is rejected at creation (issue 1031)."""
    response = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 215, "boosted": True, "vault_mode": "survival"},
    )
    assert response.status_code == 422
    assert "survival" in response.json()["detail"][0]["msg"].lower()


@pytest.mark.asyncio
async def test_vault_scenarios_list_vault_1(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    response = await async_client.get("/vaults/scenarios", headers=superuser_token_headers)
    assert response.status_code == 200
    scenarios = response.json()
    assert scenarios == [
        {
            "number": 1,
            "key": "vault_1_test",
            "title": "Vault 1 — Scout Test",
            "description": (
                "Adds a level 5 / SPECIAL 4 Scout and a single-scene stat-check expedition. "
                "Extra living capacity; starter objectives skipped. Starts at the site picker."
            ),
            "dweller_level": 5,
            "special": 4,
            "all_sites": True,
            "single_scene_only": True,
        },
        {
            "number": 68,
            "key": "vault_68_test",
            "title": "Vault 68 — The Ratio",
            "description": (
                "99 men and 1 woman. Adds a level 10 / SPECIAL 7 Scout and the Vault 68 social "
                "encounter. Extra living capacity; starter objectives skipped. Starts at the site picker."
            ),
            "dweller_level": 10,
            "special": 7,
            "all_sites": True,
            "single_scene_only": True,
        },
        {
            "number": 69,
            "key": "vault_69_test",
            "title": "Vault 69 — The Inverse",
            "description": (
                "The inverse of Vault 68: 99 women and 1 man. Adds a level 3 / SPECIAL 3 Scout "
                "and the Vault 69 social encounter. Extra living capacity; starter objectives skipped. "
                "Starts at the site picker."
            ),
            "dweller_level": 3,
            "special": 3,
            "all_sites": True,
            "single_scene_only": True,
        },
    ]


@pytest.mark.asyncio
async def test_vault_initiate_scenario_seeds_single_scene_scout(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    response = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 1, "scenario": "vault_1_test"},
    )
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id)
    scout = next(dweller for dweller in dwellers if dweller.display_name == "Scout Scenario")
    assert scout.level == 5
    assert (scout.strength, scout.perception, scout.endurance, scout.charisma) == (4, 4, 4, 4)
    assert (scout.intelligence, scout.agility, scout.luck) == (4, 4, 4)

    stored_vault = await crud.vault.get(async_session, vault_id)
    assert stored_vault is not None
    assert stored_vault.population_max is not None
    assert stored_vault.population_max > len(dwellers)
    objectives = await objective_crud.get_multi_for_vault(async_session, vault_id)
    assert not any(objective.category is ObjectiveCategoryEnum.STARTER for objective in objectives)

    explorations = await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True)
    assert len(explorations) == 1
    exploration = explorations[0]
    assert any(
        event.get("event") == "scenario_all_sites"
        and event.get("single_scene_only") is True
        and event.get("choice_only") is True
        for event in exploration.events
    )
    sites = {site.id for site in await expedition_service.list_available_sites(async_session, exploration.id)}
    assert sites == {"vault_68", "vault_69"}


@pytest.mark.parametrize(
    ("number", "key", "level", "special"),
    [
        (68, "vault_68_test", 10, 7),
        (69, "vault_69_test", 3, 3),
    ],
)
@pytest.mark.asyncio
async def test_vault_initiate_lore_scenario_profiles(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    number: int,
    key: str,
    level: int,
    special: int,
):
    response = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": number, "scenario": key},
    )
    assert response.status_code == 201, response.text
    vault_id = UUID(response.json()["id"])

    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id, limit=200)
    assert len(dwellers) == 100
    expected_men, expected_women = (99, 1) if number == 68 else (1, 99)
    assert sum(dweller.gender == GenderEnum.MALE for dweller in dwellers) == expected_men
    assert sum(dweller.gender == GenderEnum.FEMALE for dweller in dwellers) == expected_women
    stored_vault = await crud.vault.get(async_session, vault_id)
    assert stored_vault is not None
    assert stored_vault.population_max == 100

    scout = next(dweller for dweller in dwellers if dweller.display_name == "Scout Scenario")
    assert scout.gender == GenderEnum.MALE
    assert scout.level == level
    assert (scout.strength, scout.perception, scout.endurance, scout.charisma) == (
        special,
        special,
        special,
        special,
    )
    assert (scout.intelligence, scout.agility, scout.luck) == (special, special, special)

    explorations = await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True)
    assert len(explorations) == 1
    site_id = f"vault_{number}"
    sites = {site.id for site in await expedition_service.list_available_sites(async_session, explorations[0].id)}
    assert sites == {site_id}

    entered = await async_client.post(
        f"/explorations/{explorations[0].id}/site/enter",
        headers=superuser_token_headers,
        json={"site_id": site_id},
    )
    assert entered.status_code == 200
    options = entered.json()["node"]["options"]
    assert options
    resolved = await async_client.post(
        f"/explorations/{explorations[0].id}/site/resolve",
        headers=superuser_token_headers,
        json={"choice_id": options[0]["id"]},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "cleared"


@pytest.mark.asyncio
async def test_vault_initiate_without_scenario_creates_no_exploration(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    response = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 2},
    )
    assert response.status_code == 201

    vault_id = UUID(response.json()["id"])
    assert await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True) == []


@pytest.mark.asyncio
async def test_vault_initiate_rejects_unknown_or_mismatched_scenario(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    unknown = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 2, "scenario": "missing"},
    )
    assert unknown.status_code == 400

    mismatched = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 2, "scenario": "vault_1_test"},
    )
    assert mismatched.status_code == 400


@pytest.mark.asyncio
async def test_vault_mode_is_immutable_via_api(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    """Attempting to change the mode through the update endpoint is rejected and takes no effect."""
    created = await async_client.post(
        "/vaults/initiate",
        headers=superuser_token_headers,
        json={"number": 214, "vault_mode": "survival"},
    )
    assert created.status_code == 201
    vault_id = created.json()["id"]

    response = await async_client.put(
        f"/vaults/{vault_id}",
        headers=superuser_token_headers,
        json={"vault_mode": "standard"},
    )
    assert response.status_code == 422

    read = await async_client.get(f"/vaults/{vault_id}", headers=superuser_token_headers)
    assert read.json()["vault_mode"] == "survival"
