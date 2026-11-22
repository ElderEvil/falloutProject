"""Constants and validation for objective target_entity values against actual game data."""

from app.core.enums import JunkTypeEnum

# Valid room types for build objectives (snake_case, matching room names)
VALID_ROOM_TYPES = frozenset(
    {
        "vault_door",
        "elevator",
        "living_room",
        "power_generator",
        "diner",
        "water_treatment",
        "storage_room",
        "medbay",
        "science_lab",
        "overseers_office",
        "radio_studio",
        "weapon_workshop",
        "weight_room",
        "athletics_room",
        "armory",
        "classroom",
        "outfit_workshop",
        "fitness_room",
        "lounge",
        "theme_workshop",
        "game_room",
        "barbershop",
        "nuclear_reactor",
        "garden",
        "water_purification",
        "nuka_cola_bottler",
    }
)

# Valid resource types for collect objectives
VALID_RESOURCE_TYPES = frozenset(
    {
        "caps",
        "food",
        "water",
        "power",
        "stimpak",
        "radaway",
    }
)

# Valid item types for collect objectives
VALID_ITEM_TYPES = frozenset(
    {
        "weapon",
        "outfit",
        "stimpak",
        "radaway",
        "junk",
    }
)

# Junk materials a collect objective may name. The catalog is the authority.
VALID_JUNK_TYPES = frozenset(member.value for member in JunkTypeEnum)

# Collect source a template may require. Only wasteland loot is stamped with a source today.
WASTELAND_LOOT_SOURCE = "wasteland"
VALID_COLLECT_SOURCES = frozenset({WASTELAND_LOOT_SOURCE})

VALID_REACH_TYPES = frozenset({"dweller_count", "population", "level"})

# Valid rarities for scrap objectives
VALID_RARITIES = frozenset({"common", "rare", "legendary"})

# Map from objective room_type values to valid room names (for normalization)
ROOM_TYPE_ALIASES: dict[str, str] = {
    "living_quarters": "living_room",
    "living_quarter": "living_room",
    "livingquarter": "living_room",
    "quarters": "living_room",
    "storage": "storage_room",
    "power_plant": "power_generator",
    "powerplant": "power_generator",
    "water": "water_treatment",
    "water_purifier": "water_purification",
    "nuclear": "nuclear_reactor",
    "garden": "garden",
    "overseer's_office": "overseers_office",
}

RESOURCE_ALIASES: dict[str, str] = {
    # Capitalization variants
    "caps": "caps",
    "food": "food",
    "water": "water",
    "power": "power",
    "stimpack": "stimpak",
    "stimpak": "stimpak",
    "radaway": "radaway",
    # Common aliases
    "cap": "caps",
    "money": "caps",
    "currency": "caps",
    "nuka_cola": "caps",
    "nukacola": "caps",
    "electricity": "power",
    "energy": "power",
    "stim": "stimpak",
    "stimpaks": "stimpak",
    "stims": "stimpak",
    "rad_away": "radaway",
    "radaways": "radaway",
    "rads": "radaway",
}

ITEM_ALIASES: dict[str, str] = {
    "stimpack": "stimpak",
    # Plural variants
    "weapons": "weapon",
    "outfits": "outfit",
    "stimpaks": "stimpak",
    "radaways": "radaway",
    "junks": "junk",
    # Common aliases
    "gun": "weapon",
    "guns": "weapon",
    "rifle": "weapon",
    "pistol": "weapon",
    "armor": "outfit",
    "clothes": "outfit",
    "clothing": "outfit",
    "suit": "outfit",
    "scrap": "junk",
    "materials": "junk",
}


def normalize_room_type(room_type: str | None) -> str | None:
    """Normalize a room type string to snake_case, or None if invalid."""
    if not room_type:
        return None

    normalized = room_type.lower().replace(" ", "_").replace("-", "_")

    if normalized in ROOM_TYPE_ALIASES:
        return ROOM_TYPE_ALIASES[normalized]

    if normalized in VALID_ROOM_TYPES:
        return normalized

    return None


def normalize_resource_type(resource_type: str | None) -> str | None:
    """Normalize a resource type string to snake_case, or None if invalid."""
    if not resource_type:
        return None

    normalized = resource_type.lower().replace(" ", "_").replace("-", "_")

    if normalized in RESOURCE_ALIASES:
        return RESOURCE_ALIASES[normalized]

    if normalized in VALID_RESOURCE_TYPES:
        return normalized

    return None


