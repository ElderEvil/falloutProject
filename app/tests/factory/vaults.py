import random

from faker import Faker

fake = Faker()


def create_fake_vault():
    return {
        "name": str(random.randint(1, 1000)),
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        # "user_id": uuid4(),
    }
