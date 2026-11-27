"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError as JWTError
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.security import decode_token_subject
from app.db.redis import get_shared_redis
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.relationship import Relationship
from app.models.room import Room
from app.models.user import User
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.pagination import NotificationPagination, OffsetPagination, Pagination, PetPagination
from app.services import access_service
from app.services.relationship_service import relationship_service
from app.utils.exceptions import AccessDeniedException, ensure_found

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
)

# Reuse this Depends object across routes and keep request caching enabled.
# Re-entering the limited dependency with use_cache=False can deadlock a request.
DBSession = Annotated[AsyncSession, Depends(get_async_session, max_concurrency=settings.API_DB_SESSION_CONCURRENCY)]
# Streams must use this throughout their auth/access dependency tree: the normal request-scoped permit would otherwise
# remain held for the lifetime of the stream.
StreamDBSession = Annotated[AsyncSession, Depends(get_async_session)]

# Model dependencies keep query fields flat alongside endpoint filters. Direct
# Query() models cannot be combined with scalar query parameters in this FastAPI version.
PaginationParams = Annotated[Pagination, Depends()]
OffsetPaginationParams = Annotated[OffsetPagination, Depends()]
NotificationPaginationParams = Annotated[NotificationPagination, Depends()]
PetPaginationParams = Annotated[PetPagination, Depends()]


async def get_redis_client() -> AsyncGenerator[Redis]:
    """Yield the process-wide Redis client; the app lifespan owns its lifecycle."""
    yield get_shared_redis()


async def get_current_user(
    db_session: DBSession,
    token: Annotated[str, Depends(reusable_oauth2)],
) -> User:
    """Validate the OAuth2 access token; 401 on bad credentials, 404 if the user is gone."""
    try:
        user_id = UUID(decode_token_subject(token, "access"))
    except JWTError as e:
        # Missing/non-UUID subject in a signed token is a credential failure (401), not a server error.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    user = await crud.user.get(db_session=db_session, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_stream_user(
    db_session: StreamDBSession,
    token: Annotated[str, Depends(reusable_oauth2)],
) -> User:
    """Reuse token validation without holding an API permit for a stream."""
    return await get_current_user(db_session, token)


StreamUser = Annotated[User, Depends(get_stream_user)]


async def get_current_active_user(current_user: CurrentUser) -> User:
    """403 if the user is inactive."""
    if not crud.user.is_active(current_user):
        raise AccessDeniedException("Inactive user")
    return current_user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


async def get_current_verified_user(current_user: CurrentActiveUser) -> User:
    """403 unless the user's email is verified."""
    if not current_user.email_verified:
        raise AccessDeniedException("Email verification required")
    return current_user


CurrentVerifiedUser = Annotated[User, Depends(get_current_verified_user)]


async def get_current_active_superuser(current_user: CurrentActiveUser) -> User:
    """403 unless the user is a superuser."""
    if not crud.user.is_superuser(current_user):
        raise AccessDeniedException("The user doesn't have enough privileges")
    return current_user


CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]


async def get_user_vault_or_403(
    vault_id: UUID | None,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Vault:
    """Return the user's vault (or any vault for a superuser)."""
    return await access_service.get_accessible_vault(vault_id, user, db_session)


async def get_stream_user_vault_or_403(
    vault_id: UUID | None,
    user: StreamUser,
    db_session: StreamDBSession,
) -> Vault:
    """Apply the same active-user and vault policy with an uncapped session."""
    return await get_user_vault_or_403(vault_id, await get_current_active_user(user), db_session)


async def verify_dweller_access(
    dweller_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Dweller:
    """Apply the shared dweller access policy; returns the eager-loaded dweller so callers don't re-read it."""
    return await access_service.verify_dweller_access(dweller_id, user, db_session)


async def get_accessible_relationship(
    relationship_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Relationship:
    """Load a relationship and require access to its first dweller."""
    relationship = await relationship_service.get_relationship_by_id(db_session, relationship_id)
    await verify_dweller_access(relationship.dweller_1_id, user, db_session)
    return relationship


async def verify_room_access(
    room_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> tuple[Room, Vault]:
    """Return (room, vault) after authorization; 404 if missing, 403 if no vault access."""
    room = await crud.room.get(db_session, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    vault = await get_user_vault_or_403(room.vault_id, user, db_session)
    return room, vault


async def verify_item_access(
    item_id: UUID,
    model: type[Weapon | Outfit | Junk],
    user: CurrentActiveUser,
    db_session: DBSession,
) -> None:
    """403 unless the user owns the item's vault (resolved via storage or equipping dweller); 404 if unresolvable."""
    from app.crud.item_base import get_item_vault_id

    item = await db_session.get(model, item_id)
    item = ensure_found(item, model, identifier=item_id)

    vault_id = await get_item_vault_id(db_session, item)
    vault_id = ensure_found(vault_id, model, identifier=item_id)

    await get_user_vault_or_403(vault_id, user, db_session)


async def verify_exploration_access(
    exploration_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> None:
    """Authorize the exploring dweller's vault; 404 if exploration/dweller missing, 403 if no access."""
    from app.crud import exploration as crud_exploration

    exploration = await crud_exploration.get(db_session, exploration_id)
    if not exploration:
        raise HTTPException(status_code=404, detail="Exploration not found")

    # Deleted dwellers' terminal journeys stay readable by the vault owner (hence include_deleted).
    dweller = await crud.dweller.get(db_session, exploration.dweller_id, include_deleted=True)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")

    await get_user_vault_or_403(dweller.vault_id, user, db_session)
