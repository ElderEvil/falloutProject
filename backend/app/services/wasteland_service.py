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


class WastelandService:
    """Service for managing wasteland exploration logic."""

    def __init__(self):
        """Initialize the wasteland service with junk data."""
        self.junk_items: list[dict] = []
        self._load_junk_data()

    def _load_junk_data(self) -> None:
        """Load junk items from JSON file."""
        junk_file = Path(__file__).parent.parent / "data" / "items" / "junk.json"
        if junk_file.exists():
            with open(junk_file) as f:
                self.junk_items = json.load(f)

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

    def _select_random_loot(self, luck: int) -> dict:
        """Select a random junk item based on luck-adjusted rarity."""
        if not self.junk_items:
            return {"name": "Bottle Cap", "value": 1, "rarity": "Common"}

        rarity_weights = self._get_rarity_weights(luck)

        # Filter items by rarity and randomly select one
        rarity = random.choices(
            list(rarity_weights.keys()),
            weights=list(rarity_weights.values()),
            k=1,
        )[0]

        items_of_rarity = [item for item in self.junk_items if item.get("rarity") == rarity]

        if not items_of_rarity:
            items_of_rarity = self.junk_items

        return random.choice(items_of_rarity)

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
            loot_item = self._select_random_loot(exploration.dweller_luck)
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
        await crud_exploration.add_event(
            db_session,
            exploration_id=exploration.id,
            event_type=event["type"],
            description=event["description"],
            loot=event.get("loot"),
        )

        # If loot was found, update stats and add to collected loot
        if event.get("loot"):
            loot_data = event["loot"]
            item = loot_data["item"]
            caps = loot_data["caps"]

            # Add item to collected loot
            await crud_exploration.add_loot(
                db_session,
                exploration_id=exploration.id,
                item_name=item["name"],
                quantity=1,
                rarity=item.get("rarity", "Common"),
            )

            # Update stats
            await crud_exploration.update_stats(
                db_session,
                exploration_id=exploration.id,
                caps=caps,
                distance=random.randint(1, 5),
            )

        if event["type"] == "danger":
            # Update enemies encountered
            await crud_exploration.update_stats(
                db_session,
                exploration_id=exploration.id,
                enemies=1,
            )

        # Refresh exploration to get updated data
        await db_session.refresh(exploration)
        return exploration

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

        # Calculate experience based on distance and encounters
        experience = (exploration.total_distance * 10) + (exploration.enemies_encountered * 50)

        rewards_summary = {
            "caps": total_caps,
            "items": exploration.loot_collected,
            "experience": experience,
            "distance": exploration.total_distance,
            "enemies_defeated": exploration.enemies_encountered,
            "events_encountered": len(exploration.events),
        }

        return rewards_summary  # noqa: RET504

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

        # Calculate reduced experience
        base_experience = (exploration.total_distance * 10) + (exploration.enemies_encountered * 50)
        experience = int(base_experience * (progress / 100))

        rewards_summary = {
            "caps": total_caps,
            "items": exploration.loot_collected,
            "experience": experience,
            "distance": exploration.total_distance,
            "enemies_defeated": exploration.enemies_encountered,
            "events_encountered": len(exploration.events),
            "progress_percentage": progress,
            "recalled_early": True,
        }

        return rewards_summary  # noqa: RET504


# Singleton instance
wasteland_service = WastelandService()
