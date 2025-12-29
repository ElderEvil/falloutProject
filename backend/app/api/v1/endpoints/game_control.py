"""Game control endpoints for managing vault game loop."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser
from app.db.session import get_async_session
from app.services.game_loop import game_loop_service

router = APIRouter()


@router.post("/vaults/{vault_id}/pause", status_code=200)
async def pause_vault(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    """Pause the game loop for a vault."""
    # Verify vault ownership
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to pause this vault")

    game_state = await game_loop_service.pause_vault(db_session, vault_id)

    return {
        "message": "Vault paused successfully",
        "vault_id": str(vault_id),
        "is_paused": game_state.is_paused,
        "paused_at": game_state.paused_at.isoformat() if game_state.paused_at else None,
    }


@router.post("/vaults/{vault_id}/resume", status_code=200)
async def resume_vault(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    """Resume the game loop for a vault."""
    # Verify vault ownership
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to resume this vault")

    game_state = await game_loop_service.resume_vault(db_session, vault_id)

    return {
        "message": "Vault resumed successfully",
        "vault_id": str(vault_id),
        "is_paused": game_state.is_paused,
        "resumed_at": game_state.resumed_at.isoformat() if game_state.resumed_at else None,
    }


@router.get("/vaults/{vault_id}/game-state", status_code=200)
async def get_game_state(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    """Get current game state for a vault."""
    # Verify vault ownership
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to view this vault's game state")

    status = await game_loop_service.get_vault_status(db_session, vault_id)

    return status  # noqa: RET504


@router.get("/vaults/{vault_id}/incidents", status_code=200)
async def list_incidents(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    """List all active incidents in a vault."""
    # Verify vault ownership
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to view this vault's incidents")

    incidents = await crud.incident_crud.get_active_by_vault(db_session, vault_id)

    return {
        "vault_id": str(vault_id),
        "incident_count": len(incidents),
        "incidents": [
            {
                "id": str(incident.id),
                "type": incident.type,
                "status": incident.status,
                "room_id": str(incident.room_id),
                "difficulty": incident.difficulty,
                "start_time": incident.start_time.isoformat(),
                "elapsed_time": incident.elapsed_time(),
                "damage_dealt": incident.damage_dealt,
                "enemies_defeated": incident.enemies_defeated,
            }
            for incident in incidents
        ],
    }


@router.get("/vaults/{vault_id}/incidents/{incident_id}", status_code=200)
async def get_incident(
    *,
    vault_id: UUID4,
    incident_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    """Get details of a specific incident."""
    # Verify vault ownership
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to view this vault's incidents")

    incident = await crud.incident_crud.get(db_session, incident_id)
    if not incident or incident.vault_id != vault_id:
        raise HTTPException(status_code=404, detail="Incident not found")

    return {
        "id": str(incident.id),
        "vault_id": str(incident.vault_id),
        "room_id": str(incident.room_id),
        "type": incident.type,
        "status": incident.status,
        "difficulty": incident.difficulty,
        "start_time": incident.start_time.isoformat(),
        "end_time": incident.end_time.isoformat() if incident.end_time else None,
        "elapsed_time": incident.elapsed_time(),
        "duration": incident.duration,
        "damage_dealt": incident.damage_dealt,
        "enemies_defeated": incident.enemies_defeated,
        "rooms_affected": incident.rooms_affected,
        "spread_count": incident.spread_count,
        "loot": incident.loot,
    }


@router.post("/vaults/{vault_id}/tick", status_code=200)
async def manual_tick(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    """
    Manually trigger a game tick for a vault (for testing/debugging).

    This endpoint is useful for:
    - Testing resource production/consumption
    - Triggering catch-up after pause
    - Development and debugging
    """
    # Verify vault ownership
    vault = await crud.vault.get(db_session, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")

    if vault.user_id != user.id and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized to trigger tick for this vault")

    # Process a single vault tick
    result = await game_loop_service.process_vault_tick(db_session, vault_id)

    return {
        "message": "Manual tick processed successfully",
        **result,
    }
