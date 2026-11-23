from uuid import UUID, uuid4

import pytest

from app import crud
from app.core.config import settings
from app.core.enums import ItemTypeEnum, JunkTypeEnum, RarityEnum
from app.crud.vault import vault as vault_crud
from app.models.item import Item
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.recipe_unlock_service import catalog_entry
from app.services.reward_service import reward_service
from app.services.storage_maintenance_service import summary
from app.services.vault.seed_types import SEED_OUTFITS
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.items import create_fake_junk, create_fake_outfit, create_fake_weapon
from app.tests.factory.vaults import create_fake_vault
from app.utils.item_factory import build_outfit, build_weapon
from app.utils.outfit_assets import get_outfit_image_url
from app.utils.weapon_assets import get_weapon_image_url

pytestmark = pytest.mark.asyncio(scope="module")


async def _vault_with_storage(async_session, **storage_attrs):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    assert user is not None
    vault_data = {**create_fake_vault(), "user_id": str(user.id)}
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    for key, value in storage_attrs.items():
        setattr(storage, key, value)
    async_session.add(storage)
    await async_session.flush()
    return vault, storage


def _junk(storage, name: str, description: str = "Test item", **kwargs) -> Junk:
    return Junk(
        name=name,
        junk_type=JunkTypeEnum.VALUABLES,
        rarity=RarityEnum.COMMON,
        description=description,
        storage_id=storage.id,
        **kwargs,
    )


