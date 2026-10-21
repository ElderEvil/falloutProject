"""CRUD operations for GameState model."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.game_state import GameState

logger = logging.getLogger(__name__)


class CRUDGameState:
    """CRUD operations for game state management."""

    @staticmethod
    async def get_by_vault_id(db_session: AsyncSession, vault_id: UUID4) -> GameState | None:
        """Get game state by vault ID."""
        query = select(GameState).where(GameState.vault_id == vault_id)
        result = await db_session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_or_create(db_session: AsyncSession, vault_id: UUID4, *, commit: bool = True) -> GameState:
        """Get or create state, race-safe against concurrent first ticks.

        Concurrent first ticks can both see "no row" and both INSERT; the loser
        hits the unique constraint on ``vault_id``. The insert is issued as
        ``INSERT ... ON CONFLICT DO NOTHING`` so the loser's statement is a
        no-op instead of an error — no exception, no rollback, no change to the
        caller's transaction topology — then the row is re-selected and the
        winner's state is returned to both racers.
        """
        game_state = await CRUDGameState.get_by_vault_id(db_session, vault_id)

        if not game_state:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = (
                pg_insert(GameState)
                .values(vault_id=vault_id, resource_remainders={})
                .on_conflict_do_nothing(index_elements=["vault_id"])
            )
            await db_session.execute(stmt)
            game_state = await CRUDGameState.get_by_vault_id(db_session, vault_id)
            if commit:
                await db_session.commit()
                await db_session.refresh(game_state)

        return game_state

    @staticmethod
    async def pause(db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Pause game state for a vault."""
        game_state = await CRUDGameState.get_or_create(db_session, vault_id)
        game_state.pause()
        db_session.add(game_state)
        await db_session.commit()
        await db_session.refresh(game_state)
        return game_state

    @staticmethod
    async def record_presence(db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Stamp a visibility-gated vault-view heartbeat for spawn gating."""
        game_state = await CRUDGameState.get_or_create(db_session, vault_id)
        game_state.last_presence_at = datetime.utcnow()
        db_session.add(game_state)
        await db_session.commit()
        await db_session.refresh(game_state)
        return game_state

    @staticmethod
    async def resume(db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Resume game state for a vault."""
        game_state = await CRUDGameState.get_or_create(db_session, vault_id)
        game_state.resume()
        db_session.add(game_state)
        await db_session.commit()
        await db_session.refresh(game_state)
        return game_state

    @staticmethod
    async def update_tick(db_session: AsyncSession, vault_id: UUID4, seconds_passed: int) -> GameState:
        """Update game state after a tick."""
        game_state = await CRUDGameState.get_or_create(db_session, vault_id)
        game_state.update_tick(seconds_passed)
        db_session.add(game_state)
        await db_session.commit()
        await db_session.refresh(game_state)
        return game_state

    @staticmethod
    async def get_all_active(db_session: AsyncSession) -> list[GameState]:
        """Get all active (not paused) game states."""
        query = select(GameState).where(GameState.is_active & ~GameState.is_paused)
        result = await db_session.execute(query)
        return list(result.scalars().all())


# Global instance
game_state_crud = CRUDGameState()
