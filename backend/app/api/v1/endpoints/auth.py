"""Authentication endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from redis.asyncio import Redis

from app.api.deps import CurrentActiveUser, CurrentUser, DBSession, get_redis_client
from app.schemas.responses import MessageResponse
from app.schemas.token import Token
from app.services.auth_service import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login_access_token(
    db_session: DBSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Token:
    """OAuth2 compatible token login, get an access token for future requests.

    Returns:
        Token: Access and refresh tokens.

    Raises:
        HTTPException: 400 if credentials are invalid.
    """
    return await auth_service.login(
        db_session=db_session,
        email=form_data.username,
        password=form_data.password,
        redis_client=redis_client,
    )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: Annotated[str, Body(embed=True)],
    db_session: DBSession,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Token:
    """Refresh access token using refresh token.

    Returns:
        Token: New access and refresh tokens.

    Raises:
        HTTPException: 400 if refresh token is invalid. 404 if token not found.
    """
    return await auth_service.refresh_token(
        db_session=db_session,
        refresh_token=refresh_token,
        redis_client=redis_client,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: CurrentUser,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> MessageResponse:
    """Invalidate the current user's refresh token.

    Returns:
        MessageResponse: Confirmation message.
    """
    await auth_service.logout(redis_client=redis_client, user_id=str(current_user.id))
    return MessageResponse(msg="Successfully logged out")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    email: Annotated[EmailStr, Body(embed=True)],
    db_session: DBSession,
) -> MessageResponse:
    """Request password reset email.

    Returns:
        MessageResponse: Confirmation message.
    """
    result = await auth_service.forgot_password(db_session=db_session, email=email)
    return MessageResponse(msg=result["msg"])


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    token: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8)],
    db_session: DBSession,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> MessageResponse:
    """Reset password using token from email.

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 400 if token is invalid. 404 if token not found.
    """
    result = await auth_service.reset_password(
        db_session=db_session,
        token=token,
        new_password=new_password,
        redis_client=redis_client,
    )
    return MessageResponse(msg=result["msg"])


@router.put("/change-password", response_model=MessageResponse)
async def change_password(
    current_password: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8)],
    user: CurrentActiveUser,
    db_session: DBSession,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> MessageResponse:
    """Change password for authenticated user.

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 400 if current password is incorrect.
    """
    result = await auth_service.change_password(
        db_session=db_session,
        user=user,
        current_password=current_password,
        new_password=new_password,
        redis_client=redis_client,
    )
    return MessageResponse(msg=result["msg"])


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: Annotated[str, Body(embed=True)],
    db_session: DBSession,
) -> MessageResponse:
    """Verify user email using token from email.

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 400 if token is invalid. 404 if token not found.
    """
    result = await auth_service.verify_email(db_session=db_session, token=token)
    return MessageResponse(msg=result["msg"])


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification_email(
    user: CurrentActiveUser,
    db_session: DBSession,
) -> MessageResponse:
    """Resend verification email to current user.

    Returns:
        MessageResponse: Confirmation message.

    Raises:
        HTTPException: 400 if verification cannot be resent.
    """
    result = await auth_service.resend_verification_email(db_session=db_session, user=user)
    return MessageResponse(msg=result["msg"])
