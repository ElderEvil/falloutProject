"""Uniform level-up surfacing spec across all XP paths (P0 backlog item 1).

Every path that levels a dweller must emit DWELLER_LEVEL_UP and send the
level-up notification (progression-visibility red line). The canonical path
(DwellerService.add_experience) does both; the four direct
leveling_service.check_level_up call sites currently diverge. These tests pin
the target contract: passing tests guard it, failing ones prove the breach.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.incident import Incident, IncidentType
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.room import RoomCreate
from app.services.combat.arena_service import arena_service
from app.services.combat.incident_round import award_combat_xp
from app.services.dweller_service import dweller_service
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import award_work_xp
from app.services.leveling_service import LevelingService


async def _pin_level_one(async_session: AsyncSession, dweller: Dweller) -> int:
    """Pin a level-1 dweller exactly at the leveling-curve threshold."""
    dweller.level = 1
    threshold = LevelingService.calculate_xp_required(2)
    dweller.experience = threshold
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return threshold


def _level_up_events(emit_mock: AsyncMock, vault_id) -> list:
    """Emitted DWELLER_LEVEL_UP calls for one vault."""
    return [
        call
        for call in emit_mock.await_args_list
        if call.args and call.args[0] == GameEvent.DWELLER_LEVEL_UP and call.args[1] == vault_id
    ]


async def _make_production_room(async_session: AsyncSession, vault: Vault) -> Room:
    room_in = RoomCreate(
        name="Power Plant",
        category=RoomTypeEnum.PRODUCTION,
        tier=1,
        size=3,
        capacity=2,
        ability=SPECIALEnum.STRENGTH,
        base_cost=1000,
        t2_upgrade_cost=2500,
        t3_upgrade_cost=5000,
        size_min=1,
        size_max=3,
        vault_id=vault.id,
    )
    return await room_crud.create(db_session=async_session, obj_in=room_in)


@pytest.mark.asyncio
async def test_canonical_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """The canonical path emits the event and notifies on level-up."""
    dweller.level = 1
    dweller.experience = 0
    async_session.add(dweller)
    await async_session.commit()
    amount = crud.dweller.calculate_experience_required(dweller) - dweller.experience

    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up",
            new_callable=AsyncMock,
        ) as notify,
    ):
        updated = await dweller_service.add_experience(async_session, dweller, amount)

    assert updated.level == 2
    assert len(_level_up_events(emit, vault.id)) == 1
    notify.assert_awaited_once()
    assert notify.call_args.kwargs["new_level"] == 2


@pytest.mark.asyncio
async def test_canonical_path_quiet_without_level_up(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """No level-up means no event and no notification (no over-notifying)."""
    dweller.level = 1
    dweller.experience = 0
    async_session.add(dweller)
    await async_session.commit()

    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up",
            new_callable=AsyncMock,
        ) as notify,
    ):
        updated = await dweller_service.add_experience(async_session, dweller, 1)

    assert updated.level == 1
    assert _level_up_events(emit, vault.id) == []
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_work_tick_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """Work-tick level-ups must surface exactly like the canonical path."""
    room = await _make_production_room(async_session, vault)
    await _pin_level_one(async_session, dweller)

    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up",
            new_callable=AsyncMock,
        ) as notify,
    ):
        stats = await award_work_xp(async_session, dweller, room)

    assert stats["leveled_up"] >= 1
    assert len(_level_up_events(emit, vault.id)) == 1
    notify.assert_awaited_once()
    assert notify.call_args.kwargs["new_level"] == 2


@pytest.mark.asyncio
async def test_incident_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """Incident level-ups must surface exactly like the canonical path."""
    room = await _make_production_room(async_session, vault)
    await _pin_level_one(async_session, dweller)
    incident = Incident(vault_id=vault.id, room_id=room.id, type=IncidentType.RAIDER_ATTACK, difficulty=1)
    async_session.add(incident)
    await async_session.commit()

    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up",
            new_callable=AsyncMock,
        ) as notify,
    ):
        await award_combat_xp(async_session, incident, [dweller])

    await async_session.refresh(dweller)
    assert dweller.level == 2
    assert len(_level_up_events(emit, vault.id)) == 1
    notify.assert_awaited_once()
    assert notify.call_args.kwargs["new_level"] == 2


@pytest.mark.asyncio
async def test_arena_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """Arena level-ups must surface exactly like the canonical path."""
    await _pin_level_one(async_session, dweller)

    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up",
            new_callable=AsyncMock,
        ) as notify,
    ):
        await arena_service._award_combat_xp(async_session, dweller)

    await async_session.refresh(dweller)
    assert dweller.level == 2
    assert len(_level_up_events(emit, vault.id)) == 1
    notify.assert_awaited_once()
    assert notify.call_args.kwargs["new_level"] == 2


@pytest.mark.asyncio
async def test_exploration_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """Exploration level-ups must surface exactly like the canonical path."""
    exploration: Exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _pin_level_one(async_session, dweller)

    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up",
            new_callable=AsyncMock,
        ) as notify,
    ):
        await rewards_service.apply_rewards(async_session, exploration)

    await async_session.refresh(dweller)
    assert dweller.level == 2
    assert len(_level_up_events(emit, vault.id)) == 1
    notify.assert_awaited_once()
    assert notify.call_args.kwargs["new_level"] == 2
