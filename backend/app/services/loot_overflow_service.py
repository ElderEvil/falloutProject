"""Shared policy for loot a full vault had to leave behind.

Exploration and incidents each own an ``unclaimed_loot`` column and their own
template for how a held entry looks. This service owns the rules those owners
share: what fits in storage, what a held entry is worth in caps, how one entry
leaves a held list when the player takes or sells it, and how a held entry
becomes a storage row.
"""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RarityEnum
from app.core.game_config import game_config
from app.crud import storage as crud_storage
from app.crud import vault as crud_vault
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.weapon import Weapon
from app.schemas.outfit import OutfitCreate
from app.schemas.weapon import WeaponCreate
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException
from app.utils.item_factory import build_junk, build_outfit, build_weapon
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)

# Medication returns through its own stock counters, never through storage rows,
# so a held stimpak or radaway is a bug rather than a player decision.
MEDICAL_ITEM_TYPES = frozenset({"stimpak", "radaway"})

# Rarities a held entry may declare; a value outside this set falls back to COMMON,
# matching how the rest of the reward path tolerates a rogue catalog string.
_KNOWN_RARITIES = frozenset(rarity.value for rarity in RarityEnum)


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
        rarity. Gear missing from the catalog is salvaged at its rarity value so
        a catalog-miss overflow entry can still be sold and cleared.
        """
        if loot_item.get("item_type", "junk") not in {"weapon", "outfit"}:
            rarity = str(loot_item.get("rarity", "common"))
            return game_config.exploration.get_junk_value(rarity)
        catalog = self._catalog_row(loot_item)
        if catalog is None:
            return game_config.exploration.get_junk_value(str(loot_item.get("rarity", "common")))
        return catalog.value or 0

    def value_of(self, loot_item: dict) -> int:
        """Caps paid for selling every unit of a held entry."""
        return self.unit_value_of(loot_item) * (loot_item.get("quantity", 1) or 1)

    def build_storage_row(
        self, loot_item: dict, storage_id: UUID4, *, junk_description: str
    ) -> Weapon | Outfit | Junk | None:
        """Materialize one held entry as a storage row, priced as its sale would be.

        Catalog weapons and outfits resolve by name (case-insensitively) from the
        shipped catalogs and are built through ``item_factory`` so every catalog-owned
        column is populated; junk is priced by rarity and described by the owner.
        Returns ``None`` when the catalog has no matching row, so a caller can stop
        that stack instead of persisting a defaulted item.
        """
        name = self.item_name(loot_item)
        item_type = loot_item.get("item_type", "junk")
        rarity = self._rarity_of(loot_item)
        match item_type:
            case "weapon" | "outfit":
                catalog = self._catalog_row(loot_item)
                if catalog is None:
                    return None
                return (
                    build_weapon(catalog.model_dump(), rarity, storage_id)
                    if item_type == "weapon"
                    else build_outfit(catalog.model_dump(), rarity, storage_id)
                )
            case _:
                return build_junk(
                    name,
                    rarity,
                    storage_id,
                    value=self.unit_value_of(loot_item),
                    description=junk_description,
                )

    @staticmethod
    def _catalog_row(loot_item: dict) -> WeaponCreate | OutfitCreate | None:
        """The shipped catalog row a held weapon/outfit names, matched case-insensitively.

        The one lookup behind both pricing and building. A missing row cannot be
        taken, but pricing falls back to the rarity salvage value so it can be sold.
        """
        name = LootOverflowService.item_name(loot_item).lower()
        match loot_item.get("item_type", "junk"):
            case "weapon":
                return next((weapon for weapon in game_data_store.weapons if weapon.name.lower() == name), None)
            case "outfit":
                return next((outfit for outfit in game_data_store.outfits if outfit.name.lower() == name), None)
        return None

    @staticmethod
    def _rarity_of(loot_item: dict) -> RarityEnum:
        raw = str(loot_item.get("rarity", "common")).lower()
        return RarityEnum(raw) if raw in _KNOWN_RARITIES else RarityEnum.COMMON

    @staticmethod
    def _require_stored_row(row: Weapon | Outfit | Junk | None, loot_item: dict) -> Weapon | Outfit | Junk:
        """A missing catalog row is a bad request, not a silently defaulted item."""
        if row is None:
            raise ValidationException(f"Unknown loot item: {LootOverflowService.item_name(loot_item)}")
        return row

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

    async def settle_take_decision(
        self,
        db_session: AsyncSession,
        unclaimed: list[dict],
        index: int,
        *,
        owner: type[SQLModel],
        owner_id: Any,
        vault_id: UUID4,
        junk_description: str,
    ) -> tuple[dict, list[dict]]:
        """Shared take flow: pop, reject medical, require space, build rows, stage.

        The owner loads and persists its own row and supplies the junk prose; row
        construction itself is shared. Returns the taken entry and the remaining
        list so the caller can credit collection after its commit.
        """
        loot_item = self.pop_decision(unclaimed, index, owner=owner, owner_id=owner_id)
        self.reject_medical(loot_item)
        quantity = self.quantity_of(loot_item)
        storage = await self.require_space(db_session, vault_id, quantity)
        rows = [
            self._require_stored_row(
                self.build_storage_row(loot_item, storage.id, junk_description=junk_description), loot_item
            )
            for _ in range(quantity)
        ]
        db_session.add_all(rows)
        await db_session.flush()
        await crud_storage.update_used_space(db_session, storage.id)
        return loot_item, unclaimed

    @staticmethod
    def collect_event_payload(loot_item: dict) -> dict | None:
        """The ITEM_COLLECTED payload a taken entry should emit, or None for junk."""
        if loot_item.get("item_type") not in {"weapon", "outfit"}:
            return None
        return {"item_type": loot_item["item_type"], "amount": LootOverflowService.quantity_of(loot_item)}

    async def settle_sell_decision(
        self,
        db_session: AsyncSession,
        unclaimed: list[dict],
        index: int,
        *,
        owner: type[SQLModel],
        owner_id: Any,
        vault_id: UUID4,
    ) -> tuple[int, list[dict]]:
        """Shared sell flow: pop, reject medical, credit caps without committing.

        The caller persists its owner row and commits, so a later failure rolls
        the credit back with everything else. Returns the caps actually credited
        and remainder; the caller emits the collection event after commit.
        """
        from app.services.vault_service import vault_service

        loot_item = self.pop_decision(unclaimed, index, owner=owner, owner_id=owner_id)
        self.reject_medical(loot_item)
        value = self.value_of(loot_item)
        vault = await crud_vault.get(db_session, vault_id)
        credited = await vault_service.deposit_caps(
            db_session=db_session, vault_obj=vault, amount=value, commit=False, emit_event=False
        )
        return credited, unclaimed


loot_overflow_service = LootOverflowService()
