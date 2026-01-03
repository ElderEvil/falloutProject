"""Main game loop coordinator for vault simulation."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config.game_balance import MAX_OFFLINE_CATCHUP, TICK_INTERVAL
from app.crud import exploration as crud_exploration
from app.crud.incident import incident_crud
from app.crud.vault import vault as vault_crud
from app.models.game_state import GameState
from app.models.vault import Vault
from app.services.happiness_service import happiness_service
from app.services.resource_manager import ResourceManager
from app.services.wasteland_service import wasteland_service

logger = logging.getLogger(__name__)


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

    async def process_vault_tick(self, db_session: AsyncSession, vault_id: UUID4) -> dict:  # noqa: PLR0915
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
        try:
            incident_update = await self._process_incidents(db_session, vault_id, seconds_passed)
            results["updates"]["incidents"] = incident_update
        except Exception as e:
            self.logger.error(  # noqa: G201
                f"Error processing incidents for vault {vault_id}: {e}",  # noqa: G004
                exc_info=True,
            )
            results["updates"]["incidents"] = {"error": str(e), "processed": 0, "spawned": 0}

        # === PHASE 3: Wasteland Exploration ===
        try:
            exploration_update = await self._process_explorations(db_session, vault_id)
            results["updates"]["explorations"] = exploration_update
        except Exception as e:
            self.logger.error(  # noqa: G201
                f"Error processing explorations for vault {vault_id}: {e}",  # noqa: G004
                exc_info=True,
            )
            results["updates"]["explorations"] = {"error": str(e)}

        # === PHASE 4: Dweller Management ===
        try:
            dweller_update = await self._process_dwellers(db_session, vault_id)
            results["updates"]["dwellers"] = dweller_update
        except Exception as e:
            self.logger.error(f"Error processing dwellers for vault {vault_id}: {e}", exc_info=True)  # noqa: G004, G201
            results["updates"]["dwellers"] = {"error": str(e), "health_updated": 0, "leveled_up": 0}

        # === PHASE 4.5: Training System ===
        try:
            training_update = await self._process_training(db_session, vault_id)
            results["updates"]["training"] = training_update
        except Exception as e:
            self.logger.error(f"Error processing training for vault {vault_id}: {e}", exc_info=True)  # noqa: G004, G201
            results["updates"]["training"] = {"error": str(e), "sessions_updated": 0, "completed": 0}

        # === PHASE 4.6: Happiness System ===
        try:
            happiness_update = await self._process_happiness(db_session, vault_id, seconds_passed)
            results["updates"]["happiness"] = happiness_update
        except Exception as e:
            self.logger.error(  # noqa: G201
                f"Error processing happiness for vault {vault_id}: {e}",  # noqa: G004
                exc_info=True,
            )
            results["updates"]["happiness"] = {"error": str(e), "dwellers_processed": 0}

        # === PHASE 4.7: Relationships & Breeding System ===
        try:
            breeding_update = await self._process_breeding(db_session, vault_id)
            results["updates"]["breeding"] = breeding_update
        except Exception as e:
            self.logger.error(  # noqa: G201
                f"Error processing breeding for vault {vault_id}: {e}",  # noqa: G004
                exc_info=True,
            )
            results["updates"]["breeding"] = {
                "error": str(e),
                "relationships_updated": 0,
                "conceptions": 0,
                "births": 0,
                "children_aged": 0,
            }

        # === PHASE 5: Event System ===
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

    async def _process_explorations(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """
        Process all active explorations for a vault.

        - Generate events for explorations that are due
        - Auto-complete explorations that have reached their duration
        """
        stats = {
            "active_count": 0,
            "events_generated": 0,
            "completed": 0,
        }

        # Get all active explorations for this vault
        active_explorations = await crud_exploration.get_active_by_vault(
            db_session,
            vault_id=vault_id,
        )

        stats["active_count"] = len(active_explorations)

        for exploration in active_explorations:
            try:
                # Check if exploration should be auto-completed
                if exploration.time_remaining_seconds() <= 0:
                    # Auto-complete the exploration
                    await wasteland_service.complete_exploration(db_session, exploration.id)
                    stats["completed"] += 1
                    self.logger.info(
                        f"Auto-completed exploration {exploration.id} for dweller {exploration.dweller_id}"  # noqa: G004
                    )
                    continue

                # Try to generate an event
                event_generated = wasteland_service.generate_event(exploration)
                if event_generated:
                    await wasteland_service.process_event(db_session, exploration)
                    stats["events_generated"] += 1

            except Exception as e:
                self.logger.error(  # noqa: G201
                    f"Error processing exploration {exploration.id}: {e}",  # noqa: G004
                    exc_info=True,
                )

        return stats

    async def _process_dwellers(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """
        Process dweller updates for a vault.

        - Award work XP to dwellers in production rooms
        - Check for level-ups
        - Update health and needs (future)
        """
        from app.config.game_balance import WORK_EFFICIENCY_BONUS_MULTIPLIER, WORK_XP_PER_TICK
        from app.models.room import Room
        from app.schemas.common import DwellerStatusEnum, RoomTypeEnum
        from app.services.leveling_service import leveling_service

        stats = {
            "health_updated": 0,
            "leveled_up": 0,
            "xp_awarded": 0,
        }

        # Get all dwellers in this vault
        from app.models.dweller import Dweller

        dwellers_query = select(Dweller).where(Dweller.vault_id == vault_id)
        dwellers_result = await db_session.execute(dwellers_query)
        dwellers = dwellers_result.scalars().all()

        # Process each dweller
        for dweller in dwellers:
            try:
                # Award work XP for dwellers in production rooms
                if dweller.status == DwellerStatusEnum.WORKING and dweller.room_id:
                    # Get room to check if it's a production room
                    room_query = select(Room).where(Room.id == dweller.room_id)
                    room_result = await db_session.execute(room_query)
                    room = room_result.scalar_one_or_none()

                    if room and room.category == RoomTypeEnum.PRODUCTION:
                        # Base XP per tick
                        xp_to_award = WORK_XP_PER_TICK

                        # Efficiency bonus: if dweller has high matching SPECIAL
                        if room.ability:
                            dweller_stat = getattr(dweller, room.ability.value.lower(), 1)
                            # If SPECIAL >= 7, give efficiency bonus
                            if dweller_stat >= 7:
                                xp_to_award = int(xp_to_award * WORK_EFFICIENCY_BONUS_MULTIPLIER)

                        # Award XP
                        dweller.experience += xp_to_award
                        db_session.add(dweller)
                        stats["xp_awarded"] += xp_to_award

                        # Check for level-up
                        leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller)
                        if leveled_up:
                            stats["leveled_up"] += levels_gained
                            self.logger.info(
                                f"Dweller {dweller.name} gained {levels_gained} level(s)! Now level {dweller.level}"  # noqa: G004
                            )

            except Exception as e:
                self.logger.error(f"Error processing dweller {dweller.id}: {e}", exc_info=True)  # noqa: G004, G201

        return stats

    async def _process_training(self, db_session: AsyncSession, vault_id: UUID4) -> dict:
        """
        Process all active training sessions for a vault.

        - Update training progress
        - Auto-complete trainings that have finished
        - Track statistics
        """
        from app.crud import training as training_crud
        from app.services.training_service import training_service

        stats = {
            "sessions_updated": 0,
            "completed": 0,
            "active_count": 0,
        }

        # Get all active training sessions in this vault
        active_trainings = await training_crud.training.get_active_by_vault(db_session, vault_id)
        stats["active_count"] = len(active_trainings)

        for training in active_trainings:
            try:
                # Update progress (this will auto-complete if ready)
                updated_training = await training_service.update_training_progress(db_session, training)

                stats["sessions_updated"] += 1

                # Check if it was completed
                if updated_training.is_completed():
                    stats["completed"] += 1
                    self.logger.info(
                        f"Training completed: Dweller gained {updated_training.stat_being_trained.value} "  # noqa: G004
                        f"(now {updated_training.target_stat_value})"
                    )

            except Exception as e:
                self.logger.error(f"Error processing training {training.id}: {e}", exc_info=True)  # noqa: G004, G201

        return stats

    async def _process_happiness(self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int) -> dict:
        """
        Process happiness updates for all dwellers in a vault.

        - Calculate happiness changes based on vault conditions
        - Update individual dweller happiness
        - Update vault-wide average happiness
        """
        try:
            return await happiness_service.update_vault_happiness(db_session, vault_id, seconds_passed)
        except Exception as e:
            self.logger.error(  # noqa: G201
                f"Error in happiness service for vault {vault_id}: {e}",  # noqa: G004
                exc_info=True,
            )
            return {"error": str(e), "dwellers_processed": 0}

    async def _process_incidents(self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int) -> dict:
        """
        Process all active incidents for a vault.

        - Check if new incident should spawn
        - Process existing active incidents (combat, damage, resolution)
        - Handle incident spreading
        """
        # Import here to avoid circular import
        from app.services.incident_service import incident_service

        stats = {
            "spawned": 0,
            "processed": 0,
            "resolved": 0,
            "active_count": 0,
        }

        # Check if new incident should spawn
        should_spawn = await incident_service.should_spawn_incident(db_session, vault_id, seconds_passed)
        if should_spawn:
            new_incident = await incident_service.spawn_incident(db_session, vault_id)
            if new_incident:
                stats["spawned"] = 1
                self.logger.info(f"Spawned new incident {new_incident.type} in vault {vault_id}")  # noqa: G004

        # Get all active incidents
        active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
        stats["active_count"] = len(active_incidents)

        # Process each active incident
        for incident in active_incidents:
            try:
                result = await incident_service.process_incident(db_session, incident, seconds_passed)

                if result.get("skipped"):
                    continue

                stats["processed"] += 1

                # Check if incident was resolved automatically
                await db_session.refresh(incident)
                if incident.status.value in ["resolved", "failed"]:
                    stats["resolved"] += 1
                    self.logger.info(
                        f"Incident {incident.id} auto-resolved with status {incident.status}"  # noqa: G004
                    )

            except Exception as e:
                self.logger.error(  # noqa: G201
                    f"Error processing incident {incident.id}: {e}",  # noqa: G004
                    exc_info=True,
                )

        return stats

    async def _process_breeding(self, db_session: AsyncSession, vault_id: UUID4) -> dict:  # noqa: C901, PLR0912
        """
        Process relationships and breeding for a vault.

        - Update relationship affinity for dwellers in the same room
        - Check for conception in living quarters
        - Process due pregnancies and deliver babies
        - Age children to adults
        """
        from app.services.breeding_service import breeding_service
        from app.services.relationship_service import relationship_service

        stats = {
            "relationships_updated": 0,
            "conceptions": 0,
            "births": 0,
            "children_aged": 0,
        }

        # 1. Update relationships for dwellers in the same room
        try:
            from app.config.game_balance import AFFINITY_INCREASE_PER_TICK
            from app.models.dweller import Dweller

            # Get all dwellers in this vault that are in rooms
            dwellers_query = select(Dweller).where(Dweller.vault_id == vault_id, Dweller.room_id.is_not(None))
            dwellers_result = await db_session.execute(dwellers_query)
            dwellers = dwellers_result.scalars().all()

            # Group dwellers by room
            room_dwellers = {}
            for dweller in dwellers:
                if dweller.room_id not in room_dwellers:
                    room_dwellers[dweller.room_id] = []
                room_dwellers[dweller.room_id].append(dweller)

            # Update affinity for dwellers in the same room
            for _room_id, room_dweller_list in room_dwellers.items():
                if len(room_dweller_list) < 2:
                    continue

                # For each pair in the room, increase affinity
                for i, dweller1 in enumerate(room_dweller_list):
                    for dweller2 in room_dweller_list[i + 1 :]:
                        try:
                            # Get or create relationship
                            relationship = await relationship_service.create_or_get_relationship(
                                db_session, dweller1.id, dweller2.id
                            )
                            # Increase affinity
                            await relationship_service.increase_affinity(
                                db_session, relationship, AFFINITY_INCREASE_PER_TICK
                            )
                            stats["relationships_updated"] += 1
                        except Exception as e:
                            self.logger.error(  # noqa: G201
                                f"Error updating relationship between {dweller1.id} and {dweller2.id}: {e}",  # noqa: G004
                                exc_info=True,
                            )
        except Exception as e:
            self.logger.error(f"Error updating relationships: {e}", exc_info=True)  # noqa: G004, G201

        # 2. Check for conception
        try:
            new_pregnancies = await breeding_service.check_for_conception(db_session, vault_id)
            stats["conceptions"] = len(new_pregnancies)
            if new_pregnancies:
                self.logger.info(f"New pregnancies in vault {vault_id}: {len(new_pregnancies)}")  # noqa: G004
        except Exception as e:
            self.logger.error(f"Error checking for conception: {e}", exc_info=True)  # noqa: G004, G201

        # 3. Check for due pregnancies and deliver babies
        try:
            due_pregnancies = await breeding_service.check_due_pregnancies(db_session, vault_id)
            for pregnancy in due_pregnancies:
                try:
                    baby = await breeding_service.deliver_baby(db_session, pregnancy.id)
                    if baby:
                        stats["births"] += 1
                        self.logger.info(
                            f"Baby born in vault {vault_id}: {baby.first_name} {baby.last_name}"  # noqa: G004
                        )
                except Exception as e:
                    self.logger.error(f"Error delivering baby for pregnancy {pregnancy.id}: {e}", exc_info=True)  # noqa: G004, G201
        except Exception as e:
            self.logger.error(f"Error checking due pregnancies: {e}", exc_info=True)  # noqa: G004, G201

        # 4. Age children to adults
        try:
            aged_children = await breeding_service.age_children(db_session, vault_id)
            stats["children_aged"] = len(aged_children)
            if aged_children:
                self.logger.info(f"Children aged to adults in vault {vault_id}: {len(aged_children)}")  # noqa: G004
        except Exception as e:
            self.logger.error(f"Error aging children: {e}", exc_info=True)  # noqa: G004, G201

        return stats


# Global instance
game_loop_service = GameLoopService()
