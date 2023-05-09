import random

import pytest


@pytest.fixture()
def junk_data():
    return {
        "name": "Test Junk",
        "rarity": random.choice(["Common", "Rare", "Legendary"]),  # noqa: S311
        "value": random.randint(1, 1000),  # noqa: S311
    }
