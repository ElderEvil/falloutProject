"""Item service: canonical sell flow for weapons, outfits, and junk."""

import contextlib

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.item_base import get_item_vault_id
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.vault_service import vault_service
from app.utils.exceptions import ResourceNotFoundException

ItemModel = type[Weapon] | type[Outfit] | type[Junk]


class ItemService:
    """Item lifecycle operations that span items and vault resources."""

    async def sell_item(self, db_session: AsyncSession, *, item_id: UUID4, model: ItemModel) -> None:
        """Sell an item for caps: credit the owning vault, then delete the item in a single commit."""
        item = await db_session.get(model, item_id)
        if not item:
            raise ResourceNotFoundException(model, identifier=item_id)

        vault_id = await get_item_vault_id(db_session, item)
        if not vault_id:
            raise ResourceNotFoundException(Vault, identifier="Unknown - item has no storage or dweller")

        try:
            await self._credit_caps(db_session, vault_id, item.value)
            await db_session.delete(item)
            await db_session.commit()
        except SQLAlchemyError:
            # Ensure we rollback on any error to avoid partial state in async contexts
            with contextlib.suppress(Exception):
                await db_session.rollback()
            raise

    async def _credit_caps(self, db_session: AsyncSession, vault_id: UUID4, value: int) -> None:
        """Credit the sale value to the vault via VaultService without committing (part of the sell transaction)."""
        vault = await db_session.get(Vault, vault_id)
        if not vault:
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        await vault_service.deposit_caps(db_session=db_session, vault_obj=vault, amount=value, commit=False)


# Singleton instance
item_service = ItemService()
