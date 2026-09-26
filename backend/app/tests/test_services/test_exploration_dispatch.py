"""Tests for targeted dispatch runs to clearable map points (issue 772, phases 2-3)."""

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
from app.services.exploration.dispatch_resolution import resolve_dispatch_arrival
from app.services.exploration.party_resolution import distribute_damage, resolve_party_combat
from app.services.exploration_service import dispatch_travel_hours, exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.services.map_service import map_service
from app.services.notification_service import NotificationService
from app.utils.exceptions import ResourceNotFoundException, ValidationException

STRONG_STATS = {
    "strength": 10,
    "perception": 10,
    "endurance": 10,
    "charisma": 10,
    "intelligence": 10,
    "agility": 10,
    "luck": 10,
    "level": 30,
    "health": 100,
    "max_health": 100,
    "radiation": 0,
}
WEAK_STATS = {
    "strength": 1,
    "perception": 1,
    "endurance": 1,
    "charisma": 1,
    "intelligence": 1,
    "agility": 1,
    "luck": 1,
    "level": 1,
    "health": 100,
    "max_health": 100,
    "radiation": 0,
}


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
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location_id)
    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    return exploration


async def _expired_party_dispatch(async_session: AsyncSession, vault: Vault, dwellers: list[Dweller], location_id):
    """Create a party dispatch run whose travel time has already elapsed."""
    exploration = await exploration_service.dispatch(
        async_session, vault.id, [dweller.id for dweller in dwellers], location_id
    )
    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    return exploration


async def _boost_dweller(async_session: AsyncSession, dweller: Dweller, **overrides) -> Dweller:
    """Set explicit SPECIAL/level/health on a dweller for deterministic combat."""
    for key, value in overrides.items():
        setattr(dweller, key, value)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def _make_dweller(async_session: AsyncSession, vault: Vault, dweller_data: dict, **overrides) -> Dweller:
    """Create a vault dweller with explicit stats for deterministic combat."""
    return await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**{**dweller_data, **overrides}, vault_id=vault.id)
    )


# ---------------------------------------------------------------------------
# dispatch_travel_hours
# ---------------------------------------------------------------------------


def test_dispatch_travel_hours_floor_and_cap() -> None:
    """Travel is whole hours: 1h floor, 24h cap, ceil on the raw hours."""
    assert dispatch_travel_hours(0) == 1
    assert dispatch_travel_hours(1) == 2  # 1 + 0.1*1 = 1.1h -> ceil(1.1)
    assert dispatch_travel_hours(9) == 2  # 1 + 0.1*9 = 1.9h -> ceil(1.9)
    assert dispatch_travel_hours(10) == 2  # 1 + 0.1*10 = 2.0h exactly
    assert dispatch_travel_hours(11) == 3  # 2.1h -> ceil(2.1)
    assert dispatch_travel_hours(230) == 24  # 1 + 0.1*230 = 24.0h exactly
    assert dispatch_travel_hours(231) == 24  # 24.1h -> capped
    assert dispatch_travel_hours(1000) == 24  # capped


# ---------------------------------------------------------------------------
# dispatch happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_creates_targeted_run(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A dispatch creates a targeted run with the right duration, tier, and dweller state."""
    location, state = await _register_clearable(async_session, vault, dweller)

    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)

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
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], uuid4())


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
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], state.location_id)


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
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)


