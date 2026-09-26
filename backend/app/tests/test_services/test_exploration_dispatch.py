"""Tests for targeted dispatch runs to clearable map points (issue 772, phase 2)."""

import math
import random
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.notification import Notification, NotificationType
from app.models.vault import Vault
from app.models.world_location import VaultLocationState, WorldLocation
from app.schemas.dweller import DwellerCreate
from app.schemas.exploration_event import CombatOutcomeSchema
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.dispatch_resolution import resolve_dispatch_arrival
from app.services.exploration_service import dispatch_travel_hours, exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.services.map_service import map_service
from app.services.notification_service import NotificationService
from app.utils.exceptions import ResourceNotFoundException, ValidationException

WIN = CombatOutcomeSchema(victory=True, health_loss=0, description="win")
LOSS = CombatOutcomeSchema(victory=False, health_loss=5, description="loss")


async def _register_clearable(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, name: str = "Red Rocket"
) -> tuple[WorldLocation, VaultLocationState]:
    """Register a clearable map point (gas_station group) for the vault."""
    await map_service.register_bio_places(async_session, dweller, origin_place=name, visited_places=[])
    result = await async_session.execute(
        select(VaultLocationState)
        .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
        .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == name)
    )
    state = result.scalar_one()
    location = await crud.world_location.get_registry(async_session, state.location_id)
    return location, state


async def _expired_dispatch(async_session: AsyncSession, vault: Vault, dweller: Dweller, location_id):
    """Create a dispatch run whose travel time has already elapsed."""
    exploration = await exploration_service.dispatch(async_session, vault.id, dweller.id, location_id)
    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    return exploration


# ---------------------------------------------------------------------------
# dispatch_travel_hours
# ---------------------------------------------------------------------------


def test_dispatch_travel_hours_floor_and_cap() -> None:
    """Travel is whole hours: 1h floor, 24h cap, ceil on the raw seconds."""
    assert dispatch_travel_hours(0) == 1
    assert dispatch_travel_hours(1) == 1
    assert dispatch_travel_hours(15) == 1  # 1800 + 15*120 = 3600s exactly
    assert dispatch_travel_hours(16) == 2  # 3720s -> ceil(1.03)
    assert dispatch_travel_hours(690) == 24  # 84600s -> ceil(23.5)
    assert dispatch_travel_hours(1000) == 24  # capped


# ---------------------------------------------------------------------------
# dispatch happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_creates_targeted_run(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A dispatch creates a targeted run with the right duration, tier, and dweller state."""
    location, state = await _register_clearable(async_session, vault, dweller)

    exploration = await exploration_service.dispatch(async_session, vault.id, dweller.id, location.id)

    assert exploration.target_location_id == location.id
    assert exploration.clear_tier == 0
    expected_duration = dispatch_travel_hours(math.dist((50.0, 50.0), (location.coord_x, location.coord_y)))
    assert exploration.duration == expected_duration
    assert exploration.stimpaks == 0
    assert exploration.radaways == 0
    assert exploration.status == ExplorationStatus.ACTIVE

    await async_session.refresh(dweller)
    assert dweller.status.value == "exploring"
    assert dweller.room_id is None


# ---------------------------------------------------------------------------
# dispatch rejections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_rejects_unknown_location(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """An unknown location id raises ResourceNotFoundException."""
    with pytest.raises(ResourceNotFoundException):
        await exploration_service.dispatch(async_session, vault.id, dweller.id, uuid4())


@pytest.mark.asyncio
async def test_dispatch_rejects_non_clearable_group(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A landmark (non-clearable group) cannot be dispatched to."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Jefferson Memorial", visited_places=[])
    result = await async_session.execute(
        select(VaultLocationState)
        .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
        .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == "Jefferson Memorial")
    )
    state = result.scalar_one()

    with pytest.raises(ValidationException, match="cannot be cleared"):
        await exploration_service.dispatch(async_session, vault.id, dweller.id, state.location_id)


