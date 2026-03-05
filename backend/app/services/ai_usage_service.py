import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.llm_interaction import LLMInteraction
from app.schemas.ai_usage import AIUsageResponse, AIUsageStats

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


class AIUsageService:
    async def get_user_usage(
        self,
        db_session: AsyncSession,
        user_id: "UUID",
    ) -> AIUsageResponse:
        now = datetime.utcnow()
        current_month_start = datetime(now.year, now.month, 1)
        month_str = now.strftime("%Y-%m")

        all_time_stats = await self._aggregate_tokens(db_session, user_id)
        monthly_stats = await self._aggregate_tokens(db_session, user_id, since=current_month_start)

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
            month=month_str,
        )

    async def _aggregate_tokens(
        self,
        db_session: AsyncSession,
        user_id: "UUID",
        since: datetime | None = None,
    ) -> AIUsageStats:
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


ai_usage_service = AIUsageService()
