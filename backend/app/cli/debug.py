"""Dev/QA event-bus and objective debugging.

Replaces the old development-only ``/debug`` HTTP router: the same operator
tooling now lives behind the CLI, with no network surface, no unauthenticated
state mutation, and objective evaluators wired exactly as app startup wires
them.
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

import typer
from pydantic import UUID4
from sqlmodel import select

from app.core.event_bus import GameEvent, event_bus
from app.models.objective import Objective
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink

app = typer.Typer(
    name="debug",
    help="Dev/QA: emit game events, inspect objectives/evaluators, simulate builds.",
    no_args_is_help=True,
)

EVENT_DEFAULTS: dict[GameEvent, dict[str, Any]] = {
    GameEvent.RESOURCE_COLLECTED: {"resource_type": "caps", "amount": 10},
    GameEvent.ITEM_COLLECTED: {"item_type": "weapon", "amount": 1},
    GameEvent.ROOM_BUILT: {"room_type": "Living Quarters"},
    GameEvent.ROOM_UPGRADED: {"room_type": "Living Quarters", "level": 2},
    GameEvent.DWELLER_TRAINED: {"stat_trained": "strength", "dweller_id": "test-dweller"},
    GameEvent.DWELLER_ASSIGNED: {"dweller_id": "test-dweller", "room_type": "power_plant"},
    GameEvent.DWELLER_LEVEL_UP: {"dweller_id": "test-dweller", "level": 2},
}


def _echo(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str))


def _run(body):
    """Run a CLI body with a session and objective evaluators wired like startup."""

    async def _inner():
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlmodel.ext.asyncio.session import AsyncSession

        from app.core.config import settings
        from app.services.objective_evaluators import evaluator_manager, set_current_session_maker
        from app.services.objective_notifications import register_objective_event_handlers

        evaluator_manager.initialize()
        register_objective_event_handlers()
        engine = create_async_engine(str(settings.ASYNC_DATABASE_URI), echo=False, future=True, pool_pre_ping=True)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        set_current_session_maker(session_maker)
        try:
            async with session_maker() as session:
                return await body(session)
        finally:
            await engine.dispose()

    return asyncio.run(_inner())


def _handler_name(handler) -> str:
    return getattr(handler, "__name__", handler.__class__.__name__)


def _handler_map() -> dict[str, list[str]]:
    return {
        event_type.value: [_handler_name(handler) for handler in handlers]
        for event_type, handlers in event_bus._handlers.items()
    }


@app.command()
def emit(
    vault_id: Annotated[UUID4, typer.Argument(help="Target vault UUID")],
    event_type: Annotated[GameEvent, typer.Argument(help="Game event to emit")],
    data: Annotated[str | None, typer.Option(help="JSON object merged over per-event defaults")] = None,
) -> None:
    """Emit one game event so subscribed evaluators process it."""
    payload = dict(EVENT_DEFAULTS.get(event_type, {}))
    if data:
        payload.update(json.loads(data))

    async def body(_session):
        await event_bus.emit(event_type, vault_id, payload)
        return {"status": "ok", "event": event_type.value, "vault_id": str(vault_id), "data": payload}

    _echo(_run(body))


@app.command()
def events() -> None:
    """List subscribed event handlers."""

    async def body(_session):
        handlers = _handler_map()
        return {"events": handlers, "handler_count": sum(len(v) for v in handlers.values())}

    _echo(_run(body))


@app.command()
def evaluators() -> None:
    """Show evaluator-manager status and event subscriptions."""

    async def body(_session):
        from app.services.objective_evaluators import evaluator_manager

        return {"manager_initialized": evaluator_manager._initialized, "subscriptions": _handler_map()}

    _echo(_run(body))


@app.command()
def objectives(vault_id: Annotated[UUID4, typer.Argument(help="Target vault UUID")]) -> None:
    """Inspect seeded objectives and a vault's progress."""

    async def body(session):
        all_objectives = (await session.execute(select(Objective))).scalars().all()
        vault_rows = (
            await session.execute(
                select(Objective, VaultObjectiveProgressLink)
                .join(VaultObjectiveProgressLink)
                .where(VaultObjectiveProgressLink.vault_id == vault_id)
            )
        ).all()
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
                    "is_complete": obj.objective_type is not None
                    and obj.target_entity is not None
                    and obj.target_amount > 1,
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
                for obj, link in vault_rows
            ],
            "incomplete_objectives_count": len(incomplete),
            "incomplete_objectives": [
                {"id": str(obj.id), "challenge": obj.challenge, "target_amount": obj.target_amount}
                for obj in incomplete
            ],
        }

    _echo(_run(body))


