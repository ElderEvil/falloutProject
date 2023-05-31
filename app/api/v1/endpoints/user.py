from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import UUID4
from pydantic.networks import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser
from app.core.config import settings
from app.db.session import get_async_session
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter()


@router.post("/", response_model=UserRead)
async def create_user(
    *,
    db_session: AsyncSession = Depends(get_async_session),
    user_in: UserCreate,
    user: CurrentSuperuser,
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
    db_session: AsyncSession = Depends(get_async_session),
    skip: int = 0,
    limit: int = 100,
    user: CurrentSuperuser,
):
    """
    Retrieve users.
    """
    return await crud.user.get_multi(db_session, skip=skip, limit=limit)


@router.put("/me", response_model=UserRead)
async def update_user_me(
    *,
    db_session: AsyncSession = Depends(get_async_session),
    username: str = Body(None),
    password: str = Body(None),
    email: EmailStr = Body(None),
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
async def read_user_me(user: CurrentActiveUser):
    """
    Get current user.
    """
    return user


@router.post("/open", response_model=UserRead)
async def create_user_open(
    *,
    db_session: AsyncSession = Depends(get_async_session),
    username: str = Body(...),
    password: str = Body(...),
    email: EmailStr = Body(...),
):
    """
    Create new user without the need to be logged in.:

    - **username**: each user must have a username
    - **password**: a long user password
    - **email**: email of the user
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
    return user


@router.get("/{user_id}", response_model=UserRead)
async def read_user_by_id(
    *,
    user_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
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
    db_session: AsyncSession = Depends(get_async_session),
    user_id: UUID4,
    user_in: UserUpdate,
    user: CurrentSuperuser,
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
    return await crud.user.update(db_session, db_obj=user_in_db, obj_in=user_in)
