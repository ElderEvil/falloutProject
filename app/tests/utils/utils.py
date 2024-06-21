import random
import string

from faker import Faker
from httpx import AsyncClient

from app.core.config import settings
from app.schemas.common import GenderEnum, RarityEnum
from app.schemas.dweller import LETTER_TO_STAT, STATS_RANGE_BY_RARITY

fake = Faker()


def get_gender_based_name(gender: GenderEnum):
    return fake.first_name_male() if gender.value == "Male" else fake.first_name_female()


def get_name_two_words():
    return f"{fake.word().capitalize()} {fake.word().capitalize()}"


def get_stats_by_rarity(rarity: RarityEnum):
    min_value, max_value = STATS_RANGE_BY_RARITY[rarity]
    return {stat: random.randint(min_value, max_value) for stat in LETTER_TO_STAT.values()}


def random_lower_string(k: int = 32) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=k))


async def get_superuser_token_headers(async_client: AsyncClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER_EMAIL,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    response = await async_client.post("/login/access-token", data=login_data)
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}
