"""Debug endpoints for testing objectives and EventBus.

WARNING: These endpoints are for development/testing only.
Do not expose in production environments.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import UUID4
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
        GameEvent.ROOM_BUILT: {"room_type": "Living Quarters"},
        GameEvent.ROOM_UPGRADED: {"room_type": "Living Quarters", "level": 2},
        GameEvent.DWELLER_TRAINED: {"stat_trained": "strength", "dweller_id": "test-dweller"},
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


@router.get("/objectives/{vault_id}")
async def debug_objectives(vault_id: UUID4, session: AsyncSession = Depends(get_async_session)):  # noqa: FAST002
    """Debug endpoint to inspect objectives and their progress for a vault."""
    objectives_result = await session.execute(select(Objective))
    all_objectives = objectives_result.scalars().all()

    # Get vault-specific objectives with progress
    vault_objectives_result = await session.execute(
        select(Objective, VaultObjectiveProgressLink)
        .join(VaultObjectiveProgressLink)
        .where(VaultObjectiveProgressLink.vault_id == vault_id)
    )
    vault_objectives = [(obj, link) for obj, link in vault_objectives_result.all()]

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
            {"id": str(obj.id), "challenge": obj.challenge, "target_amount": obj.target_amount} for obj in incomplete
        ],
    }


@router.post("/objectives/{vault_id}/test-collect")
async def test_collect_objective(
    vault_id: UUID4,
    resource_type: str,
    amount: int,
    session: AsyncSession = Depends(get_async_session),  # noqa: FAST002, PT028
):
    """Test RESOURCE_COLLECTED event and check if objective progress updates."""

    # Get objectives BEFORE
    before_result = await session.execute(
        select(Objective, VaultObjectiveProgressLink)
        .join(VaultObjectiveProgressLink)
        .where(VaultObjectiveProgressLink.vault_id == vault_id)
        .where(Objective.objective_type == "collect")
    )
    before = [
        {"challenge": obj.challenge, "progress": link.progress, "total": link.total}
        for obj, link in before_result.all()
    ]

    # Emit the event
    await event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": resource_type, "amount": amount})

    # Get objectives AFTER
    after_result = await session.execute(
        select(Objective, VaultObjectiveProgressLink)
        .join(VaultObjectiveProgressLink)
        .where(VaultObjectiveProgressLink.vault_id == vault_id)
        .where(Objective.objective_type == "collect")
    )
    after = [
        {"challenge": obj.challenge, "progress": link.progress, "total": link.total} for obj, link in after_result.all()
    ]

    return {
        "vault_id": str(vault_id),
        "event": {"type": "RESOURCE_COLLECTED", "resource_type": resource_type, "amount": amount},
        "before": before,
        "after": after,
    }


@router.get("/evaluators")
async def debug_evaluators():
    """Check which evaluators are subscribed to which events."""
    from app.services.objective_evaluators import evaluator_manager

    return {
        "manager_initialized": evaluator_manager._initialized,
        "subscriptions": {
            event_type: [h.__name__ for h in handlers] for event_type, handlers in event_bus._handlers.items()
        },
    }


@router.post("/test-build-living-room/{vault_id}")
async def test_build_living_room(
    vault_id: UUID4,
    session: AsyncSession = Depends(get_async_session),
):
    """Debug endpoint to test building a living room and check population_max update."""
    from app import crud
    from app.models.room import Room
    from app.schemas.common import RoomTypeEnum, SPECIALEnum
    from app.schemas.room import RoomCreate

    # Get vault before building
    vault_before = await crud.vault.get(session, id=vault_id)
    if not vault_before:
        return {"error": "Vault not found"}

    # Find a living room from the rooms data
    from app.api.game_data_deps import get_static_game_data

    game_data_store = get_static_game_data()
    living_room_data = None
    for room in game_data_store.rooms:
        # Match by ability (CHARISMA) which is the authoritative attribute for living rooms
        if room.ability == SPECIALEnum.CHARISMA:
            # Convert RoomCreateWithoutVaultID to dict for compatibility
            living_room_data = room.model_dump()
            break

    if not living_room_data:
        return {"error": "No living room found in game config"}

    # Build the living room
    room_create = RoomCreate(
        vault_id=vault_id,
        name=living_room_data["name"],
        category=RoomTypeEnum(living_room_data["category"]),
        tier=1,
        size=3,
        ability=SPECIALEnum(living_room_data["ability"]) if living_room_data.get("ability") else None,
        capacity=8,  # Typical size 3 living room
        population_required=living_room_data.get("population_required"),
        base_cost=living_room_data["base_cost"],
        incremental_cost=living_room_data["incremental_cost"],
        t2_upgrade_cost=living_room_data["t2_upgrade_cost"],
        t3_upgrade_cost=living_room_data["t3_upgrade_cost"],
        size_min=living_room_data["size_min"],
        size_max=living_room_data["size_max"],
        coordinate_x=1,
        coordinate_y=1,
    )

    # Check requires_recalculation
    from app.crud.room import room as room_crud

    requires_calc = room_crud.requires_recalculation(room_create)

    # Build the room
    created_room = await room_crud.build(session, obj_in=room_create)

    # Get vault after building
    await session.refresh(vault_before)
    vault_after = await crud.vault.get(session, id=vault_id)

    # Get all rooms
    rooms_result = await session.execute(select(Room).where(Room.vault_id == vault_id))
    all_rooms = rooms_result.scalars().all()

    return {
        "vault_id": str(vault_id),
        "before": {
            "population_max": vault_before.population_max,
        },
        "after": {
            "population_max": vault_after.population_max,
        },
        "room_built": {
            "name": created_room.name,
            "category": created_room.category.value if created_room.category else None,
            "ability": created_room.ability.value if created_room.ability else None,
            "capacity": created_room.capacity,
        },
        "requires_recalculation": requires_calc,
        "all_rooms": [
            {
                "name": r.name,
                "category": r.category.value if r.category else None,
                "ability": r.ability.value if r.ability else None,
                "capacity": r.capacity,
            }
            for r in all_rooms
        ],
    }
