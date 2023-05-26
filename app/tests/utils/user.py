from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate, UserUpdate
from app.tests.utils.utils import random_lower_string


async def user_authentication_headers(
    *,
    client: AsyncClient,
    email: str,
    password: str,
) -> dict[str, str]:
    data = {"username": email, "password": password}

    async with client as ac:
        response = await ac.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = response.json()
    auth_token = response["access_token"]
    return {"Authorization": f"Bearer {auth_token}"}


async def authentication_token_from_email(
    *,
    client: AsyncClient,
    email: str,
    db: AsyncSession,
) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = await crud.user.get_by_email(db, email=email)
    if not user:
        user_in_create = UserCreate(username=email, email=email, password=password)
        user = await crud.user.create(db, obj_in=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        user = await crud.user.update(db, db_obj=user, obj_in=user_in_update)

    return await user_authentication_headers(client=client, email=email, password=password)
