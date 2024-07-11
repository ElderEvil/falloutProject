from datetime import timedelta
from typing import Any

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
    db_session: AsyncSession = Depends(get_async_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
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
    return {
        "access_token": security.create_access_token(
            user.id,
            expires_delta=access_token_expires,
        ),
        "token_type": "bearer",
    }


@router.post("/login/test-token", response_model=UserRead)
async def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user
