"""TypeSafe Jev decision-model client — typed questions with confidence.

Jev is not a language model: it answers each field of a Pydantic output type as
a typed question and returns a probability per field. It is complementary to the
chat agent (which writes text); callers ask Jev to *decide* something concrete.

The decision contracts and the model shape rules a caller's output type must
respect live in :mod:`app.schemas.jev`; this module owns the client only.

The service degrades to "disabled" without a key so no caller needs secrets at
import time; every entry point returns a typed :class:`JevDecision`.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.schemas.jev import JevDecision, OutputT
from app.utils.exceptions import FeatureDisabledException

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

#: Jev refuses anything above this; keep the state + questions under it.
JEV_STATE_TOKEN_LIMIT = 32_000


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
        """Judge ``state`` against ``output_type``'s fields.

        Bounded by ``JEV_TIMEOUT_SECONDS`` and usage-accounted: callers sit inside
        chat transactions, so a slow provider must fail (to their fallback) rather
        than hold a transaction open. The SDK's own retries are disabled so the
        deadline bounds the whole operation, not one attempt.

        Args:
            state: the material being judged (the prompt).
            output_type: a Pydantic model; each field is one typed question.
            instructions: optional framing (not a question - Jev judges text).
            model: override the configured Jev model (e.g. a pinned version).

        Raises:
            FeatureDisabledException: Jev is not enabled/keyed.
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
        user_id: "UUID4",
        decision: JevDecision,
        *,
        output_type_name: str,
    ) -> None:
        """Persist one Jev call as an LLM interaction so it appears in AI usage stats.

        Jev decides but is not the chat model, so the row is tagged ``jev_decision``
        and carries the same provenance (provider, model, tokens) as a chat call.
        The write runs in its own savepoint: a failed flush aborts the transaction,
        and catching that exception without rolling back to a savepoint would leave
        the shared session unusable for the rest of the request.
        """
        from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
        from app.schemas.llm_interaction import LLMInteractionCreate
        from app.services.ai_constants import JEV_OPERATION

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

        The API key is passed explicitly: ``settings`` is loaded from ``.env`` and is
        NOT the process environment, so ``Agent("typesafe:...")`` by name would read an
        absent env var and fail auth. ``TypeSafeProvider`` takes the key directly.
        """
        from pydantic_ai import Agent
        from pydantic_ai.models.typesafe import TypeSafeModel
        from pydantic_ai.providers.typesafe import TypeSafeProvider

        model_name = model or settings.JEV_MODEL
        provider = TypeSafeProvider(api_key=settings.TYPESAFE_API_KEY)
        return Agent(TypeSafeModel(model_name, provider=provider), output_type=output_type, instructions=instructions)


jev_service = JevService()
