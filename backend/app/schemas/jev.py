"""Typed Jev decision contracts; the producing client lives in ``app.services.jev_service``.

Jev output types must follow the Jev docs: one judgement per field; the prompt
is the material judged, the field docstring the question; pin ``JEV_MODEL``
once a confidence threshold is tuned — ``jev-latest`` shifts the numbers.
"""

from typing import TypeVar

from pydantic import BaseModel

OutputT = TypeVar("OutputT", bound=BaseModel)


class JevFieldAnswer(BaseModel):
    """One judged field. confidence is the probability of the answer shown:
    False at 0.96 means 96% sure it is *not* this — never display without the flag.
    """

    answer: bool
    confidence: float


class JevDecision[OutputT: BaseModel](BaseModel):
    """Typed answer plus per-field 0-1 confidence; pick the acting threshold per use.
    model_name records the versioned id that answered, even for ``jev-latest``.
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
