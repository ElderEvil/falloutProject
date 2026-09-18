"""Game control endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.core.game_config import game_config
from app.db.session import get_async_session
from app.models.incident import IncidentType
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.incident import (
    DeleteIncidentsResponse,
    IncidentListItem,
    IncidentListResponse,
    IncidentRead,
    IncidentRespondersRequest,
    IncidentRespondersResponse,
    IncidentSpawnResponse,
    PauseResumeResponse,
    PendingIncidentOverflowRead,
)
from app.schemas.overflow import OverflowActionRequest, OverflowActionResponse
from app.schemas.system import GameBalanceResponse
from app.schemas.team import TeamMemberRead
from app.services.combat.incident_service import incident_service
from app.services.game_loop import game_loop_service
from app.utils.exceptions import (
    AccessDeniedException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
    VaultOperationException,
)

router = APIRouter(prefix="/game", tags=["Game"])


@router.get("/balance", response_model=GameBalanceResponse)
async def get_game_balance_settings(_: CurrentActiveUser) -> GameBalanceResponse:
    """Get current game balance configuration (read-only).

    This endpoint exposes all game balance constants that can be tuned via
    environment variables. Useful for debugging and future admin panels.

    Returns:
        GameBalanceResponse: All game balance settings.
    """
    return GameBalanceResponse(
        game_loop=game_config.game_loop.model_dump(),
        incident={
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
        combat=game_config.combat.model_dump(),
        health=game_config.health.model_dump(),
        happiness=game_config.happiness.model_dump(),
        training=game_config.training.model_dump(),
        resource=game_config.resource.model_dump(),
        relationship=game_config.relationship.model_dump(),
        breeding=game_config.breeding.model_dump(),
        leveling=game_config.leveling.model_dump(),
        radio=game_config.radio.model_dump(),
        death={
            **game_config.death.model_dump(),
            "revival_cost_examples": {
                "level_1": game_config.death.calculate_revival_cost(1),
                "level_5": game_config.death.calculate_revival_cost(5),
                "level_10": game_config.death.calculate_revival_cost(10),
                "level_25": game_config.death.calculate_revival_cost(25),
                "level_50": game_config.death.calculate_revival_cost(50),
            },
        },
        dweller=game_config.dweller.model_dump(),
        exploration=game_config.exploration.model_dump(),
    )


@router.post("/vaults/{vault_id}/pause", response_model=PauseResumeResponse, status_code=200)
async def pause_vault(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> PauseResumeResponse:
    """Pause the game loop for a vault.

    Returns:
        PauseResumeResponse: Pause confirmation with vault state.
    """
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
) -> PauseResumeResponse:
    """Resume the game loop for a vault.

    Returns:
        PauseResumeResponse: Resume confirmation with vault state.
    """
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
) -> dict[str, Any]:
    """Get current game state for a vault.

    Returns:
        dict[str, Any]: Current game state details.
    """
    return await game_loop_service.get_vault_status(db_session, vault.id)


@router.get("/vaults/{vault_id}/incidents", response_model=IncidentListResponse, status_code=200)
async def list_incidents(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> IncidentListResponse:
    """List all active incidents in a vault.

    Returns:
        IncidentListResponse: List of active incidents.
    """
    incidents = await crud.incident_crud.get_active_by_vault(db_session, vault.id)

    room_ids = [incident.room_id for incident in incidents]
    rooms_result = await db_session.execute(select(Room).where(col(Room.id).in_(room_ids))) if room_ids else None
    room_names = {room.id: room.name for room in rooms_result.scalars().all()} if rooms_result else {}

    return IncidentListResponse(
        vault_id=str(vault.id),
        incident_count=len(incidents),
        incidents=[
            IncidentListItem(
                id=str(incident.id),
                type=incident.type,
                status=incident.status,
                room_id=str(incident.room_id),
                room_name=room_names.get(incident.room_id),
                difficulty=incident.difficulty,
                start_time=incident.start_time.isoformat(),
                elapsed_time=incident.elapsed_time(),
                damage_dealt=incident.damage_dealt,
                enemies_defeated=incident.enemies_defeated,
            )
            for incident in incidents
        ],
    )


@router.get(
    "/vaults/{vault_id}/incidents/pending-overflow",
    response_model=list[PendingIncidentOverflowRead],
    status_code=200,
)
async def list_pending_incident_overflow(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[PendingIncidentOverflowRead]:
    """List resolved incidents still holding loot for a take or sell decision."""
    return await incident_service.get_pending_overflow(db_session, vault.id)


@router.get("/vaults/{vault_id}/incidents/{incident_id}", response_model=IncidentRead, status_code=200)
async def get_incident(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> IncidentRead:
    """Get details of a specific incident.

    Returns:
        IncidentRead: Incident details.

    Raises:
        HTTPException: 404 if incident not found.
    """
    incident = await crud.incident_crud.get(db_session, incident_id)
    if not incident or incident.vault_id != vault.id:
        raise HTTPException(status_code=404, detail="Incident not found")

    room = await db_session.get(Room, incident.room_id)

    return await incident_service.get_incident_read(db_session, incident, room.name if room else None)


@router.post("/vaults/{vault_id}/tick", status_code=200)
async def manual_tick(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Manually trigger a game tick for a vault (for testing/debugging).

    This endpoint is useful for:
    - Testing resource production/consumption
    - Triggering catch-up after pause
    - Development and debugging

    Returns:
        dict[str, Any]: Tick processing result.
    """
    result = await game_loop_service.process_vault_tick(db_session, vault.id)

    return {
        "message": "Manual tick processed successfully",
        **result,
    }


