from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from pydantic.types import UUID4
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentUser, get_redis_client
from app.core import security
from app.core.config import settings
from app.core.email import send_password_changed_email, send_password_reset_email, send_verification_email
from app.db.session import get_async_session
from app.schemas.token import Token

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_access_token(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
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


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: Annotated[str, Body(embed=True)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> Any:
    """
    Refresh access token using refresh token.
    """
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


@router.post("/forgot-password")
async def forgot_password(
    email: Annotated[EmailStr, Body(embed=True)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """
    Request password reset email.
    """
    user = await crud.user.get_by_email(db_session, email=email)

    # Always return success to prevent email enumeration
    if not user:
        return {"msg": "If that email exists, a password reset link has been sent"}

    # Generate password reset token
    token = security.create_password_reset_token(user.email)

    # Store token and expiry in database (use naive datetime for PostgreSQL TIMESTAMP WITHOUT TIME ZONE)
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(tz=UTC).replace(tzinfo=None) + timedelta(hours=1)
    await db_session.commit()

    # Send password reset email
    await send_password_reset_email(
        email_to=user.email,
        username=user.username,
        token=token,
    )

    return {"msg": "If that email exists, a password reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    token: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client=Depends(get_redis_client),
) -> dict:
    """
    Reset password using token from email.
    """
    # Verify token
    email = security.verify_password_reset_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Get user by email
    user = await crud.user.get_by_email(db_session, email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if token matches and hasn't expired
    if user.password_reset_token != token:
        raise HTTPException(status_code=400, detail="Invalid token")

    if user.password_reset_expires:
        # Handle both timezone-aware and naive datetimes (SQLite stores naive)
        now = datetime.now(tz=UTC)
        expires = user.password_reset_expires
        if expires.tzinfo is None:
            # Convert to naive for comparison
            now = now.replace(tzinfo=None)
        if expires < now:
            raise HTTPException(status_code=400, detail="Token has expired")

    # Update password
    user.hashed_password = security.get_password_hash(new_password)

    # Clear reset token
    user.password_reset_token = None
    user.password_reset_expires = None

    await db_session.commit()

    # Invalidate all refresh tokens for security
    await security.invalidate_refresh_token(str(user.id), redis_client)

    # Send confirmation email
    await send_password_changed_email(
        email_to=user.email,
        username=user.username,
    )

    return {"msg": "Password reset successful"}


@router.put("/change-password")
async def change_password(
    current_password: Annotated[str, Body()],
    new_password: Annotated[str, Body(min_length=8)],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    redis_client=Depends(get_redis_client),
) -> dict:
    """
    Change password for authenticated user.
    """
    # Verify current password
    if not security.verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")

    # Update password
    user.hashed_password = security.get_password_hash(new_password)
    await db_session.commit()

    # Invalidate all refresh tokens for security
    await security.invalidate_refresh_token(str(user.id), redis_client)

    # Send confirmation email
    await send_password_changed_email(
        email_to=user.email,
        username=user.username,
    )

    return {"msg": "Password changed successfully"}


@router.post("/verify-email")
async def verify_email(
    token: Annotated[str, Body(embed=True)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """
    Verify user email using token from email.
    """
    # Verify token
    user_id = security.verify_email_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Get user
    user = await crud.user.get(db_session, id=UUID4(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if token matches
    if user.email_verification_token != token:
        raise HTTPException(status_code=400, detail="Invalid token")

    # Check if already verified
    if user.email_verified:
        return {"msg": "Email already verified"}

    # Mark as verified and clear token
    user.email_verified = True
    user.email_verification_token = None
    await db_session.commit()

    return {"msg": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification_email(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """
    Resend verification email to current user.
    """
    # Check if already verified
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    # Generate new verification token
    token = security.create_email_verification_token(str(user.id))

    # Store token in database
    user.email_verification_token = token
    await db_session.commit()

    # Send verification email
    await send_verification_email(
        email_to=user.email,
        username=user.username,
        token=token,
    )

    return {"msg": "Verification email sent"}
