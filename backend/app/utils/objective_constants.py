"""Constants for objective target_entity validation.

This module provides validation for objective target_entity values to ensure
they match actual game data (rooms, resources, etc.).
"""

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
        "rare_weapon",
        "rare_outfit",
    }
)

# Valid reach types for reach objectives
VALID_REACH_TYPES = frozenset({"dweller_count", "population", "level"})

# Map from objective room_type values to valid room names (for normalization)
ROOM_TYPE_ALIASES: dict[str, str] = {
    "living_quarters": "living_room",
    "livingquarter": "living_room",
    "quarters": "living_room",
    "storage": "storage_room",
    "power_plant": "power_generator",
    "powerplant": "power_generator",
    "water": "water_treatment",
    "water_purifier": "water_purification",
    "nuclear": "nuclear_reactor",
    "garden": "garden",
}

# Map from resource type aliases to canonical names
RESOURCE_ALIASES: dict[str, str] = {
    # Capitalization variants
    "caps": "caps",
    "food": "food",
    "water": "water",
    "power": "power",
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

# Map from item type aliases to canonical names
ITEM_ALIASES: dict[str, str] = {
    # Plural variants
    "weapons": "weapon",
    "outfits": "outfit",
    "stimpaks": "stimpak",
    "radaways": "radaway",
    "junks": "junk",
    "rare_weapons": "rare_weapon",
    "rare_outfits": "rare_outfit",
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
    "legendary_weapon": "rare_weapon",
    "legendary_outfit": "rare_outfit",
}


def normalize_room_type(room_type: str | None) -> str | None:
    """Normalize a room type string to valid snake_case.

    Args:
        room_type: Room type string (e.g., "Living room", "living_room", "living quarters")

    Returns:
        Normalized room type in snake_case, or None if invalid
    """
    if not room_type:
        return None

    # Convert to lowercase and replace spaces/hyphens with underscores
    normalized = room_type.lower().replace(" ", "_").replace("-", "_")

    # Check aliases first
    if normalized in ROOM_TYPE_ALIASES:
        return ROOM_TYPE_ALIASES[normalized]

    # If already valid, return it
    if normalized in VALID_ROOM_TYPES:
        return normalized

    return None


def normalize_resource_type(resource_type: str | None) -> str | None:
    """Normalize a resource type string to valid snake_case.

    Args:
        resource_type: Resource type string (e.g., "Caps", "power", "Stimpaks")

    Returns:
        Normalized resource type in snake_case, or None if invalid
    """
    if not resource_type:
        return None

    # Convert to lowercase and replace spaces/hyphens with underscores
    normalized = resource_type.lower().replace(" ", "_").replace("-", "_")

    # Check aliases first
    if normalized in RESOURCE_ALIASES:
        return RESOURCE_ALIASES[normalized]

    # If already valid, return it
    if normalized in VALID_RESOURCE_TYPES:
        return normalized

    return None


def normalize_item_type(item_type: str | None) -> str | None:
    """Normalize an item type string to valid snake_case.

    Args:
        item_type: Item type string (e.g., "Weapons", "outfits", "Rare Weapons")

    Returns:
        Normalized item type in snake_case, or None if invalid
    """
    if not item_type:
        return None

    # Convert to lowercase and replace spaces/hyphens with underscores
    normalized = item_type.lower().replace(" ", "_").replace("-", "_")

    # Check aliases first
    if normalized in ITEM_ALIASES:
        return ITEM_ALIASES[normalized]

    # If already valid, return it
    if normalized in VALID_ITEM_TYPES:
        return normalized

    return None


def validate_target_entity(
    objective_type: str | None,
    target_entity: dict | None,
) -> list[str]:
    """Validate target_entity for an objective.

    Args:
        objective_type: Type of objective (collect, build, reach)
        target_entity: Target entity dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if target_entity is None:
        return errors

    if objective_type == "build":
        room_type = target_entity.get("room_type")
        if room_type:
            # Allow wildcards
            if room_type in ("*", "any"):
                return errors
            normalized = normalize_room_type(room_type)
            if normalized is None:
                errors.append(f"Invalid room_type '{room_type}'. Must be one of: {', '.join(sorted(VALID_ROOM_TYPES))}")

    elif objective_type == "collect":
        resource_type = target_entity.get("resource_type")
        if resource_type:
            # Allow wildcards
            if resource_type not in ("*", "any"):
                normalized = normalize_resource_type(resource_type)
                if normalized is None:
                    valid_resources = ", ".join(sorted(VALID_RESOURCE_TYPES))
                    errors.append(f"Invalid resource_type '{resource_type}'. Must be one of: {valid_resources}, any")

        item_type = target_entity.get("item_type")
        if item_type:
            normalized = normalize_item_type(item_type)
            if normalized is None:
                valid_items = ", ".join(sorted(VALID_ITEM_TYPES))
                errors.append(f"Invalid item_type '{item_type}'. Must be one of: {valid_items}")

    elif objective_type == "reach":
        reach_type = target_entity.get("reach_type")
        if reach_type and reach_type not in VALID_REACH_TYPES:
            valid_reach = ", ".join(sorted(VALID_REACH_TYPES))
            errors.append(f"Invalid reach_type '{reach_type}'. Must be one of: {valid_reach}")

    return errors