@router.post("/vaults/{vault_id}/incidents/{incident_id}/responders", response_model=IncidentRespondersResponse)
async def assign_incident_responders(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    responders: IncidentRespondersRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> IncidentRespondersResponse:
    """Assign healthy adult dwellers to defend an active incident room."""
    try:
        incident = await incident_service.get_incident_for_vault(db_session, incident_id, vault.id)
        assigned = await incident_service.assign_responders(db_session, incident, responders.dweller_ids)
        return IncidentRespondersResponse(
            incident_id=incident.id, room_id=incident.room_id, assigned_dweller_ids=assigned
        )
    except (ResourceNotFoundException, AccessDeniedException, ValidationException) as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/vaults/{vault_id}/incidents/{incident_id}/team", response_model=list[TeamMemberRead])
async def get_incident_team(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[TeamMemberRead]:
    """Get the designated responder team for an incident."""
    try:
        incident = await incident_service.get_incident_for_vault(db_session, incident_id, vault.id)
        members = await crud.team_crud.get_incident_team(db_session, incident.id, incident.vault_id)
        return [
            TeamMemberRead(
                id=member.id,
                team_id=member.team_id,
                dweller_id=member.dweller_id,
                slot_number=member.slot_number,
                status=member.status,
                created_at=member.created_at,
                updated_at=member.updated_at,
            )
            for member in members
        ]
    except (ResourceNotFoundException, AccessDeniedException, ValidationException) as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/vaults/{vault_id}/incidents/{incident_id}/overflow/take", response_model=OverflowActionResponse)
async def take_incident_overflow_item(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    request: OverflowActionRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> OverflowActionResponse:
    """Store one held incident item. 409 when storage is still full."""
    remaining = await incident_service.take_unclaimed_item(db_session, incident_id, vault.id, request.index)
    return OverflowActionResponse(unclaimed_loot=remaining)


@router.post("/vaults/{vault_id}/incidents/{incident_id}/overflow/sell", response_model=OverflowActionResponse)
async def sell_incident_overflow_item(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    incident_id: UUID4,
    request: OverflowActionRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> OverflowActionResponse:
    """Sell one held incident item for caps. Needs no storage space."""
    caps, remaining = await incident_service.sell_unclaimed_item(db_session, incident_id, vault.id, request.index)
    return OverflowActionResponse(caps_granted=caps, unclaimed_loot=remaining)


@router.post("/vaults/{vault_id}/incidents/spawn", response_model=IncidentSpawnResponse, status_code=201)
async def spawn_debug_incident(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    incident_type: IncidentType | None = None,
) -> IncidentSpawnResponse:
    """[DEBUG] Manually spawn an incident for testing purposes.

    If incident_type is not provided, a radscorpion incident will be spawned.

    Returns:
        IncidentSpawnResponse: Spawned incident details.

    Raises:
        HTTPException: 400 if incidents are disabled or no occupied rooms available.
        HTTPException: 409 if the vault is at the active-incident cap.
    """
    try:
        incident = await incident_service.spawn_incident(db_session, vault.id, incident_type)
    except (
        ResourceNotFoundException,
        ResourceConflictException,
        ValidationException,
        VaultOperationException,
    ) as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

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
) -> DeleteIncidentsResponse:
    """Delete all incidents for a vault.

    Returns:
        DeleteIncidentsResponse: Deletion confirmation with count.
    """
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
) -> DeleteIncidentsResponse:
    """Delete a specific incident.

    Returns:
        DeleteIncidentsResponse: Deletion confirmation.

    Raises:
        HTTPException: 404 if incident not found. 400 if deletion fails.
    """
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
