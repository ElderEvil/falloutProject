"""User endpoints."""

import logging
from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from pydantic.networks import EmailStr
from redis.asyncio import Redis

from app.api.deps import CurrentActiveUser, CurrentSuperuser, DBSession, PaginationParams, get_redis_client
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.ai_usage import AIUsageResponse
from app.schemas.user import DeathStatsResponse, UserCreate, UserRead, UserUpdate, UserWithTokens
from app.schemas.user_profile import ProfileRead, ProfileUpdate
from app.services.admin_service import create_user_account, update_user_account
from app.services.family.death_service import death_service
from app.services.user_service import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User"])


@router.post("/", response_model=UserRead)
async def create_user(
    *,
    db_session: DBSession,
    user_in: UserCreate,
    actor: CurrentSuperuser,
) -> User:
    """Admin route to create new user."""
    return await create_user_account(db_session, user_in, actor_id=actor.id)


@router.get("/", response_model=list[UserRead])
async def read_users(
    *,
    db_session: DBSession,
    _: CurrentSuperuser,
    pagination: PaginationParams,
) -> Sequence[User]:
    """Retrieve users."""
    return await user_service.list_users(db_session, skip=pagination.skip, limit=pagination.limit)


@router.put("/me", response_model=UserRead)
async def update_user_me(
    *,
    db_session: DBSession,
    username: Annotated[str | None, Body()] = None,
    password: Annotated[str | None, Body()] = None,
    email: Annotated[EmailStr | None, Body()] = None,
    user: CurrentActiveUser,
) -> User:
    """Update current user."""
    return await user_service.update_account(
        db_session,
        user,
        username=username,
        password=password,
        email=email,
    )


@router.get("/me", response_model=UserRead)
async def read_user_me(user: CurrentActiveUser) -> User:
    """Get current user."""
    return user


@router.post("/open", response_model=UserWithTokens)
async def create_user_open(
    *,
    db_session: DBSession,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
    username: Annotated[str, Body()],
    password: Annotated[str, Body()],
    email: Annotated[EmailStr, Body()],
) -> UserWithTokens:
    """Create new user and log them in automatically."""
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
    user_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> User:
    """Get a specific user by id."""
    return await user_service.get_user_for_reader(db_session, requester=user, user_id=user_id)


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    *,
    db_session: DBSession,
    user_id: UUID,
    user_in: UserUpdate,
    actor: CurrentSuperuser,
) -> User:
    """Update a user."""
    return await update_user_account(db_session, user_id, user_in, actor_id=actor.id)


@router.get("/me/profile", response_model=ProfileRead)
async def get_my_profile(
    *,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> UserProfile:
    """Get current user's profile.

    If the profile doesn't exist, it will be auto-created with default values.
    This handles race conditions gracefully - if two concurrent requests try to
    create a profile, only one will succeed and both will return the profile.
    """
    # The service owns the create and its commit; the endpoint never touches the transaction.
    return await user_service.get_or_create_profile(db_session, user.id)


@router.put("/me/profile", response_model=ProfileRead)
async def update_my_profile(
    *,
    db_session: DBSession,
    profile_data: ProfileUpdate,
    user: CurrentActiveUser,
) -> UserProfile:
    """Update current user's profile.

    Only bio, avatar_url, and preferences can be updated via this endpoint.
    Statistics fields (total_dwellers_created, total_caps_earned, etc.) are
    managed internally by the game and cannot be modified directly.
    """
    return await user_service.update_profile(db_session, user.id, profile_data)


@router.get("/me/profile/statistics", response_model=DeathStatsResponse)
async def get_death_statistics(
    *,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> DeathStatsResponse:
    """Get life/death statistics for the current user.

    Returns statistics about dwellers born, died, and breakdown by cause of death,
    as well as counts of currently revivable and permanently dead dwellers.
    """
    data = await death_service.get_death_statistics(db_session, user.id)
    return DeathStatsResponse(**data)


@router.get("/me/profile/ai-usage")
async def get_ai_usage(
    *,
    db_session: DBSession,
    user: CurrentActiveUser,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> AIUsageResponse:
    """Get AI usage statistics for the current user."""
    data = await user_service.get_ai_usage(db_session, redis_client, str(user.id))
    return AIUsageResponse.model_validate(data)
