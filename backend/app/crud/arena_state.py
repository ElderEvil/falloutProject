"""CRUD operations for arena match state (ArenaState)."""

from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
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
        """Get or create state, recovering from a concurrent creation race.

        The insert runs inside a savepoint: a loser of the creation race rolls
        back its unique-violated insert and re-selects the winner's row instead
        of surfacing an IntegrityError.
        """
        state = await CRUDArenaState.get(db_session, room_id)
        if state is None:
            state = ArenaState(room_id=room_id)
            try:
                async with db_session.begin_nested():
                    db_session.add(state)
                    await db_session.flush()
            except IntegrityError:
                # Lost the creation race; the savepoint already rolled the loser
                # back. Re-select the winner's committed row — no session-level
                # rollback (it would expire the session's whole identity map).
                row = await db_session.execute(select(ArenaState).where(ArenaState.room_id == room_id))
                state = row.scalars().first()
                if state is None:  # pragma: no cover - constraint fired but row vanished
                    raise
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
