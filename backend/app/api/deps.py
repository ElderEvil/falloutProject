from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import UUID4, ValidationError
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.db.session import get_async_session
from app.models.user import User
from app.models.vault import Vault
from app.schemas.token import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
)


async def get_redis_client():
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield redis_client
    finally:
        await redis_client.close()


async def get_current_user(
    db_session: AsyncSession = Depends(get_async_session),
    token: str = Depends(reusable_oauth2),
) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
        user_id = UUID(token_data.sub)
    except (JWTError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from e
    user = await crud.user.get(db_session=db_session, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(current_user: CurrentUser) -> User:
    if not crud.user.is_active(current_user):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


async def get_current_active_superuser(current_user: CurrentActiveUser) -> User:
    if not crud.user.is_superuser(current_user):
        raise HTTPException(
            status_code=400,
            detail="The user doesn't have enough privileges",
        )
    return current_user


CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]


async def get_user_vault_or_403(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: AsyncSession = Depends(get_async_session),
) -> Vault:
    """
    Verify that the user has access to the specified vault.

    Returns the vault if user owns it or is a superuser.
    Raises 403 HTTPException if user doesn't have access.
    """
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    # Check if user owns the vault or is a superuser
    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )

    return vault


async def verify_dweller_access(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: AsyncSession = Depends(get_async_session),
) -> None:
    """Verify user has access to the vault containing the dweller."""
    dweller = await crud.dweller.get(db_session, dweller_id)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")

    await get_user_vault_or_403(dweller.vault_id, user, db_session)


async def verify_room_access(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: AsyncSession = Depends(get_async_session),
) -> None:
    """Verify user has access to the vault containing the room."""
    room = await crud.room.get(db_session, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    await get_user_vault_or_403(room.vault_id, user, db_session)


async def verify_exploration_access(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: AsyncSession = Depends(get_async_session),
) -> None:
    """Verify user has access to the vault containing the exploring dweller."""
    from app.crud import exploration as crud_exploration

    exploration = await crud_exploration.get(db_session, exploration_id)
    if not exploration:
        raise HTTPException(status_code=404, detail="Exploration not found")

    # Get dweller to access vault_id
    dweller = await crud.dweller.get(db_session, exploration.dweller_id)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")

    await get_user_vault_or_403(dweller.vault_id, user, db_session)
