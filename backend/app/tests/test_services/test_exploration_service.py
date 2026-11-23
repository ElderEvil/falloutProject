from collections.abc import AsyncGenerator
from contextlib import suppress
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, ExplorationStatus, RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent
from app.core.game_config import game_config
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.storage import Storage
from app.models.user import User
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.exploration_event import (
    CombatEventSchema,
    DangerEventSchema,
    ItemSchema,
    LootEventSchema,
    LootSchema,
    RestEventSchema,
)
from app.schemas.room import RoomCreate
from app.services.exploration.event_generator import event_generator
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration_service import exploration_service
from app.services.training_service import training_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.vaults import create_fake_vault
from app.tests.utils.query_counter import count_sql_statements
from app.utils.time import utcnow

JUNK_LOOT = LootEventSchema(
    description="Found treasure!",
    loot=LootSchema(item=ItemSchema(name="Desk Fan", rarity="Common", value=15), item_type="junk", caps=25),
)


async def _finish_exploration(async_session: AsyncSession, exploration) -> None:
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)


async def _complete_exploration(async_session: AsyncSession, exploration):
    """Backdate the run, walk the return leg, then finalize to collect rewards."""
    await _finish_exploration(async_session, exploration)
    await exploration_service.start_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    exploration.return_completes_at = utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()
    return await exploration_service.finalize_return(async_session, exploration.id)


async def _add_medbay(async_session: AsyncSession, vault: Vault, capacity: int = 10) -> None:
    """Give the vault a Medbay so returned Stimpaks have somewhere to go."""
    await room_crud.create(
        async_session,
        RoomCreate(
            name="Medbay",
            category=RoomTypeEnum.PRODUCTION,
            tier=1,
            size=3,
            capacity=capacity,
            ability=SPECIALEnum.INTELLIGENCE,
            base_cost=400,
            t2_upgrade_cost=1000,
            t3_upgrade_cost=3000,
            size_min=3,
            size_max=9,
            vault_id=vault.id,
        ),
    )


def _stimpak_collect_events(emit: AsyncMock) -> list[dict]:
    """The ITEM_COLLECTED payloads credited for returned Stimpaks."""
    return [
        call.args[2]
        for call in emit.await_args_list
        if call.args[0] == GameEvent.ITEM_COLLECTED and call.args[2].get("item_type") == "stimpak"
    ]


