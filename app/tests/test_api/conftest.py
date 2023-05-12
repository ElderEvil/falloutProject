import random

import pytest

from app.schemas.common import JunkType
from app.tests.utils.utils import random_lower_string


@pytest.fixture()
def junk_data():
    return {
        "name": random_lower_string(16).capitalize(),
        "rarity": random.choice(["Common", "Rare", "Legendary"]),  # noqa: S311
        "value": random.randint(1, 1000),  # noqa: S311
        "junk_type": random.choice(list(JunkType)),  # noqa: S311
        "description": random_lower_string(32),
    }
