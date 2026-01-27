import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.crud.vault import vault as vault_crud
from app.schemas.vault import VaultCreateWithUserID
from app.schemas.weapon import WeaponCreate
from app.tests.factory.items import create_fake_weapon
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_create_weapon(async_client: AsyncClient, weapon_data: dict):
    response = await async_client.post("/weapons/", json=weapon_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == weapon_data["name"]
    assert response_data["rarity"] == weapon_data["rarity"]
    assert response_data["value"] == weapon_data["value"]
    assert response_data["weapon_type"] == weapon_data["weapon_type"]
    assert response_data["weapon_subtype"] == weapon_data["weapon_subtype"]
    assert response_data["stat"] == weapon_data["stat"]
    assert response_data["damage_min"] == weapon_data["damage_min"]
    assert response_data["damage_max"] == weapon_data["damage_max"]


@pytest.mark.asyncio
async def test_create_weapon_incomplete(async_client: AsyncClient):
    response = await async_client.post(
        "/weapons/",
        json={"name": "Test Weapon"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_weapon_invalid(async_client: AsyncClient):
    response = await async_client.post(
        "/weapons/",
        json={
            "name": "Test Weapon",
            "rarity": "Unique",
            "weapon_type": ["Melee"],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_read_weapon_list(async_client: AsyncClient, async_session: AsyncSession, weapon_data: dict):
    weapon_2_data = create_fake_weapon()
    weapon_1 = WeaponCreate(**weapon_data)
    weapon_2 = WeaponCreate(**weapon_2_data)
    await crud.weapon.create(async_session, weapon_1)
    await crud.weapon.create(async_session, weapon_2)
    response = await async_client.get("/weapons/")
    all_weapons = response.json()
    assert response.status_code == 200
    assert len(all_weapons) == 2
    response_weapon_1, response_weapon_2 = all_weapons
    if response_weapon_1["name"] == weapon_2.name:
        response_weapon_1, response_weapon_2 = response_weapon_2, response_weapon_1
    assert response_weapon_1["name"] == weapon_1.name
    assert response_weapon_1["rarity"] == weapon_1.rarity.value
    assert response_weapon_1["value"] == weapon_1.value
    assert response_weapon_1["weapon_type"] == weapon_1.weapon_type.value
    assert response_weapon_1["weapon_subtype"] == weapon_1.weapon_subtype.value
    assert response_weapon_1["stat"] == weapon_1.stat
    assert response_weapon_1["damage_min"] == weapon_1.damage_min
    assert response_weapon_1["damage_max"] == weapon_1.damage_max

    assert response_weapon_2["name"] == weapon_2.name
    assert response_weapon_2["rarity"] == weapon_2.rarity.value
    assert response_weapon_2["value"] == weapon_2.value
    assert response_weapon_2["weapon_type"] == weapon_2.weapon_type.value
    assert response_weapon_2["weapon_subtype"] == weapon_2.weapon_subtype.value
    assert response_weapon_2["stat"] == weapon_2.stat
    assert response_weapon_2["damage_min"] == weapon_2.damage_min
    assert response_weapon_2["damage_max"] == weapon_2.damage_max


@pytest.mark.asyncio
async def test_read_weapon(async_client: AsyncClient, async_session: AsyncSession, weapon_data: dict):
    weapon_obj = WeaponCreate(**weapon_data)
    created_weapon = await crud.weapon.create(async_session, weapon_obj)
    response = await async_client.get(f"/weapons/{created_weapon.id}")
    assert response.status_code == 200
    response_weapon = response.json()
    assert response_weapon["name"] == weapon_obj.name
    assert response_weapon["rarity"] == weapon_obj.rarity.value
    assert response_weapon["weapon_type"] == weapon_obj.weapon_type.value
    assert response_weapon["weapon_subtype"] == weapon_obj.weapon_subtype.value
    assert response_weapon["stat"] == weapon_obj.stat
    assert response_weapon["damage_min"] == weapon_obj.damage_min
    assert response_weapon["damage_max"] == weapon_obj.damage_max


@pytest.mark.asyncio
async def test_update_weapon(async_client: AsyncClient, weapon_data: dict):
    response = await async_client.post("/weapons/", json=weapon_data)
    weapon_response = response.json()
    weapon_id = weapon_response["id"]
    weapon_new_data = create_fake_weapon()
    update_response = await async_client.put(f"/weapons/{weapon_id}", json=weapon_new_data)
    updated_weapon = update_response.json()
    assert update_response.status_code == 200
    assert updated_weapon["id"] == weapon_id
    assert updated_weapon["name"] == weapon_new_data["name"]
    assert updated_weapon["rarity"] == weapon_new_data["rarity"]
    assert updated_weapon["weapon_type"] == weapon_new_data["weapon_type"]
    assert updated_weapon["weapon_subtype"] == weapon_new_data["weapon_subtype"]
    assert updated_weapon["stat"] == weapon_new_data["stat"]
    assert updated_weapon["damage_min"] == weapon_new_data["damage_min"]
    assert updated_weapon["damage_max"] == weapon_new_data["damage_max"]


@pytest.mark.asyncio
async def test_delete_weapon(async_client: AsyncClient, weapon_data: dict):
    create_response = await async_client.post("/weapons/", json=weapon_data)
    weapon_1 = create_response.json()
    delete_response = await async_client.delete(f"/weapons/{weapon_1['id']}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/weapons/{weapon_1['id']}")
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_scrap_weapon_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    # Setup vault/storage and weapon
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    weapon_in = WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id))
    weapon = await crud.weapon.create(async_session, weapon_in)

    response = await async_client.post(f"/weapons/{weapon.id}/scrap/", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "junk" in data
    assert isinstance(data["junk"], list)
    # Weapon should be deleted as part of scrap
    read_response = await async_client.get(f"/weapons/{weapon.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_scrap_weapon_assigns_storage_id(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    weapon_in = WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id))
    weapon = await crud.weapon.create(async_session, weapon_in)
    response = await async_client.post(f"/weapons/{weapon.id}/scrap/", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    junk_list = data.get("junk", [])
    if junk_list:
        assert junk_list[0].get("storage_id") == str(storage.id)


@pytest.mark.asyncio
async def test_scrap_weapon_creates_correct_value(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    weapon_in = WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id))
    weapon = await crud.weapon.create(async_session, weapon_in)
    response = await async_client.post(f"/weapons/{weapon.id}/scrap/", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    junk_list = data.get("junk", [])
    if junk_list:
        from app.schemas.common import RarityEnum

        rarity = weapon.rarity
        mapping = {RarityEnum.COMMON: 2, RarityEnum.RARE: 50, RarityEnum.LEGENDARY: 200}
        expected_value = mapping.get(rarity, 0)
        assert junk_list[0].get("value") == expected_value


@pytest.mark.asyncio
async def test_scrap_weapon_not_found(
    async_client: AsyncClient,
    async_session: AsyncSession,  # noqa: ARG001
    superuser_token_headers: dict[str, str],
) -> None:
    fake_id = str(uuid.uuid4())
    response = await async_client.post(f"/weapons/{fake_id}/scrap/", headers=superuser_token_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sell_weapon_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    weapon_in = WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id))
    weapon = await crud.weapon.create(async_session, weapon_in)
    vault_before = await crud.vault.get(async_session, id=vault.id)
    pre_caps = vault_before.bottle_caps
    response = await async_client.post(f"/weapons/{weapon.id}/sell/", headers=superuser_token_headers)
    assert response.status_code == 200
    read_response = await async_client.get(f"/weapons/{weapon.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404
    vault_after = await crud.vault.get(async_session, id=vault.id)
    assert vault_after.bottle_caps == pre_caps + (weapon.value or 0)


@pytest.mark.asyncio
async def test_sell_weapon_adds_correct_caps(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    weapon_in = WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id))
    weapon = await crud.weapon.create(async_session, weapon_in)
    vault_before = await crud.vault.get(async_session, id=vault.id)
    pre_caps = vault_before.bottle_caps
    await async_client.post(f"/weapons/{weapon.id}/sell/", headers=superuser_token_headers)
    vault_after = await crud.vault.get(async_session, id=vault.id)
    assert vault_after.bottle_caps == pre_caps + (weapon.value or 0)


@pytest.mark.asyncio
async def test_sell_weapon_not_found(
    async_client: AsyncClient,
    async_session: AsyncSession,  # noqa: ARG001
    superuser_token_headers: dict[str, str],
) -> None:
    fake_id = str(uuid.uuid4())
    response = await async_client.post(f"/weapons/{fake_id}/sell/", headers=superuser_token_headers)
    assert response.status_code in (404, 403)


@pytest.mark.asyncio
async def test_filter_weapons_by_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_a_data = create_fake_vault()
    vault_a_data["user_id"] = str(user.id)
    vault_a_in = VaultCreateWithUserID(**vault_a_data)
    vault_a = await crud.vault.create(async_session, vault_a_in)
    storage_a = await vault_crud.create_storage(db_session=async_session, vault_id=vault_a.id)
    w1 = WeaponCreate(**create_fake_weapon(), storage_id=str(storage_a.id))
    weapon_a = await crud.weapon.create(async_session, w1)
    vault_b_data = create_fake_vault()
    vault_b_data["user_id"] = str(user.id)
    vault_b_in = VaultCreateWithUserID(**vault_b_data)
    vault_b = await crud.vault.create(async_session, vault_b_in)
    storage_b = await vault_crud.create_storage(db_session=async_session, vault_id=vault_b.id)
    w2 = WeaponCreate(**create_fake_weapon(), storage_id=str(storage_b.id))
    weapon_b = await crud.weapon.create(async_session, w2)
    response = await async_client.get(f"/weapons/?vault_id={vault_a.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    ids = [w["id"] for w in data]
    assert str(weapon_a.id) in ids
    assert str(weapon_b.id) not in ids


@pytest.mark.asyncio
async def test_filter_weapons_includes_equipped(
    async_client: AsyncClient,
    async_session: AsyncSession,  # noqa: ARG001
    equipped_dweller: tuple,
    superuser_token_headers: dict[str, str],
) -> None:
    _dweller, _, equipped_weapon = equipped_dweller
    vault_id = equipped_weapon.storage.vault_id
    response = await async_client.get(f"/weapons/?vault_id={vault_id}", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    ids = [w["id"] for w in data]
    assert str(equipped_weapon.id) in ids


@pytest.mark.asyncio
async def test_filter_weapons_excludes_other_vaults(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_a_data = create_fake_vault()
    vault_a_data["user_id"] = str(user.id)
    vault_a_in = VaultCreateWithUserID(**vault_a_data)
    vault_a = await crud.vault.create(async_session, vault_a_in)
    storage_a = await vault_crud.create_storage(db_session=async_session, vault_id=vault_a.id)
    w1 = WeaponCreate(**create_fake_weapon(), storage_id=str(storage_a.id))
    weapon_a = await crud.weapon.create(async_session, w1)
    vault_b_data = create_fake_vault()
    vault_b_data["user_id"] = str(user.id)
    vault_b_in = VaultCreateWithUserID(**vault_b_data)
    vault_b = await crud.vault.create(async_session, vault_b_in)
    storage_b = await vault_crud.create_storage(db_session=async_session, vault_id=vault_b.id)
    w2 = WeaponCreate(**create_fake_weapon(), storage_id=str(storage_b.id))
    weapon_b = await crud.weapon.create(async_session, w2)
    response = await async_client.get(f"/weapons/?vault_id={vault_a.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    ids = [w["id"] for w in data]
    assert str(weapon_a.id) in ids
    assert str(weapon_b.id) not in ids
