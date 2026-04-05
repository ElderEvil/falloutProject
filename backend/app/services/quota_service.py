"""
Quota Service - Token quota management with atomic checks and cache invalidation.

This service provides atomic quota checking using SELECT FOR UPDATE to prevent race
conditions when multiple requests check quota simultaneously. Admin users bypass quotas.

Cache invalidation happens in record_usage() to ensure fresh quota data.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.llm_interaction import LLMInteraction
from app.models.user import User

if TYPE_CHECKING:
    pass

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


class QuotaService:
    """Service for managing user token quotas with atomic checks."""

    async def check_quota(
        self,
        user_id: UUID,
        db_session: AsyncSession,
    ) -> QuotaCheckResult:
        """
        Check if user has quota available using SELECT FOR UPDATE for atomicity.

        Uses row-level locking on the user record to prevent race conditions
        when multiple requests check quota simultaneously.

        Args:
            user_id: The UUID of the user to check quota for.
            db_session: The database session for queries.

        Returns:
            QuotaCheckResult with quota status and allowance decision.

        Raises:
            ResourceNotFoundException: If user not found.
        """
        from app.utils.exceptions import ResourceNotFoundException

        user_query = select(User).where(col(User.id) == user_id).with_for_update()
        result = await db_session.execute(user_query)
        user = result.scalar_one_or_none()

        if not user:
            raise ResourceNotFoundException(User, user_id)

        if settings.QUOTA_DISABLED:
            return QuotaCheckResult(
                allowed=True,
                remaining=DEFAULT_QUOTA_LIMIT,
                limit=DEFAULT_QUOTA_LIMIT,
                percentage=0.0,
                warning=False,
                used=0,
            )

        # Admin users bypass quota checks entirely
        if user.is_superuser:
            return QuotaCheckResult(
                allowed=True,
                remaining=DEFAULT_QUOTA_LIMIT,
                limit=DEFAULT_QUOTA_LIMIT,
                percentage=0.0,
                warning=False,
                used=0,
            )

        quota_limit = user.monthly_token_limit if user.monthly_token_limit is not None else DEFAULT_QUOTA_LIMIT

        now = datetime.utcnow()
        current_month_start = datetime(now.year, now.month, 1)

        usage_query = select(func.coalesce(func.sum(col(LLMInteraction.total_tokens)), 0).label("total_used")).where(
            col(LLMInteraction.user_id) == user_id,
            col(LLMInteraction.created_at) >= current_month_start,
        )
        usage_result = await db_session.execute(usage_query)
        usage_row = usage_result.one_or_none()
        quota_used = int(usage_row[0] if usage_row else 0)

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
        """
        Record token usage and invalidate Redis cache.

        This method creates an LLMInteraction record for the token usage
        and invalidates the cached AI usage data to ensure fresh quota checks.

        Args:
            user_id: The UUID of the user who used tokens.
            tokens: Number of tokens used (total_tokens).
            db_session: The database session for the transaction.
            redis_client: The Redis client for cache invalidation.

        Raises:
            Exception: Re-raised after logging if database or cache operation fails.
        """
        from redis.exceptions import RedisError

        if tokens < 0:
            raise ValueError("Token count cannot be negative")

        try:
            interaction = LLMInteraction(
                user_id=user_id,
                total_tokens=tokens,
                prompt_tokens=0,
                completion_tokens=0,
                parameters=None,
                response=None,
                usage="quota_tracking",
            )
            db_session.add(interaction)
            await db_session.flush()

            cache_key = f"user:{user_id}:ai_usage"
            try:
                await redis_client.delete(cache_key)
                logger.debug("Invalidated cache for user %s after token usage", user_id)
            except RedisError:
                logger.warning("Failed to invalidate cache for user %s", user_id)

            logger.info("Recorded %d tokens for user %s", tokens, user_id)

        except Exception:
            logger.exception("Failed to record usage for user %s", user_id)
            raise


quota_service = QuotaService()
