"""Loot selection and rewards calculations."""

import random

from app.core.game_config import game_config
from app.schemas.exploration_event import ItemSchema, JunkSchema, OutfitSchema, WeaponSchema
from app.services.exploration import data_loader


class LootCalculator:
    """Handles loot selection and caps rewards."""

    def calculate_luck_multiplier(self, luck: int) -> float:
        """
        Calculate loot quality multiplier based on luck stat.

        Args:
            luck: Luck stat (1-10)

        Returns:
            Multiplier (0.5 to 2.0)
        """
        cfg = game_config.exploration
        # Linear interpolation: Luck 1 = 0.5x, Luck 10 = 2.0x
        return cfg.luck_multiplier_min + (luck - 1) * ((cfg.luck_multiplier_max - cfg.luck_multiplier_min) / 9)

    def get_rarity_weights(self, luck: int) -> dict[str, float]:
        """
        Get rarity weights adjusted by luck stat.

        Args:
            luck: Luck stat (1-10)

        Returns:
            Dict of rarity weights {Common, Rare, Legendary}
        """
        cfg = game_config.exploration

        # Higher luck = better rarity distribution
        if luck >= 8:
            return {"Common": 50.0, "Rare": 35.0, "Legendary": 15.0}
        if luck >= 6:
            return {"Common": 60.0, "Rare": 30.0, "Legendary": 10.0}
        if luck >= 4:
            return {
                "Common": cfg.rarity_common_base,
                "Rare": cfg.rarity_rare_base,
                "Legendary": cfg.rarity_legendary_base,
            }
        return {"Common": 80.0, "Rare": 18.0, "Legendary": 2.0}

    def select_random_weapon(self, luck: int) -> WeaponSchema:
        """Select a random weapon based on luck-adjusted rarity."""
        weapons = data_loader.load_weapons()
        if not weapons:
            return WeaponSchema(
                name="Rusty Pipe",
                rarity="Common",
                value=10,
                weapon_type="Melee",
                weapon_subtype="Blunt",
                stat="strength",
                damage_min=1,
                damage_max=3,
            )

        rarity_weights = self.get_rarity_weights(luck)
        rarity = random.choices(
            list(rarity_weights.keys()),
            weights=list(rarity_weights.values()),
            k=1,
        )[0]

        weapons_of_rarity = [w for w in weapons if w.get("rarity") == rarity]
        if not weapons_of_rarity:
            weapons_of_rarity = weapons

        return WeaponSchema(**random.choice(weapons_of_rarity))

    def select_random_outfit(self, luck: int) -> OutfitSchema:
        """Select a random outfit based on luck-adjusted rarity."""
        outfits = data_loader.load_outfits()
        if not outfits:
            return OutfitSchema(name="Vault Suit", rarity="Common", value=10, outfit_type="Common Outfit")

        rarity_weights = self.get_rarity_weights(luck)
        rarity = random.choices(
            list(rarity_weights.keys()),
            weights=list(rarity_weights.values()),
            k=1,
        )[0]

        outfits_of_rarity = [o for o in outfits if o.get("rarity") == rarity]
        if not outfits_of_rarity:
            outfits_of_rarity = outfits

        return OutfitSchema(**random.choice(outfits_of_rarity))

    def select_random_junk(self, luck: int) -> JunkSchema:
        """Select a random junk item based on luck-adjusted rarity."""
        junk_items = data_loader.load_junk_items()
        if not junk_items:
            return JunkSchema(name="Bottle Cap", value=1, rarity="Common")

        rarity_weights = self.get_rarity_weights(luck)
        rarity = random.choices(
            list(rarity_weights.keys()),
            weights=list(rarity_weights.values()),
            k=1,
        )[0]

        items_of_rarity = [item for item in junk_items if item.get("rarity") == rarity]
        if not items_of_rarity:
            items_of_rarity = junk_items

        return JunkSchema(**random.choice(items_of_rarity))

    def select_random_loot(self, luck: int) -> tuple[ItemSchema, str]:
        """
        Select a random loot item based on luck.

        Args:
            luck: Luck stat (1-10)

        Returns:
            Tuple of (item_schema, item_type) where item_type is 'junk', 'weapon', or 'outfit'
        """
        cfg = game_config.exploration

        # Determine item type with luck-adjusted weights
        if luck >= 8:
            type_weights = {"junk": 50.0, "weapon": 30.0, "outfit": 20.0}
        elif luck >= 6:
            type_weights = {"junk": 55.0, "weapon": 28.0, "outfit": 17.0}
        else:
            type_weights = {
                "junk": cfg.loot_type_junk,
                "weapon": cfg.loot_type_weapon,
                "outfit": cfg.loot_type_outfit,
            }

        item_type = random.choices(
            list(type_weights.keys()),
            weights=list(type_weights.values()),
            k=1,
        )[0]

        if item_type == "weapon":
            return (self.select_random_weapon(luck), "weapon")
        if item_type == "outfit":
            return (self.select_random_outfit(luck), "outfit")

        return (self.select_random_junk(luck), "junk")

    def calculate_caps_found(self, perception: int, luck: int) -> int:
        """
        Calculate caps found based on perception and luck.

        Args:
            perception: Perception stat (1-10)
            luck: Luck stat (1-10)

        Returns:
            Number of caps found
        """
        cfg = game_config.exploration
        base_caps = random.randint(cfg.caps_base_min, cfg.caps_base_max)
        return base_caps + (perception * cfg.caps_perception_multiplier) + (luck * cfg.caps_luck_multiplier)


# Singleton instance
loot_calculator = LootCalculator()
