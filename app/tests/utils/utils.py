import random
import string

from httpx import AsyncClient

from app.core.config import settings


def random_lower_string(k: int = 32) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=k))


async def get_superuser_token_headers(client: AsyncClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER_EMAIL,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    async with AsyncClient() as ac:
        response = await ac.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}
