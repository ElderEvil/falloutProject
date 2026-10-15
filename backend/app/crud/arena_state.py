"""CRUD operations for arena match state (ArenaState)."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.arena_state import ArenaState


class CRUDArenaState:
    """Persistence for the per-room arena selection and match flags."""

    @staticmethod
    async def get(db_session: AsyncSession, room_id: UUID4) -> ArenaState | None:
        result = await db_session.execute(select(ArenaState).where(ArenaState.room_id == room_id))
        return result.scalars().first()

    @staticmethod
    async def get_or_create(db_session: AsyncSession, room_id: UUID4) -> ArenaState:
        state = await CRUDArenaState.get(db_session, room_id)
        if state is None:
            state = ArenaState(room_id=room_id)
            db_session.add(state)
            await db_session.flush()
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
        result = await db_session.execute(query)
        return list(result.scalars().all())


arena_state_crud = CRUDArenaState()