async def _walking(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, *, stimpaks: int = 0, radaways: int = 0
):
    """A run old enough to generate events, carrying the supplies under test."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.start_time = utcnow() - timedelta(minutes=10)
    exploration.stimpaks = stimpaks
    exploration.radaways = radaways
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


async def test_lock_exploration_skips_preview_when_vault_id_supplied(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # A caller that already loaded the run must not pay for a preview SELECT.
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=1)
    async_session.expunge_all()
    with count_sql_statements(async_session) as without_vault:
        await lock_exploration_with_vault_claim(async_session, exploration.id)
    async_session.expunge_all()
    with count_sql_statements(async_session) as with_vault:
        await lock_exploration_with_vault_claim(async_session, exploration.id, vault_id=vault.id)
    assert with_vault.value == without_vault.value - 1


async def test_send_dweller_deducts_supplies_once_and_snapshots_stats(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # Supplies taken from storage must not also be removed from the dweller.
    dweller.stimpack, dweller.radaway = 2, 1
    dweller.strength, dweller.perception, dweller.endurance = 9, 8, 7
    dweller.charisma, dweller.intelligence, dweller.agility, dweller.luck = 6, 5, 4, 3
    storage = Storage(vault_id=vault.id, stimpack=5, radaway=3)
    async_session.add_all([dweller, storage])
    await async_session.commit()
    exploration = await exploration_service.send_dweller(
        async_session, vault.id, dweller.id, duration=4, stimpaks=4, radaways=2
    )
    await async_session.refresh(dweller)
    await async_session.refresh(storage)
    assert exploration.stimpaks == 4
    assert exploration.radaways == 2
    assert storage.stimpack == 1
    assert storage.radaway == 1
    assert dweller.stimpack == 2
    assert dweller.radaway == 1
    assert (
        exploration.dweller_strength,
        exploration.dweller_perception,
        exploration.dweller_endurance,
        exploration.dweller_charisma,
        exploration.dweller_intelligence,
        exploration.dweller_agility,
        exploration.dweller_luck,
    ) == (9, 8, 7, 6, 5, 4, 3)


async def test_send_dweller_rejects_dweller_already_exploring(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    with pytest.raises(ValueError, match="already on an exploration"):
        await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)


async def test_send_dweller_rejects_dead_dweller(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    dweller.is_dead = True
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValueError, match="dweller is dead"):
        await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)


@pytest.mark.parametrize(
    ("stimpaks", "radaways", "message"),
    [(-1, 0, "Stimpaks cannot be negative. Provided: -1"), (0, -1, "Radaways cannot be negative. Provided: -1")],
)
async def test_send_dweller_rejects_negative_supplies(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, stimpaks: int, radaways: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        await exploration_service.send_dweller(
            async_session, vault.id, dweller.id, duration=4, stimpaks=stimpaks, radaways=radaways
        )


async def test_nonhuman_explorer_cannot_pack_radaway(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    dweller.visual_attributes = {"race": "super_mutant"}
    async_session.add_all([dweller, Storage(vault_id=vault.id, stimpack=5, radaway=5)])
    await async_session.commit()
    with pytest.raises(ValueError, match="cannot carry RadAway"):
        await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4, stimpaks=1, radaways=1)


async def test_send_dweller_rejects_a_dweller_from_another_vault(async_session: AsyncSession, dweller: Dweller) -> None:
    with pytest.raises(ValueError, match="does not belong to this vault"):
        await exploration_service.send_dweller(async_session, uuid4(), dweller.id, duration=4)


async def test_generate_event_not_active(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await crud.exploration.start_return(async_session, exploration_id=exploration.id)
    await async_session.refresh(exploration)
    event = exploration_service.generate_event(exploration)
    assert event is None


async def test_process_event_for_paused_exploration(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.paused_at = utcnow()
    async_session.add(exploration)
    await async_session.commit()
    with pytest.raises(ValueError, match="paused"):
        await exploration_service.process_event_for_exploration(async_session, exploration.id)


async def test_generate_event_with_loot(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    exploration = await _walking(async_session, vault, dweller)
    events_generated = []
    for _ in range(20):
        event = exploration_service.generate_event(exploration)
        if event:
            events_generated.append(event)
            exploration.add_event(
                event_type=event.type, description=event.description, loot=getattr(event, "loot", None)
            )
            if exploration.events:
                exploration.events[-1]["timestamp"] = (utcnow() - timedelta(minutes=11)).isoformat()
    assert len(events_generated) > 0
    valid_types = ["combat", "loot", "danger", "rest", "discovery"]
    for event in events_generated:
        assert event.type in valid_types
        assert hasattr(event, "description")
        if event.type == "loot":
            assert event.loot is not None
            assert hasattr(event.loot, "item")
            assert hasattr(event.loot, "caps")


async def test_complete_exploration_transfers_caps(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await crud.exploration.update_stats(async_session, exploration_id=exploration.id, caps=150, distance=75, enemies=10)
    await crud.exploration.add_loot(
        async_session, exploration_id=exploration.id, item_name="Wonderglue", quantity=2, rarity="Rare"
    )
    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    # 65/80 passes the 70% survival check, but 65/100 would not: radiation makes
    # this a guard against reverting the bonus to base max health.
    dweller.max_health = 100
    dweller.health = 65
    dweller.radiation = 20
    async_session.add(dweller)
    await async_session.commit()
    initial_caps = vault.bottle_caps
    # XP uses the pre-level-up dweller state.
    base_xp = (75 * 10) + (10 * 50) + (0 * 20)  # distance*10 + enemies*50 + events*20
    expected_xp = base_xp
    if dweller.health / dweller.effective_max_health > 0.7:
        expected_xp += int(base_xp * 0.2)  # 20% survival bonus
    expected_xp += int(base_xp * (exploration.dweller_luck * 0.02))  # 2% per luck point
    rewards = await _complete_exploration(async_session, exploration)
    assert rewards.caps == 150
    assert rewards.distance == 75
    assert rewards.enemies_defeated == 10
    assert rewards.experience == expected_xp
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 150
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert exploration.end_time is not None


@pytest.mark.parametrize(
    ("capacity", "stored", "storage_left", "collect_events"),
    [
        (10, 2, 5, [{"item_type": "stimpak", "amount": 2}]),
        (4, 1, None, [{"item_type": "stimpak", "amount": 1}]),
        (None, 0, 0, []),
    ],
)
async def test_return_reports_and_credits_only_stored_stimpaks(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    capacity: int | None,
    stored: int,
    storage_left: int | None,
    collect_events: list[dict],
) -> None:
    # Supplies dropped for lack of medical capacity must not count as collected.
    if capacity is not None:
        await _add_medbay(async_session, vault, capacity=capacity)
    storage = Storage(vault_id=vault.id, stimpack=5, radaway=0)
    async_session.add(storage)
    await async_session.commit()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4, stimpaks=2)
    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        rewards = await _complete_exploration(async_session, exploration)
    assert rewards.stimpaks == 2
    assert rewards.stimpaks_stored == stored
    assert rewards.radaways_stored == 0
    assert _stimpak_collect_events(emit) == collect_events
    if storage_left is not None:
        await async_session.refresh(storage)
        assert storage.stimpack == storage_left


async def test_return_reports_caps_actually_credited_at_wallet_cap(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # A full wallet must not report caps it did not accept.
    vault.bottle_caps = 999_999
    async_session.add(vault)
    await async_session.commit()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.total_caps_found = 150
    async_session.add(exploration)
    await async_session.commit()
    rewards = await _complete_exploration(async_session, exploration)
    assert rewards.caps >= 150
    assert rewards.caps_credited == 0


async def test_complete_exploration_not_active_raises_error(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _complete_exploration(async_session, exploration)
    with pytest.raises(ValueError, match="not active"):
        await exploration_service.complete_exploration_with_data(async_session, exploration.id)


async def test_complete_exploration_before_duration_raises_error(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    with pytest.raises(ValueError, match="has not finished yet"):
        await exploration_service.complete_exploration_with_data(async_session, exploration.id)


async def test_recall_exploration_reduced_rewards(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await crud.exploration.update_stats(async_session, exploration_id=exploration.id, caps=100, distance=50, enemies=5)
    await async_session.refresh(exploration)
    initial_caps = vault.bottle_caps
    # Recall early: the run enters its return leg and rewards wait for arrival.
    recalled, pending_rewards = await exploration_service.recall_exploration_with_data(async_session, exploration.id)
    assert recalled.status == ExplorationStatus.RETURNING
    assert pending_rewards is None
    rewards = await exploration_service.finalize_return(async_session, exploration.id)
    assert rewards.caps == 100  # Caps are kept
    assert rewards.recalled_early is True
    assert rewards.progress_percentage is not None
    assert 0 <= rewards.progress_percentage <= 100
    base_exp = (50 * 10) + (5 * 50)
    expected_exp = int(base_exp * (rewards.progress_percentage / 100))
    assert rewards.experience == expected_exp
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.RECALLED
    assert exploration.end_time is not None


async def test_recall_exploration_not_active_raises_error(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _complete_exploration(async_session, exploration)
    with pytest.raises(ValueError, match="not active"):
        await exploration_service.recall_exploration_with_data(async_session, exploration.id)


async def test_process_danger_radiation_applies_to_dweller(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # Pin radiation: the fixture rolls a random start, and a value near the cap would break the +11 delta.
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.commit()
    exploration = await _walking(async_session, vault, dweller)
    initial_radiation = dweller.radiation
    mock_event = DangerEventSchema(
        description="Caught in unexpected radiation burst. Took 11 rads.", health_loss=0, radiation_gain=11
    )
    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await exploration_service.process_event(async_session, exploration)
    await async_session.refresh(dweller)
    assert dweller.radiation == initial_radiation + 11
    assert result.events[-1]["radiation_gain"] == 11


async def test_rest_event_logs_actual_healing_after_radiation_cap(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # A rest heal capped by radiation must log the HP actually restored.
    dweller.max_health = 100
    dweller.radiation = 50  # effective max 50
    dweller.health = 48  # only 2 HP of headroom
    async_session.add(dweller)
    await async_session.commit()
    exploration = await _walking(async_session, vault, dweller)
    mock_event = RestEventSchema(
        description="Rested in a safe location and recovered. Gained 10 HP.", health_restored=10
    )
    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await exploration_service.process_event(async_session, exploration)
    await async_session.refresh(dweller)
    assert dweller.health == 50
    rest_event = next(e for e in result.events if e["type"] == "rest")
    assert rest_event["health_restored"] == 2
    assert "Gained 2 HP" in rest_event["description"]


@pytest.mark.parametrize(("heal_percent", "expected_health", "expected_healing"), [(0.4, 50, 30), (0.001, 21, 1)])
async def test_auto_stimpak_logs_actual_healing_after_radiation_cap(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    monkeypatch: pytest.MonkeyPatch,
    heal_percent: float,
    expected_health: int,
    expected_healing: int,
) -> None:
    # A Stimpak heal capped by radiation must log the HP actually restored.
    monkeypatch.setattr(game_config.health, "stimpack_heal_percent", heal_percent)
    dweller.max_health = 100
    dweller.radiation = 50  # effective max 50
    dweller.health = 20  # below the 50% auto-heal threshold
    async_session.add(dweller)
    await async_session.commit()
    exploration = await _walking(async_session, vault, dweller, stimpaks=1)
    with patch.object(event_generator, "generate_event", return_value=JUNK_LOOT):
        result = await exploration_service.process_event(async_session, exploration)
    await async_session.refresh(dweller)
    assert dweller.health == expected_health
    assert result.stimpaks == 0
    item_use = next(e for e in result.events if e["type"] == "item_use")
    assert item_use["health_restored"] == expected_healing
    assert f"Healed {expected_healing} HP" in item_use["description"]


async def test_auto_radaway_logs_structured_radiation_removed(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # A RadAway auto-use must record a structured radiation_removed on the journey.
    dweller.max_health = 100
    dweller.radiation = 60  # above the auto-use threshold
    dweller.health = 40  # at the radiation-reduced ceiling, so no Stimpak branch fires
    async_session.add(dweller)
    await async_session.commit()
    exploration = await _walking(async_session, vault, dweller, radaways=1)
    with patch.object(event_generator, "generate_event", return_value=JUNK_LOOT):
        result = await exploration_service.process_event(async_session, exploration)
    await async_session.refresh(dweller)
    assert result.radaways == 0
    item_use = next(e for e in result.events if e["type"] == "item_use")
    assert item_use["radiation_removed"] == 50
    assert dweller.radiation == 10


async def test_send_dweller_cancels_active_training(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # Departing while training must cancel the session instead of orphaning it.
    room = await room_crud.create(
        async_session,
        RoomCreate(
            name="Weight Room",
            category=RoomTypeEnum.TRAINING,
            tier=1,
            size=2,
            capacity=6,
            ability=SPECIALEnum.STRENGTH,
            base_cost=1000,
            t2_upgrade_cost=2500,
            t3_upgrade_cost=5000,
            size_min=1,
            size_max=3,
            vault_id=vault.id,
        ),
    )
    dweller.status = DwellerStatusEnum.IDLE
    # The shared dweller fixture rolls random stats and can land on max strength,
    # which start_training rejects; pin a trainable value.
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    training = await training_service.start_training(async_session, dweller.id, room.id)
    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await async_session.refresh(training)
    await async_session.refresh(dweller)
    assert training.is_cancelled()
    assert dweller.status == DwellerStatusEnum.EXPLORING


async def test_auto_supplies_does_not_lower_health_above_radiation_ceiling(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    from app.services.exploration.event_service import auto_use_supplies

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    dweller.max_health = 100
    dweller.health = 20
    dweller.radiation = 90
    exploration.stimpaks = 1
    exploration.radaways = 0
    async_session.add(dweller)
    async_session.add(exploration)
    await async_session.commit()
    records = await auto_use_supplies(async_session, exploration)
    await async_session.commit()
    await async_session.refresh(dweller)
    await async_session.refresh(exploration)
    assert dweller.health == 20
    assert exploration.stimpaks == 1
    assert records == []


@pytest_asyncio.fixture
async def raw_session(db_connection: AsyncConnection) -> AsyncGenerator[RawAsyncSession]:
    """The tick-actor session type: raw SQLAlchemy ``AsyncSession`` on the shared connection.
    ``exploration_service`` runs under the dramatiq game-tick, and those actors get a raw
    session without SQLModel's ``.exec()`` (AGENTS.md "Background task session compatibility").
    The departure helpers are request-path only today, so a ``.exec()``-shaped regression there
    would pass this whole suite and fail first in a tick actor.
    """
    nested = await db_connection.begin_nested()
    session_factory = sessionmaker(
        bind=db_connection,
        class_=RawAsyncSession,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    async with session_factory() as session:
        yield session
        with suppress(Exception):
            await session.rollback()
        with suppress(Exception):
            await session.close()
    with suppress(Exception):
        await nested.rollback()
    with suppress(Exception):
        await db_connection.rollback()


async def _seed_vault_with_dweller(session: RawAsyncSession) -> tuple[Vault, Dweller]:
    """A vault and one adult dweller, written through the caller's (raw) session."""
    tag = uuid4().hex[:10]
    user = User(username=f"raw_session_{tag}", email=f"raw_session_{tag}@vault.test", hashed_password="x")
    session.add(user)
    await session.flush()
    vault = Vault(user_id=user.id, **create_fake_vault())
    session.add(vault)
    await session.flush()
    dweller = await crud.dweller.create(
        db_session=session, obj_in=DwellerCreate(vault_id=vault.id, **create_fake_adult_dweller())
    )
    return vault, dweller


