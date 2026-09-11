"""Main game loop coordinator for vault simulation."""

import logging
import random
from datetime import datetime

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import game_state_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.relationship import Relationship
from app.models.vault import Vault
from app.services.game_tick import dwellers_tick, family_tick
from app.services.resource_manager import ResourceManager
from app.services.stream_manager import sse_manager
from app.utils.dwellers import group_dwellers_by_room  # ruff: ignore[unused-import] — test patch anchor; live use is in family_tick
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException

logger = logging.getLogger(__name__)


class GameLoopService:
    """Main game loop coordinator."""

    def __init__(self):
        self.resource_manager = ResourceManager()
        self.logger = logging.getLogger(__name__)

    async def process_game_tick(self, db_session: AsyncSession) -> dict:
        """Process a single game tick for all active vaults.

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

        self.logger.info(f"Processing game tick for {len(active_vaults)} vaults")

        for vault in active_vaults:
            try:
                await self.process_vault_tick(db_session, vault.id)
                stats["vaults_processed"] += 1
            except (SQLAlchemyError, ResourceNotFoundException, VaultOperationException) as e:
                self.logger.error(f"Error processing vault {vault.id}: {e}", exc_info=True)
                stats["errors"] += 1

        stats["total_time"] = (datetime.utcnow() - start_time).total_seconds()

        self.logger.info(
            f"Game tick completed: {stats['vaults_processed']} processed, "
            f"{stats['errors']} errors, {stats['total_time']:.2f}s"
        )

        return stats

    async def process_vault_tick(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Process a single tick for a specific vault.

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
            self.logger.debug(f"Vault {vault_id} is paused, skipping tick")
            return {"status": "paused"}

        # Calculate time since last tick
        seconds_passed = game_state.calculate_offline_time()

        # Cap catch-up time to prevent abuse
        if seconds_passed > game_config.game_loop.max_offline_catchup:
            self.logger.warning(
                f"Vault {vault_id} offline time ({seconds_passed}s) exceeds max catch-up, "
                f"capping to {game_config.game_loop.max_offline_catchup}s"
            )
            seconds_passed = game_config.game_loop.max_offline_catchup

        # Use minimum tick interval if too little time has passed
        seconds_passed = max(seconds_passed, game_config.game_loop.tick_interval)

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
            await vault_crud.update(db_session, vault_id, resource_update)

            # Advance the tick boundary in the same transaction as the resource
            # update: if a later phase raises and game_tick retries, the retried
            # tick recomputes seconds_passed from this boundary instead of
            # reapplying the same production window and duplicating events.
            game_state.update_tick(seconds_passed)
            db_session.add(game_state)
            await db_session.commit()

            await self.resource_manager.emit_production_events(vault_id, resource_events)
            results["updates"]["resources"] = {
                "power": resource_update.power,
                "food": resource_update.food,
                "water": resource_update.water,
                "events": resource_events.model_dump(),
            }
        except (SQLAlchemyError, ResourceNotFoundException, VaultOperationException) as e:
            self.logger.error(f"Error updating resources for vault {vault_id}: {e}", exc_info=True)
            results["updates"]["resources"] = {"error": str(e)}

        # === PHASE 2: Incident Management ===
        # Incident combat runs on its own fast cadence (incident_tick actor), not here.

        # === PHASE 3: Wasteland Exploration ===
        exploration_update = await self._process_explorations(db_session, vault_id)
        results["updates"]["explorations"] = exploration_update

        # === PHASE 4: Dweller Management ===
        dweller_update = await self._process_dwellers(db_session, vault_id, seconds_passed)
        results["updates"]["dwellers"] = dweller_update

        # === PHASE 4.25: Youth Apprenticeships ===
        apprenticeship_update = await self._process_apprenticeships(db_session, vault_id)
        results["updates"]["apprenticeships"] = apprenticeship_update

        # === PHASE 4.5: Training System ===
        training_update = await self._process_training(db_session, vault_id)
        results["updates"]["training"] = training_update

        # === PHASE 4.6: Happiness System ===
        happiness_update = await self._process_happiness(db_session, vault_id, seconds_passed)
        results["updates"]["happiness"] = happiness_update

        # === PHASE 4.7: Relationships & Breeding System ===
        breeding_update = await self._process_breeding(db_session, vault_id)
        results["updates"]["breeding"] = breeding_update

        # === PHASE 4.8: Arena System ===
        # Arena fights run on their own fast cadence (arena_tick actor), not here.

        # === PHASE 5: Event System ===
        event_update = await self._process_events(db_session, vault_id, seconds_passed, game_state)
        results["updates"]["events"] = event_update

        try:
            await sse_manager.publish(
                vault_id,
                "game_ticks",
                {
                    "event_id": str(game_state.last_tick_time.isoformat()),
                    "type": "game_tick",
                    "vault_id": str(vault_id),
                    "results": results,
                },
            )
        except Exception:
            self.logger.exception(f"Failed to publish SSE tick for vault {vault_id}")

        return results

    async def pause_vault(self, db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Pause game loop for a specific vault."""
        game_state = await game_state_crud.pause(db_session, vault_id)
        self.logger.info(f"Vault {vault_id} paused")
        return game_state

    async def resume_vault(self, db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Resume game loop for a specific vault."""
        game_state = await game_state_crud.resume(db_session, vault_id)
        self.logger.info(f"Vault {vault_id} resumed")
        return game_state

    async def get_vault_status(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Get current game loop status for a vault."""
        game_state = await self._get_or_create_game_state(db_session, vault_id)
        game_state.update_activity()
        db_session.add(game_state)
        await db_session.commit()

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
        active_game_states = await game_state_crud.get_all_active(db_session)
        if not active_game_states:
            return []

        # Then get the corresponding vaults
        vault_ids = [gs.vault_id for gs in active_game_states]
        return list(await vault_crud.get_by_ids(vault_ids, db_session))

    async def _get_or_create_game_state(self, db_session: AsyncSession, vault_id: UUID4) -> GameState:
        """Get existing game state or create a new one."""
        return await game_state_crud.get_or_create(db_session, vault_id)

    async def _process_explorations(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Process all active explorations for a vault."""
        return await dwellers_tick.process_explorations(db_session, vault_id)

    async def _award_work_xp(self, db_session: AsyncSession, dweller, room) -> dict:
        """Award work XP to a dweller and check for level-up."""
        return await dwellers_tick.award_work_xp(db_session, dweller, room)

    async def _process_dwellers(
        self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int | None = None
    ) -> dict:
        """Process dweller updates for a vault."""
        return await dwellers_tick.process_dwellers(db_session, vault_id, seconds_passed)

    async def _process_apprenticeships(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Advance eligible youth apprentices by at most one SPECIAL point per tick."""
        return await dwellers_tick.process_apprenticeships(db_session, vault_id)

    async def _process_training(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Process all active training sessions for a vault."""
        return await dwellers_tick.process_training(db_session, vault_id)

    async def _process_happiness(self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int) -> dict:
        """Process happiness updates for all dwellers in a vault."""
        return await dwellers_tick.process_happiness(db_session, vault_id, seconds_passed)

    async def _process_events(
        self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int, game_state: GameState | None = None
    ) -> dict:
        """Fire weighted random vault events (raider scout, resource cache, wanderer)."""
        return await family_tick.process_events(db_session, vault_id, seconds_passed, game_state, rng=random)

    async def _fetch_existing_relationships(
        self, db_session: AsyncSession, dweller_ids: set[UUID4]
    ) -> list[Relationship]:
        """Batch fetch all relationships for a set of dweller IDs."""
        return await family_tick.fetch_existing_relationships(db_session, dweller_ids)

    def _build_relationships_map(self, relationships: list[Relationship]) -> dict[tuple[UUID4, UUID4], Relationship]:
        """Build a bidirectional lookup map for relationships."""
        return family_tick.build_relationships_map(relationships)

    async def _update_pair_affinity(
        self,
        db_session: AsyncSession,
        dweller1: Dweller,
        dweller2: Dweller,
        relationships_map: dict[tuple[UUID4, UUID4], Relationship],
        new_relationships: list[tuple[Relationship, int]],
    ) -> int:
        """Update affinity for a pair of dwellers, creating relationship if needed."""
        return await family_tick.update_pair_affinity(
            db_session, dweller1, dweller2, relationships_map, new_relationships
        )

    async def _create_new_relationships(
        self, db_session: AsyncSession, new_relationships: list[tuple[Relationship, int]]
    ) -> int:
        """Bulk create new relationships and update their affinity."""
        return await family_tick.create_new_relationships(db_session, new_relationships)

    async def _update_room_relationships(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Update relationship affinity for dwellers sharing living quarters."""
        return await family_tick.update_room_relationships(self, db_session, vault_id)

    async def _process_pregnancies_and_births(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Check for conception and process due pregnancies."""
        return await family_tick.process_pregnancies_and_births(db_session, vault_id)

    async def _age_children(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Age children to adults if they're ready."""
        return await family_tick.age_children(db_session, vault_id)

    async def _process_breeding(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """Process relationships and breeding for a vault."""
        return await family_tick.process_breeding(self, db_session, vault_id)


# Global instance
game_loop_service = GameLoopService()
