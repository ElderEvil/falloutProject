from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExplorationStatus
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.exploration_event import CombatEventSchema
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.game_loop_service import game_loop_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.utils.time import utcnow


async def _add_adult(async_session, vault) -> Dweller:
    data = create_fake_adult_dweller() | {"vault_id": vault.id}
    return await crud.dweller.create(async_session, DwellerCreate(**data))


async def _start_exploration(async_session, vault, dweller, *, duration: int = 4, ago: timedelta | None = None):
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=duration)
    exploration.start_time = utcnow() - (ago or timedelta(minutes=10))
    await async_session.commit()
    return exploration


async def test_process_explorations_error_handling(async_session, vault, dweller):
    second = await _add_adult(async_session, vault)
    await _start_exploration(async_session, vault, dweller)
    await _start_exploration(async_session, vault, second)

    calls = 0

    def generate(exp):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Test error")
        return {"type": "encounter", "description": "Safe event", "loot": None}

    with patch.object(exploration_service, "generate_event", side_effect=generate):
        result = await game_loop_service._process_explorations(async_session, vault.id)

    # One failing exploration must not abort the pass for the other.
    assert result["active_count"] == 2


async def test_vault_tick_processes_explorations(async_session, vault, dweller):
    exploration = await _start_exploration(async_session, vault, dweller, duration=1, ago=timedelta(hours=2))

    # First tick: exploring ends, dweller heads home — no rewards yet.
    first = await game_loop_service.process_vault_tick(async_session, vault.id)

    assert "explorations" in first["updates"]
    assert first["updates"]["explorations"]["returning"] == 1
    assert first["updates"]["explorations"]["completed"] == 0

    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.RETURNING

    exploration.return_completes_at = utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()

    second = await game_loop_service.process_vault_tick(async_session, vault.id)

    assert second["updates"]["explorations"]["completed"] == 1


async def test_process_explorations_caps_accumulate(async_session, vault, dweller):
    second = await _add_adult(async_session, vault)
    first_exp = await _start_exploration(async_session, vault, dweller, duration=1, ago=timedelta(hours=2))
    second_exp = await _start_exploration(async_session, vault, second, duration=1, ago=timedelta(hours=2))

    await crud.exploration.update_stats(async_session, exploration_id=first_exp.id, caps=100)
    await crud.exploration.update_stats(async_session, exploration_id=second_exp.id, caps=150)

    initial_caps = vault.bottle_caps

    # First pass sends both dwellers home; rewards wait for arrival.
    first = await game_loop_service._process_explorations(async_session, vault.id)
    assert first["returning"] == 2

    for exploration in (first_exp, second_exp):
        await async_session.refresh(exploration)
        exploration.return_completes_at = utcnow() - timedelta(seconds=1)
        async_session.add(exploration)
    await async_session.commit()

    result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["completed"] == 2

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 250  # 100 + 150


async def test_process_explorations_danger_event_updates_enemies(async_session, vault, dweller):
    exploration = await _start_exploration(async_session, vault, dweller)
    mock_event = CombatEventSchema(
        description="Attacked by raiders!", health_loss=10, enemy="Raider gang", victory=True
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["events_generated"] == 1
    await async_session.refresh(exploration)
    assert exploration.enemies_encountered == 1
