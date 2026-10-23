"""CRUD operations for arena match state (ArenaState)."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.arena_state import ArenaState
from app.models.room import Room


class CRUDArenaState:
    """Persistence for the per-room arena selection and match flags."""

    @staticmethod
    async def get(db_session: AsyncSession, room_id: UUID4) -> ArenaState | None:
        result = await db_session.execute(select(ArenaState).where(ArenaState.room_id == room_id))
        return result.scalars().first()

    @staticmethod
    async def get_for_update(db_session: AsyncSession, room_id: UUID4) -> ArenaState | None:
        """Serialize selection/start/resolve, even before an ArenaState exists."""
        await db_session.execute(select(Room.id).where(Room.id == room_id).with_for_update())
        query = select(ArenaState).where(ArenaState.room_id == room_id).with_for_update()
        return (await db_session.execute(query.execution_options(populate_existing=True))).scalars().first()

    @staticmethod
    async def get_or_create(db_session: AsyncSession, room_id: UUID4) -> ArenaState:
        """Get or create state, race-safe against concurrent creation.

        The insert is issued as ``INSERT ... ON CONFLICT DO NOTHING`` so the
        loser of a creation race gets a no-op instead of an IntegrityError,
        then the winner's row is re-selected and returned to both racers.
        """
        state = await CRUDArenaState.get(db_session, room_id)
        if state is None:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(ArenaState).values(room_id=room_id).on_conflict_do_nothing(index_elements=["room_id"])
            await db_session.execute(stmt)
            state = await CRUDArenaState.get(db_session, room_id)
        return state

    @staticmethod
    async def get_by_fighter(db_session: AsyncSession, dweller_id: UUID4) -> list[ArenaState]:
        """Arena state rows where the dweller occupies any fighter slot."""
        query = select(ArenaState).where(
            (ArenaState.fighter_a_id == dweller_id)
            | (ArenaState.fighter_b_id == dweller_id)
            | (ArenaState.fighter_c_id == dweller_id)
            | (ArenaState.fighter_d_id == dweller_id)
        )
        query = query.order_by(ArenaState.room_id).with_for_update().execution_options(populate_existing=True)
        result = await db_session.execute(query)
        return list(result.scalars().all())


arena_state_crud = CRUDArenaState()
