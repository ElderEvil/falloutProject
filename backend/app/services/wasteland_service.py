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

        # Biome definitions with themed variations
        self.biomes = {
            "urban_ruins": {
                "name": "Urban Ruins",
                "description": "crumbling city buildings and broken streets",
                "enemies": ["Raider gang", "Feral Ghouls", "Giant Radroach swarm"],
                "loot_locations": ["collapsed apartment", "abandoned store", "rusted car", "old office building"],
            },
            "wasteland": {
                "name": "Wasteland",
                "description": "barren landscape with scattered debris",
                "enemies": ["Radscorpion", "Mole Rats", "Feral Dog pack"],
                "loot_locations": ["buried container", "wrecked truck", "old billboard base", "traveler's corpse"],
            },
            "industrial": {
                "name": "Industrial Zone",
                "description": "rusted factories and toxic waste",
                "enemies": ["group of Raiders", "Glowing Radroach swarm", "Giant Radscorpion"],
                "loot_locations": ["factory floor", "chemical storage", "worker's locker", "machinery bay"],
            },
            "suburban": {
                "name": "Suburbs",
                "description": "destroyed neighborhoods with intact houses",
                "enemies": ["Feral Dogs", "Looters", "Radroach nest"],
                "loot_locations": ["destroyed home", "garage safe", "backyard bunker", "neighbor's shed"],
            },
            "military": {
                "name": "Military Base",
                "description": "fortified military installation",
                "enemies": ["Sentry Bot", "Deathclaw", "Military Robots"],
                "loot_locations": ["armory locker", "command center", "bunker vault", "weapons cache"],
            },
        }

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

    def _get_current_biome(self, exploration: Exploration) -> dict:
        """Determine current biome based on exploration progress."""
        progress = exploration.progress_percentage()

        # Biome changes based on distance traveled
        if progress < 20:
            return self.biomes["urban_ruins"]
        if progress < 40:
            return self.biomes["suburban"]
        if progress < 60:
            return self.biomes["wasteland"]
        if progress < 80:
            return self.biomes["industrial"]
        return self.biomes["military"]

    def _generate_combat_event(self, exploration: Exploration) -> dict:
        """Generate combat event with stat-based outcomes."""
        strength = exploration.dweller_strength
        agility = exploration.dweller_agility
        endurance = exploration.dweller_endurance

        # Determine enemy type and difficulty
        enemy_types = [
            {"name": "Radroach swarm", "difficulty": 1, "min_damage": 5, "max_damage": 15},
            {"name": "Feral Dog pack", "difficulty": 2, "min_damage": 10, "max_damage": 20},
            {"name": "group of Raiders", "difficulty": 3, "min_damage": 15, "max_damage": 30},
            {"name": "Giant Radscorpion", "difficulty": 4, "min_damage": 20, "max_damage": 40},
            {"name": "Deathclaw", "difficulty": 5, "min_damage": 30, "max_damage": 50},
        ]

        # Select enemy based on time elapsed (harder enemies later)
        progress = exploration.progress_percentage()
        max_difficulty = 1 + int(progress / 25)  # 1-5 difficulty based on progress
        available_enemies = [e for e in enemy_types if e["difficulty"] <= max_difficulty]
        enemy = random.choice(available_enemies)

        # Calculate combat outcome based on strength + agility
        combat_power = strength + (agility // 2)
        success_chance = min(0.9, 0.3 + (combat_power * 0.06))  # 30-90% based on stats

        success = random.random() < success_chance

        if success:
            # Victory - minimal damage
            damage = max(1, enemy["min_damage"] - (endurance * 2))
            descriptions = [
                f"Defeated a {enemy['name']}! Took {damage} damage but emerged victorious.",
                f"Fought off a {enemy['name']} using superior combat skills. Health reduced by {damage}.",
                f"Successfully defended against a {enemy['name']} attack. Lost {damage} HP.",
            ]
            return {
                "type": "combat",
                "description": random.choice(descriptions),
                "health_loss": damage,
                "enemy": enemy["name"],
                "victory": True,
            }

        # Defeat/Struggle - significant damage
        damage = random.randint(enemy["min_damage"], enemy["max_damage"]) - (endurance * 1)
        damage = max(damage // 2, 1)  # Reduced but still significant
        descriptions = [
            f"Barely survived an encounter with a {enemy['name']}. Took {damage} damage retreating.",
            f"Fought desperately against a {enemy['name']}. Lost {damage} HP but escaped.",
            f"Wounded by a {enemy['name']} but managed to flee. Health reduced by {damage}.",
        ]
        return {
            "type": "combat",
            "description": random.choice(descriptions),
            "health_loss": damage,
            "enemy": enemy["name"],
            "victory": False,
        }

    def _generate_discovery_event(self, exploration: Exploration) -> dict:
        """Generate discovery/exploration event based on perception and intelligence."""
        perception = exploration.dweller_perception
        intelligence = exploration.dweller_intelligence
        biome = self._get_current_biome(exploration)

        # Discovery chance based on perception + intelligence
        discovery_power = perception + (intelligence // 2)
        quality_roll = random.random() + (discovery_power * 0.05)

        # Biome-specific discoveries
        biome_discoveries = {
            "Urban Ruins": {
                "great": [
                    f"Found an intact Pre-War bunker hidden beneath {biome['description']}!",
                    "Discovered a hidden weapons cache in an old police station.",
                    "Located an abandoned Vault-Tec facility with working technology.",
                ],
                "good": [
                    "Found a collapsed overpass with salvageable materials.",
                    "Discovered a mostly intact shopping mall with supplies.",
                    "Located an old subway station perfect for shelter.",
                ],
                "minor": [
                    "Noticed useful street signs for navigation.",
                    "Found a working water fountain in a building.",
                    "Spotted a safe route through the rubble.",
                ],
            },
            "Wasteland": {
                "great": [
                    "Discovered an untouched caravan wreck with supplies!",
                    "Found a hidden underground bunker from the war!",
                    "Located a working Pre-War radio beacon with valuable intel.",
                ],
                "good": [
                    "Found fresh water source in an old well.",
                    "Discovered a cave system perfect for shelter.",
                    "Located a traveler's stash buried in the sand.",
                ],
                "minor": [
                    "Spotted some edible desert plants.",
                    "Found tracks of other wasteland travelers.",
                    "Noticed landmarks for better navigation.",
                ],
            },
            "Industrial Zone": {
                "great": [
                    "Found intact machinery and valuable tech components!",
                    "Discovered a sealed warehouse full of Pre-War supplies!",
                    "Located a functional industrial robot with useful parts!",
                ],
                "good": [
                    "Found a workshop with usable tools.",
                    "Discovered chemical supplies that could be valuable.",
                    "Located an old foreman's office with supplies.",
                ],
                "minor": [
                    "Found some scrap metal worth collecting.",
                    "Spotted safe paths through the toxic areas.",
                    "Noticed functioning emergency lights.",
                ],
            },
            "Suburbs": {
                "great": [
                    "Discovered an untouched fallout shelter with supplies!",
                    "Found a garage with a working generator!",
                    "Located a neighbor's hidden gun collection!",
                ],
                "good": [
                    "Found a mostly intact home with supplies.",
                    "Discovered a backyard bunker with food.",
                    "Located a shed full of useful tools.",
                ],
                "minor": [
                    "Found some canned food in a pantry.",
                    "Spotted a safe house to rest in.",
                    "Noticed a cleared path between houses.",
                ],
            },
            "Military Base": {
                "great": [
                    "Breached a sealed armory with advanced weapons!",
                    "Found the command center with working terminals!",
                    "Discovered a vault with Pre-War military tech!",
                ],
                "good": [
                    "Located a barracks with military gear.",
                    "Found a medical bay with supplies.",
                    "Discovered a communications array.",
                ],
                "minor": [
                    "Found military rations that are still good.",
                    "Spotted patrol routes to avoid detection.",
                    "Located a map of the base layout.",
                ],
            },
        }

        biome_name = biome["name"]
        discoveries = biome_discoveries.get(biome_name, biome_discoveries["Wasteland"])

        if quality_roll > 1.2:  # Great discovery
            return {"type": "discovery", "description": random.choice(discoveries["great"]), "quality": "great"}
        if quality_roll > 0.8:  # Good discovery
            return {"type": "discovery", "description": random.choice(discoveries["good"]), "quality": "good"}
        # Minor discovery
        return {"type": "discovery", "description": random.choice(discoveries["minor"]), "quality": "minor"}

    def _generate_stealth_event(self, exploration: Exploration) -> dict:
        """Generate stealth/avoidance event based on agility and perception."""
        agility = exploration.dweller_agility
        perception = exploration.dweller_perception
        biome = self._get_current_biome(exploration)

        # Stealth power combines agility and perception
        stealth_power = agility + (perception // 2)
        success_chance = 0.4 + (stealth_power * 0.05)  # 40-90%

        # Biome-specific stealth scenarios
        biome_stealth = {
            "Urban Ruins": {
                "success": [
                    "Spotted a Raider patrol ahead and stealthily bypassed them through back alleys.",
                    "Heard gunfire nearby and found a safe route through abandoned buildings.",
                    "Noticed trip wires in a doorway and carefully avoided them.",
                    "Detected Ghoul activity ahead and quietly moved around them.",
                ],
                "failure": [
                    "Stepped on broken glass. Alerted nearby threats.",
                    "Accidentally triggered a car alarm. Drew unwanted attention.",
                    "Knocked over debris while moving through a building.",
                ],
            },
            "Wasteland": {
                "success": [
                    "Spotted Radscorpion tracks and detoured around their nest.",
                    "Heard gunfire in the distance and found alternate path.",
                    "Detected radiation storm approaching and found shelter in time.",
                    "Saw Deathclaw in the distance and quietly moved away.",
                ],
                "failure": [
                    "Stumbled into Mole Rat tunnels. Had to fight through.",
                    "Stepped on a brittle rock. Created noise that drew attention.",
                    "Failed to notice a sand pit trap. Took minor injuries.",
                ],
            },
            "Industrial Zone": {
                "success": [
                    "Spotted security robots and stealthily avoided their patrol routes.",
                    "Heard machinery activating and found safe path around it.",
                    "Noticed toxic gas leak ahead and detoured around it.",
                    "Detected automated turrets and snuck past them.",
                ],
                "failure": [
                    "Accidentally triggered an old alarm system. Drew threats.",
                    "Stepped on rusty metal. Made loud noise.",
                    "Failed to notice laser tripwire. Set off old security.",
                ],
            },
            "Suburbs": {
                "success": [
                    "Spotted looters ahead and quietly moved around them.",
                    "Heard Feral Dogs barking and found alternate route.",
                    "Noticed booby trap on a door and avoided it.",
                    "Detected Radroach nest and stealthily bypassed it.",
                ],
                "failure": [
                    "Stepped on creaky floorboards. Alerted nearby threats.",
                    "Knocked over old furniture. Made noise.",
                    "Failed to notice tripwire. Triggered trap mechanism.",
                ],
            },
            "Military Base": {
                "success": [
                    "Spotted Sentry Bot patrol and avoided detection.",
                    "Heard combat robots ahead and found safe infiltration route.",
                    "Noticed pressure plates and carefully avoided them.",
                    "Detected turret coverage zones and moved through blind spots.",
                ],
                "failure": [
                    "Accidentally triggered motion sensor. Alerted security.",
                    "Stepped into laser grid. Set off alarms.",
                    "Failed to notice camera. Security systems activated.",
                ],
            },
        }

        biome_name = biome["name"]
        scenarios = biome_stealth.get(biome_name, biome_stealth["Wasteland"])

        if random.random() < success_chance:
            # Successfully avoided danger
            return {"type": "exploration", "description": random.choice(scenarios["success"]), "danger_avoided": True}

        # Failed stealth - forced into minor conflict
        damage = max(1, 8 - agility)
        return {
            "type": "exploration",
            "description": random.choice(scenarios["failure"]),
            "danger_avoided": False,
            "health_loss": damage,
        }

    def _generate_survival_event(self, exploration: Exploration) -> dict:
        """Generate survival/endurance event."""
        endurance = exploration.dweller_endurance
        intelligence = exploration.dweller_intelligence

        # Survival challenge
        survival_power = endurance + (intelligence // 2)
        success_chance = 0.5 + (survival_power * 0.04)

        if random.random() < success_chance:
            # Successfully handled survival challenge
            successes = [
                "Found clean water source and refilled supplies.",
                "Located edible food in an abandoned store.",
                "Built temporary shelter from a radiation storm.",
                "Treated minor wounds using scavenged medical supplies.",
                "Rested in a secure location and recovered stamina.",
            ]
            return {"type": "rest", "description": random.choice(successes), "health_restored": random.randint(3, 8)}

        # Failed survival - took environmental damage
        failures = [
            "Caught in unexpected radiation burst. Took some rads.",
            "Ran low on clean water. Feeling dehydrated.",
            "Exposed to harsh wasteland weather. Feeling worn down.",
            "Contaminated supplies. Suffered minor radiation poisoning.",
        ]
        damage = max(1, 10 - endurance)
        return {"type": "danger", "description": random.choice(failures), "health_loss": damage}

    def _generate_loot_event(self, exploration: Exploration) -> dict:
        """Generate loot discovery event."""
        perception = exploration.dweller_perception
        luck = exploration.dweller_luck

        # Get current biome for location-specific loot spots
        biome = self._get_current_biome(exploration)

        # Generate loot based on luck
        loot_item, item_type = self._select_random_loot(luck)

        # Caps scale with perception and luck
        base_caps = random.randint(10, 30)
        caps_found = base_caps + (perception * 2) + (luck * 3)

        # Use biome-specific loot locations
        location = random.choice(biome["loot_locations"])
        description = f"Searched {location} and found {loot_item['name']} along with {caps_found} caps!"

        return {
            "type": "loot",
            "description": description,
            "loot": {
                "item": loot_item,
                "item_type": item_type,
                "caps": caps_found,
            },
        }

    def generate_event(self, exploration: Exploration) -> dict | None:  # noqa: PLR0911
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

        # Determine event type with weighted probabilities
        event_weights = {
            "loot": 30,  # 30% loot events
            "combat": 25,  # 25% combat
            "exploration": 20,  # 20% exploration/stealth
            "discovery": 15,  # 15% discovery
            "survival": 10,  # 10% survival
        }

        event_type = random.choices(list(event_weights.keys()), weights=list(event_weights.values()), k=1)[0]

        # Generate event based on type
        if event_type == "loot":
            return self._generate_loot_event(exploration)
        if event_type == "combat":
            return self._generate_combat_event(exploration)
        if event_type == "discovery":
            return self._generate_discovery_event(exploration)
        if event_type == "stealth":
            return self._generate_stealth_event(exploration)
        return self._generate_survival_event(exploration)

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

        # Handle combat events
        if event["type"] == "combat":
            exploration.enemies_encountered += 1

            # Apply health loss to dweller
            if event.get("health_loss"):
                from app.crud.dweller import dweller as dweller_crud

                dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
                damage = event["health_loss"]
                dweller_obj.health = max(1, dweller_obj.health - damage)  # Don't let health go to 0
                db_session.add(dweller_obj)

        # Handle danger events with health loss
        if event["type"] == "danger" and event.get("health_loss"):
            from app.crud.dweller import dweller as dweller_crud

            dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
            damage = event["health_loss"]
            dweller_obj.health = max(1, dweller_obj.health - damage)
            db_session.add(dweller_obj)

        # Handle exploration events with health loss
        if event["type"] == "exploration" and event.get("health_loss"):
            from app.crud.dweller import dweller as dweller_crud

            dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
            damage = event["health_loss"]
            dweller_obj.health = max(1, dweller_obj.health - damage)
            db_session.add(dweller_obj)

        # Handle rest events with health restoration
        if event["type"] == "rest" and event.get("health_restored"):
            from app.crud.dweller import dweller as dweller_crud

            dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
            healing = event["health_restored"]
            dweller_obj.health = min(dweller_obj.max_health, dweller_obj.health + healing)
            db_session.add(dweller_obj)

        # Update distance traveled for all events
        exploration.total_distance += random.randint(1, 3)

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
