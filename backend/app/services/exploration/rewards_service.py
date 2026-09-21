"""Rewards application for completed explorations."""

import asyncio
import logging
from typing import Any, TypedDict

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RarityEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud import exploration as crud_exploration
from app.crud import outfit as crud_outfit
from app.crud import room as room_crud
from app.crud import storage as crud_storage
from app.crud import vault as crud_vault
from app.crud import weapon as crud_weapon
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.exploration import PendingOverflowRead
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration import data_loader
from app.services.exploration.rewards_calculator import rewards_calculator
from app.services.loot_overflow_service import loot_overflow_service
from app.services.notification_service import notification_service
from app.services.resource_manager import compute_medical_capacity
from app.services.vault_service import vault_service
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.item_factory import build_junk, build_outfit, build_weapon

logger = logging.getLogger(__name__)


class TransferResult(TypedDict):
    """Result of transferring loot to vault storage."""

    transferred: list[dict]
    overflow: list[dict]
    auto_equip_ids: list[dict]
    storage_id: UUID4 | None


class RewardsService:
    """Applies exploration rewards to vault and dweller."""

    @staticmethod
    def _parse_rarity_to_enum(rarity_str: str) -> RarityEnum:
        """Convert rarity string to RarityEnum with fallback to COMMON.

        :param rarity_str: Rarity string (e.g., "Legendary", "COMMON")
        :returns: RarityEnum value, defaults to COMMON if invalid
        """
        try:
            return RarityEnum[rarity_str.upper()]
        except (KeyError, AttributeError):
            return RarityEnum.COMMON

    def _build_item_from_loot(
        self,
        loot_item: dict,
        rarity: RarityEnum,
        storage_id: UUID4,
        weapons_data: list[dict],
        outfits_data: list[dict],
    ) -> Weapon | Outfit | Junk | None:
        """Build a storage item from a loot dict. Shared by transfer and overflow-take."""
        item_name = loot_item.get("item_name", "Unknown Item")
        try:
            match loot_item.get("item_type", "junk"):
                case "weapon":
                    weapon_data = next((w for w in weapons_data if w["name"] == item_name), None)
                    if weapon_data is None:
                        return None
                    return build_weapon(weapon_data, rarity, storage_id)
                case "outfit":
                    outfit_data = next((o for o in outfits_data if o["name"] == item_name), None)
                    if outfit_data is None:
                        return None
                    return build_outfit(outfit_data, rarity, storage_id)
                case _:
                    return build_junk(
                        item_name,
                        rarity,
                        storage_id,
                        value=game_config.exploration.get_junk_value(rarity.value),
                        description="Found during wasteland exploration",
                    )
        except (KeyError, ValueError):
            logger.exception(
                "Failed to build item from loot",
                extra={
                    "loot_item": loot_item,
                    "rarity": rarity.value if rarity else None,
                    "storage_id": str(storage_id),
                },
            )
            return None

    async def _transfer_loot_to_storage(self, db_session: AsyncSession, exploration: Exploration) -> TransferResult:
        """Transfer loot items from exploration to vault storage with space validation.

        Items are sorted by rarity (legendary > rare > uncommon > common) and
        transferred in priority order. If storage is full, remaining items are
        tracked as overflow.

        :param db_session: Database session
        :param exploration: Completed exploration
        :returns: TransferResult with transferred/overflow item lists and storage_id
        """
        if not exploration.loot_collected:
            exploration.unclaimed_loot = []
            return {"transferred": [], "overflow": [], "auto_equip_ids": [], "storage_id": None}

        vault = await crud_vault.get(db_session, exploration.vault_id)
        storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
        if not storage:
            logger.error("Storage not found for vault", extra={"vault_id": str(vault.id)})
            exploration.unclaimed_loot = exploration.loot_collected
            return {
                "transferred": [],
                "overflow": exploration.loot_collected,
                "auto_equip_ids": [],
                "storage_id": None,
            }
        storage_id = storage.id

        # Check available space
        available_space = await crud_storage.get_available_space(db_session, storage_id)

        logger.info(
            "Storage transfer starting",
            extra={
                "vault_id": str(vault.id),
                "exploration_id": str(exploration.id),
                "available_space": available_space,
                "items_to_transfer": len(exploration.loot_collected),
            },
        )

        granted, overflow = loot_overflow_service.grant_or_hold(exploration.loot_collected, available_space)

        transferred: list[dict] = []
        auto_equip_ids: list[dict] = []

        # Load item data for lookups
        weapons_data = await asyncio.to_thread(data_loader.load_weapons)
        outfits_data = await asyncio.to_thread(data_loader.load_outfits)

        for loot_item in granted:
            item_name = loot_item.get("item_name", "Unknown Item")
            item_type = loot_item.get("item_type", "junk")
            rarity_str = loot_item.get("rarity", "Common")
            rarity = self._parse_rarity_to_enum(rarity_str)
            stored_quantity = 0

            for _ in range(loot_item["quantity"]):
                item = self._build_item_from_loot(loot_item, rarity, storage_id, weapons_data, outfits_data)
                if item is None:
                    break

                db_session.add(item)

                if item_type in {"weapon", "outfit"}:
                    await event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": item_type, "amount": 1})
                    if loot_item.get("auto_equip"):
                        await db_session.flush()
                        auto_equip_ids.append({"item_type": item_type, "id": item.id})

                stored_quantity += 1

            if stored_quantity:
                transferred.append({**loot_item, "quantity": stored_quantity})
                logger.info(
                    "Item transferred to storage",
                    extra={
                        "vault_id": str(vault.id),
                        "item_name": item_name,
                        "item_type": item_type,
                        "rarity": rarity_str,
                    },
                )

        await db_session.flush()

        # Update storage used_space counter
        await crud_storage.update_used_space(db_session, storage_id)

        # Log summary
        if overflow:
            logger.warning(
                "Storage overflow occurred during transfer",
                extra={
                    "vault_id": str(vault.id),
                    "exploration_id": str(exploration.id),
                    "transferred_count": len(transferred),
                    "overflow_count": len(overflow),
                    "overflow_items": [i.get("item_name") for i in overflow],
                },
            )
        else:
            logger.info(
                "Storage transfer completed successfully",
                extra={
                    "vault_id": str(vault.id),
                    "exploration_id": str(exploration.id),
                    "transferred_count": len(transferred),
                },
            )

        exploration.unclaimed_loot = overflow

        return {
            "transferred": transferred,
            "overflow": overflow,
            "auto_equip_ids": auto_equip_ids,
            "storage_id": storage_id,
        }

    async def _load_unclaimed(self, db_session: AsyncSession, exploration_id: UUID4) -> tuple[Exploration, list[dict]]:
        exploration = await crud_exploration.get_for_update(db_session, exploration_id)
        if not exploration:
            raise ResourceNotFoundException(Exploration, exploration_id)
        if exploration.is_in_progress():
            raise ValidationException("Exploration is still in progress")
        return exploration, list(exploration.unclaimed_loot or [])

    async def get_pending_overflow(self, db_session: AsyncSession, vault_id: UUID4) -> list[PendingOverflowRead]:
        """Return every completed exploration with loot still awaiting a player decision."""
        explorations = await crud_exploration.get_by_vault(db_session, vault_id=vault_id)
        return [
            PendingOverflowRead(
                exploration_id=exploration.id,
                dweller_id=exploration.dweller_id,
                unclaimed_loot=exploration.unclaimed_loot,
            )
            for exploration in explorations
            if not exploration.is_in_progress() and exploration.unclaimed_loot
        ]

    async def take_unclaimed_item(self, db_session: AsyncSession, exploration_id: UUID4, index: int) -> list[dict]:
        """Store one overflow item. 409 when storage is still full."""
        exploration, unclaimed = await self._load_unclaimed(db_session, exploration_id)
        weapons_data = await asyncio.to_thread(data_loader.load_weapons)
        outfits_data = await asyncio.to_thread(data_loader.load_outfits)

        def build_row(loot_item: dict, storage_id: UUID4) -> Any:
            rarity = self._parse_rarity_to_enum(loot_item.get("rarity", "common"))
            return self._build_item_from_loot(loot_item, rarity, storage_id, weapons_data, outfits_data)

        unclaimed = await loot_overflow_service.settle_take_decision(
            db_session,
            unclaimed,
            index,
            owner=Exploration,
            owner_id=exploration.id,
            vault_id=exploration.vault_id,
            build_row=build_row,
        )
        exploration.unclaimed_loot = unclaimed
        db_session.add(exploration)
        await db_session.commit()
        return unclaimed

    async def sell_unclaimed_item(
        self, db_session: AsyncSession, exploration_id: UUID4, index: int
    ) -> tuple[int, list[dict]]:
        """Sell one overflow item for caps. Needs no storage space."""
        exploration, unclaimed = await self._load_unclaimed(db_session, exploration_id)
        value, unclaimed = await loot_overflow_service.settle_sell_decision(
            db_session,
            unclaimed,
            index,
            owner=Exploration,
            owner_id=exploration.id,
            vault_id=exploration.vault_id,
        )
        exploration.unclaimed_loot = unclaimed
        db_session.add(exploration)
        await db_session.commit()
        return value, unclaimed

    async def apply_rewards(
        self, db_session: AsyncSession, exploration: Exploration, progress_multiplier: float = 1.0
    ) -> RewardsSchema:
        """Apply rewards to vault and dweller."""
        from app.services.leveling_service import leveling_service

        # Get dweller
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        # Transfer caps to vault
        total_caps = exploration.total_caps_found
        if total_caps > 0:
            vault = await crud_vault.get(db_session, exploration.vault_id)
            await vault_service.deposit_caps(db_session=db_session, vault_obj=vault, amount=total_caps)

        # Calculate and apply experience
        full_experience = rewards_calculator.calculate_exploration_xp(exploration, dweller_obj)
        experience = int(full_experience * progress_multiplier)

        dweller_obj.experience = max(0, dweller_obj.experience + experience)
        db_session.add(dweller_obj)

        # Check for level-up
        leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller_obj)
        if leveled_up:
            await leveling_service.settle_level_up(
                db_session,
                dweller_obj,
                old_level=dweller_obj.level - levels_gained,
                levels_gained=levels_gained,
            )

        # Transfer loot items to vault storage (with space validation)
        transfer_result = await self._transfer_loot_to_storage(db_session, exploration)

        auto_equip_ids = transfer_result.get("auto_equip_ids", [])
        equipped: list[tuple[str, str]] = []
        for entry in auto_equip_ids:
            try:
                crud = crud_weapon if entry["item_type"] == "weapon" else crud_outfit
                item = await crud.equip(db_session=db_session, item_id=entry["id"], dweller_id=exploration.dweller_id)
                equipped.append((entry["item_type"], item.name))
            except Exception:
                logger.exception(
                    "Auto-equip failed during exploration completion: exploration=%s item=%s",
                    exploration.id,
                    entry["id"],
                )
        if transfer_result["storage_id"] is not None:
            await crud_storage.update_used_space(db_session, transfer_result["storage_id"])
        if equipped:
            await self._notify_auto_equip(db_session, exploration, dweller_obj, equipped)

        # Return unused stimpaks and radaways to vault storage
        if exploration.stimpaks > 0 or exploration.radaways > 0:
            storage_obj = await crud_storage.get_storage_by_vault(db_session, exploration.vault_id)
            if storage_obj:
                rooms = await room_crud.get_multy_by_vault(
                    db_session=db_session, vault_id=exploration.vault_id, skip=0, limit=1000
                )
                capacity = compute_medical_capacity(rooms)
                storage_obj.stimpack = min(
                    (storage_obj.stimpack or 0) + exploration.stimpaks,
                    capacity.get("stimpack", 99999),
                )
                storage_obj.radaway = min(
                    (storage_obj.radaway or 0) + exploration.radaways,
                    capacity.get("radaway", 99999),
                )
                db_session.add(storage_obj)

        await db_session.commit()

        # Emit stimpak and radaway collection events after commit
        if exploration.stimpaks > 0:
            await event_bus.emit(
                GameEvent.ITEM_COLLECTED,
                exploration.vault_id,
                {"item_type": "stimpak", "amount": exploration.stimpaks},
            )

        if exploration.radaways > 0:
            await event_bus.emit(
                GameEvent.ITEM_COLLECTED,
                exploration.vault_id,
                {"item_type": "radaway", "amount": exploration.radaways},
            )

        return RewardsSchema(
            exploration_id=exploration.id,
            caps=total_caps,
            items=transfer_result["transferred"],
            overflow_items=transfer_result["overflow"],
            experience=experience,
            distance=exploration.total_distance,
            enemies_defeated=exploration.enemies_encountered,
            events_encountered=len(exploration.events),
            stimpaks=exploration.stimpaks,
            radaways=exploration.radaways,
        )

    @staticmethod
    async def _notify_auto_equip(
        db_session: AsyncSession,
        exploration: Exploration,
        dweller_obj: Dweller,
        equipped: list[tuple[str, str]],
    ) -> None:
        """Best-effort: tell the vault owner which items were auto-equipped on return."""
        try:
            vault = await crud_vault.get(db_session, exploration.vault_id)
            if not vault or not vault.user_id:
                return
            dweller_name = f"{dweller_obj.first_name} {dweller_obj.last_name or ''}".strip()
            for item_type, item_name in equipped:
                await notification_service.notify_exploration_update(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=vault.id,
                    dweller_id=exploration.dweller_id,
                    dweller_name=dweller_name,
                    event_description=f"equipped a better {item_type} found in the wasteland: {item_name}",
                    meta_data={
                        "dweller_id": str(exploration.dweller_id),
                        "item_name": item_name,
                        "item_type": item_type,
                    },
                )
        except Exception:
            logger.exception("Failed to send auto-equip notification: exploration=%s", exploration.id)


# Singleton instance
rewards_service = RewardsService()
