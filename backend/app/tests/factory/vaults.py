import random


def create_fake_vault():
    return {
        "number": random.randint(1, 100),
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        "power": random.randint(1, 100),
        "food": random.randint(1, 100),
        "water": random.randint(1, 100),
    }
