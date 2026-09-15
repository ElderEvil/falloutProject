"""Shared policy for loot a full vault had to leave behind.

Exploration and incidents each own an ``unclaimed_loot`` column, their own item
factory, and their own template for how a held entry looks. This service owns
the rules those owners share: what fits in storage, what a held entry is worth
in caps, and how one entry leaves a held list when the player takes or sells it.
"""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import storage as crud_storage
from app.models.storage import Storage
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)

# Medication returns through its own stock counters, never through storage rows,
# so a held stimpak or radaway is a bug rather than a player decision.
MEDICAL_ITEM_TYPES = frozenset({"stimpak", "radaway"})


class LootOverflowService:
    """Rules shared by every owner that can hold loot back."""

    @staticmethod
    def item_name(loot_item: dict) -> str:
        """Catalog name of a held entry; exploration writes ``item_name``, incidents ``name``."""
        return str(loot_item.get("item_name", loot_item.get("name", "Unknown Item")))

    @staticmethod
    def quantity_of(loot_item: dict) -> int:
        """Validated unit count for one decision; malformed quantities are rejected."""
        quantity = loot_item.get("quantity", 1) or 1
        if not isinstance(quantity, int) or quantity < 1:
            raise ValidationException("Loot quantity must be a positive integer")
        return quantity

    @staticmethod
    def reject_medical(loot_item: dict) -> None:
        """Held medication cannot be resolved by hand."""
        if loot_item.get("item_type") in MEDICAL_ITEM_TYPES:
            raise ValidationException("Medical supplies are returned automatically")

    def unit_value_of(self, loot_item: dict) -> int:
        """Caps paid for one unit of a held entry, priced from the shipped catalogs.

        Weapons and outfits carry their own catalog price; junk is priced by
        rarity. Unknown names raise rather than silently paying zero.
        """
        name = self.item_name(loot_item)
        match loot_item.get("item_type", "junk"):
            case "weapon":
                data = next((weapon for weapon in game_data_store.weapons if weapon.name == name), None)
                if data is None:
                    raise ValidationException(f"Unknown weapon loot: {name}")
                return data.value or 0
            case "outfit":
                data = next((outfit for outfit in game_data_store.outfits if outfit.name == name), None)
                if data is None:
                    raise ValidationException(f"Unknown outfit loot: {name}")
                return data.value or 0
            case _:
                rarity = str(loot_item.get("rarity", "common"))
                return game_config.exploration.get_junk_value(rarity)

    def value_of(self, loot_item: dict) -> int:
        """Caps paid for selling every unit of a held entry."""
        return self.unit_value_of(loot_item) * (loot_item.get("quantity", 1) or 1)

    def grant_or_hold(self, items: list[dict], available_space: int) -> tuple[list[dict], list[dict]]:
        """Greedy rarity-first split into what storage takes and what is held.

        Every stored unit occupies one slot, so an entry whose quantity crosses
        the remaining space is split across both lists. Pure policy: no session,
        no I/O.
        """
        granted: list[dict] = []
        held: list[dict] = []
        space = max(0, available_space)
        for loot_item in sorted(items, key=self._priority, reverse=True):
            if loot_item.get("item_type") in MEDICAL_ITEM_TYPES:
                continue
            quantity = loot_item.get("quantity", 1) or 1
            if not isinstance(quantity, int) or quantity < 1:
                continue
            stored = min(quantity, space)
            space -= stored
            if stored:
                granted.append({**loot_item, "quantity": stored})
            if stored < quantity:
                held.append({**loot_item, "quantity": quantity - stored})
        return granted, held

    @staticmethod
    def _priority(loot_item: dict) -> int:
        return game_config.exploration.get_rarity_priority(str(loot_item.get("rarity", "common")))

    @staticmethod
    def pop_decision(unclaimed: list[dict], index: int, *, owner: type[SQLModel], owner_id: Any) -> dict:
        """Remove one entry for a take/sell decision; a bad index is a 404."""
        if index < 0 or index >= len(unclaimed):
            raise ResourceNotFoundException(owner, f"{owner_id} unclaimed item {index}")
        return unclaimed.pop(index)

    @staticmethod
    async def storage_for(db_session: AsyncSession, vault_id: UUID4) -> Storage | None:
        """The vault's storage row, when it has one."""
        return await crud_storage.get_storage_by_vault(db_session, vault_id)

    @staticmethod
    async def require_space(db_session: AsyncSession, vault_id: UUID4, quantity: int) -> Storage:
        """The vault's storage row when it has ``quantity`` free slots, else 409.

        The row is locked until the caller commits, so two claims cannot both
        see the same free slot and overshoot ``max_space``.
        """
        storage = await crud_storage.get_storage_by_vault_for_update(db_session, vault_id)
        if not storage or await crud_storage.get_available_space(db_session, storage.id) < quantity:
            raise ResourceConflictException("Storage is full")
        return storage


loot_overflow_service = LootOverflowService()
