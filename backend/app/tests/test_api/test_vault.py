from uuid import UUID

import pytest
import pytest_asyncio

from app import crud
from app.core.config import settings
from app.core.enums import (
    DwellerStatusEnum,
    ExplorationStatus,
    GenderEnum,
    ObjectiveCategoryEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.crud.objective import objective_crud
from app.models.room import Room
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultCreateWithUserID
from app.seeding.seed_objectives import seed_objectives_from_json
from app.services import catalog_service as data_loader
from app.services.vault_service import vault_service
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


async def _owner_id(session) -> str:
    user = await crud.user.get_by_email(session, email=settings.FIRST_SUPERUSER_EMAIL)
    return str(user.id)


async def _initiate(async_client, headers, **payload):
    return await async_client.post("/vaults/initiate", headers=headers, json=payload)


async def _auto_room(session, vault, name, category, ability=None, size=3, size_max=9) -> Room:
    spec = {"name": name, "category": category, "ability": ability, "tier": 1, "vault_id": vault.id}
    spec.update(population_required=12, base_cost=100, t2_upgrade_cost=500, t3_upgrade_cost=1500)
    spec.update(size=size, size_min=size, size_max=size_max)
    return await crud.room.create(session, RoomCreate(**spec))


async def _auto_dweller(
    session, vault, first_name, last_name="Worker", gender="male", strength=5, special=3, age_group="adult"
):
    # `special` fills the six non-strength SPECIAL stats.
    stats = dict.fromkeys(("perception", "endurance", "charisma", "intelligence", "agility", "luck"), special)
    spec = {"first_name": first_name, "last_name": last_name, "gender": gender, "rarity": "common"}
    spec.update(vault_id=vault.id, strength=strength, status=DwellerStatusEnum.IDLE, age_group=age_group)
    return await crud.dweller.create(session, DwellerCreate(**stats, **spec))


@pytest_asyncio.fixture(name="auto_assign_vault")
async def auto_assign_vault_fixture(async_session):
    data = create_fake_vault()
    data["user_id"] = await _owner_id(async_session)
    return await crud.vault.create(async_session, VaultCreateWithUserID(**data))


@pytest.mark.smoke
async def test_create_vault(async_client, async_session, superuser_token_headers) -> None:
    vault_data = create_fake_vault()
    vault_data["user_id"] = await _owner_id(async_session)
    response = await async_client.post("/vaults/", headers=superuser_token_headers, json=vault_data)
    assert response.status_code == 201
    body = response.json()
    for field in ("number", "bottle_caps", "happiness", "user_id"):
        assert body[field] == vault_data[field]


@pytest.mark.smoke
async def test_read_vault_list(async_client, async_session, superuser_token_headers) -> None:
    vault_1_data, vault_2_data = create_fake_vault(), create_fake_vault()
    # Ensure unique numbers so the disambiguation swap (number-based) is deterministic
    while vault_2_data["number"] == vault_1_data["number"]:
        vault_2_data = create_fake_vault()
    owner = await _owner_id(async_session)
    vault_1_data["user_id"] = vault_2_data["user_id"] = owner
    await crud.vault.create(async_session, VaultCreateWithUserID(**vault_1_data))
    await crud.vault.create(async_session, VaultCreateWithUserID(**vault_2_data))
    response = await async_client.get("/vaults/", headers=superuser_token_headers)
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    vault_1, vault_2 = response_data
    if vault_1["number"] == vault_2_data["number"]:
        vault_2, vault_1 = response_data
    for body, expected in ((vault_1, vault_1_data), (vault_2, vault_2_data)):
        assert body["number"] == expected["number"]
        assert body["bottle_caps"] == expected["bottle_caps"]
        assert body["happiness"] == expected["happiness"]
        assert body["user_id"] == expected["user_id"]


async def test_delete_vault(async_client, async_session, superuser_token_headers) -> None:
    vault_data = create_fake_vault()
    vault_data["user_id"] = await _owner_id(async_session)
    created = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    delete_response = await async_client.delete(f"/vaults/{created.id}", headers=superuser_token_headers)
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/vaults/{created.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404


async def test_auto_assign_respects_age_group_filter(
    async_client, async_session, superuser_token_headers, auto_assign_vault
) -> None:
    vault = auto_assign_vault
    room = await _auto_room(async_session, vault, "Power Generator", RoomTypeEnum.PRODUCTION, SPECIALEnum.STRENGTH)
    adult = await _auto_dweller(async_session, vault, "Adult")
    teen = await _auto_dweller(async_session, vault, "Teen", gender="female", age_group="teen")

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


async def test_auto_assign_separates_eligible_pool_from_slot_cap(
    async_client, async_session, superuser_token_headers, auto_assign_vault
) -> None:
    vault = auto_assign_vault
    await _auto_room(async_session, vault, "Power Generator", RoomTypeEnum.PRODUCTION, SPECIALEnum.STRENGTH)
    for index in range(3):
        await _auto_dweller(async_session, vault, f"Pool{index}", strength=5 - index)

    response = await async_client.post(f"/vaults/{vault.id}/dwellers/auto-assign-all", headers=superuser_token_headers)
    assert response.status_code == 200
    payload = response.json()
    # size=3 holds two workers, so the third eligible adult has nowhere to go.
    assert payload["assigned_count"] == 2
    assert payload["eligible_count"] == 3
    assert len(payload["assignments"]) == payload["assigned_count"]


async def test_auto_assign_training_room_sets_training_status(
    async_client, async_session, superuser_token_headers, auto_assign_vault
) -> None:
    vault = auto_assign_vault
    training_room = await _auto_room(
        async_session, vault, "Strength Training", RoomTypeEnum.TRAINING, SPECIALEnum.STRENGTH
    )
    dwellers = [await _auto_dweller(async_session, vault, f"TrainingDweller{i}", last_name="Test") for i in range(2)]

    response = await async_client.post(f"/vaults/{vault.id}/dwellers/auto-assign-all", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["assigned_count"] > 0

    # Training-room workers need a live session for the training queue.
    for created in dwellers:
        dweller = await crud.dweller.get(async_session, created.id)
        if dweller.room_id == training_room.id:
            assert dweller.status == DwellerStatusEnum.TRAINING
            training = await crud.training.training.get_active_by_dweller(async_session, created.id)
            assert training is not None
            assert training.room_id == training_room.id


async def test_auto_assign_crafting_rooms_endpoint(
    async_client, async_session, superuser_token_headers, auto_assign_vault
) -> None:
    vault = auto_assign_vault
    workshop = await _auto_room(async_session, vault, "Weapon workshop", RoomTypeEnum.CRAFTING, size=9)
    high = await _auto_dweller(async_session, vault, "High", last_name="Crafter", strength=7, special=7)
    low = await _auto_dweller(async_session, vault, "Low", last_name="Crafter", gender="female", strength=1, special=1)

    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-crafting", headers=superuser_token_headers
    )
    assert response.status_code == 200
    result = response.json()
    assert result["assigned_count"] == 2
    assert [a["dweller_id"] for a in result["assignments"]] == [str(high.id), str(low.id)]
    assert all(a["room_id"] == str(workshop.id) for a in result["assignments"])


async def test_auto_assign_crafting_rejects_foreign_vault(async_client, normal_user_token_headers, vault) -> None:
    response = await async_client.post(
        f"/vaults/{vault.id}/dwellers/auto-assign-crafting", headers=normal_user_token_headers
    )
    assert response.status_code == 403


@pytest.mark.smoke
async def test_vault_initiate_does_not_boost_superusers_by_default(
    async_client, async_session, superuser_token_headers
) -> None:
    response = await _initiate(async_client, superuser_token_headers, number=202)
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
async def test_vault_initiate_boosted_seeds_crafting_and_capacity(
    async_client, async_session, superuser_token_headers
) -> None:
    response = await _initiate(async_client, superuser_token_headers, number=203, boosted=True)
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

    assert len(dwellers) > 32
    assert vault.population_max >= len(dwellers)

    # Every junk type the craftable catalog accepts, across all three rarities.
    expected_junk = {
        (junk_type, rarity)
        for junk_type in ("steel", "leather", "circuitry", "cloth")
        for rarity in ("common", "rare", "legendary")
    } - {("leather", "legendary"), ("cloth", "legendary")}
    assert {(item.junk_type.value, item.rarity.value) for item in junk} >= expected_junk

    used_space = await crud.storage.storage.count_items(async_session, storage.id)
    assert storage.max_space > used_space


@pytest.mark.parametrize(
    ("payload", "status", "mode", "detail"),
    [
        ({"number": 211, "vault_mode": "survival"}, 201, "survival", None),
        ({"number": 212}, 201, "standard", None),
        ({"number": 213, "vault_mode": "nightmare"}, 422, None, None),
        ({"number": 215, "boosted": True, "vault_mode": "survival"}, 422, None, "survival"),
        ({"number": 2, "scenario": "missing"}, 400, None, None),
        ({"number": 2, "scenario": "vault_1_test"}, 400, None, None),
    ],
)
async def test_vault_initiate_validates_payload(
    async_client, superuser_token_headers, payload, status, mode, detail
) -> None:
    response = await _initiate(async_client, superuser_token_headers, **payload)
    assert response.status_code == status
    if detail:
        assert detail in response.json()["detail"][0]["msg"].lower()
    if mode:
        read = await async_client.get(f"/vaults/{response.json()['id']}", headers=superuser_token_headers)
        assert response.json()["vault_mode"] == mode
        assert read.status_code == 200
        assert read.json()["vault_mode"] == mode


async def test_vault_scenarios_list_vault_1(async_client, superuser_token_headers) -> None:
    response = await async_client.get("/vaults/scenarios", headers=superuser_token_headers)
    assert response.status_code == 200
    scenarios = response.json()
    assert [(scenario["number"], scenario["key"]) for scenario in scenarios] == [
        (1, "vault_1_test"),
        (67, "vault_67_short_rations"),
        (68, "vault_68_test"),
        (69, "vault_69_test"),
    ]
    test_start, *experiments = scenarios
    assert experiments[-1]["title"] == "Vault 69 — Eight Women, One Man"
    assert test_start["default_boosted"]
    assert test_start["expedition"]
    assert all(not scenario["default_on"] for scenario in scenarios)
    assert all(not scenario["requires_boosted"] and not scenario["expedition"] for scenario in experiments)


async def test_vault_initiate_scenario_seeds_dwellers_scouting_every_site(
    async_client, async_session, superuser_token_headers
) -> None:
    response = await _initiate(async_client, superuser_token_headers, number=1, scenario="vault_1_test")
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])

    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id)
    named = {dweller.display_name for dweller in dwellers}
    assert {"Ada Voss", "Bram Cole"} <= named
    assert next(dweller for dweller in dwellers if dweller.display_name == "Ada Voss").level == 5

    stored_vault = await crud.vault.get(async_session, vault_id)
    assert stored_vault is not None
    assert stored_vault.population_max is not None
    assert stored_vault.population_max >= len(dwellers)
    objectives = await objective_crud.get_multi_for_vault(async_session, vault_id)
    assert not any(objective.category is ObjectiveCategoryEnum.STARTER for objective in objectives)

    non_scenario_sites = {site.id for site in data_loader.load_expedition_sites() if not site.scenario_only}
    explorations = await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True)
    assert len(explorations) == len(non_scenario_sites)
    assert all(exploration.status is ExplorationStatus.ACTIVE for exploration in explorations)
    found = {
        event["site_id"]
        for exploration in explorations
        for event in exploration.events
        if event.get("event") == "site_found"
    }
    assert non_scenario_sites <= found


