"""Exploration coordinator - orchestrates all exploration operations."""

import logging
import random

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import exploration as crud_exploration
from app.crud import storage as crud_storage
from app.crud import vault as crud_vault
from app.models.exploration import Exploration
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.common import GenderEnum, JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration import data_loader
from app.services.exploration.event_generator import event_generator
from app.services.exploration.rewards_calculator import rewards_calculator

logger = logging.getLogger(__name__)

# Error messages as constants to satisfy ruff
ERROR_NOT_ACTIVE = "Exploration is not active"

# Rarity priority for storage overflow handling (higher = more valuable)
# Using RarityEnum.value to ensure consistent casing with the enum
RARITY_PRIORITY = {
    RarityEnum.LEGENDARY.value: 3,
    RarityEnum.RARE.value: 2,
    RarityEnum.COMMON.value: 1,
}


class ExplorationCoordinator:
    """Coordinates all exploration operations."""

    @staticmethod
    def _normalize_outfit_type(outfit_type_str: str) -> str:
        """
        Normalize outfit_type string to match OutfitTypeEnum values.

        Maps data values like 'tiered_outfit' to enum values like 'TIERED'.
        """
        normalized = outfit_type_str.upper().replace(" ", "_")
        # Remove '_OUTFIT' suffix if present (except for POWER_ARMOR)
        if normalized.endswith("_OUTFIT") and normalized != "POWER_ARMOR":
            normalized = normalized.replace("_OUTFIT", "")
        return normalized

    async def process_event(self, db_session: AsyncSession, exploration: Exploration) -> Exploration:
        """
        Generate and process an event for an active exploration.

        Args:
            db_session: Database session
            exploration: Active exploration

        Returns:
            Updated exploration
        """
        event = event_generator.generate_event(exploration)

        if not event:
            return exploration

        # Add event to exploration
        # Convert loot schema to dict for JSON storage
        loot_dict = None
        if hasattr(event, "loot") and event.loot:
            loot_dict = event.loot.model_dump()

        exploration.add_event(
            event_type=event.type,
            description=event.description,
            loot=loot_dict,
        )
        db_session.add(exploration)

        # Handle event-specific logic
        if hasattr(event, "loot") and event.loot:
            await self._handle_loot_event(db_session, exploration, event)

        if hasattr(event, "health_loss") and event.health_loss:
            await self._apply_health_loss(db_session, exploration, event.health_loss)

        if hasattr(event, "health_restored") and event.health_restored:
            await self._apply_health_restoration(db_session, exploration, event.health_restored)

        # Update distance traveled for all events
        exploration.total_distance += random.randint(1, 3)

        # Track combat encounters
        if event.type == "combat":
            exploration.enemies_encountered += 1

        # Commit changes
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration

    async def _handle_loot_event(self, _db_session: AsyncSession, exploration: Exploration, event) -> None:
        """Handle loot found in event."""
        loot_data = event.loot
        item = loot_data.item
        item_type = loot_data.item_type
        caps = loot_data.caps

        # Add item to collected loot
        exploration.add_loot(
            item_name=item.name,
            quantity=1,
            rarity=item.rarity,
            item_type=item_type,
        )

        # Update stats
        exploration.total_caps_found += caps
        exploration.total_distance += random.randint(1, 5)

    async def _apply_health_loss(self, db_session: AsyncSession, exploration: Exploration, damage: int) -> None:
        """
        Apply health loss to dweller.

        If damage would be fatal (health <= 0), the dweller dies from exploration.
        """
        from app.crud.dweller import dweller as dweller_crud

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        # Short-circuit if dweller is already dead - don't apply damage to dead dwellers
        if dweller_obj.is_dead:
            return

        new_health = dweller_obj.health - damage

        if new_health <= 0:
            # Dweller dies in the wasteland
            from app.schemas.common import DeathCauseEnum
            from app.services.death_service import death_service

            await death_service.mark_as_dead(db_session, dweller_obj, DeathCauseEnum.EXPLORATION)
        else:
            # Just apply damage (cap at 1 to give player chance to recall)
            dweller_obj.health = max(1, new_health)
            db_session.add(dweller_obj)

    async def _apply_health_restoration(self, db_session: AsyncSession, exploration: Exploration, healing: int) -> None:
        """Apply health restoration to dweller."""
        from app.crud.dweller import dweller as dweller_crud

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        dweller_obj.health = min(dweller_obj.max_health, dweller_obj.health + healing)
        db_session.add(dweller_obj)

    async def complete_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> RewardsSchema:
        """
        Complete an exploration and return rewards summary.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            dict: Rewards summary
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError(ERROR_NOT_ACTIVE)

        # Mark as completed
        await crud_exploration.complete_exploration(db_session, exploration_id=exploration_id)

        # Update dweller status
        await self._update_dweller_status_after_return(db_session, exploration)

        # Calculate and apply rewards
        return await self._apply_rewards(db_session, exploration)

    async def recall_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> RewardsSchema:
        """
        Recall a dweller early from exploration.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            dict: Rewards summary with reduced XP
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError(ERROR_NOT_ACTIVE)

        # Calculate progress percentage
        progress = exploration.progress_percentage()

        # Mark as recalled
        await crud_exploration.recall_exploration(db_session, exploration_id=exploration_id)

        # Update dweller status
        await self._update_dweller_status_after_return(db_session, exploration)

        # Calculate and apply reduced rewards
        rewards = await self._apply_rewards(db_session, exploration, progress_multiplier=progress / 100)

        # Add recall-specific fields using model_copy
        return rewards.model_copy(update={"progress_percentage": progress, "recalled_early": True})

    async def _update_dweller_status_after_return(self, db_session: AsyncSession, exploration: Exploration) -> None:
        """Update dweller status back to IDLE or WORKING."""
        from app.crud.dweller import dweller as dweller_crud
        from app.schemas.common import DwellerStatusEnum, RoomTypeEnum
        from app.schemas.dweller import DwellerUpdate

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        if dweller_obj.room_id:
            # Dweller has a room - set status based on room type
            from app.crud.room import room as room_crud

            room_obj = await room_crud.get(db_session, dweller_obj.room_id)
            if room_obj.category == RoomTypeEnum.TRAINING:
                new_status = DwellerStatusEnum.TRAINING
            elif room_obj.category == RoomTypeEnum.PRODUCTION:
                new_status = DwellerStatusEnum.WORKING
            else:
                new_status = DwellerStatusEnum.WORKING
        else:
            # No room - set to IDLE
            new_status = DwellerStatusEnum.IDLE

        await dweller_crud.update(db_session, exploration.dweller_id, DwellerUpdate(status=new_status))

    async def _apply_rewards(
        self, db_session: AsyncSession, exploration: Exploration, progress_multiplier: float = 1.0
    ) -> RewardsSchema:
        """Apply rewards to vault and dweller."""
        from app.crud.dweller import dweller as dweller_crud
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

        await db_session.commit()

        return RewardsSchema(
            caps=total_caps,
            items=transfer_result["transferred"],
            overflow_items=transfer_result["overflow"],
            experience=experience,
            distance=exploration.total_distance,
            enemies_defeated=exploration.enemies_encountered,
            events_encountered=len(exploration.events),
        )

    async def _transfer_loot_to_storage(  # noqa: PLR0912, PLR0915
        self, db_session: AsyncSession, exploration: Exploration
    ) -> dict[str, list]:
        """
        Transfer loot items from exploration to vault storage with space validation.

        Items are sorted by rarity (legendary > rare > uncommon > common) and
        transferred in priority order. If storage is full, remaining items are
        tracked as overflow.

        :param db_session: Database session
        :param exploration: Completed exploration
        :returns: Dict with 'transferred' and 'overflow' item lists
        """
        if not exploration.loot_collected:
            return {"transferred": [], "overflow": []}

        # Get vault and storage (query storage explicitly to avoid lazy load)
        vault = await crud_vault.get(db_session, exploration.vault_id)
        storage = await crud_storage.get_storage_by_vault(db_session, vault.id)
        if not storage:
            logger.error("Storage not found for vault", extra={"vault_id": str(vault.id)})
            return {"transferred": [], "overflow": exploration.loot_collected}
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
        sorted_loot = sorted(
            exploration.loot_collected,
            key=lambda x: RARITY_PRIORITY.get(x.get("rarity", "common").lower(), 0),
            reverse=True,
        )

        transferred: list[dict] = []
        overflow: list[dict] = []
        items_added = 0

        # Load item data for lookups
        weapons_data = data_loader.load_weapons()
        outfits_data = data_loader.load_outfits()

        for loot_item in sorted_loot:
            item_name = loot_item.get("item_name", "Unknown Item")
            item_type = loot_item.get("item_type", "junk")
            rarity_str = loot_item.get("rarity", "Common")

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
            try:
                rarity = RarityEnum[rarity_str.upper()]
            except (KeyError, AttributeError):
                rarity = RarityEnum.COMMON

            # Create and add item to storage
            item_created = False

            if item_type == "weapon":
                weapon_data = next((w for w in weapons_data if w["name"] == item_name), None)
                if weapon_data:
                    weapon = Weapon(
                        name=weapon_data["name"],
                        rarity=rarity,
                        value=weapon_data.get("value"),
                        weapon_type=WeaponTypeEnum[weapon_data["weapon_type"].upper()],
                        weapon_subtype=WeaponSubtypeEnum[weapon_data["weapon_subtype"].upper()],
                        stat=weapon_data["stat"],
                        damage_min=weapon_data["damage_min"],
                        damage_max=weapon_data["damage_max"],
                        storage_id=storage_id,
                    )
                    db_session.add(weapon)
                    item_created = True

            elif item_type == "outfit":
                outfit_data = next((o for o in outfits_data if o["name"] == item_name), None)
                if outfit_data:
                    outfit = Outfit(
                        name=outfit_data["name"],
                        rarity=rarity,
                        value=outfit_data.get("value"),
                        outfit_type=OutfitTypeEnum[self._normalize_outfit_type(outfit_data["outfit_type"])],
                        gender=GenderEnum[outfit_data["gender"].upper()] if outfit_data.get("gender") else None,
                        storage_id=storage_id,
                    )
                    db_session.add(outfit)
                    item_created = True

            else:
                # Create junk item
                junk = Junk(
                    name=item_name,
                    junk_type=JunkTypeEnum.VALUABLES,
                    rarity=rarity,
                    description="Found during wasteland exploration",
                    storage_id=storage_id,
                )
                db_session.add(junk)
                item_created = True

            if item_created:
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

        return {"transferred": transferred, "overflow": overflow}


# Singleton instance
exploration_coordinator = ExplorationCoordinator()
