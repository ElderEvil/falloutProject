import math
import random
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, update
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerLocationRelationEnum, DwellerStatusEnum, ExplorationStatus, NotificationType
from app.core.game_config import game_config
from app.crud.collectible import collectible_crud
from app.crud.exploration import exploration as exploration_crud
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.notification import Notification
from app.models.storage import Storage
from app.models.team import Team
from app.models.vault import Vault
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation
from app.schemas.dweller import DwellerCreate
from app.schemas.exploration_event import CombatOutcomeSchema
from app.services import catalog_service
from app.services.exploration.dispatch_resolution import resolve_dispatch_arrival
from app.services.exploration.party_resolution import distribute_damage, resolve_party_combat
from app.services.exploration_service import dispatch_travel_hours, exploration_service
from app.services.exploration_service import event_bus as exploration_event_bus
from app.services.game_tick.dwellers_tick import process_explorations
from app.services.map_service import map_service
from app.services.notification_service import NotificationService
from app.services.world_snapshot_service import world_snapshot_service
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.place_groups import get_place_group
from app.utils.place_loot import loot_table
from app.utils.time import utcnow

SPECIAL = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")
STRONG_STATS = {**dict.fromkeys(SPECIAL, 10), "level": 30, "health": 100, "max_health": 100, "radiation": 0}
WEAK_STATS = {**dict.fromkeys(SPECIAL, 1), "level": 1, "health": 100, "max_health": 100, "radiation": 0}


async def _commit(async_session: AsyncSession, *objects) -> None:
    async_session.add_all(list(objects))
    await async_session.commit()


async def _place_state(async_session: AsyncSession, vault: Vault, name: str) -> VaultLocationState:
    result = await async_session.execute(
        select(VaultLocationState)
        .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
        .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == name)
    )
    return result.scalar_one()


async def _link_visited(async_session: AsyncSession, dweller: Dweller, state: VaultLocationState) -> None:
    await crud.world_location.link_dweller(
        async_session, dweller.id, state.location_id, DwellerLocationRelationEnum.VISITED, is_unlocked=True
    )


async def _register_place(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, name: str = "Red Rocket"
) -> tuple[WorldLocation, VaultLocationState]:
    await map_service.register_bio_places(async_session, dweller, origin_place=name, visited_places=[])
    state = await _place_state(async_session, vault, name)
    return await crud.world_location.get_registry(async_session, state.location_id), state


async def _register_clearable(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, name: str = "Red Rocket"
) -> tuple[WorldLocation, VaultLocationState]:
    """Register a clearable map point for the vault, with a claimed origin slot."""
    from app.crud.vault_slot import vault_slot

    await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()
    location, state = await _register_place(async_session, vault, dweller, name)
    await _link_visited(async_session, dweller, state)
    return location, state


async def _boost(async_session: AsyncSession, dweller: Dweller, **overrides) -> Dweller:
    for key, value in overrides.items():
        setattr(dweller, key, value)
    await _commit(async_session, dweller)
    await async_session.refresh(dweller)
    return dweller


async def _make_dweller(async_session: AsyncSession, vault: Vault, dweller_data: dict, **overrides) -> Dweller:
    return await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**{**dweller_data, **overrides}, vault_id=vault.id)
    )


async def _settled(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    *,
    name: str = "Red Rocket",
    stats: dict | None = STRONG_STATS,
    clear_count: int | None = None,
) -> tuple[WorldLocation, VaultLocationState]:
    location, state = await _register_clearable(async_session, vault, dweller, name)
    if stats is not None:
        await _boost(async_session, dweller, **stats)
    if clear_count is not None:
        state.clear_count = clear_count
        await _commit(async_session, state)
    return location, state


async def _expired(
    async_session: AsyncSession, vault: Vault, dwellers: Dweller | list[Dweller], location_id
) -> Exploration:
    members = [dwellers] if isinstance(dwellers, Dweller) else dwellers
    exploration = await exploration_service.dispatch(
        async_session, vault.id, [dweller.id for dweller in members], location_id
    )
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    await _commit(async_session, exploration)
    return exploration


