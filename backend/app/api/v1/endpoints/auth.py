import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, CurrentUser, get_redis_client
from app.db.session import get_async_session
from app.schemas.responses import MessageResponse
from app.schemas.token import Token
from app.services.auth_service import auth_service
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login_access_token(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    try:
        return await auth_service.login(
            db_session=db_session,
            email=form_data.username,
            password=form_data.password,
            redis_client=redis_client,
        )
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.detail) from e


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: Annotated[str, Body(embed=True)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Token:
    """
    Refresh access token using refresh token.
    """
    try:
        return await auth_service.refresh_token(
            db_session=db_session,
            refresh_token=refresh_token,
            redis_client=redis_client,
        )
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=e.detail) from e


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: CurrentUser,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> MessageResponse:
    """
    Invalidate the current user's refresh token.
    """
    await auth_service.logout(redis_client=redis_client, user_id=current_user.id)
    return MessageResponse(msg="Successfully logged out")


@router.post("/forgot-password")
async def forgot_password(
    email: Annotated[EmailStr, Body(embed=True)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """
    Request password reset email.
    """
    return await auth_service.forgot_password(db_session=db_session, email=email)


@router.post("/reset-password")
async def reset_password(
    token: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> dict:
    """
    Reset password using token from email.
    """
    try:
        return await auth_service.reset_password(
            db_session=db_session,
            token=token,
            new_password=new_password,
            redis_client=redis_client,
        )
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=e.detail) from e


@router.put("/change-password")
async def change_password(
    current_password: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8)],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> dict:
    """
    Change password for authenticated user.
    """
    try:
        return await auth_service.change_password(
            db_session=db_session,
            user=user,
            current_password=current_password,
            new_password=new_password,
            redis_client=redis_client,
        )
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.detail) from e


@router.post("/verify-email")
async def verify_email(
    token: Annotated[str, Body(embed=True)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """
    Verify user email using token from email.
    """
    try:
        return await auth_service.verify_email(db_session=db_session, token=token)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=e.detail) from e


@router.post("/resend-verification")
async def resend_verification_email(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """
    Resend verification email to current user.
    """
    try:
        return await auth_service.resend_verification_email(db_session=db_session, user=user)
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.detail) from e