@pytest.mark.asyncio
async def test_dispatch_rejects_dweller_already_exploring(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A dweller already on a run cannot be dispatched again."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)

    with pytest.raises(ValidationException, match="already on an exploration"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)


@pytest.mark.asyncio
async def test_dispatch_rejects_dead_dweller(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A dead dweller cannot be dispatched."""
    location, state = await _register_clearable(async_session, vault, dweller)
    dweller.is_dead = True
    async_session.add(dweller)
    await async_session.commit()

    with pytest.raises(ValidationException, match="dweller is dead"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)


# ---------------------------------------------------------------------------
# arrival resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_arrival_win_clears_state_and_loot(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A winning arrival clears the point, rolls the haul, and starts the return leg."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

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
    await _boost_dweller(async_session, dweller, **WEAK_STATS)
    state.clear_count = 5  # tier snaps to the escalation cap: a lone weak dweller cannot win
    async_session.add(state)
    await async_session.commit()
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

    await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.cleared_at is None
    assert state.clear_count == 5
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    difficulty = min(5, 2 + game_config.exploration.dispatch.escalation_cap)
    members = await crud.team_crud.get_exploration_team_dwellers(async_session, exploration.id)
    _, expected_damage = resolve_party_combat(members, difficulty)
    assert dweller.health == 100 - expected_damage


@pytest.mark.asyncio
async def test_dispatch_arrival_win_notifies_location_cleared(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A winning arrival emits a LOCATION_CLEARED notification naming the location."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

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
    assert notifications[0].meta_data == {
        "location_id": str(location.id),
        "location_name": "Red Rocket",
    }


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
    await _boost_dweller(async_session, dweller, **WEAK_STATS)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

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
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    state.clear_count = 0
    async_session.add(state)
    await async_session.commit()

    exploration1 = await _expired_dispatch(async_session, vault, dweller, location.id)
    assert exploration1.clear_tier == 0
    random.seed(42)
    await resolve_dispatch_arrival(async_session, exploration1.id)
    await async_session.refresh(exploration1)
    caps1 = exploration1.total_caps_found

    dweller2 = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    await async_session.refresh(state)
    state.clear_count = 5
    state.cleared_at = None
    state.reclear_available_at = None
    async_session.add(state)
    await async_session.commit()

    exploration2 = await _expired_dispatch(async_session, vault, dweller2, location.id)
    assert exploration2.clear_tier == game_config.exploration.dispatch.escalation_cap
    random.seed(42)
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
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)

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
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    exploration = await _expired_dispatch(async_session, vault, dweller, location.id)

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


# ---------------------------------------------------------------------------
# party validation (phase 3)
# ---------------------------------------------------------------------------
    """An empty party is rejected."""
    location, _state = await _register_clearable(async_session, vault, dweller)
    with pytest.raises(ValidationException, match="at least one"):
        await exploration_service.dispatch(async_session, vault.id, [], location.id)


@pytest.mark.asyncio
async def test_dispatch_rejects_oversize_party(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """More than max_party_size dwellers is rejected."""
    location, _state = await _register_clearable(async_session, vault, dweller)
    extra = [await _make_dweller(async_session, vault, dweller_data) for _ in range(3)]
    ids = [dweller.id] + [member.id for member in extra]
    assert len(ids) == game_config.exploration.dispatch.max_party_size + 1
    with pytest.raises(ValidationException, match="Party size"):
        await exploration_service.dispatch(async_session, vault.id, ids, location.id)


@pytest.mark.asyncio
async def test_dispatch_rejects_duplicate_members(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """The same dweller twice is rejected."""
    location, _state = await _register_clearable(async_session, vault, dweller)
    with pytest.raises(ValidationException, match="only once"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id, dweller.id], location.id)


@pytest.mark.asyncio
async def test_dispatch_rejects_foreign_member(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A member from another vault is rejected and nothing is created."""
    from faker import Faker

    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreateWithUserID

    fake = Faker()
    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password()),
    )
    vault2 = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(
            number=999,
            bottle_caps=1000,
            happiness=50,
            power=10,
            food=10,
            water=10,
            population_max=50,
            user_id=user.id,
        ),
    )
    foreign = await _make_dweller(async_session, vault2, dweller_data)

    location, _state = await _register_clearable(async_session, vault, dweller)
    with pytest.raises(ValidationException, match="does not belong"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id, foreign.id], location.id)

    await async_session.refresh(dweller)
    assert dweller.status.value != "exploring"


@pytest.mark.asyncio
async def test_dispatch_rejects_busy_member(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A member already on a run blocks the whole party dispatch."""
    location, _state = await _register_clearable(async_session, vault, dweller)
    await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    partner = await _make_dweller(async_session, vault, dweller_data)

    with pytest.raises(ValidationException, match="already on an exploration"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id, partner.id], location.id)


# ---------------------------------------------------------------------------
# party departure and arrival (phase 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_creates_team(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A dispatch creates a team roster and marks every member EXPLORING."""
    location, _state = await _register_clearable(async_session, vault, dweller)
    partner = await _make_dweller(async_session, vault, dweller_data)

    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id, partner.id], location.id)

    assert exploration.team_id is not None
    team = await crud.team_crud.get_exploration_team(async_session, exploration.id)
    assert team is not None
    assert team.exploration_id == exploration.id
    assert [member.slot_number for member in sorted(team.members, key=lambda m: m.slot_number or 0)] == [1, 2]
    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    assert dweller.status.value == "exploring"
    assert partner.status.value == "exploring"
    assert dweller.room_id is None
    assert partner.room_id is None