async def _reloaded(async_session: AsyncSession, dwellers: list[Dweller]) -> list[Dweller]:
    return [await crud.dweller.get_with_equipment(async_session, dweller.id) for dweller in dwellers]


async def _cleared_notifications(async_session: AsyncSession) -> list[Notification]:
    rows = await async_session.execute(
        select(Notification).where(Notification.notification_type == NotificationType.LOCATION_CLEARED)
    )
    return list(rows.scalars().all())


async def _arrived(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    *,
    party: tuple[Dweller, ...] = (),
    name: str = "Red Rocket",
    stats: dict | None = STRONG_STATS,
    clear_count: int | None = None,
) -> tuple[WorldLocation, VaultLocationState, Exploration]:
    """Settle a site, send the party out, and let the arrival resolution run."""
    location, state = await _settled(async_session, vault, dweller, name=name, stats=stats, clear_count=clear_count)
    members = [dweller, *party]
    exploration = await _expired(async_session, vault, members, location.id)
    await resolve_dispatch_arrival(async_session, exploration.id)
    for obj in (state, exploration, *members):
        await async_session.refresh(obj)
    return location, state, exploration


# dispatch_travel_hours: 1 + 0.1 * distance hours, ceil'd, capped at 24h


@pytest.mark.parametrize(
    ("distance", "hours"), [(0, 1), (1, 2), (9, 2), (10, 2), (11, 3), (230, 24), (231, 24), (1000, 24)]
)
def test_dispatch_travel_hours_floor_and_cap(distance: int, hours: int) -> None:
    assert dispatch_travel_hours(distance) == hours


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_creates_targeted_run_with_anchor_snapshot(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    location, state = await _settled(async_session, vault, dweller)
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    assert exploration.target_location_id == location.id
    assert exploration.clear_tier == 0
    origin = await exploration_service._vault_origin(async_session, vault.id)
    assert origin is not None
    expected_duration = dispatch_travel_hours(math.dist(origin, (location.coord_x, location.coord_y)))
    assert exploration.duration == expected_duration
    assert exploration.stimpaks == 0
    assert exploration.radaways == 0
    assert exploration.status == ExplorationStatus.ACTIVE
    await async_session.refresh(dweller)
    assert dweller.status.value == "exploring"
    assert dweller.room_id is None
    assert (exploration.dweller_strength, exploration.dweller_perception, exploration.dweller_endurance) == (10, 10, 10)
    assert (exploration.dweller_charisma, exploration.dweller_intelligence) == (10, 10)
    assert (exploration.dweller_agility, exploration.dweller_luck) == (10, 10)
    await resolve_dispatch_arrival(async_session, exploration.id, arrived=True)
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert state.cleared_at is not None
    assert exploration.location_xp == get_place_group(location.group_key)["xp_reward"]


async def test_dispatch_rejects_ineligible_target(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    with pytest.raises(ResourceNotFoundException):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], uuid4())
    _location, memorial = await _register_place(async_session, vault, dweller, "Jefferson Memorial")
    with pytest.raises(ValidationException, match="cannot be cleared"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], memorial.location_id)
    _rocket, state = await _register_place(async_session, vault, dweller)
    await _link_visited(async_session, dweller, state)
    with pytest.raises(ValidationException, match="no map placement"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], state.location_id)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_rejects_currently_cleared_point(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    location, state = await _settled(async_session, vault, dweller, stats=None)
    state.reclear_available_at = utcnow() + timedelta(hours=1)
    await _commit(async_session, state)
    with pytest.raises(ValidationException, match="currently cleared"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_rejects_busy_or_dead_dweller(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, _state = await _register_clearable(async_session, vault, dweller)
    await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    with pytest.raises(ValidationException, match="already on an exploration"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    dead = await _make_dweller(async_session, vault, dweller_data)
    dead.is_dead = True
    await _commit(async_session, dead)
    with pytest.raises(ValidationException, match="dweller is dead"):
        await exploration_service.dispatch(async_session, vault.id, [dead.id], location.id)


# arrival resolution


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_arrival_win_clears_state_loot_and_notifies(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    location, state = await _settled(async_session, vault, dweller)
    exploration = await _expired(async_session, vault, dweller, location.id)
    with patch.object(NotificationService, "_deliver", new_callable=AsyncMock) as deliver:
        await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.cleared_at is not None
    assert state.clear_count == 1
    assert state.reclear_available_at is not None
    group = get_place_group(location.group_key)
    expected_reclear = state.cleared_at + timedelta(hours=group["reclear_hours"])
    assert abs((state.reclear_available_at - expected_reclear).total_seconds()) < 1
    assert len(exploration.loot_collected) == len(loot_table(group["loot_table"])["items"])
    assert exploration.total_caps_found > 0
    assert exploration.location_xp == group["xp_reward"]
    notifications = await _cleared_notifications(async_session)
    assert len(notifications) == 1
    assert notifications[0].user_id == vault.user_id
    assert notifications[0].vault_id == vault.id
    assert "Red Rocket" in notifications[0].title
    assert notifications[0].meta_data == {"location_id": str(location.id), "location_name": "Red Rocket"}
    assert deliver.await_count == 1
    payload = deliver.await_args.args[1]
    assert payload["notification"]["notification_type"] == NotificationType.LOCATION_CLEARED

    # The run must explain itself in the report: arrival loot skips apply_loot_find's logging,
    # so without this the journey finished with zero events and the player read "0 events".
    assert len(exploration.events) == 1
    event = exploration.events[0]
    assert event["type"] == "dispatch"
    assert event["loot"]["outcome"] == "cleared"
    assert event["loot"]["caps"] == exploration.total_caps_found
    assert event["location_name"] == "Red Rocket"
    assert "Red Rocket" in event["description"]


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_zero_reward_clear_stores_zero_not_null(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    location, _state = await _settled(async_session, vault, dweller)
    zero_reward_group = {**get_place_group("gas_station"), "xp_reward": 0}
    monkeypatch.setattr(
        "app.services.exploration.dispatch_resolution.effective_place_group",
        lambda group_key, kind: zero_reward_group,
    )
    exploration = await _expired(async_session, vault, dweller, location.id)
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    assert exploration.location_xp == 0


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_rejects_a_table_that_cannot_roll(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    location, _state = await _register_clearable(async_session, vault, dweller)
    empty_table = {
        "caps": {"min": 1, "max": 2},
        "items": [{"type": "junk", "rarity": "common", "junk_types": ["steel"]}],
    }
    monkeypatch.setattr("app.services.exploration_service.loot_table", lambda key: empty_table)
    monkeypatch.setattr("app.services.catalog_service.load_junk_items", list)
    with pytest.raises(ValidationException, match="nothing to loot"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)


@pytest.mark.usefixtures("default_world_snapshot")
@pytest.mark.parametrize("legacy", [True, False])
async def test_complete_exploration_resolves_an_expired_dispatch(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, legacy: bool
) -> None:
    # A legacy timed dispatch (no heading) still resolves through the API completion path; a spatial
    # run settles the movement it logged before resolving.
    location, state = await _settled(async_session, vault, dweller)
    exploration = await _expired(async_session, vault, dweller, location.id)
    if legacy:
        exploration.heading_degrees = None
        await _commit(async_session, exploration)
    else:
        assert len(exploration.trail) == 1  # departure only: movement has not been settled yet
    completed, rewards = await exploration_service.complete_exploration_with_data(async_session, exploration.id)
    await async_session.refresh(completed)
    await async_session.refresh(state)
    assert completed.status == ExplorationStatus.RETURNING
    if legacy:
        assert rewards is None
    else:
        assert len(completed.trail) > 1
    assert state.cleared_at is not None
    assert completed.location_xp == get_place_group(location.group_key)["xp_reward"]


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_second_party_is_refused_by_precheck_then_by_index(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    # One party en route owns the site; the pre-check refuses first, the partial index backstops a race.
    location, _state = await _settled(async_session, vault, dweller)
    location_id, vault_id = location.id, vault.id
    other = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    await exploration_service.dispatch(async_session, vault.id, [dweller.id], location_id)
    emit = AsyncMock()
    monkeypatch.setattr(exploration_event_bus, "emit", emit)
    with pytest.raises(ValidationException, match="already on its way"):
        await exploration_service.dispatch(async_session, vault.id, [other.id], location_id)
    monkeypatch.setattr(exploration_crud, "has_active_dispatch_to", AsyncMock(return_value=False))
    with pytest.raises(ValidationException, match="already on its way"):
        await exploration_service.dispatch(async_session, vault.id, [other.id], location_id)
    runs = (
        await async_session.execute(
            select(func.count()).select_from(Exploration).where(Exploration.target_location_id == location_id)
        )
    ).scalar_one()
    teams = (
        await async_session.execute(select(func.count()).select_from(Team).where(Team.vault_id == vault_id))
    ).scalar_one()
    await async_session.refresh(other)
    assert runs == 1
    assert teams == 1
    assert other.status == DwellerStatusEnum.IDLE
    emit.assert_not_awaited()


@pytest.mark.usefixtures("default_world_snapshot")
async def test_active_roam_does_not_occupy_a_site_but_a_dispatch_does(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    # A roam has no target, so it must not block a dispatch; the pin then says why it is closed.
    location, _state = await _settled(async_session, vault, dweller)
    other = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    await exploration_service.depart(async_session, vault.id, [dweller.id], duration=4)
    exploration = await exploration_service.dispatch(async_session, vault.id, [other.id], location.id)
    assert exploration.target_location_id == location.id
    map_data = await map_service.get_vault_map(async_session, vault)
    pin = next(loc for loc in map_data.locations if loc.id == location.id)
    assert pin.is_unlocked is True
    assert pin.dispatch_in_progress is True
    assert pin.action == "none"


@pytest.mark.usefixtures("default_world_snapshot")
async def test_early_recall_pays_no_location_xp(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    location, state = await _settled(async_session, vault, dweller)
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    experience_before = (await crud.dweller.get(async_session, dweller.id)).experience
    await exploration_service.recall_exploration_with_data(async_session, exploration.id)
    recalled = await crud.exploration.get(async_session, exploration.id)
    recalled.return_completes_at = utcnow() - timedelta(seconds=1)
    await _commit(async_session, recalled)
    await exploration_service.complete_exploration_with_data(async_session, exploration.id)
    await async_session.refresh(state)
    assert state.cleared_at is None
    assert (await crud.dweller.get(async_session, dweller.id)).experience == experience_before


# salvage sites


@pytest.mark.usefixtures("default_world_snapshot")
@pytest.mark.parametrize(
    ("case", "message"),
    [("party", "exactly one dweller"), ("searched", "cannot be cleared"), ("locked", "not known to the vault")],
)
async def test_dispatch_rejects_an_unavailable_salvage_site(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    dweller_data: dict,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    message: str,
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, state = await _register_clearable(async_session, vault, dweller, "Museum of Freedom")
    ids = [dweller.id]
    if case == "party":
        ids.append((await _make_dweller(async_session, vault, dweller_data)).id)
    elif case == "searched":
        state.searched_at = utcnow()
        await _commit(async_session, state)
    else:
        await async_session.execute(
            update(DwellerLocation).where(DwellerLocation.location_id == location.id).values(is_unlocked=False)
        )
        await async_session.commit()
    with pytest.raises(ValidationException, match=message):
        await exploration_service.dispatch(async_session, vault.id, ids, location.id)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_salvage_awards_the_bobblehead_without_combat(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location, state = await _register_clearable(async_session, vault, dweller, "Museum of Freedom")
    health_before = dweller.health
    exploration = await _expired(async_session, vault, dweller, location.id)
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    await async_session.refresh(dweller)
    claim = await collectible_crud.get_by_vault_and_key(async_session, vault.id, "perception")
    assert claim is not None
    assert claim.finder_dweller_id == dweller.id
    assert dweller.collectible_bonus == {"perception": 1}
    assert state.searched_at is not None
    assert exploration.status == ExplorationStatus.RETURNING
    assert exploration.loot_collected == []
    assert exploration.total_caps_found >= 5
    assert exploration.location_xp is None
    assert dweller.health == health_before


# combat outcomes


@pytest.mark.usefixtures("default_world_snapshot")
@pytest.mark.parametrize(
    ("stats", "clear_count", "bonus"),
    [(STRONG_STATS, None, {"strength": 1}), (WEAK_STATS, 5, None)],
)
async def test_dispatch_arrival_bobblehead_follows_the_outcome(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    monkeypatch: pytest.MonkeyPatch,
    stats: dict,
    clear_count: int | None,
    bonus: dict | None,
) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)
    _location, _state, _exploration = await _arrived(
        async_session, vault, dweller, name="Poseidon Energy", stats=stats, clear_count=clear_count
    )
    claim = await collectible_crud.get_by_vault_and_key(async_session, vault.id, "strength")
    if bonus is None:
        assert claim is None
        return
    assert claim is not None
    assert claim.finder_dweller_id == dweller.id
    assert dweller.collectible_bonus == bonus


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_arrival_loss_no_clear_no_loot_no_notification(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    _location, state, exploration = await _arrived(async_session, vault, dweller, stats=WEAK_STATS, clear_count=5)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.cleared_at is None
    assert state.clear_count == 5
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert exploration.location_xp is None
    difficulty = min(5, 2 + game_config.exploration.dispatch.escalation_cap)
    members = await crud.team_crud.get_exploration_team_dwellers(async_session, exploration.id)
    _outcome, expected_damage = resolve_party_combat(members, difficulty)
    assert dweller.health == 100 - expected_damage
    assert await _cleared_notifications(async_session) == []

    # A repelled party still records the journey: the player is told what happened and where.
    assert len(exploration.events) == 1
    event = exploration.events[0]
    assert event["type"] == "dispatch"
    assert event["loot"]["outcome"] == "repelled"
    assert event["loot"]["caps"] == 0
    assert "Repelled at Red Rocket" in event["description"]
    assert event["health_loss"] == expected_damage


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_escalation_tier_and_caps(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, state = await _settled(async_session, vault, dweller, clear_count=0)
    exploration1 = await _expired(async_session, vault, dweller, location.id)
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
    await _commit(async_session, state)
    exploration2 = await _expired(async_session, vault, dweller2, location.id)
    assert exploration2.clear_tier == game_config.exploration.dispatch.escalation_cap
    random.seed(42)
    await resolve_dispatch_arrival(async_session, exploration2.id)
    await async_session.refresh(exploration2)
    assert exploration2.total_caps_found > caps1


# tick integration


@pytest.mark.usefixtures("default_world_snapshot")
async def test_tick_generates_no_events_then_resolves_dispatch_arrival(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    location, state = await _settled(async_session, vault, dweller)
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
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    await _commit(async_session, exploration)
    stats = await process_explorations(async_session, vault.id)
    assert stats["returning"] == 1
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.clear_count == 1


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_arrival_uses_departure_tier_snapshot(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, state = await _settled(async_session, vault, dweller)
    exploration = await _expired(async_session, vault, dweller, location.id)
    assert exploration.clear_tier == 0
    await async_session.refresh(state)
    state.clear_count = 5
    await _commit(async_session, state)
    random.seed(99)
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    snapshot_caps = exploration.total_caps_found
    dweller2 = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    await async_session.refresh(state)
    state.clear_count = 0
    state.cleared_at = None
    state.reclear_available_at = None
    await _commit(async_session, state)
    control = await _expired(async_session, vault, dweller2, location.id)
    random.seed(99)
    await resolve_dispatch_arrival(async_session, control.id)
    await async_session.refresh(control)
    assert snapshot_caps == control.total_caps_found


# party validation


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_rejects_malformed_party(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, _state = await _register_clearable(async_session, vault, dweller)
    extra = [await _make_dweller(async_session, vault, dweller_data) for _ in range(3)]
    ids = [dweller.id, *(member.id for member in extra)]
    assert len(ids) == game_config.exploration.dispatch.max_party_size + 1
    with pytest.raises(ValidationException, match="at least one"):
        await exploration_service.dispatch(async_session, vault.id, [], location.id)
    with pytest.raises(ValidationException, match="only once"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id, dweller.id], location.id)
    with pytest.raises(ValidationException, match="Party size"):
        await exploration_service.dispatch(async_session, vault.id, ids, location.id)


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_rejects_foreign_member(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
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
            number=999, bottle_caps=1000, happiness=50, power=10, food=10, water=10, population_max=50, user_id=user.id
        ),
    )
    foreign = await _make_dweller(async_session, vault2, dweller_data)
    location, _state = await _register_clearable(async_session, vault, dweller)
    with pytest.raises(ValidationException, match="does not belong"):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id, foreign.id], location.id)
    await async_session.refresh(dweller)
    assert dweller.status.value != "exploring"


# party departure and arrival


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_party_win_scales_haul(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, state = await _settled(async_session, vault, dweller)
    partners = [await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS) for _ in range(2)]
    exploration = await _expired(async_session, vault, [dweller, *partners], location.id)
    # The departing party is a team, and every member leaves their room.
    assert exploration.team_id is not None
    team = await crud.team_crud.get_exploration_team(async_session, exploration.id)
    assert team is not None
    assert team.exploration_id == exploration.id
    assert [member.slot_number for member in sorted(team.members, key=lambda m: m.slot_number or 0)] == [1, 2, 3]
    for member in [dweller, *partners]:
        await async_session.refresh(member)
        assert member.status.value == "exploring"
        assert member.room_id is None
    random.seed(7)
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.clear_count == 1
    assert len(exploration.loot_collected) == 3  # single haul roll, not per member
    assert exploration.total_caps_found > 0
    assert len(team.members) == 3


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_arrival_death_trims_haul(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, state = await _settled(async_session, vault, dweller, clear_count=2)  # tier 2: lethal
    fragile = await _make_dweller(async_session, vault, dweller_data, **{**WEAK_STATS, "health": 1})
    exploration = await _expired(async_session, vault, [dweller, fragile], location.id)
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
    group = get_place_group(location.group_key)
    assert exploration.location_xp == int(
        group["xp_reward"] * (1 + game_config.exploration.dispatch.reward_per_tier * 2)
    )
    junk_types = {item["name"]: str(item["junk_type"]).lower() for item in catalog_service.load_junk_items()}
    assert junk_types[exploration.loot_collected[0]["item_name"]] == "adhesive"  # the signature roll survives

    # The event must report the haul the run keeps, not the roll: the dead member's half is gone, and
    # a log that still promises it reads as a reward the player never receives.
    event = exploration.events[-1]
    assert event["loot"]["outcome"] == "cleared"
    assert event["loot"]["caps"] == exploration.total_caps_found == 170
    assert event["loot"]["items"] == [entry["item_name"] for entry in exploration.loot_collected]
    assert "casualties cost" in event["description"]
    assert "170 caps" in event["description"]


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_arrival_party_wipe_survives_finalize(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    partner = await _make_dweller(async_session, vault, dweller_data, **{**WEAK_STATS, "health": 1})
    _location, state, exploration = await _arrived(
        async_session, vault, dweller, party=(partner,), stats={**WEAK_STATS, "health": 1}, clear_count=5
    )
    assert exploration.status == ExplorationStatus.RETURNING
    assert state.cleared_at is None
    assert state.clear_count == 5
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert dweller.is_dead
    assert partner.is_dead
    exploration.return_started_at = utcnow() - timedelta(hours=10)
    exploration.return_completes_at = utcnow() - timedelta(hours=1)
    await _commit(async_session, exploration)
    await exploration_service.finalize_return(async_session, exploration.id)
    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    assert dweller.is_dead
    assert partner.is_dead
    assert dweller.status.value == "dead"
    assert partner.status.value == "dead"


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_arrival_winning_party_wiped_leaves_point_uncleared(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    # A party that wins the fight but dies to the lethal tier never clears the point. Aggregate power can clear the
    # victory threshold while every member still drops to 0 health, so ``victory`` alone is not evidence the place was
    # looted.
    location, state = await _settled(async_session, vault, dweller, stats={**STRONG_STATS, "health": 1}, clear_count=2)
    partner = await _make_dweller(async_session, vault, dweller_data, **{**STRONG_STATS, "health": 1})
    exploration = await _expired(async_session, vault, [dweller, partner], location.id)
    difficulty = min(5, 2 + 2)  # gas_station base_difficulty 2 + tier 2
    assert resolve_party_combat(await _reloaded(async_session, [dweller, partner]), difficulty)[0] is True
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert dweller.is_dead
    assert partner.is_dead
    assert state.cleared_at is None
    assert state.reclear_available_at is None
    assert state.clear_count == 2
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert exploration.location_xp is None
    assert await _cleared_notifications(async_session) == []


# party damage distribution


@pytest.mark.parametrize(
    ("total", "size", "shares"),
    [(1, 3, None), (2, 3, None), (5, 3, None), (0, 3, [0, 0, 0]), (7, 3, None), (10, 4, None), (3, 1, None)],
)
def test_distribute_damage_sums_to_total(total: int, size: int, shares: list[int] | None) -> None:
    result = distribute_damage(total, size)
    assert len(result) == size
    assert sum(result) == total
    assert all(share >= 0 for share in result)
    if shares is not None:
        assert result == shares


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_arrival_skips_point_cleared_by_competitor(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, state = await _settled(async_session, vault, dweller)
    partner = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    exploration = await _expired(async_session, vault, [dweller, partner], location.id)
    await async_session.refresh(state)
    state.cleared_at = utcnow()
    state.reclear_available_at = utcnow() + timedelta(hours=1)
    state.clear_count = 1
    await _commit(async_session, state)
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(state)
    assert exploration.status == ExplorationStatus.RETURNING
    assert exploration.loot_collected == []
    assert exploration.total_caps_found == 0
    assert state.clear_count == 1


# party return, rewards, and boundaries


@pytest.mark.usefixtures("default_world_snapshot")
async def test_finalize_restores_party_and_deletes_team(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, _state = await _settled(async_session, vault, dweller)
    partner = await _make_dweller(async_session, vault, dweller_data, **STRONG_STATS)
    exploration = await _expired(async_session, vault, [dweller, partner], location.id)
    await resolve_dispatch_arrival(async_session, exploration.id)
    await async_session.refresh(vault)
    caps_before = vault.bottle_caps
    exploration.return_started_at = utcnow() - timedelta(hours=10)
    exploration.return_completes_at = utcnow() - timedelta(hours=1)
    await _commit(async_session, exploration)
    await exploration_service.finalize_return(async_session, exploration.id)
    await async_session.refresh(dweller)
    await async_session.refresh(partner)
    await async_session.refresh(vault)
    assert dweller.status.value == "idle"
    assert partner.status.value == "idle"
    assert vault.bottle_caps > caps_before
    assert await crud.team_crud.get_exploration_team(async_session, exploration.id) is None


@pytest.mark.usefixtures("default_world_snapshot")
async def test_party_run_rejects_site_entry(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    from app.services.exploration.expedition import expedition_service

    location, _state = await _register_clearable(async_session, vault, dweller)
    exploration = await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id)
    with pytest.raises(ValidationException, match="Party dispatches"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


async def test_free_roam_creates_no_team(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, 4)
    assert exploration.team_id is None
    await async_session.refresh(dweller)
    assert dweller.status.value == "exploring"


# supplies


@pytest.mark.usefixtures("default_world_snapshot")
async def test_dispatch_carries_supplies_from_vault_storage_and_rejects_overspend(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    location, _state = await _register_clearable(async_session, vault, dweller)
    storage = Storage(vault_id=vault.id, max_space=100, stimpack=5, radaway=3)
    await _commit(async_session, storage)
    other = await _make_dweller(async_session, vault, dweller_data)
    with pytest.raises(ValidationException, match="available stimpaks"):
        await exploration_service.dispatch(async_session, vault.id, [other.id], location.id, stimpaks=6)
    exploration = await exploration_service.dispatch(
        async_session, vault.id, [dweller.id], location.id, stimpaks=2, radaways=1
    )
    assert exploration.stimpaks == 2
    assert exploration.radaways == 1
    await async_session.refresh(storage)
    assert storage.stimpack == 3
    assert storage.radaway == 2


@pytest.mark.usefixtures("default_world_snapshot")
@pytest.mark.parametrize(("stimpaks", "radaways"), [(-1, 0), (0, -1)])
async def test_dispatch_rejects_negative_supplies(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, stimpaks: int, radaways: int
) -> None:
    location, _state = await _register_clearable(async_session, vault, dweller)
    with pytest.raises(ValidationException, match="Supplies cannot be negative"):
        await exploration_service.dispatch(
            async_session, vault.id, [dweller.id], location.id, stimpaks=stimpaks, radaways=radaways
        )


async def test_depart_targeted_forwards_requested_supplies(async_session: AsyncSession) -> None:
    vault_id, dweller_id, location_id = uuid4(), uuid4(), uuid4()
    with patch.object(exploration_service, "dispatch", new_callable=AsyncMock) as mock_dispatch:
        await exploration_service.depart(
            async_session, vault_id, [dweller_id], target_location_id=location_id, stimpaks=3, radaways=2
        )
    mock_dispatch.assert_awaited_once()
    assert mock_dispatch.await_args.kwargs["stimpaks"] == 3
    assert mock_dispatch.await_args.kwargs["radaways"] == 2
    assert mock_dispatch.await_args.kwargs["location_id"] == location_id


async def test_dispatch_snapshot_commit_cannot_strand_supplies(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # A snapshot-generation commit must not persist supplies without the run.
    location, _state = await _register_clearable(async_session, vault, dweller)
    storage = Storage(vault_id=vault.id, max_space=100, stimpack=5, radaway=3)
    await _commit(async_session, storage)

    async def _commit_then_fail(db_session: AsyncSession, recipe=None):
        await db_session.commit()
        raise RuntimeError("snapshot generation failed")

    with (
        patch.object(world_snapshot_service, "get_or_generate", new=AsyncMock(side_effect=_commit_then_fail)),
        pytest.raises(RuntimeError),
    ):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id, stimpaks=2, radaways=1)
    await async_session.refresh(storage)
    assert storage.stimpack == 5
    assert storage.radaway == 3


async def test_dispatch_revalidates_supplies_after_snapshot_commit(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    # A spend committed in the snapshot-commit window must reject the dispatch.
    location, _state = await _register_clearable(async_session, vault, dweller)
    storage = Storage(vault_id=vault.id, max_space=100, stimpack=3, radaway=1)
    await _commit(async_session, storage)
    real_get_or_generate = world_snapshot_service.get_or_generate

    async def _spend_then_generate(db_session: AsyncSession, recipe=None):
        # A competing dispatch commits its deduction before this one stages; the raw
        # UPDATE bypasses the identity map, leaving the pre-commit read stale.
        await db_session.execute(
            update(Storage)
            .where(Storage.vault_id == vault.id)
            .values(stimpack=0, radaway=0)
            .execution_options(synchronize_session=False)
        )
        await db_session.commit()
        return await real_get_or_generate(db_session, recipe)

    with (
        patch.object(world_snapshot_service, "get_or_generate", new=AsyncMock(side_effect=_spend_then_generate)),
        pytest.raises(ValidationException, match="available stimpaks"),
    ):
        await exploration_service.dispatch(async_session, vault.id, [dweller.id], location.id, stimpaks=2, radaways=1)
    await async_session.refresh(storage)
    assert storage.stimpack == 0
    assert storage.radaway == 0
    runs = (await async_session.execute(select(Exploration).where(Exploration.vault_id == vault.id))).scalars().all()
    assert runs == []
