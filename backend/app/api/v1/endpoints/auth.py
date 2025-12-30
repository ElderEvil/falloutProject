from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import EmailStr
from pydantic.types import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, get_redis_client
from app.core import security
from app.core.email import send_password_changed_email, send_password_reset_email, send_verification_email
from app.db.session import get_async_session

router = APIRouter()


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

    # Store token and expiry in database
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(tz=UTC).replace(tzinfo=None) + timedelta(hours=1)
    await db_session.commit()

    # Send password reset email (don't fail if email sending fails)
    try:
        await send_password_reset_email(
            email_to=user.email,
            username=user.username,
            token=token,
        )
    except Exception as e:  # noqa: BLE001
        # Log the error but don't fail the request
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send password reset email: {e}")  # noqa: G004, TRY400

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
