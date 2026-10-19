"""CRUD operations for GameState model."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
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
        """Get or create state, optionally leaving the insert in the caller's transaction.

        Concurrent first ticks can both see "no row" and both INSERT; the loser
        hits the unique constraint on ``vault_id``. The insert runs inside a
        savepoint so the loser rolls back its partial insert and re-selects the
        winner's committed row instead of surfacing an IntegrityError 500
        (same treatment as ``vault_slot.claim_next``).
        """
        game_state = await CRUDGameState.get_by_vault_id(db_session, vault_id)

        if not game_state:
            game_state = GameState(vault_id=vault_id)
            try:
                async with db_session.begin_nested():
                    db_session.add(game_state)
                    await db_session.flush()
            except IntegrityError:
                # Lost the creation race. The savepoint already rolled our insert
                # back (the pending loser is expunged with it), so the winner's
                # committed row is visible to a plain re-select. No session-level
                # rollback here: it would expire every instance in the session
                # and hand the caller a lazy-load bomb.
                row = await db_session.execute(select(GameState).where(GameState.vault_id == vault_id))
                game_state = row.scalars().first()
                if game_state is None:  # pragma: no cover - constraint fired but row vanished
                    raise
                logger.info("Lost GameState creation race for vault %s; recovered winner's row", vault_id)
                return game_state
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
