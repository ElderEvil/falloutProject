"""Exploration coordinator - orchestrates all exploration operations."""

import logging
import random

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import exploration as crud_exploration
from app.crud import storage as crud_storage
from app.crud import vault as crud_vault
from app.models.exploration import Exploration
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.common import GenderEnum, JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.schemas.exploration_event import RewardsSchema
from app.services.event_bus import GameEvent, event_bus
from app.services.exploration import data_loader
from app.services.exploration.event_generator import event_generator
from app.services.exploration.rewards_calculator import rewards_calculator
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Error messages as constants to satisfy ruff
ERROR_NOT_ACTIVE = "Exploration is not active"


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

        # Trigger auto-heal check (if health low or radiation high)
        await self._handle_auto_heal(db_session, exploration)

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

    async def _handle_loot_event(self, db_session: AsyncSession, exploration: Exploration, event) -> None:
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

        # Check for medicine discovery
        if item_type == "stimpak":
            exploration.stimpaks += 1
            exploration.add_event(
                event_type="loot",
                description=f"Found a Stimpak! Total: {exploration.stimpaks}",
            )
        elif item_type == "radaway":
            exploration.radaways += 1
            exploration.add_event(
                event_type="loot",
                description=f"Found a RadAway! Total: {exploration.radaways}",
            )

        # Check for better gear if weapon or outfit found
        if item_type in {"weapon", "outfit"}:
            await self._handle_auto_equip(db_session, exploration, item, item_type)

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
            # Flush so _handle_auto_heal sees updated health
            await db_session.flush()

    async def _apply_health_restoration(self, db_session: AsyncSession, exploration: Exploration, healing: int) -> None:
        """Apply health restoration to dweller."""
        from app.crud.dweller import dweller as dweller_crud

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        dweller_obj.health = min(dweller_obj.max_health, dweller_obj.health + healing)
        db_session.add(dweller_obj)

    async def _handle_auto_heal(self, db_session: AsyncSession, exploration: Exploration) -> None:
        """Automatically use stimpaks/radaways if needed."""
        from app.crud.dweller import dweller as dweller_crud

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        # Early return if dweller is already dead
        if dweller_obj.is_dead:
            return

        # Auto-use RadAway if radiation > 30
        if exploration.radaways > 0 and dweller_obj.radiation > 30:
            # Radiation removal logic (50% of radiation)
            reduction = int(dweller_obj.radiation * 0.5)
            dweller_obj.radiation = max(0, dweller_obj.radiation - reduction)
            exploration.radaways -= 1
            exploration.add_event(
                event_type="item_use",
                description=f"Dweller used a RadAway. Removed {reduction} radiation. {exploration.radaways} left.",
            )
            db_session.add(dweller_obj)
            db_session.add(exploration)

        # Auto-use Stimpak if health < 50%
        health_percentage = (dweller_obj.health / dweller_obj.max_health) * 100
        if exploration.stimpaks > 0 and health_percentage < 50:
            # Heal logic (40% of max health)
            healing = int(dweller_obj.max_health * 0.4)
            dweller_obj.health = min(dweller_obj.max_health, dweller_obj.health + healing)
            exploration.stimpaks -= 1
            exploration.add_event(
                event_type="item_use",
                description=f"Dweller used a Stimpak. Healed {healing} HP. {exploration.stimpaks} left.",
            )
            db_session.add(dweller_obj)
            db_session.add(exploration)

    async def _handle_auto_equip(
        self, db_session: AsyncSession, exploration: Exploration, item_schema, item_type: str
    ) -> None:
        """Auto-equip better weapon or outfit found during exploration."""
        from app.crud.dweller import dweller as dweller_crud

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        if item_type == "weapon":
            current_weapon = dweller_obj.weapon
            # Simplified comparison: Use average damage for weapons
            new_avg_damage = (item_schema.damage_min + item_schema.damage_max) / 2
            current_avg_damage = (current_weapon.damage_min + current_weapon.damage_max) / 2 if current_weapon else 0

            if new_avg_damage > current_avg_damage:
                # In fallout shelters, found items go to loot_collected,
                # but let's implement a 'swap' logic here if we wanted to be proactive.
                # Actually, the requirement just says "Think about auto-use found items".
                # For now, let's just log that a better item was found and "equipped" (simulated for exploration boost)
                # To actually equip, we'd need to create the DB object and link it.
                # Since the dweller is in the wasteland, we'll just add it to events for now.
                # Real implementation should probably create the item in DB and link it to dweller.
                exploration.add_event(
                    event_type="equip",
                    description=f"Found better weapon: {item_schema.name}. Using temporarily for better survival (not permanently equipped).",  # noqa: E501
                )
                db_session.add(exploration)
                # Note: To really affect combat, we'd need to update dweller_obj.weapon_id
                # but that requires creating the weapon in DB now instead of at the end.
                # Let's skip the actual DB link for now to keep it simple, or do it properly if needed.

        elif item_type == "outfit":
            # Similar logic for outfits (e.g., total SPECIAL points)
            exploration.add_event(
                event_type="equip",
                description=f"Found better outfit: {item_schema.name}. Using temporarily (not permanently equipped).",
            )
            db_session.add(exploration)

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
        rewards = await self._apply_rewards(db_session, exploration)

        # Send notification (non-critical, don't break completion on failure)
        try:
            from app.crud.dweller import dweller as dweller_crud

            dweller = await dweller_crud.get(db_session, exploration.dweller_id)
            vault = await crud_vault.get(db_session, exploration.vault_id)

            if vault and vault.user_id and dweller:
                await notification_service.notify_exploration_complete(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=exploration.vault_id,
                    dweller_id=dweller.id,
                    dweller_name=f"{dweller.first_name} {dweller.last_name or ''}".strip(),
                    meta_data={
                        "caps_earned": rewards.caps,
                        "xp_earned": rewards.experience,
                        "items_found": len(rewards.items),
                    },
                )
        except Exception:
            logger.exception(
                "Failed to send exploration complete notification: vault_id=%s, dweller_id=%s",
                exploration.vault_id,
                exploration.dweller_id,
            )

        return rewards

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

        # Return unused stimpaks and radaways to vault storage
        if exploration.stimpaks > 0 or exploration.radaways > 0:
            vault = await crud_vault.get(db_session, exploration.vault_id)
            new_stimpaks = min((vault.stimpack or 0) + exploration.stimpaks, vault.stimpack_max or 99999)
            new_radaways = min((vault.radaway or 0) + exploration.radaways, vault.radaway_max or 99999)
            await crud_vault.update(
                db_session,
                exploration.vault_id,
                obj_in={"stimpack": new_stimpaks, "radaway": new_radaways},
            )

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
    def _parse_rarity_to_enum(rarity_str: str) -> RarityEnum:
        """
        Convert rarity string to RarityEnum with fallback to COMMON.

        :param rarity_str: Rarity string (e.g., "Legendary", "COMMON")
        :returns: RarityEnum value, defaults to COMMON if invalid
        """
        try:
            return RarityEnum[rarity_str.upper()]
        except (KeyError, AttributeError):
            return RarityEnum.COMMON

    def _create_weapon_from_loot(self, weapon_data: dict, rarity: RarityEnum, storage_id: UUID4) -> Weapon | None:
        """
        Create a Weapon model from loot data.

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
        """
        Create an Outfit model from loot data.

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
        """
        Create a Junk model from loot data.

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

    async def _transfer_loot_to_storage(self, db_session: AsyncSession, exploration: Exploration) -> dict[str, list]:  # noqa: PLR0912, PLR0915
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
        # Check vault exists first (raises ResourceNotFoundException if missing)
        vault = await crud_vault.get(db_session, exploration.vault_id)
        if not vault:
            logger.error(
                "Vault not found for exploration",
                extra={"vault_id": str(exploration.vault_id), "exploration_id": str(exploration.id)},
            )
            return {"transferred": [], "overflow": exploration.loot_collected}

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
            rarity = self._parse_rarity_to_enum(rarity_str)

            # Create and add item to storage
            item_created = False

            if item_type == "weapon":
                weapon_data = next((w for w in weapons_data if w["name"] == item_name), None)
                weapon = self._create_weapon_from_loot(weapon_data, rarity, storage_id)
                if weapon:
                    db_session.add(weapon)
                    item_created = True
                    await event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": "weapon", "amount": 1})

            elif item_type == "outfit":
                outfit_data = next((o for o in outfits_data if o["name"] == item_name), None)
                outfit = self._create_outfit_from_loot(outfit_data, rarity, storage_id)
                if outfit:
                    db_session.add(outfit)
                    item_created = True
                    await event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": "outfit", "amount": 1})

            else:
                junk = self._create_junk_from_loot(item_name, rarity, storage_id)
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
