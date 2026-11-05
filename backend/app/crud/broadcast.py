"""Broadcast CRUD — date-range queries for the Vault Radio Hour broadcast model."""

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.broadcast import Broadcast


async def get_today_broadcast(db: AsyncSession, vault_id: UUID) -> Broadcast | None:
    """Get today's broadcast for the vault, if one exists.

    Returns the existing broadcast row or None.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_start = datetime.combine(today, datetime.min.time())
    tomorrow_start = datetime.combine(tomorrow, datetime.min.time())

    query = select(Broadcast).where(
        Broadcast.vault_id == vault_id,
        Broadcast.trigger == "daily",
        col(Broadcast.created_at) >= today_start,
        col(Broadcast.created_at) < tomorrow_start,
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def count_trigger_on_date(
    db: AsyncSession,
    vault_id: UUID,
    trigger: str,
    trigger_date: date,
) -> int:
    """Count broadcasts of *trigger* for *vault_id* on *trigger_date*.

    Used to enforce the manual-regeneration rate limit.
    """
    tomorrow = trigger_date + timedelta(days=1)
    day_start = datetime.combine(trigger_date, datetime.min.time())
    day_end = datetime.combine(tomorrow, datetime.min.time())

    query = select(Broadcast).where(
        Broadcast.vault_id == vault_id,
        Broadcast.trigger == trigger,
        col(Broadcast.created_at) >= day_start,
        col(Broadcast.created_at) < day_end,
    )
    result = await db.execute(query)
    return len(result.fetchall())


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
    await db.commit()
    await db.refresh(broadcast)
    return broadcast