@pytest.mark.smoke
async def test_get_storage_space_with_items(async_client, async_session, superuser_token_headers):
    vault, storage = await _vault_with_storage(async_session, max_space=100)
    for i in range(3):
        async_session.add(_junk(storage, f"Test Junk {i}"))
    await async_session.flush()

    response = await async_client.get(f"/storage/vault/{vault.id}/space", headers=superuser_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["used_space"] == 3
    assert data["available_space"] == 100 - 3  # max_space - items
    assert data["utilization_pct"] == 3.0


@pytest.mark.smoke
async def test_get_storage_items_success(async_client, async_session, superuser_token_headers):
    vault, storage = await _vault_with_storage(async_session)
    for _ in range(2):
        async_session.add(Weapon(**create_fake_weapon(), storage_id=storage.id))
    async_session.add(Outfit(**create_fake_outfit(), storage_id=storage.id))
    async_session.add(Junk(**create_fake_junk(), storage_id=storage.id))
    await async_session.flush()

    response = await async_client.get(f"/storage/vault/{vault.id}/items", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, dict)
    for kind in ("weapons", "outfits", "junk"):
        assert kind in data
        assert isinstance(data[kind], list)
    assert len(data["weapons"]) == 2
    assert len(data["outfits"]) == 1
    assert len(data["junk"]) == 1

    for item in data["weapons"] + data["outfits"] + data["junk"]:
        assert "id" in item
        assert "name" in item


async def test_storage_items_describe_recipe_status(async_client, async_session, superuser_token_headers):
    vault, storage = await _vault_with_storage(async_session)

    weapon_entry = catalog_entry("weapon", "Baseball bat")
    outfit_entry = catalog_entry("outfit", "Accountant outfit")
    assert weapon_entry is not None
    assert outfit_entry is not None
    starter_armor = next(outfit for outfit in SEED_OUTFITS if outfit["name"] == "T-51b Power Armor")
    async_session.add_all(
        [
            build_weapon(weapon_entry, "rare", storage.id),
            build_outfit(outfit_entry, "common", storage.id),
            build_outfit(starter_armor, starter_armor["rarity"], storage.id),
        ]
    )
    await async_session.flush()

    response = await async_client.get(f"/storage/vault/{vault.id}/items", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    descriptions = {item["name"]: item["description"] for item in data["weapons"] + data["outfits"]}
    assert descriptions["Baseball bat"] == "Recipe locked — scrap 1 to learn it"
    assert descriptions["Accountant outfit"] == "Not craftable"
    assert descriptions["T-51b Power Armor"] == "Not craftable"

    await crud.vault_recipe_unlock.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", recipe_name="Baseball bat", threshold=1
    )
    await async_session.flush()

    response = await async_client.get(f"/storage/vault/{vault.id}/items", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    descriptions = {item["name"]: item["description"] for item in data["weapons"] + data["outfits"]}
    assert descriptions["Baseball bat"] == "Craftable — recipe known"


async def test_get_storage_items_backfills_junk_art(async_client, async_session, superuser_token_headers):
    vault, storage = await _vault_with_storage(async_session)
    async_session.add(_junk(storage, "Teddy bear", "A well-loved bear.", image_url=None))
    await async_session.flush()

    response = await async_client.get(f"/storage/vault/{vault.id}/items", headers=superuser_token_headers)
    assert response.status_code == 200
    (entry,) = response.json()["junk"]
    assert entry["image_url"] == "/static/junk_images/FOS Teddy bear.png"


async def test_open_lunchbox_success(async_client, async_session, superuser_token_headers):
    vault, _ = await _vault_with_storage(async_session, max_space=100)
    minted = await reward_service.grant_lunchbox(async_session, vault.id)

    response = await async_client.post(
        f"/storage/vault/{vault.id}/lunchbox/open",
        json={"item_id": minted["item_id"]},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["reward_type"] == "lunchbox"
    assert len(data["items"]) == 3
    assert data["dweller"]["dweller_id"]
    assert data["dweller"]["name"]
    dweller = await crud.dweller.get(async_session, UUID(data["dweller"]["dweller_id"]))
    assert data["dweller"]["rarity"] == dweller.rarity.value
    assert data["dweller"]["image_url"] == dweller.image_url
    assert data["dweller"]["thumbnail_url"] == dweller.thumbnail_url

    for item in data["items"]:
        image_for = get_weapon_image_url if item["type"] == "weapon" else get_outfit_image_url
        assert item["image_url"] == image_for(item["name"])

    remaining = await crud.storage.get_unopened_lunchbox(async_session, UUID(minted["item_id"]), vault.id)
    assert remaining is None


async def test_open_lunchbox_unknown_item_404(async_client, async_session, superuser_token_headers):
    vault, _ = await _vault_with_storage(async_session)

    response = await async_client.post(
        f"/storage/vault/{vault.id}/lunchbox/open",
        json={"item_id": str(uuid4())},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


async def test_storage_space_reports_over_capacity_instead_of_500(async_client, async_session, superuser_token_headers):
    vault, storage = await _vault_with_storage(async_session, max_space=2)
    for index in range(5):
        async_session.add(_junk(storage, f"Overflow {index}", "Over-capacity fixture"))
    await async_session.flush()

    response = await async_client.get(f"/storage/vault/{vault.id}/space", headers=superuser_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["used_space"] == 5
    assert data["max_space"] == 2
    assert data["available_space"] == 0
    assert data["utilization_pct"] > 100


async def test_storage_space_ignores_nuka_consumables(async_client, async_session, superuser_token_headers):
    vault, storage = await _vault_with_storage(async_session, max_space=10)
    for name in ("Nuka-Cola Quantum", "Nuka-Cola"):
        async_session.add(
            Item(name=name, item_type=ItemTypeEnum.CONSUMABLE, rarity=RarityEnum.COMMON, storage_id=storage.id)
        )
    async_session.add(_junk(storage, "Counting Junk", "Still counts"))
    await async_session.flush()

    response = await async_client.get(f"/storage/vault/{vault.id}/space", headers=superuser_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["used_space"] == 1
    assert data["available_space"] == 9


async def test_distribute_recovery_supplies_endpoint(async_client, async_session, superuser_token_headers):
    vault, _ = await _vault_with_storage(async_session, radaway=10, stimpack=10)
    dweller_data = create_fake_dweller() | {"vault_id": vault.id, "radiation": 40, "max_health": 100, "health": 1}
    dweller = await crud.dweller.create(async_session, DwellerCreate(**dweller_data))
    await async_session.flush()

    response = await async_client.post(
        f"/storage/vault/{vault.id}/medical/distribute-recovery-supplies", headers=superuser_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dwellers_treated"] == 1
    assert data["radaways_used"] == 1
    assert data["stimpaks_used"] == 1
    assert data["vault_radaways"] == 9
    assert data["vault_stimpacks"] == 9
    await async_session.refresh(dweller)
    assert dweller.radiation == 0
    assert dweller.health >= 40


@pytest.mark.parametrize("enabled", [False, True])
async def test_storage_maintenance_summary_is_read_only(
    async_client, async_session, superuser_token_headers, vault, enabled, monkeypatch
):
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.storage, "maintenance_enabled", enabled)
    expected = await summary(async_session, vault.id)
    response = await async_client.get(f"/storage/vault/{vault.id}/maintenance", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json() == expected.model_dump()
    assert response.json()["hourly_chance"] == (0.02 if enabled else 0)


async def test_storage_maintenance_refuses_another_players_vault(async_client, normal_user_token_headers, vault):
    response = await async_client.get(f"/storage/vault/{vault.id}/maintenance", headers=normal_user_token_headers)
    assert response.status_code == 403
