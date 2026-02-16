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
        "overseer's_office",
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


def validate_target_entity(
    objective_type: str,
    target_entity: dict | None,
) -> list[str]:
    """Validate target_entity for an objective.

    Args:
        objective_type: Type of objective (collect, build, assign, train, reach)
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
            if resource_type not in VALID_RESOURCE_TYPES and resource_type != "any":
                errors.append(
                    f"Invalid resource_type '{resource_type}'. Must be one of: {', '.join(sorted(VALID_RESOURCE_TYPES))}, any"
                )

        item_type = target_entity.get("item_type")
        if item_type:
            if item_type not in VALID_ITEM_TYPES:
                errors.append(f"Invalid item_type '{item_type}'. Must be one of: {', '.join(sorted(VALID_ITEM_TYPES))}")

    elif objective_type == "reach":
        reach_type = target_entity.get("reach_type")
        if reach_type:
            valid_reach_types = frozenset({"dweller_count", "happiness"})
            if reach_type not in valid_reach_types:
                errors.append(f"Invalid reach_type '{reach_type}'. Must be one of: dweller_count, happiness")

    return errors
