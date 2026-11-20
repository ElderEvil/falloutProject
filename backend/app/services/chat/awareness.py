"""Awareness digest: what measurably changed in the vault since the dweller last spoke.

Only measured facts belong here — incident journal entries for this vault, and dwellers
who arrived or died. Resource deltas would need a stored snapshot to compare against;
without one there is nothing honest to say, so no line is emitted. ``since is None``
means the dweller has never spoken to this player: there is nothing to catch up on.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent

logger = logging.getLogger(__name__)

MAX_LINE_CHARS = 90


def _line(body: str) -> str:
    """One factual past-tense sentence, collapsed and clipped to the line budget."""
    text = " ".join(body.split()).strip()
    if text and text[-1] not in ".!?":
        text = f"{text}."
    if len(text) > MAX_LINE_CHARS:
        text = f"{text[: MAX_LINE_CHARS - 3].rstrip()}..."
    return text


async def _incident_lines(db: AsyncSession, vault_id: UUID, since: datetime, limit: int) -> list[str]:
    """The latest journal line of each incident touched since ``since``, oldest first."""
    incident_ids = (await db.exec(select(col(Incident.id)).where(col(Incident.vault_id) == vault_id))).all()
    if not incident_ids:
        return []
    events = (
        await db.exec(
            select(IncidentEvent)
            .where(
                col(IncidentEvent.incident_id).in_(incident_ids),
                col(IncidentEvent.created_at) > since,
            )
            .order_by(col(IncidentEvent.created_at).desc())
        )
    ).all()

    latest: dict[UUID, IncidentEvent] = {}
    for event in events:
        latest.setdefault(event.incident_id, event)

    newest = list(latest.values())[:limit]
    return [_line(event.message) for event in reversed(newest)]


async def _dweller_lines(db: AsyncSession, vault_id: UUID, since: datetime) -> list[str]:
    """Arrivals and deaths since ``since`` — names for one, a measured count for many."""
    joined = (
        await db.exec(
            select(Dweller)
            .where(col(Dweller.vault_id) == vault_id, col(Dweller.created_at) > since)
            .order_by(col(Dweller.created_at).asc())
        )
    ).all()
    deceased = (
        await db.exec(
            select(Dweller).where(
                col(Dweller.vault_id) == vault_id,
                col(Dweller.is_dead).is_(True),
                col(Dweller.death_timestamp) > since,
            )
        )
    ).all()

    lines: list[str] = []
    if len(joined) == 1:
        lines.append(_line(f"{joined[0].display_name} joined the vault"))
    elif joined:
        lines.append(_line(f"{len(joined)} dwellers joined the vault"))
    if len(deceased) == 1:
        lines.append(_line(f"{deceased[0].display_name} died"))
    elif deceased:
        lines.append(_line(f"{len(deceased)} dwellers died"))
    return lines


async def build_awareness_digest(
    db: AsyncSession, *, vault_id: UUID, since: datetime | None, max_lines: int
) -> list[str]:
    """One line per measured change since ``since``; empty when there is no baseline."""
    if since is None or max_lines <= 0:
        return []

    lines = await _incident_lines(db, vault_id, since, max_lines)
    lines.extend(await _dweller_lines(db, vault_id, since))
    return lines[:max_lines]
