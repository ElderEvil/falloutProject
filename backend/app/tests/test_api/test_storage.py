"""Tests for storage API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import JunkTypeEnum, RarityEnum
from app.crud.vault import vault as vault_crud
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.vault import VaultCreateWithUserID
from app.services.recipe_unlock_service import catalog_entry
from app.services.vault.seed_types import SEED_OUTFITS
from app.tests.factory.items import create_fake_junk, create_fake_outfit, create_fake_weapon
from app.tests.factory.vaults import create_fake_vault
from app.utils.item_factory import build_outfit, build_weapon

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_get_storage_space_with_items(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test storage space info correctly reflects items in storage."""
    # Create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)

    # Create storage for the vault with a reasonable max_space
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 100  # Set reasonable max space for testing
    async_session.add(storage)
    await async_session.flush()

    # Add items to storage
    for i in range(3):
        junk = Junk(
            name=f"Test Junk {i}",
            junk_type=JunkTypeEnum.VALUABLES,
            rarity=RarityEnum.COMMON,
            description="Test item",
            storage_id=storage.id,
        )
        async_session.add(junk)
    await async_session.flush()

    # Get storage info
    response = await async_client.get(
        f"/storage/vault/{vault.id}/space",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify items are counted
    assert data["used_space"] == 3
    assert data["available_space"] == 100 - 3  # max_space - items
    assert data["utilization_pct"] == 3.0  # 3/100 * 100 = 3%


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_get_storage_items_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test GET /storage/vault/{vault_id}/items returns all item types."""
    # Create vault for superuser
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)

    # Create storage for the vault
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    # Create items for storage
    for _ in range(2):
        w = Weapon(**create_fake_weapon(), storage_id=storage.id)
        async_session.add(w)
    o = Outfit(**create_fake_outfit(), storage_id=storage.id)
    async_session.add(o)
    j = Junk(**create_fake_junk(), storage_id=storage.id)
    async_session.add(j)
    await async_session.flush()

    # Get items
    response = await async_client.get(
        f"/storage/vault/{vault.id}/items",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, dict)
    assert "weapons" in data
    assert isinstance(data["weapons"], list)
    assert "outfits" in data
    assert isinstance(data["outfits"], list)
    assert "junk" in data
    assert isinstance(data["junk"], list)
    assert len(data["weapons"]) == 2
    assert len(data["outfits"]) == 1
    assert len(data["junk"]) == 1

    # Basic field checks on returned items
    for item in data["weapons"]:
        assert "id" in item
        assert "name" in item
    for item in data["outfits"]:
        assert "id" in item
        assert "name" in item
    for item in data["junk"]:
        assert "id" in item
        assert "name" in item


@pytest.mark.asyncio
async def test_storage_items_describe_recipe_status(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Weapon and outfit cards report craftability and whether this vault knows the recipe."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

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


@pytest.mark.asyncio
async def test_get_storage_items_backfills_junk_art(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Legacy junk rows stored without image_url still render art in storage."""
    from app.core.enums import JunkTypeEnum

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    async_session.add(
        Junk(
            name="Teddy bear",
            junk_type=JunkTypeEnum.VALUABLES,
            rarity="common",
            description="A well-loved bear.",
            image_url=None,
            storage_id=storage.id,
        )
    )
    await async_session.flush()

    response = await async_client.get(
        f"/storage/vault/{vault.id}/items",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    (entry,) = response.json()["junk"]
    assert entry["image_url"] == "/static/junk_images/FOS Teddy bear.png"


@pytest.mark.asyncio
async def test_open_lunchbox_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test POST /storage/vault/{vault_id}/lunchbox/open consumes the box and reveals contents."""
    from uuid import UUID

    from app.services.reward_service import reward_service

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 100
    async_session.add(storage)
    await async_session.flush()

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
    from app.utils.outfit_assets import get_outfit_image_url
    from app.utils.weapon_assets import get_weapon_image_url

    for item in data["items"]:
        image_for = get_weapon_image_url if item["type"] == "weapon" else get_outfit_image_url
        assert item["image_url"] == image_for(item["name"])

    remaining = await crud.storage.get_unopened_lunchbox(async_session, UUID(minted["item_id"]), vault.id)
    assert remaining is None


@pytest.mark.asyncio
async def test_open_lunchbox_unknown_item_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test opening an unknown lunchbox returns 404 without distinguishing the cause."""
    from uuid import uuid4

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    response = await async_client.post(
        f"/storage/vault/{vault.id}/lunchbox/open",
        json={"item_id": str(uuid4())},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_storage_space_reports_over_capacity_instead_of_500(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Scrapping can leave more items than slots; the endpoint must still answer."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 2
    async_session.add(storage)
    await async_session.flush()

    for index in range(5):
        async_session.add(
            Junk(
                name=f"Overflow {index}",
                junk_type=JunkTypeEnum.VALUABLES,
                rarity=RarityEnum.COMMON,
                description="Over-capacity fixture",
                storage_id=storage.id,
            )
        )
    await async_session.flush()

    response = await async_client.get(
        f"/storage/vault/{vault.id}/space",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["used_space"] == 5
    assert data["max_space"] == 2
    assert data["available_space"] == 0
    assert data["utilization_pct"] > 100


@pytest.mark.asyncio
async def test_storage_space_ignores_nuka_consumables(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Space-free nuka-cola bottles never reduce used_space or available_space."""
    from app.core.enums import ItemTypeEnum
    from app.models.item import Item

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 10
    async_session.add(storage)
    await async_session.flush()

    for name in ("Nuka-Cola Quantum", "Nuka-Cola"):
        async_session.add(
            Item(
                name=name,
                item_type=ItemTypeEnum.CONSUMABLE,
                rarity=RarityEnum.COMMON,
                storage_id=storage.id,
            )
        )
    async_session.add(
        Junk(
            name="Counting Junk",
            junk_type=JunkTypeEnum.VALUABLES,
            rarity=RarityEnum.COMMON,
            description="Still counts",
            storage_id=storage.id,
        )
    )
    await async_session.flush()

    response = await async_client.get(
        f"/storage/vault/{vault.id}/space",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["used_space"] == 1
    assert data["available_space"] == 9


@pytest.mark.asyncio
async def test_distribute_recovery_supplies_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """The one-shot action treats irradiated dwellers and reports the supplies used."""
    from app.schemas.dweller import DwellerCreate
    from app.tests.factory.dwellers import create_fake_dweller

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.radaway = 10
    storage.stimpack = 10
    async_session.add(storage)

    dweller_data = create_fake_dweller()
    dweller_data["vault_id"] = vault.id
    dweller_data["radiation"] = 40
    dweller_data["max_health"] = 100
    dweller_data["health"] = 1
    dweller = await crud.dweller.create(async_session, DwellerCreate(**dweller_data))
    await async_session.flush()

    response = await async_client.post(
        f"/storage/vault/{vault.id}/medical/distribute-recovery-supplies",
        headers=superuser_token_headers,
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
    async_client,
    async_session,
    superuser_token_headers,
    vault,
    enabled,
    monkeypatch,
):
    from app.core.game_config import game_config
    from app.services.storage_maintenance_service import summary

    monkeypatch.setattr(game_config.storage, "maintenance_enabled", enabled)
    expected = await summary(async_session, vault.id)
    response = await async_client.get(f"/storage/vault/{vault.id}/maintenance", headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json() == expected.model_dump()
    assert response.json()["hourly_chance"] == (0.02 if enabled else 0)


async def test_storage_maintenance_refuses_another_players_vault(
    async_client,
    normal_user_token_headers,
    vault,
):
    response = await async_client.get(
        f"/storage/vault/{vault.id}/maintenance",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
