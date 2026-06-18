"""Game control endpoints for managing vault game loop."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentSuperuser, get_user_vault_or_403
from app.core.game_config import game_config
from app.db.session import get_async_session
from app.models.incident import IncidentType
from app.models.vault import Vault
from app.schemas.incident import (
    DeleteIncidentsResponse,
    IncidentListItem,
    IncidentListResponse,
    IncidentRead,
    IncidentSpawnResponse,
    PauseResumeResponse,
)
from app.services.game_loop import game_loop_service
from app.services.incident_service import incident_service

router = APIRouter()


@router.get("/balance")
async def get_game_balance_settings() -> dict[str, Any]:
    """
    Get current game balance configuration (read-only).

    This endpoint exposes all game balance constants that can be tuned via
    environment variables. Useful for debugging and future admin panels.

    :returns: Dictionary containing all game balance settings organized by category
    :rtype: dict[str, Any]
    """
    return {
        "game_loop": game_config.game_loop.model_dump(),
        "incident": {
            **game_config.incident.model_dump(),
            "difficulty_ranges": {
                incident_type.value: game_config.incident.get_difficulty_range(incident_type)
                for incident_type in IncidentType
            },
            "spawn_weights": {
                incident_type.value: weight
                for incident_type, weight in game_config.incident.get_spawn_weights().items()
            },
        },
        "combat": game_config.combat.model_dump(),
        "health": game_config.health.model_dump(),
        "happiness": game_config.happiness.model_dump(),
        "training": game_config.training.model_dump(),
        "resource": game_config.resource.model_dump(),
        "relationship": game_config.relationship.model_dump(),
        "breeding": game_config.breeding.model_dump(),
        "leveling": game_config.leveling.model_dump(),
        "radio": game_config.radio.model_dump(),
        "death": {
            **game_config.death.model_dump(),
            "revival_cost_examples": {
                "level_1": game_config.death.calculate_revival_cost(1),
                "level_5": game_config.death.calculate_revival_cost(5),
                "level_10": game_config.death.calculate_revival_cost(10),
                "level_25": game_config.death.calculate_revival_cost(25),
                "level_50": game_config.death.calculate_revival_cost(50),
            },
        },
    }


@router.post("/vaults/{vault_id}/pause", response_model=PauseResumeResponse, status_code=200)
async def pause_vault(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Pause the game loop for a vault."""
    game_state = await game_loop_service.pause_vault(db_session, vault.id)

    return PauseResumeResponse(
        message="Vault paused successfully",
        vault_id=str(vault.id),
        is_paused=game_state.is_paused,
        paused_at=game_state.paused_at.isoformat() if game_state.paused_at else None,
    )


