"""
AI Usage Service - Token aggregation for user quotas.

IMPORTANT - Caching Strategy for Quota Enforcement:
- The AIUsageResponse now includes quota fields (quota_limit, quota_used, etc.)
- Quota data should NOT be cached for real-time enforcement
- Cache invalidation MUST happen when tokens are recorded (see QuotaService.record_usage)
- The cache key pattern is: user:{user_id}:ai_usage

Why quota cannot be cached:
- Users must see real-time quota status to avoid exceeding limits
- Warning (80%) and blocking (100%) require fresh data
- Cache invalidation happens in QuotaService.record_usage() via Redis DELETE
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.llm_interaction import LLMInteraction
from app.schemas.ai_usage import AIUsageResponse, AIUsageStats, QuotaInfo

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)

DEFAULT_QUOTA_LIMIT = 100000


class AIUsageService:
    async def get_user_usage(
        self,
        db_session: AsyncSession,
        user_id: "UUID",
    ) -> AIUsageResponse:
        try:
            now = datetime.utcnow()
            current_month_start = datetime(now.year, now.month, 1)
            month_str = now.strftime("%Y-%m")

            all_time_stats = await self._aggregate_tokens(db_session, user_id)
            monthly_stats = await self._aggregate_tokens(db_session, user_id, since=current_month_start)

            quota_used = monthly_stats.total_tokens
            quota_limit = DEFAULT_QUOTA_LIMIT
            quota_remaining = max(0, quota_limit - quota_used)
            quota_percentage = (quota_used / quota_limit * 100) if quota_limit > 0 else 0.0
            quota_warning = quota_percentage >= 80.0
            quota_exceeded = quota_percentage >= 100.0

            next_month = now.replace(day=28) + timedelta(days=4)
            reset_date = datetime(next_month.year, next_month.month, 1).strftime("%Y-%m-%d")

            return AIUsageResponse(
                all_time=AIUsageStats(
                    prompt_tokens=all_time_stats.prompt_tokens,
                    completion_tokens=all_time_stats.completion_tokens,
                    total_tokens=all_time_stats.total_tokens,
                ),
                current_month=AIUsageStats(
                    prompt_tokens=monthly_stats.prompt_tokens,
                    completion_tokens=monthly_stats.completion_tokens,
                    total_tokens=monthly_stats.total_tokens,
                ),
                quota=QuotaInfo(
                    quota_limit=quota_limit,
                    quota_used=quota_used,
                    quota_remaining=quota_remaining,
                    quota_percentage=quota_percentage,
                    quota_warning=quota_warning,
                    quota_exceeded=quota_exceeded,
                    reset_date=reset_date,
                ),
                month=month_str,
            )
        except Exception:
            logger.exception("Unexpected error fetching usage for user %s", user_id)
            raise

    async def _aggregate_tokens(
        self,
        db_session: AsyncSession,
        user_id: "UUID",
        since: datetime | None = None,
    ) -> AIUsageStats:
        try:
            query = select(
                func.coalesce(func.sum(LLMInteraction.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LLMInteraction.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(LLMInteraction.total_tokens), 0).label("total_tokens"),
            ).where(LLMInteraction.user_id == user_id)

            if since:
                query = query.where(LLMInteraction.created_at >= since)

            result = await db_session.exec(query)
            row = result.first()

            if row:
                return AIUsageStats(
                    prompt_tokens=int(row.prompt_tokens or 0),
                    completion_tokens=int(row.completion_tokens or 0),
                    total_tokens=int(row.total_tokens or 0),
                )

            return AIUsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        except Exception:
            logger.exception("Unexpected error aggregating tokens for user %s", user_id)
            raise


ai_usage_service = AIUsageService()
