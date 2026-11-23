"""Authoritative dweller snapshot in the tick SSE payload, read once after all mutating phases."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, RarityEnum
from app.core.stream_manager import sse_manager
from app.models.dweller import Dweller
from app.models.pet import Pet
from app.models.vault import Vault
from app.options.pet_modifiers import pet_effect_for_name
from app.schemas.dweller import DwellerCreate
from app.services.game_loop_service import game_loop_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.utils.query_counter import count_sql_statements

SNAPSHOT_KEYS = {"id", "health", "max_health", "radiation", "happiness", "level", "experience", "status", "room_id", "is_dead", "effective_max_health"}  # fmt: skip


async def _tick_and_capture(async_session, vault_id, **kwargs) -> dict:
    with patch.object(sse_manager, "publish", new_callable=AsyncMock) as publish:
        await game_loop_service.process_vault_tick(async_session, vault_id, **kwargs)
    publish.assert_awaited_once()
    _vault_id, topic, data = publish.await_args.args
    assert topic == "game_ticks"
    return data["results"]["updates"]


async def test_tick_snapshot_has_one_exact_entry_per_live_dweller(async_session, vault, dweller):
    deleted = await crud.dweller.create(
        db_session=async_session, obj_in=DwellerCreate(**create_fake_dweller(), vault_id=vault.id)
    )
    deleted.is_deleted = True
    async_session.add(deleted)
    await async_session.commit()

    async def mutate_late(db_session, _vault_id, _seconds_passed, _game_state=None):
        row = await crud.dweller.get(db_session, dweller.id)
        row.happiness = 97
        db_session.add(row)
        await db_session.commit()
        return {"triggered": 0, "events": []}

    with patch.object(game_loop_service, "_process_events", new=mutate_late):
        updates = await _tick_and_capture(async_session, vault.id)

    assert "resources" in updates
    snapshot = updates["dweller_snapshot"]
    assert {entry["id"] for entry in snapshot} == {str(dweller.id)}
    assert set(snapshot[0]) == SNAPSHOT_KEYS
    assert isinstance(snapshot[0]["status"], str)
    assert snapshot[0]["room_id"] is None
    assert snapshot[0]["happiness"] == 97  # written by a late tick phase, so read after mutation

    # The snapshot query itself stays a single SELECT.
    with count_sql_statements(async_session) as statements:
        rows = await crud.dweller.get_tick_snapshot(async_session, vault.id)
    assert statements.value == 1
    assert [row.id for row in rows] == [dweller.id]
    assert rows[0].pet_name is None


async def test_snapshot_values_match_db_and_effective_max_health(
    async_session, user_with_vault: tuple, dweller_in_vault, room_in_vault
):
    _, vault = user_with_vault
    dweller = dweller_in_vault
    dweller.room_id = room_in_vault.id
    dweller.status = DwellerStatusEnum.WORKING
    dweller.health = 90
    dweller.radiation = 10
    async_session.add(dweller)
    async_session.add(Pet(name="Dogmeat (Fallout 4)", rarity=RarityEnum.LEGENDARY, dweller_id=dweller.id))
    await async_session.commit()

    updates = await _tick_and_capture(async_session, vault.id)
    entry = next(item for item in updates["dweller_snapshot"] if item["id"] == str(dweller.id))

    persisted = await crud.dweller.get(async_session, dweller.id)
    assert entry["health"] == persisted.health
    assert entry["max_health"] == persisted.max_health
    assert entry["radiation"] == persisted.radiation
    assert entry["happiness"] == persisted.happiness
    assert entry["level"] == persisted.level
    assert entry["experience"] == persisted.experience
    assert entry["status"] == persisted.status.value
    assert entry["room_id"] == str(persisted.room_id)
    assert entry["is_dead"] is persisted.is_dead

    pet_bonus = pet_effect_for_name("Dogmeat (Fallout 4)").max_health
    assert pet_bonus > 0
    assert entry["effective_max_health"] == max(1, persisted.max_health + pet_bonus - max(0, persisted.radiation))
    assert entry["effective_max_health"] == persisted.effective_max_health


async def test_snapshot_db_failure_recovers_session_and_commits_marker(async_session, vault):
    vault_id = vault.id

    async def drop_pet_table(db_session, _vault_id, _seconds_passed, _game_state=None):
        await db_session.execute(text("DROP TABLE pet"))
        return {"triggered": 0, "events": []}

    with (
        patch.object(game_loop_service, "_process_events", new=drop_pet_table),
        patch.object(sse_manager, "publish", new_callable=AsyncMock) as publish,
    ):
        result = await game_loop_service.process_vault_tick(async_session, vault_id, tick_id="tick-snapshot-db-fail")

    publish.assert_not_called()
    assert "dweller_snapshot" not in result["updates"]
    state = await crud.game_state_crud.get_or_create(async_session, vault_id)
    assert "tick-snapshot-db-fail" in (state.recent_tick_ids or [])