@pytest.mark.parametrize(
    ("number", "key", "expected_men", "expected_women"), [(68, "vault_68_test", 8, 1), (69, "vault_69_test", 1, 8)]
)
async def test_vault_initiate_ratio_scenario_keeps_the_starter_journey(
    async_client, async_session, superuser_token_headers, number, key, expected_men, expected_women
) -> None:
    await seed_objectives_from_json(async_session)
    response = await _initiate(async_client, superuser_token_headers, number=number, scenario=key)
    assert response.status_code == 201, response.text
    vault_id = UUID(response.json()["id"])

    persisted = await crud.vault.get(async_session, vault_id)
    assert persisted.scenario_key == key
    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id, limit=200)
    assert len(dwellers) == 9
    assert sum(dweller.gender == GenderEnum.MALE for dweller in dwellers) == expected_men
    assert sum(dweller.gender == GenderEnum.FEMALE for dweller in dwellers) == expected_women
    rooms = await crud.room.get_all_by_vault(async_session, vault_id)
    assert not any(room.name == "Overseer's Office" for room in rooms)
    assert await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True) == []
    objectives = await objective_crud.get_multi_for_vault(async_session, vault_id)
    assert any(objective.category is ObjectiveCategoryEnum.STARTER for objective in objectives)


async def test_vault_67_starts_with_half_the_standard_food_and_water(async_client, superuser_token_headers) -> None:
    baseline = await _initiate(async_client, superuser_token_headers, number=66)
    challenge = await _initiate(
        async_client, superuser_token_headers, number=67, scenario="vault_67_short_rations", boosted=True
    )
    assert baseline.status_code == challenge.status_code == 201
    standard, short_rations = baseline.json(), challenge.json()
    for field in ("power", "food_max", "water_max", "bottle_caps", "population_max"):
        assert short_rations[field] == standard[field]
    for field in ("food", "water"):
        assert short_rations[field] == standard[field] // 2