def normalize_item_type(item_type: str | None) -> str | None:
    """Normalize an item type string to snake_case, or None if invalid."""
    if not item_type:
        return None

    normalized = item_type.lower().replace(" ", "_").replace("-", "_")

    if normalized in ITEM_ALIASES:
        return ITEM_ALIASES[normalized]

    if normalized in VALID_ITEM_TYPES:
        return normalized

    return None


def _validate_room_type(room_type: str | None) -> list[str]:
    """Validate a room type value."""
    if not room_type or room_type in ("*", "any"):
        return []
    if normalize_room_type(room_type) is None:
        return [f"Invalid room_type '{room_type}'. Must be one of: {', '.join(sorted(VALID_ROOM_TYPES))}"]
    return []


def _validate_resource_type(resource_type: str | None) -> list[str]:
    """Validate a resource type value."""
    if not resource_type or resource_type in ("*", "any"):
        return []
    if normalize_resource_type(resource_type) is None:
        return [
            f"Invalid resource_type '{resource_type}'. Must be one of: {', '.join(sorted(VALID_RESOURCE_TYPES))}, any"
        ]
    return []


def _validate_item_type(item_type: str | None) -> list[str]:
    """Validate an item type value."""
    if not item_type or item_type in ("*", "any"):
        return []
    if normalize_item_type(item_type) is None:
        return [f"Invalid item_type '{item_type}'. Must be one of: {', '.join(sorted(VALID_ITEM_TYPES))}"]
    return []


def _validate_junk_type(junk_type: str | None, item_type: str | None) -> list[str]:
    """Validate an optional junk material filter on a collect objective."""
    if not junk_type:
        return []
    if normalize_item_type(item_type or "") != "junk":
        return ["junk_type requires item_type 'junk'"]
    if str(junk_type).lower() not in VALID_JUNK_TYPES:
        return [f"Invalid junk_type '{junk_type}'. Must be one of: {', '.join(sorted(VALID_JUNK_TYPES))}"]
    return []


def _validate_collect_source(source: str | None) -> list[str]:
    """Validate an optional collect source restriction."""
    if not source:
        return []
    if str(source).lower() not in VALID_COLLECT_SOURCES:
        return [f"Invalid source '{source}'. Must be one of: {', '.join(sorted(VALID_COLLECT_SOURCES))}"]
    return []


def _validate_reach_type(reach_type: str | None) -> list[str]:
    """Validate a reach type value."""
    if not reach_type or reach_type in VALID_REACH_TYPES:
        return []
    return [f"Invalid reach_type '{reach_type}'. Must be one of: {', '.join(sorted(VALID_REACH_TYPES))}"]


def _validate_rarity(rarity: str | None) -> list[str]:
    """Validate a rarity value."""
    if not rarity or rarity in ("*", "any"):
        return []
    if str(rarity).lower() not in VALID_RARITIES:
        return [f"Invalid rarity '{rarity}'. Must be one of: {', '.join(sorted(VALID_RARITIES))}, any"]
    return []


def validate_target_entity(
    objective_type: str | None,
    target_entity: dict | None,
) -> list[str]:
    """Validate an objective's target_entity; returns a list of errors (empty if valid)."""
    if target_entity is None:
        return []

    validators = {
        "build": lambda: _validate_room_type(target_entity.get("room_type")),
        "collect": lambda: (
            _validate_resource_type(target_entity.get("resource_type"))
            + _validate_item_type(target_entity.get("item_type"))
            + _validate_junk_type(target_entity.get("junk_type"), target_entity.get("item_type"))
            + _validate_collect_source(target_entity.get("source"))
        ),
        "reach": lambda: _validate_reach_type(target_entity.get("reach_type")),
        "equip": lambda: (
            [] if target_entity.get("item_type") in {"weapon", "outfit"} else ["Equipment requires weapon or outfit"]
        ),
        "scrap": lambda: (
            _validate_item_type(target_entity.get("item_type")) + _validate_rarity(target_entity.get("rarity"))
        ),
    }

    validator = validators.get(objective_type or "")
    return validator() if validator else []
