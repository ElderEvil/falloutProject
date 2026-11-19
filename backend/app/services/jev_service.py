"""TypeSafe Jev decision-model client — typed questions with confidence, not a language model.

Jev answers each field of a Pydantic output type with a probability; contracts live in app.schemas.jev.
Degrades to "disabled" without a key so import needs no secrets.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.schemas.jev import JevDecision, OutputT
from app.utils.exceptions import FeatureDisabledException

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """True when Jev is enabled and has an API key."""
    return bool(settings.JEV_ENABLED and settings.TYPESAFE_API_KEY)


class JevService:
    """Run typed Jev decisions; disabled (not failing) without configuration."""

    async def decide(
        self,
        state: str,
        output_type: type[OutputT],
        *,
        instructions: str | None = None,
        model: str | None = None,
    ) -> JevDecision[OutputT]:
        """Judge state against output_type's fields.

        Bounded by JEV_TIMEOUT_SECONDS with SDK retries disabled so the deadline bounds the whole operation:
        callers sit inside chat transactions and a slow provider must fail to their fallback, not hold one open.
        """
        if not is_configured():
            raise FeatureDisabledException(detail="Jev is not configured (set JEV_ENABLED and TYPESAFE_API_KEY).")

        agent = self._build_agent(output_type, instructions=instructions, model=model)
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(agent.run(state), timeout=settings.JEV_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning(
                "Jev decision timed out",
                extra={"output_type": output_type.__name__, "timeout_s": settings.JEV_TIMEOUT_SECONDS},
            )
            raise
        elapsed = time.perf_counter() - started

        provider_details = result.response.provider_details or {}
        confidence = dict(provider_details.get("confidence") or {})
        usage = result.usage() if callable(result.usage) else result.usage
        logger.info(
            "Jev decision",
            extra={
                "output_type": output_type.__name__,
                "model": result.response.model_name or "",
                "elapsed_s": round(elapsed, 3),
                "total_tokens": getattr(usage, "total_tokens", None),
                "confidence": confidence,
            },
        )
        return JevDecision[OutputT](
            output=result.output,
            confidence=confidence,
            model_name=result.response.model_name or "",
            prompt_tokens=getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
            elapsed_s=round(elapsed, 3),
        )

    @staticmethod
    async def record_usage(
        db_session: "AsyncSession",
        user_id: "UUID",
        decision: JevDecision,
        *,
        output_type_name: str,
    ) -> None:
        """Persist one Jev call as an LLM interaction so it appears in AI usage stats.

        Tagged jev_decision. The write runs in its own savepoint: a failed flush aborts the transaction, and
        catching it without rolling back to the savepoint would leave the shared session unusable.
        """
        from app.core.ai_constants import JEV_OPERATION
        from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
        from app.schemas.llm_interaction import LLMInteractionCreate

        try:
            async with db_session.begin_nested():
                await llm_interaction_crud.create(
                    db_session,
                    LLMInteractionCreate(
                        user_id=user_id,
                        usage=JEV_OPERATION,
                        provider="typesafe",
                        model=decision.model_name,
                        prompt_tokens=decision.prompt_tokens,
                        completion_tokens=decision.completion_tokens,
                        total_tokens=decision.total_tokens,
                        parameters=output_type_name,
                        response=None,
                    ),
                )
        except Exception:
            logger.exception("Failed to record Jev usage")

    @staticmethod
    def _build_agent(
        output_type: type[OutputT],
        *,
        instructions: str | None,
        model: str | None,
    ) -> Any:
        """Build the Jev agent lazily so importing this module needs no SDK/key.

        The key is passed explicitly: settings loads .env, not the process environment, so Agent("typesafe:...")
        by name would read an absent env var and fail auth.
        """
        from pydantic_ai import Agent
        from pydantic_ai.models.typesafe import TypeSafeModel
        from pydantic_ai.providers.typesafe import TypeSafeProvider

        model_name = model or settings.JEV_MODEL
        provider = TypeSafeProvider(api_key=settings.TYPESAFE_API_KEY)
        return Agent(TypeSafeModel(model_name, provider=provider), output_type=output_type, instructions=instructions)


jev_service = JevService()
