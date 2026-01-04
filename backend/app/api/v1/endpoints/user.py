from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import UUID4
from pydantic.networks import EmailStr
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_redis_client
from app.core import security
from app.core.config import settings
from app.core.email import send_verification_email
from app.db.session import get_async_session
from app.schemas.user import UserCreate, UserRead, UserUpdate, UserWithTokens

router = APIRouter()


@router.post("/", response_model=UserRead)
async def create_user(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user_in: UserCreate,
    _: CurrentSuperuser,
):
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
):
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
):
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
def read_user_me(user: CurrentActiveUser):
    """
    Get current user.
    """
    return user


@router.post("/open", response_model=UserWithTokens)
async def create_user_open(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client=Depends(get_redis_client),
    username: str = Body(...),  # noqa: FAST002
    password: str = Body(...),  # noqa: FAST002
    email: EmailStr = Body(...),  # noqa: FAST002
):
    """
    Create new user and log them in automatically.
    """
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Open user registration is forbidden on this server",
        )
    user = await crud.user.get_by_email(db_session, email=email)
    if user:
        raise HTTPException(
            status_code=409,
            detail="The user with this email already exists in the system",
        )
    user_in = UserCreate(username=username, password=password, email=email)
    user = await crud.user.create(db_session, obj_in=user_in)

    # Generate email verification token
    verification_token = security.create_email_verification_token(str(user.id))
    user.email_verification_token = verification_token
    await db_session.commit()
    await db_session.refresh(user)

    # Send verification email (non-blocking, failures won't stop registration)
    try:
        await send_verification_email(
            email_to=user.email,
            username=user.username,
            token=verification_token,
        )
    except Exception as e:
        # Log error but don't fail registration
        import logging

        logging.exception(f"Failed to send verification email: {e}")  # noqa: LOG015, TRY401

    access_token = security.create_access_token(user.id)
    refresh_token = await security.create_refresh_token(user.id, redis_client)

    return UserWithTokens(
        **user.model_dump(),
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.get("/{user_id}", response_model=UserRead)
async def read_user_by_id(
    *,
    user_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
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
):
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
