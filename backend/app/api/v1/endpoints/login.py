from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import UUID4
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentUser, get_redis_client
from app.core import security
from app.core.config import settings
from app.db.session import get_async_session
from app.schemas.token import Token

router = APIRouter()


@router.post("/login/access-token", response_model=Token)
async def login_access_token(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Any:
    user = await crud.user.authenticate(
        db_session=db_session,
        email=form_data.username,
        password=form_data.password,
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    return {
        "access_token": security.create_access_token(
            user.id,
            expires_delta=access_token_expires,
        ),
        "refresh_token": await security.create_refresh_token(
            user.id,
            expires_delta=refresh_token_expires,
            redis_client=redis_client,
        ),
        "token_type": "bearer",
    }


@router.post("/login/refresh-token", response_model=Token)
async def refresh_access_token(
    refresh_token: str,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Any:
    user_id = await security.verify_refresh_token(refresh_token, redis_client)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid refresh token")

    user = await crud.user.get(db_session, id=UUID4(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = security.create_access_token(
        user.id,
        expires_delta=access_token_expires,
    )

    # Generate a new refresh token and store it in Redis
    new_refresh_token = await security.create_refresh_token(user.id, redis_client)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(current_user: CurrentUser, redis_client: Annotated[Redis, Depends(get_redis_client)]) -> Any:
    """
    Invalidate the current user's refresh token.
    """
    await security.invalidate_refresh_token(current_user.id, redis_client)
    return {"msg": "Successfully logged out"}
