"""Radio tick phase: the roll, the gates (mode, room), failure isolation and the vault-tick wiring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.room import RoomCreate
from app.schemas.vault import ResourceTickEvents
from app.services.game_loop_service import game_loop_service
from app.services.game_tick.radio_tick import process_radio
from app.services.radio_service import radio_service


def _rng(value: float):
    return SimpleNamespace(random=lambda: value)


async def _set_mode(async_session, vault, mode: str) -> None:
    vault.radio_mode = mode
    async_session.add(vault)
    await async_session.commit()


async def _make_radio_room(async_session, vault) -> Room:
    # The service matches radio rooms by name.
    room_in = RoomCreate(
        name="Radio Studio",
        category=RoomTypeEnum.MISC,
        ability=SPECIALEnum.CHARISMA,
        base_cost=100,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=1,
        size_max=3,
        size=2,
        vault_id=vault.id,
    )
    return await crud.room.create(db_session=async_session, obj_in=room_in)


@pytest_asyncio.fixture(name="radio_room")
async def radio_room_fixture(async_session, vault) -> Room:
    return await _make_radio_room(async_session, vault)


async def test_recruits_only_when_the_roll_succeeds(async_session, vault, radio_room) -> None:
    await _set_mode(async_session, vault, "recruitment")
    before = await crud.dweller.count_in_vault(async_session, vault.id)
    assert (await process_radio(async_session, vault.id, rng=_rng(1.0)))["recruited"] == 0
    assert await crud.dweller.count_in_vault(async_session, vault.id) == before
    assert (await process_radio(async_session, vault.id, rng=_rng(0.0)))["recruited"] == 1
    assert await crud.dweller.count_in_vault(async_session, vault.id) == before + 1


@pytest.mark.parametrize(("mode", "has_room"), [("happiness", True), ("recruitment", False)])
async def test_does_not_recruit_when_the_phase_is_gated(async_session, vault, mode, has_room) -> None:
    if has_room:
        await _make_radio_room(async_session, vault)
    await _set_mode(async_session, vault, mode)
    assert (await process_radio(async_session, vault.id, rng=_rng(0.0)))["recruited"] == 0


async def test_recovers_the_session_when_recruitment_raises(async_session, vault) -> None:
    vault_id = vault.id
    with patch.object(radio_service, "check_for_recruitment", new=AsyncMock(side_effect=SQLAlchemyError("boom"))):
        stats = await process_radio(async_session, vault_id)
    assert "error" in stats
    assert stats["recruited"] == 0
    # recover_session rolled back, so the session still serves queries. Read the captured id: the
    # rollback expired the vault instance.
    assert await crud.dweller.count_in_vault(async_session, vault_id) == 0


async def test_process_vault_tick_runs_the_radio_phase(async_session, vault) -> None:
    mock_update = MagicMock()
    mock_update.power = 100
    mock_update.food = 50
    mock_update.water = 75
    with (
        patch.object(game_loop_service.resource_manager, "process_vault_resources", new_callable=AsyncMock) as mr,
        patch.object(game_loop_service, "_process_dwellers", new_callable=AsyncMock, return_value={}),
        patch.object(game_loop_service, "_process_training", new_callable=AsyncMock, return_value={}),
        patch.object(game_loop_service, "_process_happiness", new_callable=AsyncMock, return_value={}),
        patch.object(game_loop_service, "_process_breeding", new_callable=AsyncMock, return_value={}),
        patch.object(
            game_loop_service, "_process_radio", new_callable=AsyncMock, return_value={"recruited": 1}
        ) as radio,
    ):
        mr.return_value = (mock_update, ResourceTickEvents())
        result = await game_loop_service.process_vault_tick(async_session, vault.id)
    radio.assert_awaited_once()
    assert result["updates"]["radio"] == {"recruited": 1}
