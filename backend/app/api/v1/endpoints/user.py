import logging
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
from app.schemas.ai_usage import AIUsageResponse
from app.schemas.user import DeathStatsResponse, UserCreate, UserRead, UserUpdate, UserWithTokens
from app.schemas.user_profile import ProfileRead, ProfileUpdate
from app.services.death_service import death_service
from app.services.user_service import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User"])


@router.post("/", response_model=UserRead)
async def create_user(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user_in: UserCreate,
    _: CurrentSuperuser,
) -> UserRead:
    """
    Admin route to create new user.
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
) -> list[UserRead]:
    """
    Retrieve users.
    """
    return await crud.user.get_multi(db_session, skip=skip, limit=limit)


@router.put("/me", response_model=UserRead)
async def update_user_me(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    username: Annotated[str | None, Body()] = None,
    password: Annotated[str | None, Body()] = None,
    email: Annotated[EmailStr, Body()] = None,
    user: CurrentActiveUser,
) -> UserRead:
    """
    Update current user.
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
async def read_user_me(user: CurrentActiveUser) -> UserRead:
    """
    Get current user.
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
    """
    Create new user and log them in automatically.
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
) -> UserRead:
    """
    Get a specific user by id.
    """
    user_in_db = await crud.user.get(db_session, id=user_id)
    if user_in_db == user:
        return user_in_db
    if not crud.user.is_superuser(user):
        raise HTTPException(
            status_code=400,
            detail="The user doesn't have enough privileges",
        )
    return user_in_db


@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user_id: UUID4,
    user_in: UserUpdate,
    _: CurrentSuperuser,
) -> UserRead:
    """
    Update a user.
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


@router.get("/me/profile")
async def get_my_profile(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> ProfileRead:
    """
    Get current user's profile.

    If the profile doesn't exist, it will be auto-created with default values.
    This handles race conditions gracefully - if two concurrent requests try to
    create a profile, only one will succeed and both will return the profile.

    :param db_session: Database session
    :type db_session: AsyncSession
    :param user: Current authenticated active user
    :type user: CurrentActiveUser
    :returns: User's profile with statistics and preferences
    :rtype: ProfileRead
    :raises HTTPException: 500 if profile retrieval/creation fails unexpectedly
    """
    try:
        profile = await profile_crud.get_by_user_id(db_session, user.id)
        if not profile:
            # Auto-create profile if it doesn't exist
            # create_for_user handles race conditions internally
            profile = await profile_crud.create_for_user(db_session, user.id)
    except Exception as e:
        logger.exception("Failed to get/create profile for user %s", user.id)
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return profile


@router.put("/me/profile")
async def update_my_profile(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    profile_data: ProfileUpdate,
    user: CurrentActiveUser,
) -> ProfileRead:
    """
    Update current user's profile.

    Only bio, avatar_url, and preferences can be updated via this endpoint.
    Statistics fields (total_dwellers_created, total_caps_earned, etc.) are
    managed internally by the game and cannot be modified directly.

    :param db_session: Database session
    :type db_session: AsyncSession
    :param profile_data: Profile update data (bio, avatar_url, preferences)
    :type profile_data: ProfileUpdate
    :param user: Current authenticated active user
    :type user: CurrentActiveUser
    :returns: Updated profile
    :rtype: ProfileRead
    :raises HTTPException: 404 if profile not found
    :raises HTTPException: 500 if profile update fails unexpectedly
    """
    try:
        profile = await profile_crud.get_by_user_id(db_session, user.id)
    except Exception as e:
        logger.exception("Failed to get profile for user %s", user.id)
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        return await profile_crud.update(db_session, id=profile.id, obj_in=profile_data)
    except Exception as e:
        logger.exception("Failed to update profile for user %s", user.id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/me/profile/statistics", response_model=DeathStatsResponse)
async def get_death_statistics(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> DeathStatsResponse:
    """
    Get life/death statistics for the current user.

    Returns statistics about dwellers born, died, and breakdown by cause of death,
    as well as counts of currently revivable and permanently dead dwellers.
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
    data = await user_service.get_ai_usage(db_session, redis_client, str(user.id))
    return AIUsageResponse.model_validate(data)
