"""Jev triage label for exploration event narratives (advisory).

Classifies an already-generated event description into a coarse category for log
routing and analytics without brittle keyword rules. Jev never replaces the
generator's ``event_type``: a low-confidence, unconfigured, or failed call
returns no category and the caller keeps the original event type.

One question per field (Jev's rule): the description is the material judged and
the field's option docstrings are the question's options.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.services.jev_service import is_configured, jev_service

logger = logging.getLogger(__name__)


class EventTriage(BaseModel):
    """What kind of wasteland event a log entry describes."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    event_kind: Literal["combat", "loot", "danger", "rest", "discovery", "travel"]
    """Which one best fits: fighting enemies (combat), gaining caps/items/supplies
    (loot), radiation/traps/injury/hazard (danger), healing or camping (rest),
    finding a new place or landmark (discovery), or plain travel (travel)?"""


@dataclass(slots=True)
class TriageResult:
    """Jev category for an event narrative; None means keep the default."""

    category: str | None = None
    confidence: float = 0.0


async def triage_description(description: str) -> TriageResult:
    """Classify an event narrative; empty result when unconfigured, unsure, or failed."""
    if not is_configured() or not description.strip():
        return TriageResult()
    try:
        decision = await jev_service.decide(description, EventTriage)
    except Exception:
        logger.exception("Jev triage failed; keeping generator event type")
        return TriageResult()

    confidence = decision.confidence_for("event_kind")
    if confidence < settings.JEV_TRIAGE_CONFIDENCE:
        logger.info(
            "Jev triage below threshold; keeping generator event type",
            extra={"category": decision.output.event_kind, "confidence": confidence, "model": decision.model_name},
        )
        return TriageResult()

    logger.info(
        "Jev triage applied",
        extra={"category": decision.output.event_kind, "confidence": confidence, "model": decision.model_name},
    )
    return TriageResult(category=decision.output.event_kind, confidence=confidence)
