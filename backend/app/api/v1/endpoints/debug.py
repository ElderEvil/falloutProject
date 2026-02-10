"""Debug endpoints for testing objectives and EventBus.

WARNING: These endpoints are for development/testing only.
Do not expose in production environments.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import UUID4
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import get_async_session
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.event_bus import GameEvent, event_bus

router = APIRouter()


@router.post("/emit/{vault_id}")
async def emit_test_event(
    vault_id: UUID4,
    event_type: GameEvent,
    data: dict[str, Any] | None = None,
):
    """Emit a test event to the EventBus for debugging objectives."""
    if data is None:
        data = {}

    # Add default values based on event type for testing
    defaults = {
        GameEvent.RESOURCE_COLLECTED: {"resource_type": "caps", "amount": 10},
        GameEvent.ITEM_COLLECTED: {"item_type": "weapon", "amount": 1},
        GameEvent.ROOM_BUILT: {"room_type": "living_quarters"},
        GameEvent.ROOM_UPGRADED: {"room_type": "living_quarters", "level": 2},
        GameEvent.DWELLER_TRAINED: {"stat": "strength", "dweller_id": "test-dweller"},
        GameEvent.DWELLER_ASSIGNED: {"dweller_id": "test-dweller", "room_type": "power_plant"},
        GameEvent.DWELLER_LEVEL_UP: {"dweller_id": "test-dweller", "level": 2},
    }

    # Merge defaults with provided data
    if event_type in defaults:
        defaults[event_type].update(data)
        data = defaults[event_type]

    await event_bus.emit(event_type, vault_id, data)
    return {
        "status": "ok",
        "event": event_type,
        "vault_id": str(vault_id),
        "data": data,
    }


@router.get("/events")
async def list_subscribed_events():
    """List all currently subscribed events and their handlers."""
    handlers = {}
    for event_type, handler_list in event_bus._handlers.items():
        handlers[event_type] = [h.__name__ for h in handler_list]
    return {
        "events": handlers,
        "handler_count": sum(len(h) for h in event_bus._handlers.values()),
    }


@router.get("/health")
async def debug_health():
    """Debug health check endpoint."""
    return {"status": "debug_mode_active"}


@router.get("/objectives/{vault_id}")
async def debug_objectives(vault_id: UUID4):
    """Debug endpoint to inspect objectives and their progress for a vault."""
    async for session in get_async_session():
        # Get all seeded objectives
        objectives_result = await session.execute(select(Objective))
        all_objectives = objectives_result.scalars().all()

        # Get vault-specific objectives with progress
        vault_objectives_result = await session.execute(
            select(Objective, VaultObjectiveProgressLink)
            .join(VaultObjectiveProgressLink)
            .where(VaultObjectiveProgressLink.vault_id == vault_id)
        )
        vault_objectives = [{"objective": obj, "link": link} for obj, link in vault_objectives_result.all()]

        # Check for incomplete objectives (missing required fields)
        incomplete = [
            obj
            for obj in all_objectives
            if obj.objective_type is None or obj.target_entity is None or obj.target_amount == 1
        ]

        return {
            "vault_id": str(vault_id),
            "all_seeded_objectives": [
                {
                    "id": str(obj.id),
                    "challenge": obj.challenge,
                    "objective_type": obj.objective_type,
                    "target_entity": obj.target_entity,
                    "target_amount": obj.target_amount,
                    "is_complete": (
                        obj.objective_type is not None and obj.target_entity is not None and obj.target_amount > 1
                    ),
                }
                for obj in all_objectives
            ],
            "vault_objectives_with_progress": [
                {
                    "id": str(obj.id),
                    "challenge": obj.challenge,
                    "objective_type": obj.objective_type,
                    "target_entity": obj.target_entity,
                    "target_amount": obj.target_amount,
                    "progress": link.progress,
                    "total": link.total,
                    "is_completed": link.is_completed,
                }
                for obj, link in vault_objectives
            ],
            "incomplete_objectives_count": len(incomplete),
            "incomplete_objectives": [
                {"id": str(obj.id), "challenge": obj.challenge, "target_amount": obj.target_amount}
                for obj in incomplete
            ],
        }
