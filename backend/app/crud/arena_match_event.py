"""CRUD operations for the arena match journal (ArenaMatchEvent)."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.arena_match_event import ArenaMatchEvent


class CRUDArenaMatchEvent:
    """CRUD operations for arena journal rows."""

    @staticmethod
    async def get_by_room(db_session: AsyncSession, room_id: UUID4) -> list[ArenaMatchEvent]:
        """All journal events of a room, oldest first."""
        result = await db_session.execute(
            select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == room_id).order_by(ArenaMatchEvent.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_recent_by_room(db_session: AsyncSession, room_id: UUID4, limit: int = 40) -> list[ArenaMatchEvent]:
        """Recent journal events of a room, newest first."""
        result = await db_session.execute(
            select(ArenaMatchEvent)
            .where(ArenaMatchEvent.room_id == room_id)
            .order_by(ArenaMatchEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_for_room(db_session: AsyncSession, room_id: UUID4) -> int:
        """Delete all journal events of a room (no commit — caller owns the transaction)."""
        events = await CRUDArenaMatchEvent.get_by_room(db_session, room_id)
        for event in events:
            await db_session.delete(event)
        return len(events)


arena_match_event_crud = CRUDArenaMatchEvent()
