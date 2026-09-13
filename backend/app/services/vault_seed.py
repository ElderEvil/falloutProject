"""Value objects used while seeding a newly created vault."""

from dataclasses import dataclass, field
from typing import Any

from app.core.enums import JunkTypeEnum, OutfitTypeEnum, RarityEnum, SPECIALEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.models import Room
from app.schemas.room import RoomCreate

# Living rooms are one slot; the workshops are three, so the workshops own the
# top floor's right side and the living rooms stay on the lower, single-slot rows.
BOOSTED_LIVING_ROOM_COORDINATES = ((16, 3), (19, 3), (22, 3), (25, 3))
BOOSTED_CRAFTING_ROOM_SPECS: tuple[tuple[str, int, int], ...] = (
    ("Weapon workshop", 7, 0),
    ("Outfit workshop", 16, 0),
)
BOOSTED_TRAINING_STATS = (
    SPECIALEnum.STRENGTH,
    SPECIALEnum.PERCEPTION,
    SPECIALEnum.ENDURANCE,
    SPECIALEnum.CHARISMA,
    SPECIALEnum.INTELLIGENCE,
    SPECIALEnum.AGILITY,
    SPECIALEnum.LUCK,
)
YOUTH_APPRENTICE_BIRTH_AGE_HOURS = 13
SEED_WEAPONS: list[dict[str, Any]] = [
    {
        "name": "Rusty Pistol",
        "rarity": RarityEnum.COMMON,
        "value": 50,
        "weapon_type": WeaponTypeEnum.GUN,
        "weapon_subtype": WeaponSubtypeEnum.PISTOL,
        "stat": "agility",
        "damage_min": 2,
        "damage_max": 5,
    },
    {
        "name": "Hunting Rifle",
        "rarity": RarityEnum.RARE,
        "value": 150,
        "weapon_type": WeaponTypeEnum.GUN,
        "weapon_subtype": WeaponSubtypeEnum.RIFLE,
        "stat": "perception",
        "damage_min": 5,
        "damage_max": 12,
    },
    {
        "name": "Sledgehammer",
        "rarity": RarityEnum.RARE,
        "value": 300,
        "weapon_type": WeaponTypeEnum.MELEE,
        "weapon_subtype": WeaponSubtypeEnum.BLUNT,
        "stat": "strength",
        "damage_min": 8,
        "damage_max": 15,
    },
    {
        "name": "Laser Pistol",
        "rarity": RarityEnum.LEGENDARY,
        "value": 500,
        "weapon_type": WeaponTypeEnum.ENERGY,
        "weapon_subtype": WeaponSubtypeEnum.PISTOL,
        "stat": "intelligence",
        "damage_min": 10,
        "damage_max": 20,
    },
]
SEED_OUTFITS: list[dict[str, Any]] = [
    {
        "name": "Vault Jumpsuit",
        "rarity": RarityEnum.COMMON,
        "value": 20,
        "outfit_type": OutfitTypeEnum.COMMON,
        "gender": None,
    },
    {
        "name": "Leather Armor",
        "rarity": RarityEnum.RARE,
        "value": 100,
        "outfit_type": OutfitTypeEnum.RARE,
        "gender": None,
    },
    {
        "name": "Metal Armor",
        "rarity": RarityEnum.RARE,
        "value": 250,
        "outfit_type": OutfitTypeEnum.RARE,
        "gender": None,
    },
    {
        "name": "T-51b Power Armor",
        "rarity": RarityEnum.LEGENDARY,
        "value": 1000,
        "outfit_type": OutfitTypeEnum.POWER_ARMOR,
        "gender": None,
    },
]
# Crafting materials a boosted vault starts with so item creation is testable
# from the first login. Covers every junk type the craftable catalog accepts
# (steel/leather/circuitry/cloth) across all three material rarities, enough for
# several common crafts plus rare and legendary ones. Built from junk.json.
BOOSTED_SEED_JUNK: tuple[tuple[JunkTypeEnum, RarityEnum, int], ...] = (
    (JunkTypeEnum.STEEL, RarityEnum.COMMON, 6),
    (JunkTypeEnum.LEATHER, RarityEnum.COMMON, 3),
    (JunkTypeEnum.CIRCUITRY, RarityEnum.COMMON, 6),
    (JunkTypeEnum.CLOTH, RarityEnum.COMMON, 3),
    (JunkTypeEnum.STEEL, RarityEnum.RARE, 3),
    (JunkTypeEnum.LEATHER, RarityEnum.RARE, 3),
    (JunkTypeEnum.CIRCUITRY, RarityEnum.RARE, 3),
    (JunkTypeEnum.CLOTH, RarityEnum.RARE, 3),
    (JunkTypeEnum.STEEL, RarityEnum.LEGENDARY, 3),
    (JunkTypeEnum.CIRCUITRY, RarityEnum.LEGENDARY, 3),
)
BOOSTED_LOADOUTS = (
    ("abraham-washington", "Lever-action rifle", "Abraham's relaxedwear", WeaponSubtypeEnum.RIFLE),
    ("allistair-tenpenny", "Hunting rifle", "Eulogy Jones' suit", WeaponSubtypeEnum.RIFLE),
    ("bittercup", "10mm pistol", "Bittercup's outfit", WeaponSubtypeEnum.PISTOL),
)


@dataclass(slots=True)
class PreparedRooms:
    infrastructure: list[RoomCreate]
    capacity: list[RoomCreate]
    production: list[RoomCreate]
    misc: list[RoomCreate]
    training: list[RoomCreate]
    arena: list[RoomCreate]
    crafting: list[RoomCreate] = field(default_factory=list)


@dataclass(slots=True)
class CreatedRooms:
    production: list[Room]
    training: list[Room]
    misc: list[Room]
    capacity: list[Room]
    arena: list[Room]
    crafting: list[Room] = field(default_factory=list)
