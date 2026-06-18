"""Service for authentication operations: login, token refresh, password management."""

import logging
from datetime import UTC, datetime, timedelta

from pydantic import EmailStr
from pydantic.types import UUID4
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core import security
from app.core.config import settings
from app.core.email import send_password_changed_email, send_password_reset_email, send_verification_email
from app.models.user import User
from app.schemas.token import Token
from app.utils.exceptions import (
    ResourceNotFoundException,
    ValidationException,
)

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication and token management."""

    async def login(
        self,
        db_session: AsyncSession,
        email: str,
        password: str,
        redis_client: Redis,
    ) -> Token:
        """Authenticate user and return tokens.

        Args:
            db_session: Database session
            email: User email
            password: User password
            redis_client: Redis client for refresh token storage

        Returns:
            Token with access and refresh tokens

        Raises:
            ValidationException: If credentials are invalid or user is inactive
        """
        user = await crud.user.authenticate(
            db_session=db_session,
            email=email,
            password=password,
        )
        if not user:
            raise ValidationException(detail="Incorrect email or password")

        if not crud.user.is_active(user):
            raise ValidationException(detail="Inactive user")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

        return Token(
            access_token=security.create_access_token(
                user.id,
                expires_delta=access_token_expires,
            ),
            refresh_token=await security.create_refresh_token(
                user.id,
                expires_delta=refresh_token_expires,
                redis_client=redis_client,
            ),
            token_type="bearer",
        )

    async def refresh_token(
        self,
        db_session: AsyncSession,
        refresh_token: str,
        redis_client: Redis,
    ) -> Token:
        """Refresh an access token using a refresh token.

        Args:
            db_session: Database session
            refresh_token: Refresh token to validate
            redis_client: Redis client

        Returns:
            New Token with refreshed access and refresh tokens

        Raises:
            ValidationException: If refresh token is invalid or user inactive
            ResourceNotFoundException: If user not found
        """
        user_id = await security.verify_refresh_token(refresh_token, redis_client)
        if not user_id:
            raise ValidationException(detail="Invalid refresh token")

        user = await crud.user.get(db_session, id=UUID4(user_id))
        if not user:
            raise ResourceNotFoundException(model=User, identifier=user_id)

        if not crud.user.is_active(user):
            raise ValidationException(detail="Inactive user")

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = security.create_access_token(
            user.id,
            expires_delta=access_token_expires,
        )

        new_refresh_token = await security.create_refresh_token(user.id, redis_client)

        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    async def logout(self, redis_client: Redis, user_id: str) -> None:
        """Invalidate the user's refresh token.

        Args:
            redis_client: Redis client
            user_id: User ID to invalidate tokens for
        """
        await security.invalidate_refresh_token(user_id, redis_client)

    async def forgot_password(self, db_session: AsyncSession, email: EmailStr) -> dict:
        """Request password reset email.

        Always returns success to prevent email enumeration.

        Args:
            db_session: Database session
            email: User email

        Returns:
            Response message
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

        # Send password reset email
        await send_password_reset_email(
            email_to=user.email,
            username=user.username,
            token=token,
        )

        return {"msg": "If that email exists, a password reset link has been sent"}

    async def reset_password(
        self,
        db_session: AsyncSession,
        token: str,
        new_password: str,
        redis_client: Redis,
    ) -> dict:
        """Reset password using token from email.

        Args:
            db_session: Database session
            token: Password reset token
            new_password: New password (min 8 chars)
            redis_client: Redis client

        Returns:
            Response message

        Raises:
            ValidationException: If token is invalid or expired
            ResourceNotFoundException: If user not found
        """
        # Verify token
        email = security.verify_password_reset_token(token)
        if not email:
            raise ValidationException(detail="Invalid or expired token")

        # Get user by email
        user = await crud.user.get_by_email(db_session, email=email)
        if not user:
            raise ResourceNotFoundException(model=User, name=email)

        # Check if token matches and hasn't expired
        if user.password_reset_token != token:
            raise ValidationException(detail="Invalid token")

        if user.password_reset_expires:
            # Handle both timezone-aware and naive datetimes
            now = datetime.now(tz=UTC)
            expires = user.password_reset_expires
            if expires.tzinfo is None:
                now = now.replace(tzinfo=None)
            if expires < now:
                raise ValidationException(detail="Token has expired")

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

    async def change_password(
        self,
        db_session: AsyncSession,
        user: User,
        current_password: str,
        new_password: str,
        redis_client: Redis,
    ) -> dict:
        """Change password for authenticated user.

        Args:
            db_session: Database session
            user: Current authenticated user
            current_password: Current password for verification
            new_password: New password (min 8 chars)
            redis_client: Redis client

        Returns:
            Response message

        Raises:
            ValidationException: If current password is incorrect
        """
        # Verify current password
        if not security.verify_password(current_password, user.hashed_password):
            raise ValidationException(detail="Incorrect password")

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

    async def verify_email(self, db_session: AsyncSession, token: str) -> dict:
        """Verify user email using token from email.

        Args:
            db_session: Database session
            token: Email verification token

        Returns:
            Response message

        Raises:
            ValidationException: If token is invalid or expired
            ResourceNotFoundException: If user not found
        """
        # Verify token
        user_id = security.verify_email_token(token)
        if not user_id:
            raise ValidationException(detail="Invalid or expired token")

        # Get user
        user = await crud.user.get(db_session, id=UUID4(user_id))
        if not user:
            raise ResourceNotFoundException(model=User, identifier=user_id)

        # Check if token matches
        if user.email_verification_token != token:
            raise ValidationException(detail="Invalid token")

        # Check if already verified
        if user.email_verified:
            return {"msg": "Email already verified"}

        # Mark as verified and clear token
        user.email_verified = True
        user.email_verification_token = None
        await db_session.commit()

        return {"msg": "Email verified successfully"}

    async def resend_verification_email(self, db_session: AsyncSession, user: User) -> dict:
        """Resend verification email to user.

        Args:
            db_session: Database session
            user: Current authenticated user

        Returns:
            Response message

        Raises:
            ValidationException: If email already verified
        """
        # Check if already verified
        if user.email_verified:
            raise ValidationException(detail="Email already verified")

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


# Singleton instance
auth_service = AuthService()
