"""Jev triage labels for exploration event narratives (experimental).

Classifies an already-generated event description with a ``choice`` question
so log routing/analytics need no brittle keyword rules. Low-confidence or
failed calls return None and the caller keeps the generator's event type.
"""

import logging
from dataclasses import dataclass

from app.services import jev_service

logger = logging.getLogger(__name__)

TRIAGE_CONFIDENCE = 0.8

TRIAGE_QUESTION = jev_service.make_choice(
    "What kind of wasteland event does this log entry describe?",
    {
        "combat": "Fighting raiders, creatures, or other enemies",
        "loot": "Finding caps, items, supplies, or treasure",
        "danger": "Radiation, traps, injury, or environmental hazards",
        "rest": "Resting, healing, camping, or recovering",
        "discovery": "Discovering a new location or place",
    },
)


@dataclass
class TriageResult:
    """Jev category for an event narrative; None category means keep the default."""

    category: str | None = None
    confidence: float = 0.0


def parse_choice_answer(answer: dict) -> tuple[str | None, float]:
    """Extract (choice, confidence) from a choice answer in either known Zen shape."""
    if not isinstance(answer, dict):
        return None, 0.0
    choice = answer.get("choice")
    if not isinstance(choice, str):
        return None, 0.0
    return choice, float(answer.get("confidence", 0.0))


async def triage_description(description: str) -> TriageResult:
    """Classify an event narrative; return empty result on low confidence or Jev errors."""
    if not description.strip():
        return TriageResult()
    try:
        payload = await jev_service.decide(description, {"event_kind": TRIAGE_QUESTION})
    except Exception:
        logger.exception("Jev triage failed; keeping generator event type")
        return TriageResult()
    answers = payload.get("answers", {}) if isinstance(payload, dict) else {}
    category, confidence = parse_choice_answer(answers.get("event_kind", {}))
    if category is None or confidence < TRIAGE_CONFIDENCE:
        return TriageResult()
    return TriageResult(category=category, confidence=confidence)
