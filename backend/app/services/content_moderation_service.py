"""Player-text moderation via Jev (experimental).

Screens player-controlled free text (dweller names, bio addenda) with a
``score`` question and rejects high-confidence toxic content. Jev errors fail
OPEN with a log so writes keep working when Jev is unreachable.
"""

import logging

from app.services import jev_service
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

TOXIC_SCORE = 0.66
TOXIC_CONFIDENCE = 0.8


async def moderate_player_text(text: str, *, field: str = "text") -> None:
    """Reject player text Jev scores as toxic with high confidence.

    Raises:
        ValidationException: Text judged hateful/toxic.
    """
    if not text.strip():
        return
    try:
        payload = await jev_service.decide(
            text,
            {
                "toxicity": jev_service.make_score(
                    f"How toxic or hateful is this player-chosen {field}?",
                    ["Clean", "Rude", "Hateful"],
                )
            },
        )
    except Exception:
        logger.exception("Jev moderation failed open for player %s", field)
        return
    answers = payload.get("answers", {}) if isinstance(payload, dict) else {}
    answer = answers.get("toxicity")
    if not isinstance(answer, dict):
        return
    try:
        score = float(answer.get("score", 0.0))
        confidence = float(answer.get("confidence", 0.0))
    except (TypeError, ValueError):
        return
    if score >= TOXIC_SCORE and confidence >= TOXIC_CONFIDENCE:
        raise ValidationException(f"This {field} was rejected by automated moderation")
