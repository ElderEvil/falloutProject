"""CRUD operations for GameState model."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.game_state import GameState


class CRUDGameState:
    """CRUD operations for game state management."""

    @staticmethod
    async def get_by_vault_id(db_session: AsyncSession, vault_id: UUID4) -> GameState | None:
        """Get game state by vault ID."""
        query = select(GameState).where(GameState.vault_id == vault_id)
        result = await db_session.exec(query)
        return result.first()

    @staticmethod
    async def get_or_create(db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Get existing game state or create new one."""
        game_state = await CRUDGameState.get_by_vault_id(db_session, vault_id)

        if not game_state:
            game_state = GameState(vault_id=vault_id)
            db_session.add(game_state)
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
        query = select(GameState).where((GameState.is_active == True) & (GameState.is_paused == False))
        result = await db_session.exec(query)
        return list(result.all())


# Global instance
game_state_crud = CRUDGameState()
