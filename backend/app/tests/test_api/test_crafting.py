"""Tests for the crafting API — recipes and the workshop order queue."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import JunkTypeEnum, RarityEnum, RoomTypeEnum
from app.core.game_config import game_config
from app.models.junk import Junk
from app.models.room import Room
from app.models.storage import Storage
from app.schemas.vault import VaultCreateWithUserID
from app.services.crafting_service import crafting_service
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")

COMMON_WEAPON = "Pipe pistol"


async def _superuser_vault(async_session: AsyncSession):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    return await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))


async def _seed_crafting(
    async_session: AsyncSession,
    vault_id,
    *,
    workshop: str | None = "Weapon workshop",
    junk_count: int | None = None,
) -> Storage:
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

    count = junk_count if junk_count is not None else game_config.crafting.junk_cost("common")
    for index in range(count):
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


async def _finish_queue(async_session: AsyncSession, vault_id) -> None:
    """Force active orders past completion and run the tick so collect can succeed."""
    for order in await crud.crafting_order.get_active_by_vault(async_session, vault_id):
        order.estimated_completion_at = datetime.utcnow() - timedelta(seconds=1)
        async_session.add(order)
    await async_session.commit()
    await crafting_service.advance_orders(async_session, vault_id)


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
    pipe_pistol = next(recipe for recipe in recipes if recipe["name"] == COMMON_WEAPON)
    assert pipe_pistol["can_craft"] is True
    assert pipe_pistol["junk_cost"] == game_config.crafting.junk_cost("common")
    assert pipe_pistol["caps_cost"] == game_config.crafting.caps_cost("common")


@pytest.mark.asyncio
async def test_start_order_returns_the_queued_order(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id)

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/orders",
        json={"item_name": COMMON_WEAPON, "item_type": "weapon"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["item_name"] == COMMON_WEAPON
    assert body["status"] == "active"
    assert body["junk_spent"] == game_config.crafting.junk_cost("common")
    assert body["progress"] == 0.0


@pytest.mark.asyncio
async def test_list_orders_returns_the_queue(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id)
    await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")

    response = await async_client.get(
        f"/crafting/vault/{vault.id}/orders",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert [order["item_name"] for order in response.json()["orders"]] == [COMMON_WEAPON]


@pytest.mark.asyncio
async def test_collect_order_grants_the_item(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    await _finish_queue(async_session, vault.id)

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/orders/{order.id}/collect",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == COMMON_WEAPON


@pytest.mark.asyncio
async def test_collect_before_completion_returns_400(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/orders/{order.id}/collect",
        headers=superuser_token_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_start_without_workshop_returns_400(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id, workshop=None)

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/orders",
        json={"item_name": COMMON_WEAPON, "item_type": "weapon"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_start_without_materials_returns_400(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    vault = await _superuser_vault(async_session)
    await _seed_crafting(async_session, vault.id, junk_count=0)

    response = await async_client.post(
        f"/crafting/vault/{vault.id}/orders",
        json={"item_name": COMMON_WEAPON, "item_type": "weapon"},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
