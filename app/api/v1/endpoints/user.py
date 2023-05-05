from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic.networks import EmailStr
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app import crud
from app.db.base import get_session
from app.models.user import User
from app.schemas.user import UserRead, UserCreate, UserUpdate

router = APIRouter()


@router.post("/", response_model=UserRead)
def create_user(
    *,
    db: Session = Depends(deps.get_session),
    user_in: UserCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Admin route to create new user.
    """
    user = crud.user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )

    return crud.user.create(db, obj_in=user_in)


@router.get("/", response_model=list[UserRead])
def read_users(
    db: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Retrieve users.
    """
    return crud.user.get_multi(db, skip=skip, limit=limit)


@router.put("/me", response_model=UserRead)
def update_user_me(
    *,
    db: Session = Depends(deps.get_session),
    username: str = Body(None),
    password: str = Body(None),
    email: EmailStr = Body(None),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update current user.
    """
    current_user_data = jsonable_encoder(current_user)
    user_in = UserUpdate(**current_user_data)
    if password is not None:
        user_in.password = password
    if username is not None:
        user_in.full_name = username
    if email is not None:
        user_in.email = email
    return crud.user.update(db, id=current_user.id, obj_in=user_in)


@router.get("/me", response_model=UserRead)
def read_user_me(current_user: User = Depends(deps.get_current_active_user)) -> Any:
    """
    Get current user.
    """
    return current_user


@router.post("/open", response_model=User)
def create_user_open(
    *,
    db: Session = Depends(deps.get_session),
    username: str = Body(None),
    password: str = Body(...),
    email: EmailStr = Body(...),
) -> Any:
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
    user = crud.user.get_by_email(db, email=email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )
    user_in = UserCreate(username=username, password=password, email=email)
    user = user.create(db, obj_in=user_in)
    return user


@router.get("/{user_id}", response_model=UserRead)
def read_user_by_id(
    user_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_session),
) -> Any:
    """
    Get a specific user by id.
    """
    user = crud.user.get(db, id=user_id)
    if user == current_user:
        return user
    if not crud.user.is_superuser(current_user):
        raise HTTPException(
            status_code=400,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    *,
    db: Session = Depends(deps.get_session),
    user_id: int,
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Update a user.
    """
    user = crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system",
        )
    user = crud.user.update(db, db_obj=user, obj_in=user_in)
    return user
