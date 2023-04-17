import json
from enum import Enum

from Game.Items.Items import Item
from utilities.generic import Rarity

PREFIXES = [
    "Rusty",
    "Enhanced",
    "Hardened",
]


class WeaponType(str, Enum):
    Melee = "Melee"
    Gun = "Gun"
    Energy = "Energy"
    Heavy = "Heavy"


class WeaponSubtype(str, Enum):
    Blunt = "Blunt"
    Edged = "Edged"
    Pointed = "Pointed"

    Pistol = "Pistol"
    Rifle = "Rifle"
    Shotgun = "Shotgun"

    Automatic = "Automatic"
    Explosive = "Explosive"
    Flamer = "Flamer"


class Weapon(Item):
    weapon_type: WeaponType
    weapon_subtype: WeaponSubtype
    stat: str
    damage_range: tuple[int, int]
    prefix: str | None = None

    def __str__(self):
        return f"🔫{self.name}" \
               f" 💥{self.damage_range[0]}-{self.damage_range[1]}" \
               f" 🪙{self.value}" \
               f" 💎{self.rarity.name.title()}"


def generate_prefixes_and_modifiers(weapon_type, weapon_subtype):
    prefixes = {
        "Melee": {"Enhanced": 1.1, "Hardened": 1.2, "Serrated": 1.3},
        "Gun": {"Enhanced", "Hardened", "Armor Piercing"},
        "Energy": {"Focused", "Amplified", "Charged"},
        "Heavy": {"Enhanced", "Hardened", "Double-Barrel"}
    }

    return prefixes[weapon_type]


def load_weapons_from_json(json_file_path: str) -> list[Weapon]:
    with open(json_file_path) as json_file:
        weapon_data = json.load(json_file)

    value_by_rarity = {
        Rarity.common: 10,
        Rarity.rare: 100,
        Rarity.legendary: 500,
    }
    weapons = []
    for weapon_item in weapon_data:
        weapon = Weapon(**weapon_item, value=value_by_rarity[weapon_item["rarity"]])
        print(weapon)
        weapons.append(weapon)
        variations = []
        for prefix, modifier in zip(PREFIXES, (0.1, 1.1, 1.2)):
            name = f"{prefix} {weapon.name}"
            d_min, d_max = weapon.damage_range
            damage_range = (d_min, max(int(d_max * modifier), d_min))
            rarity, value = (Rarity.common, 10) if prefix == "Rusty" else (Rarity.rare, 100)
            variation = Weapon(
                weapon_type=weapon.weapon_type,
                weapon_subtype=weapon.weapon_subtype,
                name=name,
                prefix=prefix,
                stat=weapon.stat,
                damage_range=damage_range,
                rarity=rarity,
                value=value
            )
            print(variation)
            variations.append(variation)
        weapons.extend(variations)
    print(weapons)
    return weapons


load_weapons_from_json("weapons.json")
