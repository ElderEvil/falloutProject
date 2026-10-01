"""TypeSafe Jev decision-model client — typed questions with confidence.

Jev is not a language model: it answers each field of a Pydantic output type as
a typed question and returns a probability per field. It is complementary to the
chat agent (which writes text); callers ask Jev to *decide* something concrete.

Model shape rules (from the Jev docs) that callers must respect:
- one judgement per field — never hide two questions in one field;
- the prompt is the material judged, the field docstring is the question;
- pin ``JEV_MODEL`` once a confidence threshold has been tuned, because
  ``jev-latest`` moves and shifts the numbers under it.

The service degrades to "disabled" without a key so no caller needs secrets at
import time; every entry point returns a typed :class:`JevDecision`.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.utils.exceptions import FeatureDisabledException

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

OutputT = TypeVar("OutputT", bound=BaseModel)

#: Jev refuses anything above this; keep the state + questions under it.
JEV_STATE_TOKEN_LIMIT = 32_000


class JevFieldAnswer(BaseModel):
    """One judged field: the answer and how confident Jev was in it.

    ``confidence`` is the probability of the answer shown, so a ``False`` answer at
    0.96 means "96% sure it is *not* this" - never display it without the flag.
    """

    answer: bool
    confidence: float


class JevDecision[OutputT: BaseModel](BaseModel):
    """A resolved Jev judgement: the typed answer plus per-field confidence.

    ``confidence`` maps each output field to 0-1; pick the acting threshold per
    use - an automatic action deserves a higher bar than flagging for review.
    ``model_name`` records the versioned id that answered, even when the
    ``jev-latest`` alias was requested.
    """

    output: OutputT
    confidence: dict[str, float]
    model_name: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    elapsed_s: float = 0.0

    def confidence_for(self, field: str) -> float:
        """Confidence for one field, 0.0 when Jev reported none."""
        return self.confidence.get(field, 0.0)


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
        Recording is best-effort: a failure must not break the decision the caller
        already made.
        """
        from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
        from app.schemas.llm_interaction import LLMInteractionCreate
        from app.services.ai_constants import JEV_OPERATION

        try:
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
