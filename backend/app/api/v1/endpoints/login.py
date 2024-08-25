from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentUser
from app.core import security
from app.core.config import settings
from app.db.session import get_async_session
from app.schemas.token import Token
from app.schemas.user import UserRead

router = APIRouter()


@router.post("/login/access-token", response_model=Token)
async def login_access_token(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
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
        ),
        "token_type": "bearer",
    }


@router.post("/login/refresh-token", response_model=Token)
async def refresh_access_token(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    refresh_token: str,
) -> Any:
    user_id = security.verify_refresh_token(refresh_token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid refresh token")

    user = await crud.user.get(db_session, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not crud.user.is_active(user):
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id,
            expires_delta=access_token_expires,
        ),
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(current_user: CurrentUser) -> Any:
    """
    Invalidate the current user's refresh token.
    """
    await security.invalidate_refresh_token(current_user.id)
    return {"msg": "Successfully logged out"}


@router.post("/login/test-token", response_model=UserRead)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user
