"""Value objects used while seeding a newly created vault."""

from dataclasses import dataclass, field
from typing import Any

from app.core.enums import (
    JunkTypeEnum,
    OutfitTypeEnum,
    RarityEnum,
    RelationshipTypeEnum,
    SPECIALEnum,
    WeaponSubtypeEnum,
    WeaponTypeEnum,
)
from app.models import Room
from app.schemas.room import RoomCreate

# The workshops are 3-segment rooms and own the top floor's right side. The living space is one fully merged room
# (size 9) plus a base room, which is what gives the boosted population its capacity.
BOOSTED_CRAFTING_ROOM_SPECS: tuple[tuple[str, int, int], ...] = (
    ("Weapon workshop", 7, 4),
    ("Outfit workshop", 16, 4),
)
BOOSTED_MERGED_LIVING_ROOM: tuple[str, int, int, int] = ("living room", 13, 3, 9)
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
# Seeded households: couples start committed so lineage reads immediately.
SEEDED_COUPLE_STAGE = RelationshipTypeEnum.MARRIED
SEEDED_COUPLE_AFFINITY = 95
SEEDED_FAMILIES_STANDARD = 1
SEEDED_FAMILIES_BOOSTED = 3
SEEDED_CHILD_AGE_HOURS = 6
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
        "charisma": 1,
        "luck": 1,
    },
    {
        "name": "Leather Armor",
        "rarity": RarityEnum.RARE,
        "value": 100,
        "outfit_type": OutfitTypeEnum.RARE,
        "gender": None,
        "strength": 1,
        "agility": 1,
    },
    {
        "name": "T-51b Power Armor",
        "rarity": RarityEnum.LEGENDARY,
        "value": 1000,
        "outfit_type": OutfitTypeEnum.POWER_ARMOR,
        "gender": None,
        "strength": 3,
        "perception": 1,
        "endurance": 2,
    },
]
# Crafting materials a boosted vault starts with so item creation is testable from first login: every junk type the
# craftable catalog accepts (steel/leather/circuitry/cloth) across all three rarities, enough for several common
# crafts plus rare/legendary ones. Built from junk.json.
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
# Spare hazard-team gear a boosted vault starts with so the fire/radiation responder team has outfits in storage.
# Names reference the outfit catalog (items/outfits/rare.json); stats are read from the catalog at seed time.
BOOSTED_SEED_OUTFITS: tuple[tuple[str, int], ...] = (
    ("Firefighter suit", 3),
    ("Hazmat suit", 3),
)
# Common +3 outfits keyed to each production room's stat: every boosted worker wears the matching one so live output
# matches BALANCE_PLAYTEST.md §10 (+3 turns a boosted stat-5 worker into effective 8). STR/AGI/INT in common.json, PER
# as the Armored vault suit in tiered.json.
BOOSTED_WORKER_OUTFITS: dict[SPECIALEnum, str] = {
    SPECIALEnum.STRENGTH: "Military fatigues",
    SPECIALEnum.AGILITY: "Handyman jumpsuit",
    SPECIALEnum.INTELLIGENCE: "Lab coat",
    SPECIALEnum.PERCEPTION: "Armored vault suit",
}
BOOSTED_LEGENDARY_DWELLER_COUNT = 3
# Seeded at 3: boosted population (33 non-legendary + 3 legendary = 36) fits living-space capacity 36; the fused
# size-6 generator's crew reuses the same slots. Pets start in storage unassigned; names must exist in the pet
# art/effect catalog or the seed silently produces art-less, effect-less pets.
BOOSTED_SEED_PETS: tuple[tuple[str, RarityEnum], ...] = (
    ("Dogmeat (Fallout 4)", RarityEnum.LEGENDARY),
    ("CX404", RarityEnum.LEGENDARY),
    ("Baby Deathclaw", RarityEnum.LEGENDARY),
    ("Yao Guai Cub", RarityEnum.RARE),
    ("Vault-Tec Parrot", RarityEnum.RARE),
)
# A boosted start equips these on its legendary roster; the remaining seed pet stays in storage so the equip flow is
# still available immediately.
BOOSTED_EQUIPPED_PETS: tuple[str, ...] = ("Dogmeat (Fallout 4)", "CX404")


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
