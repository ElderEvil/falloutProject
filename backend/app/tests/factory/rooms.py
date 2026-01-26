import random

from faker import Faker

from app.schemas.common import RoomTypeEnum
from app.schemas.dweller import LETTER_TO_STAT
from app.utils.room_assets import ROOM_NAME_TO_ASSET_KEY, get_room_image_url

fake = Faker()


def create_fake_room():
    # Pick a real room name from our assets if possible
    room_name = random.choice(list(ROOM_NAME_TO_ASSET_KEY.keys()))
    tier = random.randint(1, 3)

    # Generate size_min and size_max first
    size_min = random.randint(1, 3)
    size_max = random.randint(6, 9)

    # Ensure size is within the valid range
    valid_sizes = [s for s in [3, 6, 9] if size_min <= s <= size_max]
    # Fallback: use size_min if no valid sizes in [3, 6, 9]
    size = size_min if not valid_sizes else random.choice(valid_sizes)

    image_url = get_room_image_url(room_name, tier=tier, size=size)

    return {
        "name": room_name,
        "category": random.choice(list(RoomTypeEnum)),
        "ability": LETTER_TO_STAT[random.choice(["S", "P", "E", "C", "I", "A", "L"])],
        "population_required": random.randint(12, 100),
        "base_cost": random.randint(100, 10_000),
        "incremental_cost": random.randint(25, 5_000),
        "tier": tier,
        "t2_upgrade_cost": random.randint(500, 50_000),
        "t3_upgrade_cost": random.randint(1_500, 150_000),
        "output": random.randint(1, 100),
        "size_min": size_min,
        "size_max": size_max,
        "size": size,
        "image_url": image_url,
    }
