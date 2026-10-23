"""User registration and profile business logic."""

import logging
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import UUID4, EmailStr
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core import security
from app.core.config import settings
from app.core.email import send_verification_email
from app.crud.user_profile import profile_crud
from app.models.user import User
from app.models.vault import Vault
from app.schemas.user import UserCreate, UserWithTokens
from app.services.auth_service import auth_service
from app.utils.exceptions import (
    AccessDeniedException,
    AccountChangeCooldownException,
    EmailDeliveryException,
    ResourceAlreadyExistsException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)

logger = logging.getLogger(__name__)

ProfileStatistic = Literal[
    "total_dwellers_created",
    "total_caps_earned",
    "total_explorations",
    "total_rooms_built",
]


def _cooldown_until(last_change: datetime | None, cooldown_days: int) -> datetime | None:
    if last_change is None:
        return None
    next_allowed = last_change + timedelta(days=cooldown_days)
    return next_allowed if next_allowed > datetime.utcnow() else None


class UserService:
    """Service for user registration and profile operations."""

    async def update_account(
        self,
        db_session: AsyncSession,
        user: User,
        *,
        username: str | None = None,
        password: str | None = None,
        email: EmailStr | None = None,
    ) -> User:
        """Validate and persist every supplied account change in one transaction.

        Raises:
            ValidationException: 400 if the username violates length bounds.
            ResourceNotFoundException: 404 if the locked user row disappeared.
            ResourceConflictException: 409 if the username or email is taken.
            AccountChangeCooldownException: 429 while a change cooldown is active.
            EmailDeliveryException: 502 when the account was saved but the mail could not be sent.
        """
        locked_user = await crud.user.get_for_update(db_session, user.id)
        if locked_user is None:
            raise ResourceNotFoundException(model=User, identifier=str(user.id))

        if password is not None and not 8 <= len(password) <= 128:
            raise ValidationException("Password must be between 8 and 128 characters.")

        username_change = await self._validate_username_change(db_session, locked_user, username)

        email_change = email if email is not None and email != locked_user.email else None
        if email_change is not None:
            self._assert_email_change_allowed(locked_user)
            await self._assert_email_available(db_session, locked_user.id, email_change)

        changed_at = datetime.utcnow()
        verification_token: str | None = None
        if username_change is not None:
            locked_user.username = username_change
            locked_user.username_changed_at = changed_at
        if email_change is not None:
            locked_user.email = email_change
            locked_user.email_verified = False
            locked_user.email_changed_at = changed_at
            verification_token = security.create_email_verification_token(str(locked_user.id))
            locked_user.email_verification_token = verification_token
        if password is not None:
            locked_user.hashed_password = security.get_password_hash(password)

        try:
            await db_session.commit()
        except IntegrityError as exc:
            await db_session.rollback()
            constraint = str(getattr(exc, "orig", exc)).lower()
            if "email" in constraint:
                raise ResourceConflictException(detail="This email address is already in use.") from exc
            if "username" in constraint:
                raise ResourceConflictException(detail="This username is already taken.") from exc
            raise
        await db_session.refresh(locked_user)

        if email_change is not None and verification_token is not None:
            try:
                await send_verification_email(
                    email_to=locked_user.email,
                    username=locked_user.username,
                    token=verification_token,
                )
            except Exception as exc:
                logger.exception("Failed to send verification email after email change")
                raise EmailDeliveryException(
                    detail="Failed to send the verification email to the new address."
                ) from exc

        return locked_user

    async def _validate_username_change(self, db_session: AsyncSession, user: User, username: str | None) -> str | None:
        if username is None:
            return None
        normalized = username.strip()
        if not 3 <= len(normalized) <= 32:
            raise ValidationException("Username must be between 3 and 32 characters.")
        if normalized == user.username:
            return None
        next_allowed = _cooldown_until(user.username_changed_at, settings.USERNAME_CHANGE_COOLDOWN_DAYS)
        if next_allowed is not None:
            raise AccountChangeCooldownException(detail=f"Username can be changed again on {next_allowed:%Y-%m-%d}.")
        existing = await crud.user.get_by_username(db_session, username=normalized)
        if existing and existing.id != user.id:
            raise ResourceConflictException(detail="This username is already taken.")
        return normalized

    def _assert_email_change_allowed(self, user: User) -> None:
        next_allowed = _cooldown_until(user.email_changed_at, settings.EMAIL_CHANGE_COOLDOWN_DAYS)
        if next_allowed is not None:
            raise AccountChangeCooldownException(detail=f"Email can be changed again on {next_allowed:%Y-%m-%d}.")

    async def _assert_email_available(self, db_session: AsyncSession, user_id: UUID4, new_email: EmailStr) -> None:
        existing = await crud.user.get_by_email(db_session, email=new_email, include_deleted=True)
        if existing is not None and existing.id != user_id:
            raise ResourceConflictException(detail="This email address is already in use.")

    async def register_user(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        username: str,
        password: str,
        email: EmailStr,
    ) -> UserWithTokens:
        """Register a new user, verify email, and return tokens."""
        if not settings.USERS_OPEN_REGISTRATION:
            raise AccessDeniedException("Open user registration is forbidden on this server")

        existing = await crud.user.get_by_email(db_session, email=email)
        if existing:
            raise ResourceAlreadyExistsException(model=User, name=email)

        user_in = UserCreate(username=username, password=password, email=email)
        user = await crud.user.create(db_session, obj_in=user_in)

        verification_token = security.create_email_verification_token(str(user.id))
        user.email_verification_token = verification_token
        await db_session.commit()
        await db_session.refresh(user)

        try:
            await send_verification_email(
                email_to=user.email,
                username=user.username,
                token=verification_token,
            )
        except Exception:
            logger.exception("Failed to send verification email")

        tokens = await auth_service.issue_tokens(user, redis_client)

        return UserWithTokens(
            **user.model_dump(),
            has_password=user.hashed_password is not None,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
        )

    async def get_ai_usage(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        user_id: str,
    ) -> dict:
        """Get AI usage stats with Redis caching."""
        import json

        from app.services.ai_constants import AI_USAGE_CACHE_KEY
        from app.services.ai_usage_service import AIUsageService

        cache_key = AI_USAGE_CACHE_KEY.format(user_id=user_id)

        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        usage_service = AIUsageService()
        result = await usage_service.get_user_usage(db_session, UUID(user_id))

        data = result.model_dump(mode="json")
        await redis_client.setex(cache_key, 300, json.dumps(data))
        return data

    async def record_vault_statistic(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        statistic: ProfileStatistic,
        amount: int = 1,
        *,
        commit: bool = True,
    ) -> None:
        """Record a positive lifetime statistic for a vault's overseer."""
        if amount <= 0:
            return

        vault = await crud.vault.get_or_none(db_session, vault_id, include_deleted=True)
        if isinstance(vault, Vault) and vault.user_id:
            await profile_crud.increment_statistic(db_session, vault.user_id, statistic, amount, commit=commit)


user_service = UserService()
