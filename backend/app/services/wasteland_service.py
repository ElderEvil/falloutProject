"""Wasteland exploration service for managing expeditions and events."""

import json
import random
from datetime import datetime
from pathlib import Path

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import exploration as crud_exploration
from app.crud import vault as crud_vault
from app.models.exploration import Exploration
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.common import GenderEnum, JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum


class WastelandService:
    """Service for managing wasteland exploration logic."""

    def __init__(self):
        """Initialize the wasteland service with item data."""
        self.junk_items: list[dict] = []
        self.weapons: list[dict] = []
        self.outfits: list[dict] = []
        self._load_item_data()

    def _load_item_data(self) -> None:
        """Load junk, weapons, and outfits from JSON files."""
        data_dir = Path(__file__).parent.parent / "data" / "items"

        # Load junk items
        junk_file = data_dir / "junk.json"
        if junk_file.exists():
            with open(junk_file) as f:
                self.junk_items = json.load(f)

        # Load weapons
        weapons_file = data_dir / "weapons.json"
        if weapons_file.exists():
            with open(weapons_file) as f:
                self.weapons = json.load(f)

        # Load outfits from all outfit files
        outfits_dir = data_dir / "outfits"
        if outfits_dir.exists():
            for outfit_file in outfits_dir.glob("*.json"):
                with open(outfit_file) as f:
                    self.outfits.extend(json.load(f))

    def _calculate_luck_multiplier(self, luck: int) -> float:
        """Calculate loot quality multiplier based on luck stat."""
        # Luck 1 = 0.5x, Luck 5-6 = 1.0x, Luck 10 = 2.0x
        return 0.5 + (luck - 1) * (1.5 / 9)

    def _calculate_perception_bonus(self, perception: int) -> float:
        """Calculate loot discovery chance based on perception."""
        # Perception 1 = 50% chance, Perception 10 = 95% chance
        return 0.5 + (perception - 1) * (0.45 / 9)

    def _calculate_endurance_stamina(self, endurance: int, duration: int) -> int:
        """Calculate how many events can occur based on endurance and duration."""
        # Base: 1 event per 2 hours, endurance adds 0-50% more
        base_events = duration // 2
        endurance_bonus = 1.0 + (endurance - 1) * (0.5 / 9)
        return max(1, int(base_events * endurance_bonus))

    def _calculate_exploration_xp(self, exploration, dweller) -> int:
        """
        Calculate total XP from exploration with all bonuses.

        Includes:
        - Base XP from distance, enemies, and events
        - Survival bonus (if returned with >70% health)
        - Luck bonus (scales with luck stat)

        Args:
            exploration: Completed exploration
            dweller: Dweller who completed exploration

        Returns:
            Total XP to award
        """
        from app.core.game_config import game_config

        # Base XP sources
        distance_xp = exploration.total_distance * game_config.leveling.exploration_xp_per_distance
        combat_xp = exploration.enemies_encountered * game_config.leveling.exploration_xp_per_enemy
        event_xp = len(exploration.events) * game_config.leveling.exploration_xp_per_event

        base_xp = distance_xp + combat_xp + event_xp

        # Survival bonus (returned with >70% health)
        survival_bonus = 0
        if dweller.health / dweller.max_health > 0.7:
            survival_bonus = int(base_xp * game_config.leveling.exploration_survival_bonus)

        # Luck bonus (2% per luck point)
        luck_bonus = int(base_xp * (exploration.dweller_luck * game_config.leveling.exploration_luck_bonus))

        total_xp = base_xp + survival_bonus + luck_bonus

        return int(total_xp)

    def _get_rarity_weights(self, luck: int) -> dict[str, float]:
        """Get rarity weights adjusted by luck stat."""
        base_weights = {
            "Common": 70.0,
            "Rare": 25.0,
            "Legendary": 5.0,
        }

        luck_multiplier = self._calculate_luck_multiplier(luck)  # noqa: F841

        # Higher luck = more rare/legendary items
        if luck >= 8:
            return {"Common": 50.0, "Rare": 35.0, "Legendary": 15.0}
        if luck >= 6:
            return {"Common": 60.0, "Rare": 30.0, "Legendary": 10.0}
        if luck >= 4:
            return base_weights
        return {"Common": 80.0, "Rare": 18.0, "Legendary": 2.0}

    def _select_random_weapon(self, luck: int) -> dict:
        """Select a random weapon based on luck-adjusted rarity."""
        if not self.weapons:
            return {
                "name": "Rusty Pipe",
                "rarity": "Common",
                "value": 10,
                "weapon_type": "Melee",
                "weapon_subtype": "Blunt",
                "stat": "strength",
                "damage_min": 1,
                "damage_max": 3,
            }

        rarity_weights = self._get_rarity_weights(luck)

        # Filter weapons by rarity and randomly select one
        rarity = random.choices(
            list(rarity_weights.keys()),
            weights=list(rarity_weights.values()),
            k=1,
        )[0]

        weapons_of_rarity = [weapon for weapon in self.weapons if weapon.get("rarity") == rarity]

        if not weapons_of_rarity:
            weapons_of_rarity = self.weapons

        return random.choice(weapons_of_rarity)

    def _select_random_outfit(self, luck: int) -> dict:
        """Select a random outfit based on luck-adjusted rarity."""
        if not self.outfits:
            return {"name": "Vault Suit", "rarity": "Common", "value": 10, "outfit_type": "Common Outfit"}

        rarity_weights = self._get_rarity_weights(luck)

        # Filter outfits by rarity and randomly select one
        rarity = random.choices(
            list(rarity_weights.keys()),
            weights=list(rarity_weights.values()),
            k=1,
        )[0]

        outfits_of_rarity = [outfit for outfit in self.outfits if outfit.get("rarity") == rarity]

        if not outfits_of_rarity:
            outfits_of_rarity = self.outfits

        return random.choice(outfits_of_rarity)

    def _select_random_loot(self, luck: int) -> tuple[dict, str]:
        """
        Select a random loot item based on luck-adjusted rarity.

        Returns tuple of (item_dict, item_type) where item_type is 'junk', 'weapon', or 'outfit'.
        """
        # Determine item type with luck-adjusted weights
        # Base: 60% junk, 25% weapons, 15% outfits
        # High luck shifts toward weapons/outfits
        if luck >= 8:
            type_weights = {"junk": 50.0, "weapon": 30.0, "outfit": 20.0}
        elif luck >= 6:
            type_weights = {"junk": 55.0, "weapon": 28.0, "outfit": 17.0}
        else:
            type_weights = {"junk": 60.0, "weapon": 25.0, "outfit": 15.0}

        item_type = random.choices(
            list(type_weights.keys()),
            weights=list(type_weights.values()),
            k=1,
        )[0]

        if item_type == "weapon":
            return (self._select_random_weapon(luck), "weapon")
        if item_type == "outfit":
            return (self._select_random_outfit(luck), "outfit")
        # Select junk item
        if not self.junk_items:
            return ({"name": "Bottle Cap", "value": 1, "rarity": "Common"}, "junk")

        rarity_weights = self._get_rarity_weights(luck)
        rarity = random.choices(
            list(rarity_weights.keys()),
            weights=list(rarity_weights.values()),
            k=1,
        )[0]

        items_of_rarity = [item for item in self.junk_items if item.get("rarity") == rarity]
        if not items_of_rarity:
            items_of_rarity = self.junk_items

        return (random.choice(items_of_rarity), "junk")

    def generate_event(self, exploration: Exploration) -> dict | None:
        """
        Generate a random wasteland event based on dweller stats and time elapsed.

        Returns event dict or None if no event should be generated.
        """
        if not exploration.is_active():
            return None

        # Check if enough time has passed for a new event
        last_event_time = None
        if exploration.events:
            last_event = exploration.events[-1]
            last_event_time = datetime.fromisoformat(last_event["timestamp"])

        if not exploration.should_generate_event(last_event_time):
            return None

        # Calculate if loot is found based on perception
        perception_chance = self._calculate_perception_bonus(exploration.dweller_perception)
        found_loot = random.random() < perception_chance

        if found_loot:
            # Generate loot based on luck
            loot_item, item_type = self._select_random_loot(exploration.dweller_luck)
            caps_found = random.randint(5, 20 + exploration.dweller_luck * 3)

            event_descriptions = [
                f"Discovered an abandoned building. Found {loot_item['name']} and {caps_found} caps!",
                f"Stumbled upon a hidden cache containing {loot_item['name']} and {caps_found} caps.",
                f"Found a rusted locker with {loot_item['name']} and {caps_found} caps inside.",
                f"Scavenged through rubble and recovered {loot_item['name']} and {caps_found} caps.",
            ]

            return {
                "type": "loot_found",
                "description": random.choice(event_descriptions),
                "loot": {
                    "item": loot_item,
                    "item_type": item_type,
                    "caps": caps_found,
                },
            }
        # Generate narrative event based on agility/luck
        agility = exploration.dweller_agility
        luck = exploration.dweller_luck  # noqa: F841

        # Higher agility = better chances to avoid danger
        danger_avoided = random.random() < (0.5 + agility * 0.05)

        if danger_avoided:
            safe_events = [
                "Heard gunshots in the distance but managed to avoid the area.",
                "Spotted a group of Raiders ahead and took a safer route around them.",
                "Found fresh water source and rested safely.",
                "Discovered an intact pre-war billboard with useful directions.",
                "Met a friendly trader who shared some supplies.",
                "Found shelter in an old subway station to rest.",
            ]
            return {
                "type": "encounter",
                "description": random.choice(safe_events),
                "loot": None,
            }
        dangerous_events = [
            "Encountered hostile Radroaches! Had to fight them off.",
            "Ran into a pack of feral dogs. Managed to escape with minor injuries.",
            "Got caught in a radiation storm. Took some rads but found cover.",
            "Stumbled into Raider territory. Had to fight through them.",
            "Nearly fell into a hidden pit trap. Agility saved the day!",
        ]
        return {
            "type": "danger",
            "description": random.choice(dangerous_events),
            "loot": None,
        }

    async def process_event(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
    ) -> Exploration:
        """Process and add a generated event to an exploration."""
        event = self.generate_event(exploration)

        if not event:
            return exploration

        # Add event to exploration
        exploration.add_event(
            event_type=event["type"],
            description=event["description"],
            loot=event.get("loot"),
        )
        db_session.add(exploration)

        # If loot was found, update stats and add to collected loot
        if event.get("loot"):
            loot_data = event["loot"]
            item = loot_data["item"]
            item_type = loot_data.get("item_type", "junk")
            caps = loot_data["caps"]

            # Add item to collected loot
            exploration.add_loot(
                item_name=item["name"],
                quantity=1,
                rarity=item.get("rarity", "Common"),
                item_type=item_type,
            )

            # Update stats
            exploration.total_caps_found += caps
            exploration.total_distance += random.randint(1, 5)

        if event["type"] == "danger":
            # Update enemies encountered
            exploration.enemies_encountered += 1

        # Commit changes
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration

    async def _transfer_loot_to_storage(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        description_suffix: str = "",
    ) -> None:
        """
        Transfer loot items from exploration to vault storage.

        Creates Weapon, Outfit, or Junk instances based on item_type.
        """
        if not exploration.loot_collected:
            return

        # Get vault storage
        vault = await crud_vault.get(db_session, exploration.vault_id)

        for loot_item in exploration.loot_collected:
            item_type = loot_item.get("item_type", "junk")
            item_name = loot_item.get("item_name", "Unknown Item")
            rarity_str = loot_item.get("rarity", "Common")

            # Convert rarity string to enum
            try:
                rarity = RarityEnum[rarity_str.upper()]
            except (KeyError, AttributeError):
                rarity = RarityEnum.COMMON

            if item_type == "weapon":
                # Find the weapon data to get all attributes
                weapon_data = next((w for w in self.weapons if w["name"] == item_name), None)
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
                        storage_id=vault.storage.id,
                    )
                    db_session.add(weapon)
            elif item_type == "outfit":
                # Find the outfit data to get all attributes
                outfit_data = next((o for o in self.outfits if o["name"] == item_name), None)
                if outfit_data:
                    outfit = Outfit(
                        name=outfit_data["name"],
                        rarity=rarity,
                        value=outfit_data.get("value"),
                        outfit_type=OutfitTypeEnum[outfit_data["outfit_type"].upper().replace(" ", "_")],
                        gender=GenderEnum[outfit_data["gender"].upper()] if outfit_data.get("gender") else None,
                        storage_id=vault.storage.id,
                    )
                    db_session.add(outfit)
            else:
                # Create junk item in storage
                description = f"Found during wasteland exploration{description_suffix}"
                junk = Junk(
                    name=item_name,
                    junk_type=JunkTypeEnum.MISC,  # Default type
                    rarity=rarity,
                    description=description,
                    storage_id=vault.storage.id,
                )
                db_session.add(junk)

    async def complete_exploration(
        self,
        db_session: AsyncSession,
        exploration_id: UUID4,
    ) -> dict:
        """
        Complete an exploration and return rewards summary.

        Transfers loot and caps to the vault.
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError("Exploration is not active")  # noqa: EM101, TRY003

        # Mark as completed
        await crud_exploration.complete_exploration(db_session, exploration_id=exploration_id)

        # Update dweller status back to IDLE (or WORKING if they have a room)
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

        # Calculate rewards
        total_caps = exploration.total_caps_found
        total_items = len(exploration.loot_collected)  # noqa: F841

        # Transfer caps to vault
        if total_caps > 0:
            vault = await crud_vault.get(db_session, exploration.vault_id)
            await crud_vault.deposit_caps(db_session=db_session, vault_obj=vault, amount=total_caps)

        # Calculate experience with enhanced rewards
        experience = self._calculate_exploration_xp(exploration, dweller_obj)

        # Apply experience to dweller
        dweller_obj.experience += experience
        db_session.add(dweller_obj)

        # Check for level-up
        from app.services.leveling_service import leveling_service

        await leveling_service.check_level_up(db_session, dweller_obj)

        # Transfer loot items to vault storage
        await self._transfer_loot_to_storage(db_session, exploration)

        await db_session.commit()

        return {
            "caps": total_caps,
            "items": exploration.loot_collected,
            "experience": experience,
            "distance": exploration.total_distance,
            "enemies_defeated": exploration.enemies_encountered,
            "events_encountered": len(exploration.events),
        }

    async def recall_exploration(
        self,
        db_session: AsyncSession,
        exploration_id: UUID4,
    ) -> dict:
        """
        Recall a dweller early from exploration.

        Returns reduced rewards based on progress.
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError("Exploration is not active")  # noqa: EM101, TRY003

        # Calculate progress percentage
        progress = exploration.progress_percentage()

        # Mark as recalled
        await crud_exploration.recall_exploration(db_session, exploration_id=exploration_id)

        # Update dweller status back to IDLE (or WORKING if they have a room)
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

        # Calculate reduced rewards based on progress
        total_caps = exploration.total_caps_found
        total_items = len(exploration.loot_collected)  # noqa: F841

        # Transfer caps to vault
        if total_caps > 0:
            vault = await crud_vault.get(db_session, exploration.vault_id)
            await crud_vault.deposit_caps(db_session=db_session, vault_obj=vault, amount=total_caps)

        # Calculate reduced experience (full XP calculation, then reduced by progress)
        full_experience = self._calculate_exploration_xp(exploration, dweller_obj)
        experience = int(full_experience * (progress / 100))

        # Apply experience to dweller
        dweller_obj.experience += experience
        db_session.add(dweller_obj)

        # Check for level-up
        from app.services.leveling_service import leveling_service

        await leveling_service.check_level_up(db_session, dweller_obj)

        # Transfer loot items to vault storage
        await self._transfer_loot_to_storage(db_session, exploration, " (recalled early)")

        await db_session.commit()

        return {
            "caps": total_caps,
            "items": exploration.loot_collected,
            "experience": experience,
            "distance": exploration.total_distance,
            "enemies_defeated": exploration.enemies_encountered,
            "events_encountered": len(exploration.events),
            "progress_percentage": progress,
            "recalled_early": True,
        }


# Singleton instance
wasteland_service = WastelandService()
