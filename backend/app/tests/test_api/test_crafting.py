"""Tests for the crafting API endpoints."""

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import JunkTypeEnum, RarityEnum, RoomTypeEnum
from app.models.junk import Junk
from app.models.room import Room
from app.models.storage import Storage
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


async def _superuser_vault(async_session: AsyncSession):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    return await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))


async def _seed_crafting(async_session: AsyncSession, vault_id, *, workshop: str | None = "Weapon workshop"):
    storage = Storage(vault_id=vault_id, max_space=100)
    async_session.add(storage)
    if workshop:
        async_session.add(
            Room(
                name=workshop,
                category=RoomTypeEnum.CRAFTING,
                ability=None,
                population_required=None,
                base_cost=800,
                incremental_cost=600,
                t2_upgrade_cost=8000,
                t3_upgrade_cost=60000,
                size_min=9,
                size_max=9,
                size=9,
                tier=1,
                coordinate_x=0,
                coordinate_y=0,
                image_url=None,
                vault_id=vault_id,
            )
        )
    await async_session.commit()
    await async_session.refresh(storage)
    for index in range(3):
        async_session.add(
            Junk(
                name=f"Steel api{index}",
                junk_type=JunkTypeEnum.STEEL,
                rarity=RarityEnum.COMMON,
                value=2,
                description="API test material",
                storage_id=storage.id,
            )
        )
    await async_session.commit()
    return storage


@pytest.mark.asyncio
async def test_list_recipes_returns_costs(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id)

    response = await async_client.get(
        f"/crafting/vault/{vault.id}/recipes/weapon",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    recipes = response.json()["recipes"]
    assert recipes
    pipe_pistol = next(recipe for recipe in recipes if recipe["name"] == "Pipe pistol")
    assert pipe_pistol["can_craft"] is True
    assert pipe_pistol["junk_cost"] == 3
    assert pipe_pistol["caps_cost"] == 0


@pytest.mark.asyncio
async def test_craft_item_returns_result(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id)

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/craft",
        json={"item_name": "Pipe pistol", "item_type": "weapon"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Pipe pistol"
    assert body["junk_spent"] == 3
    assert body["item_type"] == "weapon"


@pytest.mark.asyncio
async def test_craft_without_workshop_returns_400(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id, workshop=None)

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/craft",
        json={"item_name": "Pipe pistol", "item_type": "weapon"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_craft_without_materials_returns_400(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id)
    for row in (await async_session.execute(select(Junk))).scalars().all():
        await async_session.delete(row)
    await async_session.commit()

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/craft",
        json={"item_name": "Pipe pistol", "item_type": "weapon"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
