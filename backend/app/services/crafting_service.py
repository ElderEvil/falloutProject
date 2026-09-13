"""Workshop crafting — recipe listing and the timed order queue.

Recipes are the existing item catalogs filtered by their ``craftable`` flag;
costs derive from rarity. Materials are junk of the crafted item's rarity or
better, spent cheapest-first, so scrapping duplicates feeds crafting. Materials
are consumed when an order starts; the item is collected once the tick marks
the order complete.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import JunkTypeEnum, RarityEnum, RoomTypeEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.models.crafting_order import CraftingOrder, CraftingOrderStatus
from app.models.junk import Junk
from app.models.room import Room
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
    def craft_types(entry: dict[str, Any]) -> list[str]:
        """Junk types this item accepts, from its catalog craft block."""
        craft = entry.get("craft") or {}
        types = craft.get("types") or []
        return [str(junk_type).lower() for junk_type in types]

    @staticmethod
    def _spend_plan(
        junk: list[Junk], rarity: RarityEnum, types: list[str]
    ) -> tuple[list[Junk], dict[str, int]]:
        """Pick the exact materials this rarity needs, plus any per-material shortfall.

        Each tier requires its own rarity, so cheaper scrap cannot substitute for
        a legendary requirement, and only the item's listed junk types count.
        Within a material rarity the cheapest pieces go first.
        """
        recipe = game_config.crafting.junk_recipe(rarity.value)
        allowed = {junk_type.lower() for junk_type in types}
        pools: dict[str, list[Junk]] = {material: [] for material in recipe}
        for item in junk:
            key = RarityEnum(item.rarity).value
            if key in pools and (not allowed or JunkTypeEnum(item.junk_type).value in allowed):
                pools[key].append(item)

        plan: list[Junk] = []
        shortfall: dict[str, int] = {}
        for material, needed in recipe.items():
            pool = sorted(pools[material], key=lambda item: (item.value or 0, item.name))
            plan.extend(pool[:needed])
            if len(pool) < needed:
                shortfall[material] = needed - len(pool)
        return plan, shortfall

    @staticmethod
    def _cost(rarity: RarityEnum) -> tuple[int, int]:
        return game_config.crafting.junk_cost(rarity.value), game_config.crafting.caps_cost(rarity.value)

    async def _find_craftable(self, item_type: str, item_name: str) -> dict[str, Any]:
        catalog = await self._catalog(item_type)
        entry = next((item for item in catalog if str(item.get("name", "")).lower() == item_name.lower()), None)
        if entry is None:
            raise ValidationException(f"Unknown {item_type}: {item_name}")
        if not entry.get("craftable", False):
            raise ValidationException(f"{entry['name']} cannot be crafted")
        return entry

    async def list_recipes(self, db_session: AsyncSession, vault_id: UUID4, item_type: str) -> list[CraftingRecipeRead]:
        """Craftable entries for one item type, with costs and current affordability."""
        if item_type not in CRAFTABLE_ITEM_TYPES:
            raise ValidationException(f"Unknown craftable item type: {item_type}")

        vault = await crud.vault.get(db_session, vault_id)
        storage = await crud.storage.get_storage_by_vault(db_session, vault_id)
        junk: list[Junk] = await crud.junk.get_in_storage(db_session, storage.id) if storage else []

        # The recipe view reports what the crew would achieve, so the panel never
        # has to infer timing or stock from other endpoints.
        room = await self._workshop_room(db_session, vault_id, self.workshop_name(item_type))
        crew = await crud.dweller.get_by_room(db_session, room.id) if room else []

        recipes: list[CraftingRecipeRead] = []
        for entry in await self._catalog(item_type):
            if not entry.get("craftable", False):
                continue
            rarity = RarityEnum(entry["rarity"])
            junk_cost, caps_cost = self._cost(rarity)
            craft_types = self.craft_types(entry)
            _, shortfall = self._spend_plan(junk, rarity, craft_types)
            missing = sum(shortfall.values())
            required_stat = self._required_stat(entry)
            ability_sum = sum(int(getattr(dweller, required_stat, 0) or 0) for dweller in crew)
            available = self._available_by_rarity(junk, craft_types)
            materials = game_config.crafting.junk_recipe(rarity.value)
            recipes.append(
                CraftingRecipeRead(
                    name=str(entry["name"]),
                    item_type=item_type,
                    rarity=rarity,
                    value=entry.get("value"),
                    stat=required_stat,
                    junk_types=craft_types,
                    junk_materials=materials,
                    available_junk={material: available.get(material, 0) for material in materials},
                    ability_sum=ability_sum,
                    duration_seconds=self.order_duration_seconds(rarity, ability_sum),
                    junk_cost=junk_cost,
                    caps_cost=caps_cost,
                    can_craft=missing == 0 and vault.bottle_caps >= caps_cost,
                    missing_junk=missing,
                )
            )

        return sorted(recipes, key=lambda recipe: (_RARITY_ORDER[recipe.rarity], recipe.name))

    @staticmethod
    def _available_by_rarity(junk: list[Junk], types: list[str]) -> dict[str, int]:
        """How much usable junk the vault holds, per material rarity."""
        allowed = {junk_type.lower() for junk_type in types}
        counts: dict[str, int] = {}
        for item in junk:
            if allowed and JunkTypeEnum(item.junk_type).value not in allowed:
                continue
            key = RarityEnum(item.rarity).value
            counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _required_stat(entry: dict[str, Any]) -> str:
        """The dweller SPECIAL that speeds this item's craft, from the catalog."""
        return str(entry.get("stat") or "strength").lower()

    @staticmethod
    def order_duration_seconds(rarity: RarityEnum, ability_sum: int) -> int:
        """Base duration for the rarity, shortened by the crew's total in the item's stat.

        Mirrors room production: the item names the stat (pistols want agility),
        and the dwellers working that workshop supply the points.
        """
        base = game_config.crafting.order_seconds(rarity.value)
        speedup = max(0, ability_sum) * game_config.crafting.craft_speed_per_stat
        floor = int(base * game_config.crafting.min_order_fraction)
        return max(floor, int(base / (1 + speedup)))

    @staticmethod
    async def _workshop_room(db_session: AsyncSession, vault_id: UUID4, workshop: str) -> Room | None:
        rooms = await crud.room.get_by_name_pattern(db_session, vault_id, f"%{workshop}%")
        return rooms[0] if rooms else None

    async def start_order(
        self, db_session: AsyncSession, vault_id: UUID4, item_name: str, item_type: str
    ) -> CraftingOrder:
        """Queue a craft and consume its materials up front.

        Materials are taken at start, not collection, so the queue cannot be
        filled with orders the vault cannot pay for.

        Raises:
            ValidationException: Unknown item type, unknown/uncraftable item, or missing workshop.
            ResourceNotFoundException: Vault has no storage row.
            InsufficientResourcesException: Not enough eligible junk or caps.
        """
        if item_type not in CRAFTABLE_ITEM_TYPES:
            raise ValidationException(f"Unknown craftable item type: {item_type}")

        vault = await crud.vault.lock_for_update(db_session, vault_id)
        storage = await crud.storage.get_storage_by_vault(db_session, vault_id)
        if storage is None:
            raise ResourceNotFoundException(Storage, vault_id, identifier_type="vault_id")

        workshop = self.workshop_name(item_type)
        room = await self._workshop_room(db_session, vault_id, workshop)
        if room is None:
            raise ValidationException(f"Build the {workshop} to craft {item_type}s")

        entry = await self._find_craftable(item_type, item_name)
        rarity = RarityEnum(entry["rarity"])
        junk_cost, caps_cost = self._cost(rarity)

        spent, shortfall = self._spend_plan(
            await crud.junk.get_in_storage(db_session, storage.id), rarity, self.craft_types(entry)
        )
        if shortfall:
            missing = ", ".join(f"{count} {material}" for material, count in sorted(shortfall.items()))
            raise InsufficientResourcesException(
                resource_name=f"crafting materials ({missing})", resource_amount=sum(shortfall.values())
            )

        if caps_cost:
            await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=caps_cost, commit=False)
        for junk_item in spent:
            await db_session.delete(junk_item)

        workers = await crud.dweller.get_by_room(db_session, room.id)
        required_stat = self._required_stat(entry)
        ability_sum = sum(int(getattr(dweller, required_stat, 0) or 0) for dweller in workers)
        now = datetime.utcnow()
        order = CraftingOrder(
            vault_id=vault_id,
            room_id=room.id,
            item_name=str(entry["name"]),
            item_type=item_type,
            rarity=rarity,
            started_at=now,
            estimated_completion_at=now + timedelta(seconds=self.order_duration_seconds(rarity, ability_sum)),
            required_stat=required_stat,
            ability_sum_at_start=ability_sum,
            item_snapshot=dict(entry),
            junk_spent=len(spent),
            caps_spent=caps_cost,
        )
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(order)
        logger.info(
            f"Queued {item_type} '{order.item_name}' ({rarity.value}) for vault {vault_id} "
            f"with {required_stat} {ability_sum} in {self.order_duration_seconds(rarity, ability_sum)}s"
        )
        return order

    async def list_orders(self, db_session: AsyncSession, vault_id: UUID4) -> list[CraftingOrder]:
        """Every order for a vault, newest first."""
        return await crud.crafting_order.get_by_vault(db_session, vault_id)

    async def advance_orders(self, db_session: AsyncSession, vault_id: UUID4) -> int:
        """Advance the queue one tick; returns how many orders just completed."""
        orders = await crud.crafting_order.get_active_by_vault(db_session, vault_id)
        if not orders:
            return 0

        now = datetime.utcnow()
        completed = 0
        for order in orders:
            total = (order.estimated_completion_at - order.started_at).total_seconds()
            elapsed = (now - order.started_at).total_seconds()
            order.progress = min(1.0, max(0.0, elapsed / total)) if total > 0 else 1.0
            if order.estimated_completion_at <= now:
                order.status = CraftingOrderStatus.COMPLETED
                order.completed_at = now
                order.progress = 1.0
                completed += 1
            db_session.add(order)

        await db_session.flush()
        return completed

    async def collect_order(self, db_session: AsyncSession, vault_id: UUID4, order_id: UUID4) -> CraftResultRead:
        """Move a finished order's item into storage.

        Raises:
            ResourceNotFoundException: Unknown order, or vault has no storage row.
            ValidationException: The order is still in the queue.
            ResourceConflictException: Storage cannot hold the crafted item.
        """
        order = await crud.crafting_order.get_for_vault_for_update(db_session, order_id, vault_id)
        if order is None:
            raise ResourceNotFoundException(CraftingOrder, order_id)
        if not order.is_completed():
            raise ValidationException("Order is not ready to collect")

        # Lock the vault so a concurrent collect cannot claim the same free slot.
        await crud.vault.lock_for_update(db_session, vault_id)
        storage = await crud.storage.get_storage_by_vault(db_session, vault_id)
        if storage is None:
            raise ResourceNotFoundException(Storage, vault_id, identifier_type="vault_id")
        info = await crud.storage.get_storage_info(db_session, storage.id)
        if info["max_space"] - info["used_space"] < 1:
            raise ResourceConflictException("Storage is full")

        # Build from the snapshot the order was paid for, not the live catalog.
        snapshot = order.item_snapshot or {}
        crafted = (
            build_weapon(snapshot, order.rarity, storage.id)
            if order.item_type == "weapon"
            else build_outfit(snapshot, order.rarity, storage.id)
        )
        db_session.add(crafted)
        order.status = CraftingOrderStatus.COLLECTED
        db_session.add(order)
        await db_session.commit()
        await db_session.refresh(crafted)

        await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": order.item_type, "amount": 1})
        logger.info(f"Collected {order.item_type} '{crafted.name}' ({order.rarity.value}) for vault {vault_id}")

        return CraftResultRead(
            item_type=order.item_type,
            item_id=crafted.id,
            name=crafted.name,
            rarity=order.rarity,
            junk_spent=order.junk_spent,
            caps_spent=order.caps_spent,
        )


crafting_service = CraftingService()
