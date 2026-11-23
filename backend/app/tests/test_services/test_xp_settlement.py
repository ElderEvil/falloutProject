from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import IncidentType, RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.room import RoomCreate
from app.services.combat.arena_service import arena_service
from app.services.combat.incident_round import award_combat_xp
from app.services.dweller_service import dweller_service
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import award_work_xp
from app.services.leveling_service import LevelingService, leveling_service


@contextmanager
def _surfacing():
    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up", new_callable=AsyncMock
        ) as notify,
    ):
        yield emit, notify


def _level_up_events(emit: AsyncMock, vault_id) -> list:
    return [
        call
        for call in emit.await_args_list
        if call.args and call.args[0] == GameEvent.DWELLER_LEVEL_UP and call.args[1] == vault_id
    ]


def _assert_surfaced_level_up(emit: AsyncMock, notify: AsyncMock, vault_id, level: int = 2) -> None:
    assert len(_level_up_events(emit, vault_id)) == 1
    notify.assert_awaited_once()
    assert notify.call_args.kwargs["new_level"] == level


async def _pin_level_one(async_session: AsyncSession, dweller: Dweller) -> int:
    dweller.level = 1
    threshold = LevelingService.calculate_xp_required(2)
    dweller.experience = threshold
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return threshold


async def _production_room(async_session: AsyncSession, vault: Vault) -> Room:
    return await room_crud.create(
        db_session=async_session,
        obj_in=RoomCreate(
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
        ),
    )


async def _room_and_incident(async_session: AsyncSession, vault: Vault) -> Incident:
    room = await _production_room(async_session, vault)
    incident = Incident(vault_id=vault.id, room_id=room.id, type=IncidentType.RAIDER_ATTACK, difficulty=1)
    async_session.add(incident)
    await async_session.commit()
    return incident


async def test_canonical_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    dweller.level = 1
    dweller.experience = 0
    async_session.add(dweller)
    await async_session.commit()
    amount = LevelingService.calculate_xp_required(2) - dweller.experience
    with _surfacing() as (emit, notify):
        updated = await dweller_service.add_experience(async_session, dweller, amount)
    assert updated.level == 2
    _assert_surfaced_level_up(emit, notify, vault.id)


async def test_canonical_path_quiet_without_level_up(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    dweller.level = 1
    dweller.experience = 0
    async_session.add(dweller)
    await async_session.commit()
    with _surfacing() as (emit, notify):
        updated = await dweller_service.add_experience(async_session, dweller, 1)
    assert updated.level == 1
    assert _level_up_events(emit, vault.id) == []
    notify.assert_not_awaited()


async def test_work_tick_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    room = await _production_room(async_session, vault)
    await _pin_level_one(async_session, dweller)
    with _surfacing() as (emit, notify):
        stats = await award_work_xp(async_session, dweller, room)
    assert stats["leveled_up"] >= 1
    _assert_surfaced_level_up(emit, notify, vault.id)


async def test_incident_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    incident = await _room_and_incident(async_session, vault)
    await _pin_level_one(async_session, dweller)
    with _surfacing() as (emit, notify):
        await award_combat_xp(async_session, incident, [dweller])
        assert _level_up_events(emit, vault.id) == []
        notify.assert_not_awaited()
        await leveling_service.deliver_deferred_level_ups(async_session)
    await async_session.refresh(dweller)
    assert dweller.level == 2
    _assert_surfaced_level_up(emit, notify, vault.id)


async def test_incident_level_up_rolls_back_with_the_round(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    incident = await _room_and_incident(async_session, vault)
    await _pin_level_one(async_session, dweller)
    await award_combat_xp(async_session, incident, [dweller])
    await async_session.rollback()
    await async_session.refresh(dweller)
    assert dweller.level == 1


async def test_arena_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    await _pin_level_one(async_session, dweller)
    with _surfacing() as (emit, notify):
        await arena_service._award_combat_xp(async_session, dweller, 60)
    await async_session.refresh(dweller)
    assert dweller.level == 2
    _assert_surfaced_level_up(emit, notify, vault.id)


async def test_exploration_path_surfaces_level_up(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _pin_level_one(async_session, dweller)
    with _surfacing() as (emit, notify):
        await rewards_service.apply_rewards(async_session, exploration)
    await async_session.refresh(dweller)
    assert dweller.level == 2
    _assert_surfaced_level_up(emit, notify, vault.id)


async def test_deferred_level_up_queues_until_drained(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    with _surfacing() as (emit, notify):
        await leveling_service.settle_level_up(
            async_session, dweller, old_level=dweller.level, levels_gained=1, commit=False
        )
        assert _level_up_events(emit, vault.id) == []
        notify.assert_not_awaited()
        await leveling_service.deliver_deferred_level_ups(async_session)
    _assert_surfaced_level_up(emit, notify, vault.id, level=dweller.level)


async def test_discarded_level_up_never_dispatches(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    with _surfacing() as (emit, notify):
        await leveling_service.settle_level_up(
            async_session, dweller, old_level=dweller.level, levels_gained=1, commit=False
        )
        leveling_service.discard_deferred_level_ups(async_session)
        await leveling_service.deliver_deferred_level_ups(async_session)
    assert _level_up_events(emit, vault.id) == []
    notify.assert_not_awaited()
