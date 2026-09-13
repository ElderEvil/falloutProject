"""Instant crafting at the weapon and outfit workshops.

Recipes are the existing item catalogs filtered by their ``craftable`` flag;
costs derive from rarity. Materials are junk of the crafted item's rarity or
better, spent cheapest-first, so scrapping duplicates feeds crafting.
"""

import asyncio
import logging
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RarityEnum, RoomTypeEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.models.junk import Junk
from app.models.storage import Storage
from app.schemas.crafting import CraftingRecipeRead, CraftResultRead
from app.services.exploration import data_loader
from app.services.vault_service import vault_service
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.utils.item_factory import build_outfit, build_weapon
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)

CRAFTABLE_ITEM_TYPES = ("weapon", "outfit")

_RARITY_ORDER: dict[RarityEnum, int] = {
    RarityEnum.COMMON: 0,
    RarityEnum.RARE: 1,
    RarityEnum.LEGENDARY: 2,
}


class CraftingService:
    """Crafts catalog weapons and outfits from stored junk at a matching workshop."""

    @staticmethod
    def workshop_name(item_type: str) -> str:
        """Catalog room name that crafts this item type (e.g. ``Weapon workshop``)."""
        for room in game_data_store.rooms:
            if room.category == RoomTypeEnum.CRAFTING and item_type in room.name.lower():
                return room.name
        raise ValidationException(f"No workshop room is configured for {item_type}s")

    @staticmethod
    async def _catalog(item_type: str) -> list[dict[str, Any]]:
        loader = data_loader.load_weapons if item_type == "weapon" else data_loader.load_outfits
        return await asyncio.to_thread(loader)

    @staticmethod
    def _eligible_junk(junk: list[Junk], rarity: RarityEnum) -> list[Junk]:
        """Junk that may pay for this rarity, cheapest and least rare first."""
        threshold = _RARITY_ORDER[rarity]
        eligible = [item for item in junk if _RARITY_ORDER[RarityEnum(item.rarity)] >= threshold]
        return sorted(eligible, key=lambda item: (_RARITY_ORDER[RarityEnum(item.rarity)], item.value or 0, item.name))

    @staticmethod
    def _cost(rarity: RarityEnum) -> tuple[int, int]:
        return game_config.crafting.junk_cost(rarity.value), game_config.crafting.caps_cost(rarity.value)

    async def _find_craftable(self, item_type: str, item_name: str) -> dict[str, Any]:
        catalog = await self._catalog(item_type)
        entry = next((item for item in catalog if str(item.get("name", "")).lower() == item_name.lower()), None)
        if entry is None:
            raise ValidationException(f"Unknown {item_type}: {item_name}")
        if not entry.get("craftable", True):
            raise ValidationException(f"{entry['name']} cannot be crafted")
        return entry

    async def list_recipes(self, db_session: AsyncSession, vault_id: UUID4, item_type: str) -> list[CraftingRecipeRead]:
        """Craftable entries for one item type, with costs and current affordability."""
        if item_type not in CRAFTABLE_ITEM_TYPES:
            raise ValidationException(f"Unknown craftable item type: {item_type}")

        vault = await crud.vault.get(db_session, vault_id)
        storage = await crud.storage.get_storage_by_vault(db_session, vault_id)
        junk: list[Junk] = await crud.junk.get_in_storage(db_session, storage.id) if storage else []
        has_space = bool(storage) and await crud.storage.get_available_space(db_session, storage.id) >= 1

        recipes: list[CraftingRecipeRead] = []
        for entry in await self._catalog(item_type):
            if not entry.get("craftable", True):
                continue
            rarity = RarityEnum(entry["rarity"])
            junk_cost, caps_cost = self._cost(rarity)
            shortfall = max(0, junk_cost - len(self._eligible_junk(junk, rarity)))
            recipes.append(
                CraftingRecipeRead(
                    name=str(entry["name"]),
                    item_type=item_type,
                    rarity=rarity,
                    value=entry.get("value"),
                    junk_cost=junk_cost,
                    caps_cost=caps_cost,
                    can_craft=shortfall == 0 and vault.bottle_caps >= caps_cost and has_space,
                    missing_junk=shortfall,
                )
            )

        return sorted(recipes, key=lambda recipe: (_RARITY_ORDER[recipe.rarity], recipe.name))

    async def craft(self, db_session: AsyncSession, vault_id: UUID4, item_name: str, item_type: str) -> CraftResultRead:
        """Consume junk and caps, then place the crafted item in storage.

        Raises:
            ValidationException: Unknown item type, unknown/uncraftable item, or missing workshop.
            ResourceNotFoundException: Vault has no storage row.
            InsufficientResourcesException: Not enough eligible junk.
            ResourceConflictException: Storage cannot hold the crafted item.
        """
        if item_type not in CRAFTABLE_ITEM_TYPES:
            raise ValidationException(f"Unknown craftable item type: {item_type}")

        vault = await crud.vault.get(db_session, vault_id)
        storage = await crud.storage.get_storage_by_vault(db_session, vault_id)
        if storage is None:
            raise ResourceNotFoundException(Storage, vault_id, identifier_type="vault_id")

        workshop = self.workshop_name(item_type)
        room_names = await crud.room.get_existing_room_names(db_session=db_session, vault_id=vault_id)
        if workshop.lower() not in room_names:
            raise ValidationException(f"Build the {workshop} to craft {item_type}s")

        entry = await self._find_craftable(item_type, item_name)
        rarity = RarityEnum(entry["rarity"])
        junk_cost, caps_cost = self._cost(rarity)

        eligible = self._eligible_junk(await crud.junk.get_in_storage(db_session, storage.id), rarity)
        if len(eligible) < junk_cost:
            raise InsufficientResourcesException(
                resource_name=f"{rarity.value} junk", resource_amount=junk_cost - len(eligible)
            )

        if await crud.storage.get_available_space(db_session, storage.id) < 1:
            raise ResourceConflictException("Storage is full")

        spent = eligible[:junk_cost]
        if caps_cost:
            await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=caps_cost, commit=False)
        for junk_item in spent:
            await db_session.delete(junk_item)

        crafted = (
            build_weapon(entry, rarity, storage.id)
            if item_type == "weapon"
            else build_outfit(entry, rarity, storage.id)
        )
        db_session.add(crafted)
        await db_session.commit()
        await db_session.refresh(crafted)

        await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": item_type, "amount": 1})
        logger.info(f"Crafted {item_type} '{crafted.name}' ({rarity.value}) for vault {vault_id}")

        return CraftResultRead(
            item_type=item_type,
            item_id=crafted.id,
            name=crafted.name,
            rarity=rarity,
            junk_spent=len(spent),
            caps_spent=caps_cost,
        )


crafting_service = CraftingService()
