"""Typed Jev decision contracts shared by every Jev caller.

Jev is a decision model, not a chat model: it answers each field of a Pydantic
output type as a typed question and returns a probability per field. Callers
(chat guardrails, CLI evals) read these shapes, so they live in the schema layer;
the client that produces them stays in ``app.services.jev_service``.

Model shape rules (from the Jev docs) that a caller's output type must respect:
- one judgement per field — never hide two questions in one field;
- the prompt is the material judged, the field docstring is the question;
- pin ``JEV_MODEL`` once a confidence threshold has been tuned, because
  ``jev-latest`` moves and shifts the numbers under it.
"""

from typing import TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


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
