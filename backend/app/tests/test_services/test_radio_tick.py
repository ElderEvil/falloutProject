"""Tests for the radio tick phase (passive radio recruitment).

``RadioService.check_for_recruitment`` was complete but had no production caller,
so passive recruitment never ran despite the UI advertising a rate and ETA.
These tests pin the phase that now drives it: the roll, the gates (recruitment
mode, an operating radio room), failure isolation, and the wiring into
``process_vault_tick``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate
from app.schemas.vault import ResourceTickEvents
from app.services.game_loop import game_loop_service
from app.services.game_tick.radio_tick import process_radio
from app.services.radio_service import radio_service


class _FixedRng:
    """Randomness source whose roll always returns the same value."""

    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


@pytest_asyncio.fixture(name="radio_room")
async def radio_room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """A radio studio; the service matches radio rooms by name."""
    room_in = RoomCreate(
        name="Radio Studio",
        category=RoomTypeEnum.MISC,
        ability=SPECIALEnum.CHARISMA,
        population_required=None,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        capacity=2,
        output=None,
        size_min=1,
        size_max=3,
        size=2,
        tier=1,
        coordinate_x=0,
        coordinate_y=0,
        image_url=None,
        vault_id=vault.id,
    )
    return await crud.room.create(db_session=async_session, obj_in=room_in)


async def _set_radio_mode(async_session: AsyncSession, vault: Vault, mode: str) -> None:
    vault.radio_mode = mode
    async_session.add(vault)
    await async_session.commit()


@pytest.mark.asyncio
async def test_recruits_when_the_roll_succeeds(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    """A winning roll adds a dweller to the vault."""
    await _set_radio_mode(async_session, vault, "recruitment")
    before = await crud.dweller.count_in_vault(async_session, vault.id)

    stats = await process_radio(async_session, vault.id, rng=_FixedRng(0.0))

    assert stats["recruited"] == 1
    assert await crud.dweller.count_in_vault(async_session, vault.id) == before + 1


@pytest.mark.asyncio
async def test_does_not_recruit_when_the_roll_fails(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    """A losing roll recruits nobody."""
    await _set_radio_mode(async_session, vault, "recruitment")
    before = await crud.dweller.count_in_vault(async_session, vault.id)

    stats = await process_radio(async_session, vault.id, rng=_FixedRng(1.0))

    assert stats["recruited"] == 0
    assert await crud.dweller.count_in_vault(async_session, vault.id) == before


@pytest.mark.asyncio
async def test_does_not_recruit_in_happiness_mode(async_session: AsyncSession, vault: Vault, radio_room: Room) -> None:
    """Happiness mode is not a recruitment mode, even on a winning roll."""
    await _set_radio_mode(async_session, vault, "happiness")

    stats = await process_radio(async_session, vault.id, rng=_FixedRng(0.0))

    assert stats["recruited"] == 0


@pytest.mark.asyncio
async def test_does_not_recruit_without_a_radio_room(async_session: AsyncSession, vault: Vault) -> None:
    """No radio studio means no recruitment, even on a winning roll."""
    await _set_radio_mode(async_session, vault, "recruitment")

    stats = await process_radio(async_session, vault.id, rng=_FixedRng(0.0))

    assert stats["recruited"] == 0


@pytest.mark.asyncio
async def test_recovers_the_session_when_recruitment_raises(async_session: AsyncSession, vault: Vault) -> None:
    """A database failure is isolated and leaves the session usable."""
    vault_id = vault.id
    with patch.object(radio_service, "check_for_recruitment", new=AsyncMock(side_effect=SQLAlchemyError("boom"))):
        stats = await process_radio(async_session, vault_id)

    assert "error" in stats
    assert stats["recruited"] == 0
    # recover_session rolled back, so the session still serves queries. Read the
    # captured id: the rollback expired the vault instance.
    assert await crud.dweller.count_in_vault(async_session, vault_id) == 0


@pytest.mark.asyncio
async def test_process_vault_tick_runs_the_radio_phase(async_session: AsyncSession, vault: Vault) -> None:
    """process_vault_tick drives the radio phase and records its result."""
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
        patch.object(game_loop_service, "_process_radio", new_callable=AsyncMock, return_value={"recruited": 1}) as radio,
    ):
        mr.return_value = (mock_update, ResourceTickEvents())
        result = await game_loop_service.process_vault_tick(async_session, vault.id)

    radio.assert_awaited_once()
    assert result["updates"]["radio"] == {"recruited": 1}
