"""Value objects used while seeding a newly created vault."""

from dataclasses import dataclass

from app.core.enums import OutfitTypeEnum, RarityEnum, SPECIALEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.models import Room
from app.schemas.room import RoomCreate

BOOSTED_LIVING_ROOM_COORDINATES = ((4, 3), (5, 3), (3, 3), (7, 3), (1, 3), (2, 3))
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
SEED_WEAPONS = [
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
SEED_OUTFITS = [
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


@dataclass(slots=True)
class CreatedRooms:
    production: list[Room]
    training: list[Room]
    misc: list[Room]
    capacity: list[Room]
    arena: list[Room]