@app.command()
def collect(
    vault_id: Annotated[UUID4, typer.Argument(help="Target vault UUID")],
    resource_type: Annotated[str, typer.Option(help="Resource collected")] = "caps",
    amount: Annotated[int, typer.Option(help="Amount collected")] = 10,
) -> None:
    """Emit RESOURCE_COLLECTED and report collect-objective progress before/after."""

    async def body(session):
        def _rows(rows):
            return [{"challenge": obj.challenge, "progress": link.progress, "total": link.total} for obj, link in rows]

        before = _rows(
            (
                await session.execute(
                    select(Objective, VaultObjectiveProgressLink)
                    .join(VaultObjectiveProgressLink)
                    .where(VaultObjectiveProgressLink.vault_id == vault_id)
                    .where(Objective.objective_type == "collect")
                )
            ).all()
        )
        await event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": resource_type, "amount": amount})
        await session.commit()
        after = _rows(
            (
                await session.execute(
                    select(Objective, VaultObjectiveProgressLink)
                    .join(VaultObjectiveProgressLink)
                    .where(VaultObjectiveProgressLink.vault_id == vault_id)
                    .where(Objective.objective_type == "collect")
                )
            ).all()
        )
        return {
            "vault_id": str(vault_id),
            "event": {"type": "RESOURCE_COLLECTED", "resource_type": resource_type, "amount": amount},
            "before": before,
            "after": after,
        }

    _echo(_run(body))


@app.command(name="build-living-room")
def build_living_room(vault_id: Annotated[UUID4, typer.Argument(help="Target vault UUID")]) -> None:
    """Build a living room via the room service and report population_max before/after."""

    async def body(session):
        from app import crud
        from app.core.enums import SPECIALEnum
        from app.core.game_data import get_static_game_data
        from app.models.room import Room
        from app.schemas.room import RoomBuild
        from app.services.room_service import room_service
        from app.utils.exceptions import ResourceNotFoundException

        vault = await crud.vault.get(session, id=vault_id)
        if not vault:
            raise ResourceNotFoundException(model=Vault, identifier=vault_id)

        game_data_store = await get_static_game_data()
        living_room = next((room for room in game_data_store.rooms if room.ability == SPECIALEnum.CHARISMA), None)
        if not living_room:
            raise ResourceNotFoundException(model=Vault, identifier="living room", identifier_type="name")

        before_population_max = vault.population_max
        created = await room_service.build_room(
            session,
            RoomBuild(vault_id=vault_id, room_name=living_room.name, coordinate_x=1, coordinate_y=1),
        )
        requires_calc = crud.room.requires_recalculation(created)

        await session.refresh(vault)
        all_rooms = (await session.execute(select(Room).where(Room.vault_id == vault_id))).scalars().all()
        return {
            "vault_id": str(vault_id),
            "before": {"population_max": before_population_max},
            "after": {"population_max": vault.population_max},
            "room_built": {
                "name": created.name,
                "category": created.category.value if created.category else None,
                "ability": created.ability.value if created.ability else None,
                "capacity": created.capacity,
            },
            "requires_recalculation": requires_calc,
            "all_rooms": [
                {
                    "name": room.name,
                    "category": room.category.value if room.category else None,
                    "ability": room.ability.value if room.ability else None,
                    "capacity": room.capacity,
                }
                for room in all_rooms
            ],
        }

    _echo(_run(body))
