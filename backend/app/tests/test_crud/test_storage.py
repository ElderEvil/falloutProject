from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ItemTypeEnum, RarityEnum
from app.models.item import Item


async def test_count_items_excludes_nuka_consumables(async_session: AsyncSession, vault) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    sid = storage.id
    base = {"item_type": ItemTypeEnum.CONSUMABLE, "rarity": RarityEnum.COMMON, "storage_id": sid}
    async_session.add_all([Item(name=name, **base) for name in ("Nuka-Cola Quantum", "nuka-cola", "Stimpak")])
    async_session.add(Item(name="Lunchbox", item_type=ItemTypeEnum.LUNCHBOX, rarity=RarityEnum.COMMON, storage_id=sid))
    await async_session.flush()
    assert await crud.storage.count_storage_items(async_session, sid) == 2