async def test_departure_through_a_raw_session_keeps_the_tick_actor_contract(raw_session: RawAsyncSession) -> None:
    # A ``.exec()``-shaped regression here would pass the SQLModel suite and fail in a tick actor.
    assert not hasattr(raw_session, "exec"), "fixture must yield the raw SQLAlchemy session type"
    vault, dweller = await _seed_vault_with_dweller(raw_session)
    dweller.strength, dweller.perception, dweller.endurance = 9, 8, 7
    dweller.charisma, dweller.intelligence, dweller.agility, dweller.luck = 6, 5, 4, 3
    dweller.stimpack = 0
    dweller.radaway = 0
    storage = Storage(vault_id=vault.id, stimpack=5, radaway=3)
    raw_session.add_all([dweller, storage])
    await raw_session.commit()
    exploration = await exploration_service.send_dweller(
        raw_session, vault.id, dweller.id, duration=4, stimpaks=4, radaways=2
    )
    assert (
        exploration.dweller_strength,
        exploration.dweller_perception,
        exploration.dweller_endurance,
        exploration.dweller_charisma,
        exploration.dweller_intelligence,
        exploration.dweller_agility,
        exploration.dweller_luck,
    ) == (9, 8, 7, 6, 5, 4, 3)
    storage.stimpack, storage.radaway = 2, 0
    other = await crud.dweller.create(
        db_session=raw_session, obj_in=DwellerCreate(vault_id=vault.id, **create_fake_adult_dweller())
    )
    other.stimpack, other.radaway = 0, 0
    raw_session.add_all([other, storage])
    await raw_session.commit()
    with pytest.raises(ValueError, match=r"Total available stimpaks: 2"):
        await exploration_service.send_dweller(raw_session, vault.id, other.id, duration=4, stimpaks=3)
    await raw_session.refresh(storage)
    assert (storage.stimpack, storage.radaway) == (2, 0)
