"""Rewards application for completed explorations."""

import asyncio
import logging
from typing import TypedDict

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import compute_medical_capacity, game_config
from app.crud import dweller as dweller_crud
from app.crud import outfit as crud_outfit
from app.crud import storage as crud_storage
from app.crud import vault as crud_vault
from app.crud import weapon as crud_weapon
from app.models import Room
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.common import GenderEnum, JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.schemas.exploration_event import RewardsSchema
from app.services.event_bus import GameEvent, event_bus
from app.services.exploration import data_loader
from app.services.exploration.rewards_calculator import rewards_calculator
from app.services.notification_service import notification_service
from app.utils.outfit_assets import get_outfit_image_url
from app.utils.weapon_assets import get_weapon_image_url

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
    def _normalize_outfit_type(outfit_type_str: str) -> str:
        """Normalize outfit_type string to match OutfitTypeEnum values.

        Maps data values like 'tiered_outfit' to enum values like 'TIERED'.
        """
        normalized = outfit_type_str.upper().replace(" ", "_")
        # Remove '_OUTFIT' suffix if present (except for POWER_ARMOR)
        if normalized.endswith("_OUTFIT") and normalized != "POWER_ARMOR":
            normalized = normalized.replace("_OUTFIT", "")
        return normalized

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

    def _create_weapon_from_loot(self, weapon_data: dict, rarity: RarityEnum, storage_id: UUID4) -> Weapon | None:
        """Create a Weapon model from loot data.

        :param weapon_data: Weapon data dict from data_loader
        :param rarity: RarityEnum value
        :param storage_id: Storage ID to assign weapon to
        :returns: Weapon instance or None if data is invalid
        """
        if not weapon_data:
            return None
        try:
            return Weapon(
                name=weapon_data["name"],
                rarity=rarity,
                value=weapon_data.get("value"),
                weapon_type=WeaponTypeEnum[weapon_data["weapon_type"].upper()],
                weapon_subtype=WeaponSubtypeEnum[weapon_data["weapon_subtype"].upper()],
                stat=weapon_data["stat"],
                damage_min=weapon_data["damage_min"],
                damage_max=weapon_data["damage_max"],
                image_url=get_weapon_image_url(weapon_data["name"]),
                storage_id=storage_id,
            )
        except (KeyError, ValueError):
            logger.exception(
                "Failed to create weapon from loot data",
                extra={
                    "weapon_data": weapon_data,
                    "rarity": rarity.value if rarity else None,
                    "storage_id": str(storage_id),
                },
            )
            return None

    def _create_outfit_from_loot(self, outfit_data: dict, rarity: RarityEnum, storage_id: UUID4) -> Outfit | None:
        """Create an Outfit model from loot data.

        :param outfit_data: Outfit data dict from data_loader
        :param rarity: RarityEnum value
        :param storage_id: Storage ID to assign outfit to
        :returns: Outfit instance or None if data is invalid
        """
        if not outfit_data:
            return None
        try:
            return Outfit(
                name=outfit_data["name"],
                rarity=rarity,
                value=outfit_data.get("value"),
                outfit_type=OutfitTypeEnum[self._normalize_outfit_type(outfit_data["outfit_type"])],
                gender=GenderEnum[outfit_data["gender"].upper()] if outfit_data.get("gender") else None,
                image_url=get_outfit_image_url(outfit_data["name"]),
                storage_id=storage_id,
            )
        except (KeyError, ValueError):
            logger.exception(
                "Failed to create outfit from loot data",
                extra={
                    "outfit_data": outfit_data,
                    "rarity": rarity.value if rarity else None,
                    "storage_id": str(storage_id),
                },
            )
            return None

    def _create_junk_from_loot(self, item_name: str, rarity: RarityEnum, storage_id: UUID4) -> Junk:
        """Create a Junk model from loot data.

        :param item_name: Name of the junk item
        :param rarity: RarityEnum value
        :param storage_id: Storage ID to assign junk to
        :returns: Junk instance
        """
        return Junk(
            name=item_name,
            junk_type=JunkTypeEnum.VALUABLES,
            rarity=rarity,
            value=game_config.exploration.get_junk_value(rarity.value),
            description="Found during wasteland exploration",
            storage_id=storage_id,
        )

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
            return {"transferred": [], "overflow": [], "auto_equip_ids": [], "storage_id": None}

        vault = await crud_vault.get(db_session, exploration.vault_id)
        storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
        if not storage:
            logger.error("Storage not found for vault", extra={"vault_id": str(vault.id)})
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

        # Sort loot by rarity (higher priority items first)
        # Normalize rarity to enum first to ensure consistent priority calculation
        sorted_loot = sorted(
            exploration.loot_collected,
            key=lambda x: game_config.exploration.get_rarity_priority(
                self._parse_rarity_to_enum(x.get("rarity", "common")).value
            ),
            reverse=True,
        )

        transferred: list[dict] = []
        overflow: list[dict] = []
        auto_equip_ids: list[dict] = []
        items_added = 0

        # Load item data for lookups
        weapons_data = await asyncio.to_thread(data_loader.load_weapons)
        outfits_data = await asyncio.to_thread(data_loader.load_outfits)

        for loot_item in sorted_loot:
            item_name = loot_item.get("item_name", "Unknown Item")
            item_type = loot_item.get("item_type", "junk")
            rarity_str = loot_item.get("rarity", "Common")

            if item_type in {"stimpak", "radaway"}:
                # Medical loot is returned via the stimpack/radaway counters in
                # apply_rewards; creating junk here would double-count it and
                # burn storage space.
                continue

            # Check if space available
            if items_added >= available_space:
                overflow.append(loot_item)
                logger.warning(
                    "Storage full - item dropped",
                    extra={
                        "vault_id": str(vault.id),
                        "item_name": item_name,
                        "item_type": item_type,
                        "rarity": rarity_str,
                        "items_in_storage": items_added,
                        "max_space": storage.max_space,
                    },
                )
                continue

            # Convert rarity string to enum
            rarity = self._parse_rarity_to_enum(rarity_str)

            match item_type:
                case "weapon":
                    weapon_data = next((w for w in weapons_data if w["name"] == item_name), None)
                    item = self._create_weapon_from_loot(weapon_data, rarity, storage_id)
                case "outfit":
                    outfit_data = next((o for o in outfits_data if o["name"] == item_name), None)
                    item = self._create_outfit_from_loot(outfit_data, rarity, storage_id)
                case _:
                    item = self._create_junk_from_loot(item_name, rarity, storage_id)

            if item is None:
                continue

            db_session.add(item)

            if item_type in {"weapon", "outfit"}:
                await event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": item_type, "amount": 1})
                if loot_item.get("auto_equip"):
                    await db_session.flush()
                    auto_equip_ids.append({"item_type": item_type, "id": item.id})

            items_added += 1
            transferred.append(loot_item)
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

        return {
            "transferred": transferred,
            "overflow": overflow,
            "auto_equip_ids": auto_equip_ids,
            "storage_id": storage_id,
        }

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
            await crud_vault.deposit_caps(db_session=db_session, vault_obj=vault, amount=total_caps)

        # Calculate and apply experience
        full_experience = rewards_calculator.calculate_exploration_xp(exploration, dweller_obj)
        experience = int(full_experience * progress_multiplier)

        dweller_obj.experience = max(0, dweller_obj.experience + experience)
        db_session.add(dweller_obj)

        # Check for level-up
        await leveling_service.check_level_up(db_session, dweller_obj)

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
                room_result = await db_session.execute(select(Room).where(Room.vault_id == exploration.vault_id))
                rooms = room_result.scalars().all()
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
