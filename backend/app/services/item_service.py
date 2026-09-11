"""Item service: canonical sell flow for weapons, outfits, and junk."""

import contextlib

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.item_base import get_item_vault_id
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.vault_service import vault_service
from app.utils.exceptions import ResourceNotFoundException

ItemModel = type[Weapon] | type[Outfit] | type[Junk]

_ITEM_CRUD = {Weapon: crud.weapon, Outfit: crud.outfit, Junk: crud.junk}


def _crud_for(model: ItemModel):
    return _ITEM_CRUD[model]


class ItemService:
    """Item lifecycle operations that span items and vault resources."""

    async def sell_item(self, db_session: AsyncSession, *, item_id: UUID4, model: ItemModel) -> None:
        """Sell an item for caps: credit the owning vault, then delete the item in a single commit."""
        item = await _crud_for(model).get_or_none(db_session, item_id)
        if not item:
            raise ResourceNotFoundException(model, identifier=item_id)

        vault_id = await get_item_vault_id(db_session, item)
        if not vault_id:
            raise ResourceNotFoundException(Vault, identifier="Unknown - item has no storage or dweller")

        try:
            credited = await self._credit_caps(db_session, vault_id, item.value)
            await db_session.delete(item)
            await db_session.commit()
        except SQLAlchemyError:
            # Ensure we rollback on any error to avoid partial state in async contexts
            with contextlib.suppress(Exception):
                await db_session.rollback()
            raise

        # Publish only after the sale commits: the objective handler runs on a
        # separate session and must never observe a rolled-back sale.
        from app.core.event_bus import GameEvent, event_bus

        await event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": "caps", "amount": credited})

    async def _credit_caps(self, db_session: AsyncSession, vault_id: UUID4, value: int) -> int:
        """Credit the sale value to the vault via VaultService without committing or emitting.

        Returns the amount actually credited (part of the sell transaction).
        """
        vault = await crud.vault.get_or_none(db_session, vault_id, include_deleted=True)
        if not vault:
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        return await vault_service.deposit_caps(
            db_session=db_session, vault_obj=vault, amount=value, commit=False, emit_event=False
        )


# Singleton instance
item_service = ItemService()