@pytest.mark.asyncio
async def test_dispatch_rejects_currently_cleared_point(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A point inside its reclear window cannot be dispatched to."""
    location, state = await _register_clearable(async_session, vault, dweller)
    state.reclear_available_at = datetime.utcnow() + timedelta(hours=1)
    async_session.add(state)
    await async_session.commit()

    with pytest.raises(ValidationException, match="currently cleared"):
        await exploration_service.dispatch(async_session, vault.id, dweller.id, location.id)


@pytest.mark.asyncio
async def test_dispatch_rejects_dweller_already_exploring(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A dweller already on a run cannot be dispatched again."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await exploration_service.dispatch(async_session, vault.id, dweller.id, location.id)

    with pytest.raises(ValidationException, match="already on an exploration"):
        await exploration_service.dispatch(async_session, vault.id, dweller.id, location.id)


@pytest.mark.asyncio
async def test_dispatch_rejects_dead_dweller(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A dead dweller cannot be dispatched."""
    location, state = await _register_clearable(async_session, vault, dweller)
    dweller.is_dead = True
    async_session.add(dweller)
    await async_session.commit()

    with pytest.raises(ValidationException, match="dweller is dead"):
        await exploration_service.dispatch(async_session, vault.id, dweller.id, location.id)


# ---------------------------------------------------------------------------
# arrival resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_arrival_win_clears_state_and_loot(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A winning arrival clears the point, rolls the haul, and starts the return leg."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.cleared_at is not None
    assert state.clear_count == 1
    assert state.reclear_available_at is not None
    expected_reclear = state.cleared_at + timedelta(hours=48)  # gas_station reclear_hours
    assert abs((state.reclear_available_at - expected_reclear).total_seconds()) < 1
    assert len(exploration.loot_collected) == 3  # low table has 3 items
    assert exploration.total_caps_found > 0


@pytest.mark.asyncio
async def test_dispatch_arrival_loss_no_clear_no_loot(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A losing arrival leaves the point uncleared, deals damage, and starts the return leg."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)
    health_before = dweller.health

    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=LOSS):
        await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.cleared_at is None
    assert state.clear_count == 0
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert dweller.health == max(1, health_before - 5)


@pytest.mark.asyncio
async def test_dispatch_arrival_win_notifies_location_cleared(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A winning arrival emits a LOCATION_CLEARED notification naming the location."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        await resolve_dispatch_arrival(async_session, exploration.id)

    notifications = (
        (
            await async_session.execute(
                select(Notification).where(Notification.notification_type == NotificationType.LOCATION_CLEARED)
            )
        )
        .scalars()
        .all()
    )
    assert len(notifications) == 1
    assert notifications[0].user_id == vault.user_id
    assert notifications[0].vault_id == vault.id
    assert "Red Rocket" in notifications[0].title


@pytest.mark.asyncio
async def test_dispatch_arrival_win_delivers_location_cleared_live(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A winning arrival drains the deferred LOCATION_CLEARED over WS/SSE, not just the row."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

    with (
        patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN),
        patch.object(NotificationService, "_deliver", new_callable=AsyncMock) as deliver,
    ):
        await resolve_dispatch_arrival(async_session, exploration.id)

    assert deliver.await_count == 1
    payload = deliver.await_args.args[1]
    assert payload["notification"]["notification_type"] == NotificationType.LOCATION_CLEARED


@pytest.mark.asyncio
async def test_dispatch_arrival_loss_no_notification(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A losing arrival does not emit a LOCATION_CLEARED notification."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=LOSS):
        await resolve_dispatch_arrival(async_session, exploration.id)

    notifications = (
        (
            await async_session.execute(
                select(Notification).where(Notification.notification_type == NotificationType.LOCATION_CLEARED)
            )
        )
        .scalars()
        .all()
    )
    assert notifications == []


@pytest.mark.asyncio
async def test_dispatch_escalation_tier_and_caps(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """Tier follows min(clear_count, cap) and a higher tier scales the caps roll."""
    location, state = await _register_clearable(async_session, vault, dweller)
    state.clear_count = 0
    async_session.add(state)
    await async_session.commit()

    exploration1 = await _expired_dispatch(async_session, vault, dweller, location.id)
    assert exploration1.clear_tier == 0
    random.seed(42)
    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        await resolve_dispatch_arrival(async_session, exploration1.id)
    await async_session.refresh(exploration1)
    caps1 = exploration1.total_caps_found

    dweller2 = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await async_session.refresh(state)
    state.clear_count = 5
    state.cleared_at = None
    state.reclear_available_at = None
    async_session.add(state)
    await async_session.commit()

    exploration2 = await _expired_dispatch(async_session, vault, dweller2, location.id)
    assert exploration2.clear_tier == game_config.exploration.dispatch.escalation_cap
    random.seed(42)
    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        await resolve_dispatch_arrival(async_session, exploration2.id)
    await async_session.refresh(exploration2)
    caps2 = exploration2.total_caps_found

    assert caps2 > caps1


# ---------------------------------------------------------------------------
# tick integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_run_generates_no_random_events(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A targeted run suppresses random events while active."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await exploration_service.dispatch(async_session, vault.id, dweller.id, location.id)

    with patch.object(
        exploration_service,
        "generate_event",
        return_value=CombatOutcomeSchema(victory=True, health_loss=1, description="x"),
    ) as mock_generate:
        stats = await process_explorations(async_session, vault.id)

    assert stats["events_generated"] == 0
    mock_generate.assert_not_called()
    await async_session.refresh(exploration)
    assert exploration.events == []


@pytest.mark.asyncio
async def test_tick_resolves_dispatch_arrival(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """The tick resolves an expired dispatch run instead of a plain return."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        stats = await process_explorations(async_session, vault.id)

    assert stats["returning"] == 1
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.clear_count == 1


# ---------------------------------------------------------------------------
# arrival consistency (review: tier snapshot + competing clears)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_arrival_uses_departure_tier_snapshot(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A run fights and earns at its departure tier even if the count moved mid-travel."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)
    assert exploration.clear_tier == 0

    await async_session.refresh(state)
    state.clear_count = 5
    async_session.add(state)
    await async_session.commit()

    random.seed(99)
    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    snapshot_caps = exploration.total_caps_found

    dweller2 = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await async_session.refresh(state)
    state.clear_count = 0
    state.cleared_at = None
    state.reclear_available_at = None
    async_session.add(state)
    await async_session.commit()
    control = await _expired_dispatch(async_session, vault, dweller2, location.id)
    random.seed(99)
    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        await resolve_dispatch_arrival(async_session, control.id)
    await async_session.refresh(control)

    assert snapshot_caps == control.total_caps_found


@pytest.mark.asyncio
async def test_dispatch_arrival_skips_point_cleared_by_competitor(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """An arrival that finds the point already cleared returns without loot or a second clear."""
    location, state = await _register_clearable(async_session, vault, dweller)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

    await async_session.refresh(state)
    state.cleared_at = datetime.utcnow()
    state.reclear_available_at = datetime.utcnow() + timedelta(hours=1)
    state.clear_count = 1
    async_session.add(state)
    await async_session.commit()

    with patch.object(combat_calculator, "calculate_combat_outcome", return_value=WIN):
        await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert state.clear_count == 1
