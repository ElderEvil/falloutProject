"""User endpoints."""

import logging
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import UUID4
from pydantic.networks import EmailStr
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_redis_client
from app.crud.user_profile import profile_crud
from app.db.session import get_async_session
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.ai_usage import AIUsageResponse
from app.schemas.user import DeathStatsResponse, UserCreate, UserRead, UserUpdate, UserWithTokens
from app.schemas.user_profile import ProfileRead, ProfileUpdate
from app.services.family.death_service import death_service
from app.services.user_service import user_service
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User"])


@router.post("/", response_model=UserRead)
async def create_user(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user_in: UserCreate,
    _: CurrentSuperuser,
) -> User:
    """Admin route to create new user.

    Returns:
        The created user.

    Raises:
        HTTPException: 409 if user with this email already exists.
    """
    user = await crud.user.get_by_email(db_session=db_session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=409,
            detail="The user with this username already exists in the system.",
        )

    return await crud.user.create(db_session, obj_in=user_in)


@router.get("/", response_model=list[UserRead])
async def read_users(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
    _: CurrentSuperuser,
) -> Sequence[User]:
    """Retrieve users.

    Returns:
        List of users.
    """
    return await crud.user.get_multi(db_session, skip=skip, limit=limit)


@router.put("/me", response_model=UserRead)
async def update_user_me(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    username: Annotated[str | None, Body()] = None,
    password: Annotated[str | None, Body()] = None,
    email: Annotated[EmailStr | None, Body()] = None,
    user: CurrentActiveUser,
) -> User:
    """Update current user.

    Returns:
        The updated user.
    """
    user_data = jsonable_encoder(user)
    user_in = UserUpdate(**user_data)
    if password is not None:
        user_in.password = password
    if username is not None:
        user_in.username = username
    if email is not None:
        user_in.email = email
    return await crud.user.update(db_session, id=user.id, obj_in=user_in)


@router.get("/me", response_model=UserRead)
async def read_user_me(user: CurrentActiveUser) -> User:
    """Get current user.

    Returns:
        The current authenticated user.
    """
    return user


@router.post("/open", response_model=UserWithTokens)
async def create_user_open(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    username: Annotated[str, Body()],
    password: Annotated[str, Body()],
    email: Annotated[EmailStr, Body()],
) -> UserWithTokens:
    """Create new user and log them in automatically.

    Returns:
        New user with authentication tokens.
    """
    return await user_service.register_user(
        db_session=db_session,
        redis_client=redis_client,
        username=username,
        password=password,
        email=email,
    )


@router.get("/{user_id}", response_model=UserRead)
async def read_user_by_id(
    *,
    user_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> User:
    """Get a specific user by id.

    Returns:
        The requested user.

    Raises:
        ResourceNotFoundException: 404 if the user does not exist, or the caller
            may not see it. A 403 for an existing id and a 404 for an unknown one
            would let a regular user probe which ids exist.
    """
    if user_id != user.id and not crud.user.is_superuser(user):
        raise ResourceNotFoundException(model=User, identifier=user_id)
    return await crud.user.get(db_session, id=user_id)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user_id: UUID4,
    user_in: UserUpdate,
    _: CurrentSuperuser,
) -> User:
    """Update a user.

    Returns:
        The updated user.

    Raises:
        HTTPException: 404 if user not found.
    """
    user_in_db = await crud.user.get(db_session, id=user_id)
    if not user_in_db:
        raise HTTPException(
            status_code=404,
            detail="The user with this ID does not exist in the system",
        )
    return await crud.user.update(db_session, id=user_in_db.id, obj_in=user_in)


# =============================================================================
# Profile Endpoints (migrated from profile.py)
# =============================================================================


@router.get("/me/profile", response_model=ProfileRead)
async def get_my_profile(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> UserProfile:
    """Get current user's profile.

    If the profile doesn't exist, it will be auto-created with default values.
    This handles race conditions gracefully - if two concurrent requests try to
    create a profile, only one will succeed and both will return the profile.

    Returns:
        User's profile with statistics and preferences.
    """
    profile = await profile_crud.get_by_user_id(db_session, user.id)
    if not profile:
        # create_for_user handles the concurrent-create race internally.
        profile = await profile_crud.create_for_user(db_session, user.id)
    return profile


@router.put("/me/profile", response_model=ProfileRead)
async def update_my_profile(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    profile_data: ProfileUpdate,
    user: CurrentActiveUser,
) -> UserProfile:
    """Update current user's profile.

    Only bio, avatar_url, and preferences can be updated via this endpoint.
    Statistics fields (total_dwellers_created, total_caps_earned, etc.) are
    managed internally by the game and cannot be modified directly.

    Returns:
        Updated profile.

    Raises:
        ResourceNotFoundException: 404 if the profile does not exist.
    """
    profile = await profile_crud.get_by_user_id(db_session, user.id)
    if not profile:
        raise ResourceNotFoundException(model=UserProfile, identifier=user.id)

    return await profile_crud.update(db_session, id=profile.id, obj_in=profile_data)


@router.get("/me/profile/statistics", response_model=DeathStatsResponse)
async def get_death_statistics(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> DeathStatsResponse:
    """Get life/death statistics for the current user.

    Returns statistics about dwellers born, died, and breakdown by cause of death,
    as well as counts of currently revivable and permanently dead dwellers.

    Returns:
        Death statistics for the current user.
    """
    data = await death_service.get_death_statistics(db_session, user.id)
    return DeathStatsResponse(**data)


@router.get("/me/profile/ai-usage")
async def get_ai_usage(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> AIUsageResponse:
    """Get AI usage statistics for the current user.

    Returns:
        AI usage statistics including token counts and rate limits.
    """
    data = await user_service.get_ai_usage(db_session, redis_client, str(user.id))
    return AIUsageResponse.model_validate(data)
