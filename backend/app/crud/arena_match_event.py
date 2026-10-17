"""CRUD operations for the arena match journal (ArenaMatchEvent)."""

from pydantic import UUID4
from sqlalchemy.orm import aliased
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RoomTypeEnum
from app.models.arena_match_event import ArenaMatchEvent
from app.models.arena_state import ArenaState
from app.models.room import Room


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
            .order_by(ArenaMatchEvent.created_at.desc(), ArenaMatchEvent.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_vault_snapshot(db_session: AsyncSession, vault_id: UUID4):
        """One statement observes match flags and the latest 40 events coherently.

        Rank only this vault's journal; no roster loads, row creation or combat locks.
        """
        ranked = (
            select(
                ArenaMatchEvent,
                func.row_number()
                .over(
                    partition_by=ArenaMatchEvent.room_id,
                    order_by=(ArenaMatchEvent.created_at.desc(), ArenaMatchEvent.id.desc()),
                )
                .label("position"),
            )
            .join(Room, Room.id == ArenaMatchEvent.room_id)
            .where(Room.vault_id == vault_id, Room.category == RoomTypeEnum.ARENA)
            .subquery()
        )
        event = aliased(ArenaMatchEvent, ranked)
        query = (
            select(Room.id, ArenaState.fight_started_at, ArenaState.last_fight_at, event)
            .outerjoin(ArenaState, ArenaState.room_id == Room.id)
            .outerjoin(ranked, (ranked.c.room_id == Room.id) & (ranked.c.position <= 40))
            .where(Room.vault_id == vault_id, Room.category == RoomTypeEnum.ARENA)
            .order_by(Room.id, ranked.c.position.desc())
        )
        return (await db_session.execute(query)).all()

    @staticmethod
    async def delete_for_room(db_session: AsyncSession, room_id: UUID4) -> int:
        """Delete all journal events of a room (no commit — caller owns the transaction)."""
        events = await CRUDArenaMatchEvent.get_by_room(db_session, room_id)
        for event in events:
            await db_session.delete(event)
        return len(events)


arena_match_event_crud = CRUDArenaMatchEvent()
