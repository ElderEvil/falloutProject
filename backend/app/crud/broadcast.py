"""Broadcast CRUD — date-range queries for the Vault Radio Hour broadcast model."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.broadcast import Broadcast


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time())
    return start, start + timedelta(days=1)


async def get_today_broadcast(db: AsyncSession, vault_id: UUID) -> Broadcast | None:
    """Get today's broadcast for the vault, if one exists.

    Returns the existing broadcast row or None.
    """
    today_start, tomorrow_start = _day_bounds(datetime.now(UTC).date())

    query = (
        select(Broadcast)
        .where(
            Broadcast.vault_id == vault_id,
            col(Broadcast.created_at) >= today_start,
            col(Broadcast.created_at) < tomorrow_start,
        )
        .order_by(col(Broadcast.created_at).desc(), col(Broadcast.id).desc())
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def get_audio_keys_before(db: AsyncSession, vault_id: UUID, before: datetime) -> list[str]:
    """Audio keys for broadcasts created before ``before``."""
    query = select(Broadcast.audio_key).where(
        Broadcast.vault_id == vault_id,
        col(Broadcast.created_at) < before,
        col(Broadcast.audio_key).is_not(None),
    )
    return [key for key in (await db.execute(query)).scalars().all() if key]


async def count_trigger_on_date(
    db: AsyncSession,
    vault_id: UUID,
    trigger: str,
    trigger_date: date,
) -> int:
    """Count broadcasts of *trigger* for *vault_id* on *trigger_date*.

    Used to enforce the manual-regeneration rate limit.
    """
    day_start, day_end = _day_bounds(trigger_date)

    query = select(func.count()).select_from(Broadcast).where(
        Broadcast.vault_id == vault_id,
        Broadcast.trigger == trigger,
        col(Broadcast.created_at) >= day_start,
        col(Broadcast.created_at) < day_end,
    )
    result = await db.execute(query)
    return int(result.scalar_one())


async def create_broadcast(
    db: AsyncSession,
    vault_id: UUID,
    title: str,
    script: str,
    audio_key: str | None = None,
    trigger: str = "daily",
) -> Broadcast:
    """Create and persist a new broadcast row."""
    broadcast = Broadcast(
        vault_id=vault_id,
        title=title,
        script=script,
        audio_key=audio_key,
        trigger=trigger,
    )
    db.add(broadcast)
    await db.flush()
    return broadcast