async def test_named_vault_without_scenario_uses_the_ordinary_start(
    async_client, async_session, superuser_token_headers
) -> None:
    response = await _initiate(async_client, superuser_token_headers, number=67)
    assert response.status_code == 201
    vault_id = UUID(response.json()["id"])
    assert await crud.exploration.get_by_vault(async_session, vault_id=vault_id, active_only=True) == []


async def test_vault_mode_is_immutable_via_api(async_client, superuser_token_headers) -> None:
    created = await _initiate(async_client, superuser_token_headers, number=214, vault_mode="survival")
    assert created.status_code == 201
    vault_id = created.json()["id"]

    response = await async_client.put(
        f"/vaults/{vault_id}", headers=superuser_token_headers, json={"vault_mode": "standard"}
    )
    assert response.status_code == 422

    read = await async_client.get(f"/vaults/{vault_id}", headers=superuser_token_headers)
    assert read.json()["vault_mode"] == "survival"


async def test_read_vault_serialises_a_null_radio_mode(async_client, async_session, superuser_token_headers) -> None:
    """The Postgres column is nullable, so a legacy row must still read as a 200."""
    data = create_fake_vault()
    data["user_id"] = await _owner_id(async_session)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**data))
    vault.radio_mode = None
    await async_session.commit()

    response = await async_client.get(f"/vaults/{vault.id}", headers=superuser_token_headers)

    assert response.status_code == 200
    assert response.json()["radio_mode"] is None
