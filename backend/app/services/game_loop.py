"""Main game loop coordinator for vault simulation."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.vault import vault as vault_crud
from app.models.game_state import GameState
from app.models.vault import Vault
from app.services.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

# Game loop configuration
TICK_INTERVAL = 60  # Seconds between ticks
MAX_OFFLINE_CATCHUP = 3600  # Maximum 1 hour of catch-up per tick


class GameLoopService:
    """Main game loop coordinator."""

    def __init__(self):
        self.resource_manager = ResourceManager()
        self.logger = logging.getLogger(__name__)

    async def process_game_tick(self, db_session: AsyncSession) -> dict:
        """
        Process a single game tick for all active vaults.

        Returns:
            dict: Statistics about the tick processing
        """
        stats = {
            "vaults_processed": 0,
            "vaults_skipped": 0,
            "errors": 0,
            "total_time": 0,
        }

        start_time = datetime.utcnow()

        # Get all active vaults
        active_vaults = await self._get_active_vaults(db_session)

        self.logger.info(f"Processing game tick for {len(active_vaults)} vaults")  # noqa: G004

        for vault in active_vaults:
            try:
                await self.process_vault_tick(db_session, vault.id)
                stats["vaults_processed"] += 1
            except Exception as e:
                self.logger.error(f"Error processing vault {vault.id}: {e}", exc_info=True)  # noqa: G004, G201
                stats["errors"] += 1

        stats["total_time"] = (datetime.utcnow() - start_time).total_seconds()

        self.logger.info(
            f"Game tick completed: {stats['vaults_processed']} processed, "  # noqa: G004
            f"{stats['errors']} errors, {stats['total_time']:.2f}s"
        )

        return stats

    async def process_vault_tick(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """
        Process a single tick for a specific vault.

        Args:
            db_session: Database session
            vault_id: UUID of the vault to process

        Returns:
            dict: Results of the tick processing
        """
        # Get or create game state
        game_state = await self._get_or_create_game_state(db_session, vault_id)

        # Skip if paused
        if game_state.is_paused:
            self.logger.debug(f"Vault {vault_id} is paused, skipping tick")  # noqa: G004
            return {"status": "paused"}

        # Calculate time since last tick
        seconds_passed = game_state.calculate_offline_time()

        # Cap catch-up time to prevent abuse
        if seconds_passed > MAX_OFFLINE_CATCHUP:
            self.logger.warning(
                f"Vault {vault_id} offline time ({seconds_passed}s) exceeds max catch-up, capping to {MAX_OFFLINE_CATCHUP}s"  # noqa: E501, G004
            )
            seconds_passed = MAX_OFFLINE_CATCHUP

        # Use minimum tick interval if too little time has passed
        seconds_passed = max(seconds_passed, TICK_INTERVAL)

        results = {
            "vault_id": str(vault_id),
            "seconds_passed": seconds_passed,
            "updates": {},
        }

        # === PHASE 1: Resource Management ===
        try:
            resource_update, resource_events = await self.resource_manager.process_vault_resources(
                db_session, vault_id, seconds_passed
            )

            # Apply resource updates
            await vault_crud.update(db_session, vault_id, resource_update)

            results["updates"]["resources"] = {
                "power": resource_update.power,
                "food": resource_update.food,
                "water": resource_update.water,
                "events": resource_events,
            }

        except Exception as e:
            self.logger.error(f"Error updating resources for vault {vault_id}: {e}", exc_info=True)  # noqa: G004, G201
            results["updates"]["resources"] = {"error": str(e)}

        # === PHASE 2: Incident Management ===
        # TODO: Implement in next phase
        results["updates"]["incidents"] = {"processed": 0, "spawned": 0}

        # === PHASE 3: Dweller Management ===
        # TODO: Implement in next phase
        results["updates"]["dwellers"] = {"health_updated": 0, "leveled_up": 0}

        # === PHASE 4: Event System ===
        # TODO: Implement in next phase
        results["updates"]["events"] = {"triggered": 0}

        # Update game state
        game_state.update_tick(seconds_passed)
        db_session.add(game_state)
        await db_session.commit()

        return results

    async def pause_vault(self, db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Pause game loop for a specific vault."""
        game_state = await self._get_or_create_game_state(db_session, vault_id)
        game_state.pause()
        db_session.add(game_state)
        await db_session.commit()
        await db_session.refresh(game_state)

        self.logger.info(f"Vault {vault_id} paused")  # noqa: G004
        return game_state

    async def resume_vault(self, db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Resume game loop for a specific vault."""
        game_state = await self._get_or_create_game_state(db_session, vault_id)
        game_state.resume()
        db_session.add(game_state)
        await db_session.commit()
        await db_session.refresh(game_state)

        self.logger.info(f"Vault {vault_id} resumed")  # noqa: G004
        return game_state

    async def get_vault_status(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Get current game loop status for a vault."""
        game_state = await self._get_or_create_game_state(db_session, vault_id)

        return {
            "vault_id": str(vault_id),
            "is_active": game_state.is_active,
            "is_paused": game_state.is_paused,
            "total_game_time": game_state.total_game_time,
            "last_tick_time": game_state.last_tick_time.isoformat(),
            "offline_time": game_state.calculate_offline_time(),
        }

    async def _get_active_vaults(self, db_session: AsyncSession) -> list[Vault]:
        """Get all vaults that should be processed this tick."""
        # First get all active game states
        game_state_query = select(GameState).where((GameState.is_active == True) & (GameState.is_paused == False))
        result = await db_session.execute(game_state_query)
        active_game_states = list(result.scalars().all())

        if not active_game_states:
            return []

        # Then get the corresponding vaults
        vault_ids = [gs.vault_id for gs in active_game_states]
        vault_query = select(Vault).where(Vault.id.in_(vault_ids))
        vault_result = await db_session.execute(vault_query)
        return list(vault_result.scalars().all())

    async def _get_or_create_game_state(self, db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Get existing game state or create a new one."""
        query = select(GameState).where(GameState.vault_id == vault_id)
        result = await db_session.execute(query)
        game_state = result.scalars().first()

        if not game_state:
            game_state = GameState(vault_id=vault_id)
            db_session.add(game_state)
            await db_session.commit()
            await db_session.refresh(game_state)
            self.logger.info(f"Created new game state for vault {vault_id}")  # noqa: G004

        return game_state


# Global instance
game_loop_service = GameLoopService()
