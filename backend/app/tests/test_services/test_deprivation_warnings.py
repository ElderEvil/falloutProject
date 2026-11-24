"""Deprivation warnings: one per transition, staged in the phase transaction, pushed after its commit."""

import pytest

from app.core.enums import NotificationType
from app.crud import notification as crud_notification
from app.models.game_state import GameState
from app.services.game_loop_service import game_loop_service
from app.services.game_tick import dwellers_tick
from app.services.game_tick.deprivation import DeprivationResult

HUNGER_GRACE_MS = 60 * 60_000


async def _recent(async_session, vault):
    return await crud_notification.get_recent_for_vault(async_session, vault.id, limit=10)


@pytest.mark.asyncio
async def test_hunger_warning_fires_once_per_transition(async_session, vault) -> None:
    await dwellers_tick._announce_deprivation(async_session, vault.id, DeprivationResult(entered_hunger=True))
    await async_session.commit()
    await dwellers_tick._announce_deprivation(async_session, vault.id, DeprivationResult())
    await async_session.commit()

    rows = await _recent(async_session, vault)
    assert [row.notification_type for row in rows] == [NotificationType.RESOURCE_LOW]


@pytest.mark.asyncio
async def test_critical_warning_is_an_event_not_a_state(async_session, vault) -> None:
    await dwellers_tick._announce_deprivation(async_session, vault.id, DeprivationResult(became_critical=1))
    await async_session.commit()
    await dwellers_tick._announce_deprivation(async_session, vault.id, DeprivationResult())
    await async_session.commit()

    rows = await _recent(async_session, vault)
    assert [row.notification_type for row in rows] == [NotificationType.RESOURCE_CRITICAL]


@pytest.mark.asyncio
async def test_the_dweller_phase_commits_and_drains_its_own_warnings(async_session, vault, dweller) -> None:
    """The hunger warning must reach storage through the phase commit and leave nothing pending to push."""
    vault.food = 0
    async_session.add_all([vault, dweller, GameState(vault_id=vault.id, food_deprived_ms=HUNGER_GRACE_MS)])
    await async_session.commit()

    await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=60)

    rows = await _recent(async_session, vault)
    assert [row.notification_type for row in rows] == [NotificationType.RESOURCE_LOW]
    assert not async_session.info.get("deferred_notification_deliveries")
