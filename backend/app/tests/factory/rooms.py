import random

from faker import Faker

from app.schemas.common import RoomTypeEnum
from app.schemas.dweller import LETTER_TO_STAT
from app.tests.utils.utils import get_name_two_words

fake = Faker()


def create_fake_room():
    return {
        "name": get_name_two_words(),
        "category": random.choice(list(RoomTypeEnum)),
        "ability": LETTER_TO_STAT[random.choice(["S", "P", "E", "C", "I", "A", "L"])].capitalize(),
        "population_required": random.randint(12, 100),
        "base_cost": random.randint(100, 10_000),
        "incremental_cost": random.randint(25, 5_000),
        "tier": 1,
        "t2_upgrade_cost": random.randint(500, 50_000),
        "t3_upgrade_cost": random.randint(1_500, 150_000),
        "output": str(random.randint(1, 100)),
        "size_min": random.randint(1, 3),
        "size_max": random.randint(6, 9),
    }