@pytest.mark.asyncio
async def test_dispatch_party_win_scales_haul(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A winning party clears the point with one shared haul scaled by party size."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    partners = [await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS) for _ in range(2)]
    exploration = await _expired_party_dispatch(async_session, vault, [dweller, *partners], location.id)

    random.seed(7)
    await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.clear_count == 1
    assert len(exploration.loot_collected) == 3  # single haul roll, not per member
    assert exploration.total_caps_found > 0
    team = await crud.team_crud.get_exploration_team(async_session, exploration.id)
    assert team is not None
    assert len(team.members) == 3


@pytest.mark.asyncio
async def test_dispatch_arrival_death_trims_haul(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A member who dies at a lethal tier loses their carried share of the haul."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    fragile = await _make_dweller(async_session, vault, dweller_data, **{**WEAK_STATS, "health": 1})
    state.clear_count = 2  # tier 2: lethal, but the strong anchor still wins
    async_session.add(state)
    await async_session.commit()
    exploration = await _expired_party_dispatch(async_session, vault, [dweller, fragile], location.id)

    with patch("random.randint", return_value=100):
        await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    await async_session.refresh(dweller)
    await async_session.refresh(fragile)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.clear_count == 3
    assert not dweller.is_dead
    assert fragile.is_dead
    assert exploration.total_caps_found == 170  # 100 * 1.7 tier * 2 members, minus the dead half
    assert len(exploration.loot_collected) == 1  # 3 entries trimmed to the survivor's share


@pytest.mark.asyncio
async def test_dispatch_arrival_party_wipe(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A wiped party leaves the point uncleared with no loot."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **{**WEAK_STATS, "health": 1})
    partner = await _make_dweller(async_session, vault, dweller_data, **{**WEAK_STATS, "health": 1})
    state.clear_count = 5  # tier snaps to the cap: far beyond a weak party
    async_session.add(state)
    await async_session.commit()
    exploration = await _expired_party_dispatch(async_session, vault, [dweller, partner], location.id)

    await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.cleared_at is None
    assert state.clear_count == 5
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert dweller.is_dead
    assert partner.is_dead


# ---------------------------------------------------------------------------
# party damage distribution (phase 3)
# ---------------------------------------------------------------------------


def test_distribute_damage_sums_to_total() -> None:
    """Shares always sum to exactly the total, even when total < size."""
    for total, size in [(1, 3), (2, 3), (5, 3), (0, 3), (7, 3), (10, 4), (3, 1)]:
        shares = distribute_damage(total, size)
        assert len(shares) == size
        assert sum(shares) == total
        assert all(share >= 0 for share in shares)


def test_distribute_damage_zero_total_is_all_zeros() -> None:
    """total=0 yields a zero share for every member."""
    assert distribute_damage(0, 3) == [0, 0, 0]


@pytest.mark.asyncio
async def test_finalize_wipe_restores_no_one(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A wiped party finalizes without restoring any dead dweller's status."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **{**WEAK_STATS, "health": 1})
    partner = await _make_dweller(async_session, vault, dweller_data, **{**WEAK_STATS, "health": 1})
    state.clear_count = 5  # tier snaps to the cap: far beyond a weak party
    async_session.add(state)
    await async_session.commit()
    exploration = await _expired_party_dispatch(async_session, vault, [dweller, partner], location.id)

    await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    assert dweller.is_dead
    assert partner.is_dead

    exploration.return_started_at = datetime.utcnow() - timedelta(hours=10)
    exploration.return_completes_at = datetime.utcnow() - timedelta(hours=1)
    async_session.add(exploration)
    await async_session.commit()
    await exploration_service.finalize_return(async_session, exploration.id)

    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    assert dweller.is_dead
    assert partner.is_dead
    assert dweller.status.value == "dead"
    assert partner.status.value == "dead"


@pytest.mark.asyncio
async def test_dispatch_arrival_skips_point_cleared_by_competitor(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """A party arrival that finds the point already cleared returns without loot or a second clear."""
    location, state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    partner = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    exploration = await _expired_party_dispatch(async_session, vault, [dweller, partner], location.id)

    await async_session.refresh(state)
    state.cleared_at = datetime.utcnow()
    state.reclear_available_at = datetime.utcnow() + timedelta(hours=1)
    state.clear_count = 1
    async_session.add(state)
    await async_session.commit()

    await resolve_dispatch_arrival(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert state.clear_count == 1


# ---------------------------------------------------------------------------
# party return, rewards, and boundaries (phase 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_restores_party_and_deletes_team(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """Finalize restores every living member, settles the haul once, and deletes the team."""
    location, _state = await _register_clearable(async_session, vault, dweller)
    await _boost_dweller(async_session, dweller, **STRONG_STATS)
    partner = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    exploration = await _expired_party_dispatch(async_session, vault, [dweller, partner], location.id)
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(vault)
    caps_before = vault.bottle_caps

    exploration.return_started_at = datetime.utcnow() - timedelta(hours=10)
    exploration.return_completes_at = datetime.utcnow() - timedelta(hours=1)
    async_session.add(exploration)
    await async_session.commit()
    await exploration_service.finalize_return(async_session, exploration.id)

    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    await async_session.refresh(vault)
    assert dweller.status.value == "idle"
    assert partner.status.value == "idle"
    assert vault.bottle_caps > caps_before
    assert await crud.team_crud.get_exploration_team(async_session, exploration.id) is None


@pytest.mark.asyncio
async def test_party_run_rejects_site_entry(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A party dispatch run cannot enter an expedition site."""
    from app.services.exploration.expedition import expedition_service

    location, _state = await _register_clearable(async_session, vault, dweller)
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)

    with pytest.raises(ValidationException, match="Party dispatches"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_free_roam_creates_no_team(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """Free-roam sends keep the solo path with no team roster."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, 4)

    assert exploration.team_id is None
    await async_session.refresh(dweller)
    assert dweller.status.value == "exploring"
