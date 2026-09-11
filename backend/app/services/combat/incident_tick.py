"""Incident tick orchestration: per-vault processing and the advisory-locked fan-out."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.game_config import game_config
from app.crud.incident import incident_crud
from app.crud.vault import vault as vault_crud
from app.models.game_state import GameState
from app.models.vault import Vault
from app.services.combat import incident_spawning
from app.services.notification_service import notification_service
from app.utils.exceptions import ResourceNotFoundException

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.services.combat.incident_service import IncidentService

logger = logging.getLogger(__name__)


async def process_vault_incidents(
    service: IncidentService,
    db_session: AsyncSession,
    vault_id: UUID4,
    seconds_passed: int,
    game_state: GameState | None = None,
) -> dict:
    """Process one vault's incidents: spawn check, combat rounds, spreading, caps.

    Runs on its own fast tick (``incident_tick`` actor), independent of the
    60-second game loop, so combat gives live feedback.
    """
    stats = {"spawned": 0, "processed": 0, "resolved": 0, "active_count": 0, "caps_earned": 0}

    try:
        if game_state is None:
            game_state = await db_session.get(GameState, vault_id)

        vault = await db_session.get(Vault, vault_id)
        if incident_spawning.is_spawning_disabled(vault):
            return stats

        active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
        stats["active_count"] = len(active_incidents)

        if game_state and game_state.is_paused:
            return stats

        # Incidents do not punish players for time away from the vault.
        if game_state and not game_state.is_user_online():
            return stats

        if await service.should_spawn_incident(db_session, vault_id, seconds_passed, game_state):
            new_incident = await service.spawn_incident(db_session, vault_id)
            if new_incident:
                stats["spawned"] = 1
                logger.info(f"Spawned new incident {new_incident.type} in vault {vault_id}")

        total_caps_earned = 0

        for incident in active_incidents:
            try:
                result = await service.process_incident(
                    db_session, incident, min(seconds_passed, game_config.game_loop.tick_interval)
                )

                if result.skipped:
                    continue

                stats["processed"] += 1

                if result.caps_earned > 0:
                    total_caps_earned += result.caps_earned

                await db_session.refresh(incident)
                if incident.status.value in ("resolved", "failed"):
                    stats["resolved"] += 1
                    logger.info(f"Incident {incident.id} auto-resolved with status {incident.status}")

            except (SQLAlchemyError, ValueError, RuntimeError) as e:
                notification_service.discard_deferred_notifications(db_session)
                logger.error(f"Error processing incident {incident.id}: {e}", exc_info=True)

        if total_caps_earned > 0:
            from app.services.vault_service import vault_service

            vault = await vault_crud.get(db_session, vault_id)
            if vault:
                await vault_service.deposit_caps(db_session=db_session, vault_obj=vault, amount=total_caps_earned)
                stats["caps_earned"] = total_caps_earned
                logger.info(f"Awarded {total_caps_earned} caps to vault {vault_id} from incidents")

    except (SQLAlchemyError, ResourceNotFoundException) as e:  # TODO: Should it be here?
        logger.error(f"Error managing incidents for vault {vault_id}: {e}", exc_info=True)
        stats["error"] = str(e)

    return stats


async def process_all_vaults_incidents(
    service: IncidentService, db_session: AsyncSession, seconds_passed: int
) -> dict:  # TODO: Must be tested for performance
    """Process incidents for every active vault (fast-tick entry point).

    A PostgreSQL advisory lock serializes execution across workers; the
    transaction is rolled back before releasing it so a failed tick cannot
    leave the session in an aborted state that makes the unlock itself fail.
    """
    if not await _try_acquire_tick_lock(db_session):
        return {"vaults": 0, "spawned": 0, "resolved": 0}

    try:
        vaults = await vault_crud.get_active_ordered(db_session)
        vault_ids = [vault.id for vault in vaults]

        totals = {"vaults": len(vault_ids), "spawned": 0, "resolved": 0}
        for vault_id in vault_ids:
            stats = await process_vault_incidents(service, db_session, vault_id, seconds_passed)
            totals["spawned"] += stats["spawned"]
            totals["resolved"] += stats["resolved"]
    except Exception:
        # The session is in a failed state after an error; roll back so the
        # advisory unlock below can run on a healthy transaction.
        await db_session.rollback()
        raise
    else:
        return totals
    finally:
        await _release_tick_lock(db_session)


async def _try_acquire_tick_lock(db_session: AsyncSession) -> bool:
    if db_session.get_bind().dialect.name != "postgresql":
        return True

    result = await db_session.execute(
        text("SELECT pg_try_advisory_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": "incident-tick"},
    )
    return bool(result.scalar())


async def _release_tick_lock(db_session: AsyncSession) -> None:
    if db_session.get_bind().dialect.name != "postgresql":
        return
    try:
        await db_session.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))"),
            {"lock_key": "incident-tick"},
        )
    except Exception:
        # Unlock failure must not mask the original tick error or stall the
        # worker; the advisory lock self-releases on session close anyway.
        logger.exception("Failed to release incident tick advisory lock")
