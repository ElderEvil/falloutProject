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

import logging
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.utils.exceptions import FeatureDisabledException

logger = logging.getLogger(__name__)

OutputT = TypeVar("OutputT", bound=BaseModel)

#: Jev refuses anything above this; keep the state + questions under it.
JEV_STATE_TOKEN_LIMIT = 32_000


class JevDecision(BaseModel):
    """A resolved Jev judgement: the typed answer plus per-field confidence.

    ``confidence`` maps each output field to 0-1; pick the acting threshold per
    use - an automatic action deserves a higher bar than flagging for review.
    ``model_name`` records the versioned id that answered, even when the
    ``jev-latest`` alias was requested.
    """

    output: BaseModel
    confidence: dict[str, float]
    model_name: str

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
    ) -> JevDecision:
        """Judge ``state`` against ``output_type``'s fields.

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
        result = await agent.run(state)
        provider_details = result.response.provider_details or {}
        confidence = dict(provider_details.get("confidence") or {})
        return JevDecision(output=result.output, confidence=confidence, model_name=result.response.model_name or "")

    @staticmethod
    def _build_agent(
        output_type: type[OutputT],
        *,
        instructions: str | None,
        model: str | None,
    ) -> Any:
        """Build the Jev agent lazily so importing this module needs no SDK/key."""
        from pydantic_ai import Agent

        model_name = model or settings.JEV_MODEL
        return Agent(f"typesafe:{model_name}", output_type=output_type, instructions=instructions)


jev_service = JevService()
