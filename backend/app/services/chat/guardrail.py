"""Jev guardrail screening for player-authored text.

Two typed yes/no questions (prompt-injection, toxic); blocks only on high-confidence affirmative. Any Jev
failure fails OPEN so gameplay never breaks; the verdict is advisory, a filter alongside deterministic
checks — Jev answers the exact question written, not a moderator.
"""

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.ai_constants import JEV_OPERATION
from app.core.config import settings
from app.schemas.chat import ChatGuardrail
from app.schemas.jev import JevFieldAnswer
from app.services.jev_service import is_configured, jev_service

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GuardrailVerdict:
    """Allow by default; blocked only on a high-confidence Jev affirmative.

    ``fields`` carries each question's answer and confidence together, so callers
    reporting the verdict show which way it answered - a bare confidence beside a
    field named ``jailbreak`` reads as P(jailbreak) when a false answer means it is
    actually P(not jailbreak).
    """

    blocked: bool = False
    reason: str | None = None
    ran: bool = False
    fields: dict[str, JevFieldAnswer] = field(default_factory=dict)


async def screen_message(
    message_text: str,
    *,
    db_session: AsyncSession | None = None,
    user_id: UUID | None = None,
    kind: str = "chat input",
    usage: str = JEV_OPERATION,
) -> GuardrailVerdict:
    """Screen one player-authored text; allow on low confidence or any Jev failure.

    When a session and user are supplied, the Jev call is recorded as a usage row tagged
    ``usage`` so it shows up in AI usage stats; screening itself never depends on that.
    """
    if not is_configured() or not message_text.strip():
        return GuardrailVerdict()

    try:
        decision = await jev_service.decide(message_text, ChatGuardrail)
    except Exception:
        logger.exception("Jev guardrail failed open for %s", kind)
        return GuardrailVerdict()

    if db_session is not None and user_id is not None:
        await jev_service.record_usage(db_session, user_id, decision, output_type_name="ChatGuardrail", usage=usage)

    fields = {
        name: JevFieldAnswer(answer=bool(getattr(decision.output, name)), confidence=decision.confidence_for(name))
        for name in ("jailbreak", "toxic")
    }

    for name, label, threshold in (
        ("jailbreak", "prompt-injection", settings.JEV_GUARDRAIL_INJECTION_CONFIDENCE),
        ("toxic", "toxic content", settings.JEV_GUARDRAIL_TOXIC_CONFIDENCE),
    ):
        if fields[name].answer and fields[name].confidence >= threshold:
            logger.warning(
                "Jev guardrail blocked %s",
                kind,
                extra={
                    "reason": label,
                    "confidence": fields[name].confidence,
                    "threshold": threshold,
                    "model": decision.model_name,
                },
            )
            return GuardrailVerdict(blocked=True, reason=f"blocked: suspected {label}", ran=True, fields=fields)

    logger.info(
        "Jev guardrail allowed %s",
        kind,
        extra={"fields": {n: f.model_dump() for n, f in fields.items()}, "model": decision.model_name},
    )
    return GuardrailVerdict(ran=True, fields=fields)


async def screen_input(
    db_session: AsyncSession,
    *,
    user_id: UUID,
    text: str,
    kind: str = "chat input",
    usage: str = JEV_OPERATION,
) -> GuardrailVerdict:
    """Screen player text and commit its usage row before the caller's transaction opens.

    Every transport and every player-writable text field enters here, so one policy covers
    text chat, voice chat and dweller profiles instead of each caller enforcing its own.
    """
    verdict = await screen_message(text, db_session=db_session, user_id=user_id, kind=kind, usage=usage)
    if verdict.ran:
        await db_session.commit()
    return verdict