@router.post("/vaults/{vault_id}/resume", response_model=PauseResumeResponse, status_code=200)
async def resume_vault(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Resume the game loop for a vault."""
    game_state = await game_loop_service.resume_vault(db_session, vault.id)

    return PauseResumeResponse(
        message="Vault resumed successfully",
        vault_id=str(vault.id),
        is_paused=game_state.is_paused,
        resumed_at=game_state.resumed_at.isoformat() if game_state.resumed_at else None,
    )


@router.get("/vaults/{vault_id}/game-state", status_code=200)
async def get_game_state(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get current game state for a vault."""
    return await game_loop_service.get_vault_status(db_session, vault.id)


@router.get("/vaults/{vault_id}/incidents", response_model=IncidentListResponse, status_code=200)
async def list_incidents(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """List all active incidents in a vault."""
    incidents = await crud.incident_crud.get_active_by_vault(db_session, vault.id)

    return IncidentListResponse(
        vault_id=str(vault.id),
        incident_count=len(incidents),
        incidents=[
            IncidentListItem(
                id=str(incident.id),
                type=incident.type,
                status=incident.status,
                room_id=str(incident.room_id),
                difficulty=incident.difficulty,
                start_time=incident.start_time.isoformat(),
                elapsed_time=incident.elapsed_time(),
                damage_dealt=incident.damage_dealt,
                enemies_defeated=incident.enemies_defeated,
            )
            for incident in incidents
        ],
    )


@router.get("/vaults/{vault_id}/incidents/{incident_id}", response_model=IncidentRead, status_code=200)
async def get_incident(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get details of a specific incident."""
    incident = await crud.incident_crud.get(db_session, incident_id)
    if not incident or incident.vault_id != vault.id:
        raise HTTPException(status_code=404, detail="Incident not found")

    return IncidentRead(
        id=incident.id,
        vault_id=incident.vault_id,
        room_id=incident.room_id,
        type=incident.type,
        status=incident.status,
        difficulty=incident.difficulty,
        start_time=incident.start_time.isoformat(),
        end_time=incident.end_time.isoformat() if incident.end_time else None,
        elapsed_time=incident.elapsed_time(),
        duration=incident.duration,
        damage_dealt=incident.damage_dealt,
        enemies_defeated=incident.enemies_defeated,
        rooms_affected=incident.rooms_affected,
        spread_count=incident.spread_count,
        loot=incident.loot,
    )


@router.post("/vaults/{vault_id}/tick", status_code=200)
async def manual_tick(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Manually trigger a game tick for a vault (for testing/debugging).

    This endpoint is useful for:
    - Testing resource production/consumption
    - Triggering catch-up after pause
    - Development and debugging
    """
    result = await game_loop_service.process_vault_tick(db_session, vault.id)

    return {
        "message": "Manual tick processed successfully",
        **result,
    }


@router.post("/vaults/{vault_id}/incidents/{incident_id}/resolve", status_code=200)
async def resolve_incident(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    success: bool = True,
):
    """
    Manually resolve an active incident.

    This endpoint allows players to mark an incident as resolved,
    triggering loot generation and cleanup.
    """
    # Verify incident belongs to vault
    incident = await crud.incident_crud.get(db_session, incident_id)
    if not incident or incident.vault_id != vault.id:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        return await incident_service.resolve_incident_manually(db_session, incident_id, success)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/vaults/{vault_id}/incidents/spawn", response_model=IncidentSpawnResponse, status_code=201)
async def spawn_debug_incident(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    incident_type: IncidentType | None = None,
):
    """
    [DEBUG] Manually spawn an incident for testing purposes.

    If incident_type is not provided, a random type will be chosen.
    """
    incident = await incident_service.spawn_incident(db_session, vault.id, incident_type)

    if not incident:
        raise HTTPException(status_code=400, detail="Failed to spawn incident. No occupied rooms available.")

    return IncidentSpawnResponse(
        message="Incident spawned successfully",
        vault_id=str(vault.id),
        incident_id=str(incident.id),
        type=incident.type.value,
        room_id=str(incident.room_id),
        difficulty=incident.difficulty,
    )


@router.delete("/vaults/{vault_id}/incidents", response_model=DeleteIncidentsResponse, status_code=200)
async def delete_all_incidents(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _user: CurrentSuperuser,
):
    """Delete all incidents for a vault."""
    count = await crud.incident_crud.remove_all_by_vault(db_session, vault.id)

    return DeleteIncidentsResponse(
        message=f"Successfully deleted {count} incidents",
        vault_id=str(vault.id),
        deleted_count=count,
    )


@router.delete("/vaults/{vault_id}/incidents/{incident_id}", response_model=DeleteIncidentsResponse, status_code=200)
async def delete_incident(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _user: CurrentSuperuser,
):
    """Delete a specific incident."""
    # Verify incident belongs to vault
    incident = await crud.incident_crud.get(db_session, incident_id)
    if not incident or incident.vault_id != vault.id:
        raise HTTPException(status_code=404, detail="Incident not found")

    success = await crud.incident_crud.remove(db_session, incident_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete incident")

    return DeleteIncidentsResponse(
        message="Incident deleted successfully",
        vault_id=str(vault.id),
        deleted_count=1 if success else 0,
    )
