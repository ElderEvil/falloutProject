"""Token quota policy; callers own the transaction covering checks and usage writes."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.crud.user import user as user_crud
from app.models.user import User
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.ai_constants import AI_USAGE_CACHE_KEY, QUOTA_TRACKING_OPERATION
from app.utils.exceptions import QuotaExceededException, ResourceNotFoundException

logger = logging.getLogger(__name__)

DEFAULT_QUOTA_LIMIT = 500000
WARNING_THRESHOLD = 80.0


@dataclass
class QuotaCheckResult:
    """Result of a quota check operation."""

    allowed: bool
    """Whether the request is allowed (True if under quota or admin)."""

    remaining: int
    """Number of tokens remaining in the quota for this month."""

    limit: int
    """Total monthly token limit for the user."""

    percentage: float
    """Percentage of quota used (0-100+)."""

    warning: bool
    """True if usage is at or above warning threshold (80%)."""

    used: int
    """Number of tokens used this month."""

    def ensure_allowed(self) -> None:
        """Reject exhausted quota with domain metadata for the caller."""
        if not self.allowed:
            raise QuotaExceededException(
                detail=f"Monthly token quota exceeded. You have used {self.used} of {self.limit} tokens.",
                remaining=self.remaining,
                warning=self.warning,
            )


class QuotaService:
    """Service for managing user token quotas with atomic checks."""

    async def check_quota(
        self,
        user_id: UUID,
        db_session: AsyncSession,
    ) -> QuotaCheckResult:
        """Lock the user until the caller commits usage, then evaluate this month's quota."""
        user = await user_crud.get_for_update(db_session, user_id)

        if not user:
            raise ResourceNotFoundException(User, user_id)

        if settings.QUOTA_DISABLED or user.is_superuser:
            return QuotaCheckResult(
                allowed=True,
                remaining=DEFAULT_QUOTA_LIMIT,
                limit=DEFAULT_QUOTA_LIMIT,
                percentage=0.0,
                warning=False,
                used=0,
            )

        quota_limit = user.monthly_token_limit if user.monthly_token_limit is not None else DEFAULT_QUOTA_LIMIT

        now = datetime.now(UTC)
        current_month_start = datetime(now.year, now.month, 1)

        quota_used = await llm_interaction_crud.total_tokens_since(db_session, user_id, current_month_start)

        quota_remaining = max(0, quota_limit - quota_used)
        quota_percentage = (quota_used / quota_limit * 100) if quota_limit > 0 else 0.0
        quota_warning = quota_percentage >= WARNING_THRESHOLD
        quota_exceeded = quota_used >= quota_limit

        return QuotaCheckResult(
            allowed=not quota_exceeded,
            remaining=quota_remaining,
            limit=quota_limit,
            percentage=quota_percentage,
            warning=quota_warning,
            used=quota_used,
        )

    async def record_usage(
        self,
        user_id: UUID,
        tokens: int,
        db_session: AsyncSession,
        redis_client: Redis,
    ) -> None:
        """Stage usage without committing; cache invalidation is a best-effort side effect."""
        if tokens < 0:
            raise ValueError("Token count cannot be negative")
        await llm_interaction_crud.create(
            db_session,
            LLMInteractionCreate(
                user_id=user_id,
                total_tokens=tokens,
                prompt_tokens=0,
                completion_tokens=0,
                parameters=None,
                response=None,
                usage=QUOTA_TRACKING_OPERATION,
            ),
        )
        try:
            await redis_client.delete(AI_USAGE_CACHE_KEY.format(user_id=user_id))
        except RedisError:
            logger.exception("Failed to invalidate cache for user %s", user_id)


quota_service = QuotaService()
