"""User registration and profile business logic."""

import logging

from pydantic import EmailStr
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core import security
from app.core.config import settings
from app.core.email import send_verification_email
from app.models.user import User
from app.schemas.user import UserCreate, UserWithTokens
from app.utils.exceptions import AccessDeniedException, ResourceAlreadyExistsException

logger = logging.getLogger(__name__)


class UserService:
    """Service for user registration and profile operations."""

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

        access_token = security.create_access_token(user.id)
        refresh_token = await security.create_refresh_token(user.id, redis_client)

        return UserWithTokens(
            **user.model_dump(),
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def get_ai_usage(
        self,
        db_session: AsyncSession,
        redis_client: Redis,
        user_id: str,
    ) -> dict:
        """Get AI usage stats with Redis caching."""
        import json

        from app.services.ai_usage_service import AIUsageService

        cache_key = f"ai_usage:{user_id}"

        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        usage_service = AIUsageService()
        result = await usage_service.get_user_usage(db_session, user_id)

        data = result.model_dump(mode="json")
        await redis_client.setex(cache_key, 300, json.dumps(data))
        return data


user_service = UserService()
