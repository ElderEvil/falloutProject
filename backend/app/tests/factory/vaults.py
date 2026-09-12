import random

from app.utils.place_seed import get_seeded_vault_numbers


def random_vault_number(low: int = 1, high: int = 999) -> int:
    """Random vault number excluding seeded NPC signal numbers (reserved)."""
    reserved = get_seeded_vault_numbers()
    choices = [n for n in range(low, high + 1) if n not in reserved]
    return random.choice(choices)


def create_fake_vault():
    return {
        "number": random_vault_number(1, 100),
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        "power": random.randint(1, 100),
        "food": random.randint(1, 100),
        "water": random.randint(1, 100),
    }
