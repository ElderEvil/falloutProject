"""Tests for the exploration return leg (half the exploring time)."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExpeditionRunStatus, ExplorationStatus
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.expedition import expedition_service
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.utils.exceptions import ValidationException


async def _expired_exploration(async_session: AsyncSession, vault: Vault, dweller: Dweller, duration: int = 4):
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=duration)
    exploration.start_time = datetime.utcnow() - timedelta(hours=duration)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


@pytest.mark.asyncio
async def test_return_leg_lasts_half_the_exploring_time(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A completed 4h run gets a 2h return leg."""
    exploration = await _expired_exploration(async_session, vault, dweller, duration=4)

    returned = await exploration_coordinator.start_return(async_session, exploration.id)

    assert returned.status == ExplorationStatus.RETURNING
    assert returned.return_started_at is not None
    assert returned.return_completes_at is not None
    assert returned.recalled_early is False
    return_seconds = (returned.return_completes_at - returned.return_started_at).total_seconds()
    assert return_seconds == 2 * 3600


@pytest.mark.asyncio
async def test_recall_return_leg_is_half_the_elapsed_time(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """An early recall returns in half the time actually spent exploring, not half the plan."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=10)
    exploration.start_time = datetime.utcnow() - timedelta(hours=2)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)

    returned = await exploration_coordinator.start_return(async_session, exploration.id, recalled=True)

    assert returned.status == ExplorationStatus.RETURNING
    assert returned.recalled_early is True
    return_seconds = (returned.return_completes_at - returned.return_started_at).total_seconds()
    assert return_seconds == 1 * 3600


@pytest.mark.asyncio
async def test_dweller_stays_busy_during_return_leg(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A returning dweller cannot be sent on another run until they arrive."""
    exploration = await _expired_exploration(async_session, vault, dweller)

    await exploration_coordinator.start_return(async_session, exploration.id)
    await async_session.refresh(dweller)

    assert dweller.status == DwellerStatusEnum.EXPLORING
    with pytest.raises(ValueError, match="already on an exploration"):
        await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=2)


@pytest.mark.asyncio
async def test_recall_during_return_leg_raises(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A run already on the return leg cannot be recalled again, and the racing recall
    must not overwrite the natural finish's timestamps or recalled_early flag."""
    exploration = await _expired_exploration(async_session, vault, dweller)

    returned = await exploration_coordinator.start_return(async_session, exploration.id)

    with pytest.raises(ValueError, match="not active"):
        await exploration_coordinator.start_return(async_session, exploration.id, recalled=True)

    await async_session.refresh(exploration)
    assert exploration.recalled_early is False
    assert exploration.return_completes_at == returned.return_completes_at


@pytest.mark.asyncio
async def test_loot_not_collectable_until_arrival(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Overflow loot stays locked while the dweller is still returning."""
    exploration = await _expired_exploration(async_session, vault, dweller)
    exploration.add_loot(item_name="Desk Fan", quantity=1, rarity="Common", item_type="junk")
    async_session.add(exploration)
    await async_session.commit()

    await exploration_coordinator.start_return(async_session, exploration.id)

    assert await rewards_service.get_pending_overflow(async_session, vault.id) == []
    with pytest.raises(ValidationException, match="still in progress"):
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)


@pytest.mark.asyncio
async def test_finalize_return_restores_dweller_and_completes(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Finalizing a return leg restores the dweller and marks the run completed."""
    exploration = await _expired_exploration(async_session, vault, dweller)

    await exploration_coordinator.start_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()
    await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert exploration.end_time is not None
    assert dweller.status == DwellerStatusEnum.IDLE


@pytest.mark.asyncio
async def test_tick_sends_dweller_home_then_finalizes(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """The tick moves an expired run onto its return leg, then finalizes it on arrival."""
    exploration = await _expired_exploration(async_session, vault, dweller, duration=1)

    first = await process_explorations(async_session, vault.id)
    assert first["returning"] == 1
    assert first["completed"] == 0

    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.RETURNING

    exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()

    second = await process_explorations(async_session, vault.id)
    assert second["completed"] == 1
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.COMPLETED


@pytest.mark.asyncio
async def test_finalize_return_rolls_back_terminal_transition_when_rewards_fail(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A reward failure mid-finalization must roll back the terminal transition.

    Finalization is one transaction: if reward settlement raises, the run must stay
    RETURNING (and the dweller unrestored) so the next tick retries it instead of
    leaving a run marked arrived with no rewards granted.
    """
    exploration = await _expired_exploration(async_session, vault, dweller)

    await exploration_coordinator.start_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    exploration.total_caps_found = 250
    vault.bottle_caps = 0
    async_session.add_all([exploration, vault])
    await async_session.commit()

    with (
        patch.object(
            rewards_service,
            "apply_rewards",
            new_callable=AsyncMock,
            side_effect=RuntimeError("reward settlement exploded"),
        ),
        pytest.raises(RuntimeError, match="reward settlement exploded"),
    ):
        await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.RETURNING
    assert dweller.status == DwellerStatusEnum.EXPLORING

    await exploration_coordinator.finalize_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(vault)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert vault.bottle_caps == 250
