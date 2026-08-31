"""AI Usage Service - Token aggregation for user quotas.

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
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.llm_interaction import LLMInteraction
from app.models.user import User
from app.schemas.ai_usage import AIOperationStats, AIUsageResponse, AIUsageStats, QuotaInfo
from app.services.ai_constants import QUOTA_TRACKING_OPERATION
from app.services.quota_service import DEFAULT_QUOTA_LIMIT

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)

CHAT_HEAVY_OPERATION = "chat_with_dweller"
CHAT_HEAVY_THRESHOLD = 0.8


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

            user_result = await db_session.execute(select(User).where(col(User.id) == user_id))
            user = user_result.scalar_one_or_none()

            all_time_stats = await self._aggregate_tokens(db_session, user_id)
            monthly_stats = await self._aggregate_tokens(db_session, user_id, since=current_month_start)
            by_operation = await self._aggregate_by_operation(db_session, user_id, since=current_month_start)

            quota_used = monthly_stats.total_tokens
            quota_limit = (
                user.monthly_token_limit if user and user.monthly_token_limit is not None else DEFAULT_QUOTA_LIMIT
            )
            quota_remaining = max(0, quota_limit - quota_used)
            quota_percentage = (quota_used / quota_limit * 100) if quota_limit > 0 else 0.0
            quota_warning = quota_percentage >= 80.0
            quota_exceeded = quota_percentage >= 100.0

            next_month = now.replace(day=28) + timedelta(days=4)
            reset_date = datetime(next_month.year, next_month.month, 1).strftime("%Y-%m-%d")

            return AIUsageResponse(
                all_time=all_time_stats,
                current_month=monthly_stats,
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
                by_operation=by_operation,
                chat_heavy=self._is_chat_heavy(by_operation),
            )
        except Exception:
            logger.exception("Unexpected error fetching usage for user %s", user_id)
            raise

    @staticmethod
    def _is_chat_heavy(by_operation: list[AIOperationStats]) -> bool:
        """Anomaly flag: chat_with_dweller dominates monthly token spend (>80%)."""
        non_operational = [op for op in by_operation if not op.is_operational]
        month_total = sum(op.total_tokens for op in non_operational)
        if month_total <= 0:
            return False
        chat_total = sum(op.total_tokens for op in non_operational if op.operation == CHAT_HEAVY_OPERATION)
        return chat_total / month_total > CHAT_HEAVY_THRESHOLD

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

    async def _aggregate_by_operation(
        self,
        db_session: AsyncSession,
        user_id: "UUID",
        since: datetime | None = None,
    ) -> list[AIOperationStats]:
        """Group token usage by operation tag (LLMInteraction.usage).

        One GROUP BY usage covers the per-operation totals; a daily trend would
        need a separate GROUP BY day query and is intentionally not faked here.
        NULL usage is reported as "unknown"; quota_tracking is kept but flagged
        operational (bookkeeping, not an LLM request).
        """
        try:
            operation = func.coalesce(LLMInteraction.usage, "unknown")
            query = select(
                operation.label("operation"),
                func.coalesce(func.sum(LLMInteraction.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(LLMInteraction.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(LLMInteraction.total_tokens), 0).label("total_tokens"),
                func.count().label("interaction_count"),
            ).where(LLMInteraction.user_id == user_id)

            if since:
                query = query.where(LLMInteraction.created_at >= since)

            query = query.group_by(operation).order_by(func.sum(LLMInteraction.total_tokens).desc())

            result = await db_session.exec(query)
            return [
                AIOperationStats(
                    operation=row.operation,
                    prompt_tokens=int(row.prompt_tokens or 0),
                    completion_tokens=int(row.completion_tokens or 0),
                    total_tokens=int(row.total_tokens or 0),
                    count=int(row.interaction_count),
                    is_operational=row.operation == QUOTA_TRACKING_OPERATION,
                )
                for row in result.all()
            ]
        except Exception:
            logger.exception("Unexpected error aggregating usage by operation for user %s", user_id)
            raise


ai_usage_service = AIUsageService()
