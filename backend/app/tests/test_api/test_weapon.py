import uuid
from unittest.mock import patch

import pytest

from app import crud
from app.core.config import settings
from app.core.enums import DwellerStatusEnum, JunkTypeEnum, RarityEnum
from app.crud.vault import vault as vault_crud
from app.models.junk import Junk
from app.schemas.vault import VaultCreateWithUserID
from app.schemas.weapon import WeaponCreate
from app.tests.factory.items import create_fake_weapon
from app.tests.factory.vaults import create_fake_vault
from app.utils.item_factory import build_outfit, build_pet, build_weapon

pytestmark = pytest.mark.asyncio(scope="module")


async def _vault_with_storage(async_session, *, max_space: int | None = None, **vault_overrides):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault() | {"user_id": str(user.id), **vault_overrides}
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    if max_space is not None:
        storage.max_space = max_space
        async_session.add(storage)
        await async_session.flush()
    return vault, storage


async def test_create_weapon_invalid(async_client, superuser_token_headers) -> None:
    response = await async_client.post(
        "/weapons/",
        json={"name": "Test Weapon", "rarity": "Unique", "weapon_type": ["Melee"]},
        headers=superuser_token_headers,
    )
    assert response.status_code == 422


async def test_read_weapon_list(async_client, async_session, weapon_data, superuser_token_headers, vault) -> None:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    weapon_2_data = create_fake_weapon()
    weapon_1 = WeaponCreate(**weapon_data)
    weapon_2 = WeaponCreate(**weapon_2_data)
    await crud.weapon.create(async_session, {**weapon_data, "storage_id": storage.id})
    await crud.weapon.create(async_session, {**weapon_2_data, "storage_id": storage.id})
    response = await async_client.get(f"/weapons/?vault_id={vault.id}", headers=superuser_token_headers)
    all_weapons = response.json()
    assert response.status_code == 200
    assert len(all_weapons) == 2
    response_weapon_1, response_weapon_2 = all_weapons
    if response_weapon_1["name"] == weapon_2.name:
        response_weapon_1, response_weapon_2 = response_weapon_2, response_weapon_1
    for response_weapon, expected in ((response_weapon_1, weapon_1), (response_weapon_2, weapon_2)):
        assert response_weapon["name"] == expected.name
        assert response_weapon["rarity"] == expected.rarity.value
        assert response_weapon["value"] == expected.value
        assert response_weapon["weapon_type"] == expected.weapon_type.value
        assert response_weapon["weapon_subtype"] == expected.weapon_subtype.value
        assert response_weapon["stat"] == expected.stat
        assert response_weapon["damage_min"] == expected.damage_min
        assert response_weapon["damage_max"] == expected.damage_max


async def test_update_weapon(async_client, weapon_data, superuser_token_headers) -> None:
    weapon_id = (await async_client.post("/weapons/", json=weapon_data, headers=superuser_token_headers)).json()["id"]
    weapon_new_data = create_fake_weapon()
    update_response = await async_client.put(
        f"/weapons/{weapon_id}", json=weapon_new_data, headers=superuser_token_headers
    )
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


async def test_delete_weapon(async_client, weapon_data, superuser_token_headers) -> None:
    weapon_1 = (await async_client.post("/weapons/", json=weapon_data, headers=superuser_token_headers)).json()
    delete_response = await async_client.delete(f"/weapons/{weapon_1['id']}", headers=superuser_token_headers)
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/weapons/{weapon_1['id']}", headers=superuser_token_headers)
    assert read_response.status_code == 404


async def test_scrap_weapon_success(async_client, async_session, superuser_token_headers) -> None:
    _vault, storage = await _vault_with_storage(async_session, max_space=5)
    weapon = await crud.weapon.create(async_session, WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id)))
    response = await async_client.post(f"/weapons/{weapon.id}/scrap/", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "junk" in data
    assert isinstance(data["junk"], list)
    read_response = await async_client.get(f"/weapons/{weapon.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404


async def test_scrap_weapon_rejects_when_junk_would_exceed_capacity(
    async_client, async_session, superuser_token_headers
) -> None:
    """Scrapping replaces one item with junk; it must not push storage past capacity."""
    _vault, storage = await _vault_with_storage(async_session, max_space=1)
    weapon = await crud.weapon.create(async_session, WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id)))
    two_junk = [
        Junk(name="Steel", junk_type=JunkTypeEnum.STEEL, rarity=RarityEnum.COMMON, description="Scrap", value=2),
        Junk(name="Leather", junk_type=JunkTypeEnum.LEATHER, rarity=RarityEnum.COMMON, description="Scrap", value=2),
    ]
    with patch("app.crud.item_base.CRUDItem.convert_to_junk", return_value=two_junk):
        response = await async_client.post(f"/weapons/{weapon.id}/scrap/", headers=superuser_token_headers)
    assert response.status_code == 409
    assert await crud.weapon.get_or_none(async_session, weapon.id) is not None


async def test_sell_weapon_success(async_client, async_session, superuser_token_headers) -> None:
    # Deterministic caps: the factory rolls up to 1M and deposit_caps caps at 999_999,
    # which would overflow the exact-sum assertion below on a high roll.
    vault, storage = await _vault_with_storage(async_session, bottle_caps=500)
    weapon = await crud.weapon.create(async_session, WeaponCreate(**create_fake_weapon(), storage_id=str(storage.id)))
    pre_caps = (await crud.vault.get(async_session, id=vault.id)).bottle_caps
    response = await async_client.post(f"/weapons/{weapon.id}/sell/", headers=superuser_token_headers)
    assert response.status_code == 200
    read_response = await async_client.get(f"/weapons/{weapon.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404
    vault_after = await crud.vault.get(async_session, id=vault.id)
    assert vault_after.bottle_caps == pre_caps + (weapon.value or 0)


async def test_sell_weapon_not_found(async_client, superuser_token_headers) -> None:
    response = await async_client.post(f"/weapons/{uuid.uuid4()}/sell/", headers=superuser_token_headers)
    assert response.status_code in (404, 403)


@pytest.mark.parametrize("item_type", ["weapon", "outfit", "pet"])
@pytest.mark.parametrize("status", ["exploring", "questing"])
async def test_away_dweller_cannot_equip_from_storage(
    async_client, async_session, superuser_token_headers, vault, dweller, item_type, status
) -> None:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    builder = {"weapon": build_weapon, "outfit": build_outfit, "pet": build_pet}[item_type]
    item = builder({"name": "Test equipment"}, RarityEnum.COMMON, storage.id)
    async_session.add(item)
    dweller.status = DwellerStatusEnum(status)
    await async_session.commit()
    path = f"/{item_type}s/{dweller.id}/equip/{item.id}"
    response = await async_client.post(path, headers=superuser_token_headers)
    assert response.status_code == 409
    assert "outside the vault" in response.json()["detail"]
    await async_session.refresh(item)
    assert item.storage_id == storage.id
    assert item.dweller_id is None
    dweller.status = DwellerStatusEnum.IDLE
    await async_session.commit()
    response = await async_client.post(path, headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json()["dweller_id"] == str(dweller.id)
