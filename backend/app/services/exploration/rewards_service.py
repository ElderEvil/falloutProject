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
from app.models.exploration import Exploration
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.exploration import PendingOverflowRead
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration import data_loader
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.rewards_calculator import rewards_calculator
from app.services.loot_overflow_service import loot_overflow_service
from app.services.resource_manager import compute_medical_capacity
from app.services.vault_service import vault_service
from app.utils.exceptions import ValidationException
from app.utils.item_factory import build_junk, build_outfit, build_weapon

logger = logging.getLogger(__name__)

_PENDING_REWARD_EVENTS = "pending_exploration_reward_events"


class TransferResult(TypedDict):
    """Result of transferring loot to vault storage."""

    transferred: list[dict]
    overflow: list[dict]
    storage_id: UUID4 | None


class RewardsService:
    """Applies exploration rewards to vault and dweller."""

    @staticmethod
    def _queue_event(db_session: AsyncSession, event: GameEvent, vault_id: UUID4, payload: dict[str, Any]) -> None:
        """Park a reward event until the finalization transaction commits."""
        db_session.info.setdefault(_PENDING_REWARD_EVENTS, []).append((event, vault_id, payload))

    async def deliver_pending_reward_events(self, db_session: AsyncSession) -> None:
        """Emit reward events parked while a deferred finalization was in flight."""
        for event, vault_id, payload in db_session.info.pop(_PENDING_REWARD_EVENTS, []):
            await event_bus.emit(event, vault_id, payload)

    def discard_pending_rewards(self, db_session: AsyncSession) -> None:
        """Drop parked reward events for a rolled-back finalization."""
        db_session.info.pop(_PENDING_REWARD_EVENTS, None)

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

    @staticmethod
    def _held_spec(row: Weapon | Outfit, item_type: str) -> dict:
        return {
            "item_name": row.name,
            "item_type": item_type,
            "rarity": row.rarity.value,
            "quantity": 1,
            "held_row_id": row.id,
            "held_model": item_type,
        }

    @staticmethod
    def _plain_spec(candidate: dict) -> dict:
        return {key: value for key, value in candidate.items() if key not in ("held_row_id", "held_model")}

    async def _transfer_loot_to_storage(self, db_session: AsyncSession, exploration: Exploration) -> TransferResult:
        """Transfer loot and expedition-held equipment to vault storage with space validation.

        Held rows (Weapon/Outfit with ``exploration_id`` set) and ordinary loot
        entries share ONE rarity-first capacity budget: every stored unit occupies
        one slot, so ``grant_or_hold`` splits the merged candidate list once. Entries
        already equipped mid-run (``equipped`` truthy) are skipped entirely.

        :param db_session: Database session
        :param exploration: Completed exploration
        :returns: TransferResult with transferred/overflow item lists and storage_id
        """
        held_weapon_rows = await crud_weapon.get_held_for_exploration(db_session, exploration.id)
        held_outfit_rows = await crud_outfit.get_held_for_exploration(db_session, exploration.id)
        loot_entries = [entry for entry in exploration.loot_collected if not entry.get("equipped")]

        if not loot_entries and not held_weapon_rows and not held_outfit_rows:
            exploration.unclaimed_loot = []
            return {"transferred": [], "overflow": [], "storage_id": None}

        candidates = list(loot_entries)
        candidates.extend(self._held_spec(row, "weapon") for row in held_weapon_rows)
        candidates.extend(self._held_spec(row, "outfit") for row in held_outfit_rows)
        held_rows: dict[UUID4, Weapon | Outfit] = {row.id: row for row in (*held_weapon_rows, *held_outfit_rows)}

        vault = await crud_vault.get(db_session, exploration.vault_id)
        storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
        if not storage:
            logger.error("Storage not found for vault", extra={"vault_id": str(vault.id)})
            overflow = [self._plain_spec(candidate) for candidate in candidates]
            for candidate in candidates:
                if "held_row_id" in candidate:
                    await db_session.delete(held_rows[candidate["held_row_id"]])
            exploration.unclaimed_loot = overflow
            return {"transferred": [], "overflow": overflow, "storage_id": None}
        storage_id = storage.id

        # Check available space once; held rows have storage_id IS NULL, so they
        # are not counted and the merged list shares this single budget.
        available_space = await crud_storage.get_available_space(db_session, storage_id)

        logger.info(
            "Storage transfer starting",
            extra={
                "vault_id": str(vault.id),
                "exploration_id": str(exploration.id),
                "available_space": available_space,
                "items_to_transfer": len(candidates),
            },
        )

        granted, overflow = loot_overflow_service.grant_or_hold(candidates, available_space)

        transferred: list[dict] = []

        # Load item data for lookups
        weapons_data = await asyncio.to_thread(data_loader.load_weapons)
        outfits_data = await asyncio.to_thread(data_loader.load_outfits)

        for loot_item in granted:
            if "held_row_id" in loot_item:
                row = held_rows[loot_item["held_row_id"]]
                row.storage_id = storage_id
                row.exploration_id = None
                db_session.add(row)
                transferred.append(self._plain_spec(loot_item))
                continue

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
                    self._queue_event(
                        db_session, GameEvent.ITEM_COLLECTED, vault.id, {"item_type": item_type, "amount": 1}
                    )

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

        overflow_specs: list[dict] = []
        for loot_item in overflow:
            if "held_row_id" in loot_item:
                await db_session.delete(held_rows[loot_item["held_row_id"]])
                overflow_specs.append(self._plain_spec(loot_item))
            else:
                overflow_specs.append(loot_item)

        await db_session.flush()

        # Update storage used_space counter
        await crud_storage.update_used_space(db_session, storage_id)

        # Log summary
        if overflow_specs:
            logger.warning(
                "Storage overflow occurred during transfer",
                extra={
                    "vault_id": str(vault.id),
                    "exploration_id": str(exploration.id),
                    "transferred_count": len(transferred),
                    "overflow_count": len(overflow_specs),
                    "overflow_items": [i.get("item_name") for i in overflow_specs],
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

        exploration.unclaimed_loot = overflow_specs

        return {
            "transferred": transferred,
            "overflow": overflow_specs,
            "storage_id": storage_id,
        }

    async def _load_unclaimed(self, db_session: AsyncSession, exploration_id: UUID4) -> tuple[Exploration, list[dict]]:
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
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
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        progress_multiplier: float = 1.0,
        *,
        commit: bool = True,
    ) -> RewardsSchema:
        """Apply rewards to vault and dweller.

        Args:
            db_session: Database session
            exploration: Completed exploration
            progress_multiplier: Scales XP for an early recall
            commit: Commit the settlement here. False batches it into the caller's
                single transaction; the caller then drains parked surfacing after
                its own commit.
        """
        from app.services.leveling_service import leveling_service

        # Get dweller
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        # Transfer caps to vault
        total_caps = exploration.total_caps_found
        if total_caps > 0:
            vault = await crud_vault.get(db_session, exploration.vault_id)
            credited = await vault_service.deposit_caps(
                db_session=db_session, vault_obj=vault, amount=total_caps, commit=commit, emit_event=False
            )
            self._queue_event(
                db_session,
                GameEvent.RESOURCE_COLLECTED,
                exploration.vault_id,
                {"resource_type": "caps", "amount": credited},
            )

        # Calculate and apply experience
        full_experience = rewards_calculator.calculate_exploration_xp(exploration, dweller_obj)
        experience = int(full_experience * progress_multiplier)

        dweller_obj.experience = max(0, dweller_obj.experience + experience)
        db_session.add(dweller_obj)

        # Check for level-up
        leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller_obj, commit=commit)
        if leveled_up:
            await leveling_service.settle_level_up(
                db_session,
                dweller_obj,
                old_level=dweller_obj.level - levels_gained,
                levels_gained=levels_gained,
                commit=commit,
            )

        # Transfer loot items to vault storage (with space validation)
        transfer_result = await self._transfer_loot_to_storage(db_session, exploration)

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

        if exploration.stimpaks > 0:
            self._queue_event(
                db_session,
                GameEvent.ITEM_COLLECTED,
                exploration.vault_id,
                {"item_type": "stimpak", "amount": exploration.stimpaks},
            )
        if exploration.radaways > 0:
            self._queue_event(
                db_session,
                GameEvent.ITEM_COLLECTED,
                exploration.vault_id,
                {"item_type": "radaway", "amount": exploration.radaways},
            )

        if commit:
            await db_session.commit()
            await self.deliver_pending_reward_events(db_session)

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


# Singleton instance
rewards_service = RewardsService()
