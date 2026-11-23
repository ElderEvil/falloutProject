import random

import pytest

from app import crud
from app.core.config import settings
from app.core.enums import JunkTypeEnum
from app.crud.vault import vault as vault_crud
from app.schemas.junk import JunkCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.items import create_fake_junk
from app.tests.factory.vaults import create_fake_vault
from app.tests.utils.utils import random_lower_string

pytestmark = pytest.mark.asyncio(scope="module")


async def test_create_junk_invalid(async_client, superuser_token_headers) -> None:
    response = await async_client.post(
        "/junk/", json={"name": "Test Junk", "rarity": "Unique"}, headers=superuser_token_headers
    )
    assert response.status_code == 422


async def test_read_junk_list(async_client, async_session, junk_data, superuser_token_headers, vault) -> None:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    junk_data_2 = {
        "name": "Test Junk 2",
        "rarity": "Common",
        "value": 10,
        "junk_type": "Adhesive",
        "description": "Very sticky.",
    }
    junk_obj_1 = JunkCreate(**junk_data)
    junk_obj_2 = JunkCreate(**junk_data_2)
    await crud.junk.create(async_session, {**junk_data, "storage_id": storage.id})
    await crud.junk.create(async_session, {**junk_data_2, "storage_id": storage.id})
    response = await async_client.get(f"/junk/?vault_id={vault.id}", headers=superuser_token_headers)
    all_junk = response.json()
    assert response.status_code == 200
    assert len(all_junk) == 2
    response_junk_1, response_junk_2 = all_junk
    if response_junk_1["name"] == junk_obj_2.name:
        response_junk_1, response_junk_2 = response_junk_2, response_junk_1
    for response_junk, expected in ((response_junk_1, junk_obj_1), (response_junk_2, junk_obj_2)):
        assert response_junk["name"] == expected.name
        assert response_junk["rarity"] == expected.rarity
        assert response_junk["value"] == expected.value
        assert response_junk["junk_type"] == expected.junk_type
        assert response_junk["description"] == expected.description


async def test_update_junk(async_client, junk_data, superuser_token_headers) -> None:
    response = await async_client.post("/junk/", json=junk_data, headers=superuser_token_headers)
    junk_item = response.json()
    junk_new_data = {
        "name": random_lower_string(16).capitalize(),
        "rarity": "legendary",
        "value": random.randint(1, 1_000),
        "junk_type": random.choice(list(JunkTypeEnum)),
        "description": random_lower_string(16),
    }
    update_response = await async_client.put(
        f"/junk/{junk_item['id']}", json=junk_new_data, headers=superuser_token_headers
    )
    updated_junk = update_response.json()
    assert update_response.status_code == 200
    assert updated_junk["name"] == junk_new_data["name"]
    assert updated_junk["rarity"] == junk_new_data["rarity"]
    assert updated_junk["value"] == junk_new_data["value"]
    assert updated_junk["junk_type"] == junk_new_data["junk_type"]
    assert updated_junk["description"] == junk_new_data["description"]


async def test_delete_junk(async_client, junk_data, superuser_token_headers) -> None:
    created_junk = (await async_client.post("/junk/", json=junk_data, headers=superuser_token_headers)).json()
    delete_response = await async_client.delete(f"/junk/{created_junk['id']}", headers=superuser_token_headers)
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/junk/{created_junk['id']}", headers=superuser_token_headers)
    assert read_response.status_code == 404


async def test_sell_junk_success(async_client, async_session, superuser_token_headers) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    junk_data = create_fake_junk() | {"storage_id": str(storage.id)}
    junk = await crud.junk.create(async_session, JunkCreate(**junk_data))
    pre_caps = (await crud.vault.get(async_session, id=vault.id)).bottle_caps
    response = await async_client.post(f"/junk/{junk.id}/sell/", headers=superuser_token_headers)
    assert response.status_code == 200
    read_response = await async_client.get(f"/junk/{junk.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404
    vault_after = await crud.vault.get(async_session, id=vault.id)
    assert vault_after.bottle_caps == pre_caps + (junk.value or 0)
