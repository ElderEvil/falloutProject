import math

from app.schemas.common import RoomTypeEnum

# Map internal room names (from rooms.json) to asset keys (from wiki filenames)
ROOM_NAME_TO_ASSET_KEY = {
    "Vault Door": "Vault Door Adv",  # Special case
    "Elevator": "Elevator",  # Special case - no tier/size variants
    "Living room": "Living Quarters",
    "Power Generator": "Power",
    "Diner": "Diner",
    "Water Treatment": "Water1",
    "Storage room": "Storage",
    "Medbay": "Medbay",
    "Science Lab": "Scilab",
    "Overseer's Office": "Overseers Office",  # Special case - fixed size
    "Radio studio": "Radio",
    "Weapon workshop": "Weapon Workshop",  # Special case - different naming
    "Weight room": "Weight Room",
    "Athletics room": "Athletics",
    "Armory": "Armory",
    "Classroom": "Classroom",
    "Outfit workshop": "Outfit Crafting",  # Special case - different naming
    "Fitness room": "Fitness",
    "Lounge": "Lounge",
    "Theme workshop": "Theme Crafting",  # Special case - different naming
    "Game room": "Game Room",
    "Barbershop": "Barber",  # Special case - different naming
    "Nuclear reactor": "Nuclear Reactor",
    "Garden": "Garden",
    "Water purification": "Water Purification",
    "Nuka-Cola bottler": "Bottler",
}

# Rooms that don't follow the tier-segment pattern
SPECIAL_CASE_ROOMS = {
    "Elevator": "FOS Elevator icon.png",
    "Vault Door": "Vault Door Adv.png",
    "Barbershop": "FOS Barber 1.png",  # Only has 2 tiers
}

# Workshops use different naming (no tier-segment)
WORKSHOP_ROOMS = ["Weapon workshop", "Outfit workshop", "Theme workshop"]

ROOM_TYPE_TO_DEFAULT_NAME = {
    RoomTypeEnum.PRODUCTION: "Power Generator",
    RoomTypeEnum.CAPACITY: "Living room",
    RoomTypeEnum.TRAINING: "Weight room",
    RoomTypeEnum.CRAFTING: "Weapon workshop",
    RoomTypeEnum.THEME: "Theme workshop",
    RoomTypeEnum.QUESTS: "Overseer's Office",
    RoomTypeEnum.MISC: "Elevator",
}


def get_room_image_url(room_name: str, tier: int = 1, size: int = 3) -> str | None:
    """
    Generate the image URL for a room based on its name, tier, and size.

    Args:
        room_name: Internal room name (e.g., "Power Generator", "Living room")
        tier: Room tier/level (1-3)
        size: Room size (3, 6, or 9)

    Returns:
        URL path to the room image, or None if not found

    Examples:
        >>> get_room_image_url("Power Generator", tier=1, size=3)
        '/static/room_images/FOS Power 1-1.png'
        >>> get_room_image_url("Living room", tier=2, size=6)
        '/static/room_images/FOS Living Quarters 2-2.png'
    """
    # Handle special cases first
    if room_name in SPECIAL_CASE_ROOMS:
        return f"/static/room_images/{SPECIAL_CASE_ROOMS[room_name]}"

    # Get asset key
    asset_key = ROOM_NAME_TO_ASSET_KEY.get(room_name)
    if not asset_key:
        return None

    # Handle workshops (different naming pattern)
    if room_name in WORKSHOP_ROOMS:
        # Workshops use just tier number: "FOS Weapon Workshop 1.png"
        return f"/static/room_images/FOS {asset_key} {tier}.png"

    # Handle Overseer's Office (fixed size, only tier varies)
    if room_name == "Overseer's Office":
        return f"/static/room_images/FOS {asset_key} {tier}.png"

    # Calculate segment from size (3->1, 6->2, 9->3)
    segment = math.ceil(size / 3)

    # Standard pattern: "FOS {Asset_Key} {tier}-{segment}.png"
    return f"/static/room_images/FOS {asset_key} {tier}-{segment}.png"


def get_room_image(room_name: str) -> str | None:
    """
    Legacy function - get default tier 1, size 3 image.
    Use get_room_image_url() for dynamic tier/size support.
    """
    return get_room_image_url(room_name, tier=1, size=3)
