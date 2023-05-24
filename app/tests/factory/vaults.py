import random

from faker import Faker

fake = Faker()


def create_fake_vault():
    return {
        "name": random.randint(1, 100),
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
    }
