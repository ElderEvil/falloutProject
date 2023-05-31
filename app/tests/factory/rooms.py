import random

from faker import Faker

from app.schemas.common import RoomType

fake = Faker()


def create_fake_room():
    return {
        "name": f"{fake.word().capitalize()} {fake.word().capitalize()}",
        "category": random.choice(list(RoomType)),
        "ability": random.choice(["S", "P", "E", "C", "I", "A", "L"]),
        "population_required": random.randint(12, 100),
        "base_cost": random.randint(100, 10_000),
        "incremental_cost": random.randint(25, 5_000),
        "tier": random.randint(1, 3),
        "max_tier": random.randint(1, 3),
        "t2_upgrade_cost": random.randint(500, 50_000),
        "t3_upgrade_cost": random.randint(1500, 150_000),
        "output": random.randint(1, 100),
        "size": random.randint(1, 9),
    }
