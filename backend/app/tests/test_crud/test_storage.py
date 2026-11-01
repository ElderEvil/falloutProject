"""Tests for storage counting semantics."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ItemTypeEnum, RarityEnum
from app.models.item import Item


@pytest.mark.asyncio
async def test_count_items_excludes_nuka_consumables(async_session: AsyncSession, vault) -> None:
    """Nuka-cola consumables are space-free; every other item still counts."""
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)

    for name in ("Nuka-Cola Quantum", "nuka-cola", "Stimpak"):
        async_session.add(
            Item(
                name=name,
                item_type=ItemTypeEnum.CONSUMABLE,
                rarity=RarityEnum.COMMON,
                storage_id=storage.id,
            )
        )
    async_session.add(
        Item(name="Lunchbox", item_type=ItemTypeEnum.LUNCHBOX, rarity=RarityEnum.COMMON, storage_id=storage.id)
    )
    await async_session.flush()

    assert await crud.storage.count_storage_items(async_session, storage.id) == 2
