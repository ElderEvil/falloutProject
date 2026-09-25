"""Tests for the expedition site resolution engine (SQLite, seeded RNG)."""

import random

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExpeditionRun, ExpeditionRunStatus, ExplorationStatus
from app.schemas.dweller import DwellerCreate
from app.schemas.expedition import EnemySpec, ExpeditionResolveRequest
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.exploration import data_loader
from app.services.exploration import expedition as expedition_module
from app.services.exploration.expedition import (
    expedition_service,
    resolve_enemy_spec,
    roll_gear,
    success_odds,
    validate_site_content,
)
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ValidationException

# Weak stats: combat success chance 0.36, so seeded defeats/victories are easy to arrange.
WEAK_STATS = {
    "strength": 1,
    "agility": 1,
    "endurance": 10,
    "perception": 1,
    "charisma": 1,
    "intelligence": 1,
    "luck": 1,
}


async def _make_exploration(async_session: AsyncSession, level: int = 10, stats: dict | None = None):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller_data = create_fake_adult_dweller() | {"level": level, "health": 100, "max_health": 100}
    if stats:
        dweller_data |= stats
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)),
    )
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    return vault, dweller, exploration


async def _push_on_until(async_session: AsyncSession, exploration_id, room_index: int, max_attempts: int = 8):
    """Resolve (push-on through defeats) until the cursor reaches room_index."""
    view = await expedition_service.resolve_node(async_session, exploration_id, ExpeditionResolveRequest())
    for _ in range(max_attempts):
        if view.room_index >= room_index:
            return view
        view = await expedition_service.resolve_node(async_session, exploration_id, ExpeditionResolveRequest())
    return view


def test_success_odds_boundaries():
    assert success_odds(10, 1) == 0.95
    assert success_odds(1, 5) == pytest.approx(0.15)
    assert 0.05 < success_odds(5, 3) < 0.95


def test_resolve_enemy_spec_inline_boss():
    boss = resolve_enemy_spec(EnemySpec(name="Raider Boss", difficulty=4, min_damage=25, max_damage=45))
    assert boss.name == "Raider Boss"
    assert boss.min_damage == 25


def test_resolve_enemy_spec_table_lookup():
    enemy = resolve_enemy_spec(EnemySpec(name="Mole Rat pack"))
    assert enemy.difficulty == 2


def test_resolve_enemy_spec_unknown_raises():
    with pytest.raises(ValidationException, match="Unknown expedition enemy"):
        resolve_enemy_spec(EnemySpec(name="No Such Thing"))


def test_site_content_validates():
    for site in data_loader.load_expedition_sites():
        validate_site_content(site)


def test_roll_gear_respects_floor():
    random.seed(7)
    item = roll_gear(1, "weapon", "rare", attempts=5)
    assert item.rarity.lower() in ("rare", "legendary")


@pytest.mark.asyncio
async def test_enter_unknown_site_rejected(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    with pytest.raises(ValidationException, match="Unknown expedition site"):
        await expedition_service.enter_run(async_session, exploration.id, "no_such_site")


@pytest.mark.asyncio
async def test_enter_level_gate(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session, level=1)
    with pytest.raises(ValidationException, match="needs dweller level"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_enter_twice_conflicts(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    with pytest.raises(ResourceConflictException, match="already has an open expedition run"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_enter_after_recent_clear_conflicts(async_session: AsyncSession):
    from datetime import datetime

    vault, dweller, exploration = await _make_exploration(async_session)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
    )
    run.status = ExpeditionRunStatus.CLEARED
    run.finished_at = datetime.utcnow()
    async_session.add(run)
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="quiet"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_enter_after_retreat_blocked_by_cooldown(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    view = await expedition_service.retreat_run(async_session, exploration.id)
    assert view.status == "retreated"
    with pytest.raises(ResourceConflictException, match="quiet"):
        await expedition_service.enter_run(async_session, exploration.id, "red_rocket")


@pytest.mark.asyncio
async def test_second_exploration_same_site_blocked(async_session: AsyncSession):
    vault, dweller, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    dweller2_data = create_fake_adult_dweller() | {"level": 10, "health": 100, "max_health": 100}
    dweller2 = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller2_data, vault_id=str(vault.id)),
    )
    exploration2 = await exploration_service.send_dweller(async_session, vault.id, dweller2.id, duration=4)
    with pytest.raises(ResourceConflictException, match="red_rocket already has an open expedition run"):
        await expedition_service.enter_run(async_session, exploration2.id, "red_rocket")


@pytest.mark.asyncio
async def test_site_available_again_after_cooldown_window(async_session: AsyncSession):
    from datetime import datetime, timedelta

    vault, dweller, exploration = await _make_exploration(async_session)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
    )
    run.status = ExpeditionRunStatus.RETREATED
    run.finished_at = datetime.utcnow() - timedelta(days=8)
    async_session.add(run)
    await async_session.commit()

    sites = await expedition_service.list_available_sites(async_session, exploration.id)
    assert "red_rocket" in {site.id for site in sites}

    view = await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    assert view.site_id == "red_rocket"


def test_roll_gear_never_below_floor_for_any_item_type():
    for item_type in ("weapon", "outfit", "junk"):
        for _ in range(20):
            item = roll_gear(1, item_type, "rare", attempts=3)
            assert item.rarity.lower() in ("rare", "legendary")


def test_validate_site_content_rejects_unsatisfiable_floor(monkeypatch):
    monkeypatch.setattr(
        data_loader,
        "load_weapons",
        lambda: [{"name": "Rusty Pipe", "rarity": "Common", "value": 10}],
    )
    site = data_loader.get_expedition_site("super_duper_mart")
    assert site is not None
    with pytest.raises(ValidationException, match="no weapon at or above rarity"):
        validate_site_content(site)


@pytest.mark.asyncio
async def test_full_red_rocket_clear(async_session: AsyncSession):
    random.seed(42)
    _, _, exploration = await _make_exploration(async_session)
    view = await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    assert view.site_id == "red_rocket"
    assert view.room_total == 3
    assert view.node.kind == "trap"
    assert view.can_retreat is True

    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm")
    )
    assert view.room_index == 1
    assert view.node.kind == "combat"
    assert view.outcome is not None

    random.seed(570)
    view = await _push_on_until(async_session, exploration.id, room_index=2)
    assert view.room_index == 2
    assert view.node.kind == "finale"

    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.status == "cleared"
    assert view.finale_paid is True
    assert view.outcome is not None
    assert view.outcome.caps_gained > 0
    assert view.can_retreat is False

    refreshed = await crud.exploration.get(async_session, exploration.id)
    assert refreshed.total_caps_found > 0
    assert refreshed.loot_collected


@pytest.mark.asyncio
async def test_resolve_requires_choice_id(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    with pytest.raises(ValidationException, match="needs a choice"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    with pytest.raises(ValidationException, match="Unknown choice"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest(choice_id="nope"))


@pytest.mark.asyncio
async def test_retreat_keeps_run_closed(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    view = await expedition_service.retreat_run(async_session, exploration.id)
    assert view.status == "retreated"
    with pytest.raises(ValidationException, match="No open expedition run"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())


@pytest.mark.asyncio
async def test_combat_death_ends_run(async_session: AsyncSession):
    random.seed(1)
    _, dweller, exploration = await _make_exploration(async_session)
    await crud.dweller.update(async_session, dweller.id, {"health": 1}, commit=True)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="tank")
    )
    assert view.status == "died"
    assert view.outcome is not None
    assert "died" in view.outcome.text


@pytest.mark.asyncio
async def test_current_view_none_without_run(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    assert await expedition_service.current_view(async_session, exploration.id) is None


@pytest.mark.asyncio
async def test_mart_trade_without_caps_falls_back(async_session: AsyncSession):
    random.seed(3)
    _, _, exploration = await _make_exploration(async_session, level=10)
    await expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    view = await _push_on_until(async_session, exploration.id, room_index=1)
    assert view.room_index == 1
    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="call_out")
    )
    assert view.room_index == 2
    assert view.outcome is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [ExplorationStatus.COMPLETED, ExplorationStatus.RETURNING])
async def test_resolve_after_exploration_leaves_active_raises(async_session: AsyncSession, status: ExplorationStatus):
    """Resolving a room on a non-active exploration is rejected under the lock (Gap 1)."""
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    exploration.status = status
    async_session.add(exploration)
    await async_session.commit()
    with pytest.raises(ValidationException, match="Expedition sites need an active exploration"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())


@pytest.mark.asyncio
async def test_retreat_after_exploration_completed_raises(async_session: AsyncSession):
    """Retreating on a non-active exploration is rejected under the lock (Gap 1)."""
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    exploration.status = ExplorationStatus.COMPLETED
    async_session.add(exploration)
    await async_session.commit()
    with pytest.raises(ValidationException, match="Expedition sites need an active exploration"):
        await expedition_service.retreat_run(async_session, exploration.id)


@pytest.mark.asyncio
async def test_finale_payout_blocked_by_recent_terminal(async_session: AsyncSession):
    """A site in cooldown cannot pay its finale, even for an already-open run."""
    from datetime import datetime

    random.seed(42)
    vault, dweller, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm"))
    random.seed(570)
    await _push_on_until(async_session, exploration.id, room_index=2)

    terminal = ExpeditionRun(
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
        status=ExpeditionRunStatus.CLEARED,
        finished_at=datetime.utcnow(),
    )
    async_session.add(terminal)
    await async_session.commit()

    with pytest.raises(ValidationException, match="quiet"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())


@pytest.mark.asyncio
async def test_combat_defeat_stops_pack_and_does_not_advance(async_session: AsyncSession):
    """A lost fight (survivor) stops the pack, keeps the cursor, and signals defeated."""
    random.seed(0)
    _, _, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm"))
    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())

    assert view.room_index == 1
    assert view.status == "in_room"
    assert view.defeated is True
    assert view.outcome is not None
    assert "Overpowered by" in view.outcome.text
    assert "Raider gang" not in view.outcome.text

    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run is not None
    assert run.room_cursor == 1
    pending = run.flags["pending_fight"]
    assert pending["room_id"] == "garage"
    assert [enemy["name"] for enemy in pending["enemies"]] == ["Mole Rat pack", "Mole Rat pack", "Raider gang"]

    refreshed = await crud.exploration.get(async_session, exploration.id)
    assert refreshed.enemies_encountered == 0


@pytest.mark.asyncio
async def test_push_on_after_defeat_refights_same_pack_and_advances(async_session: AsyncSession):
    """Push-on replays the recorded pack; a full win clears the room and advances."""
    random.seed(0)
    _, _, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm"))
    defeated = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert defeated.defeated is True

    random.seed(32)
    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.room_index == 2
    assert view.status == "in_room"
    assert view.defeated is False
    assert view.outcome is not None
    assert "Defeated" in view.outcome.text

    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run is not None
    assert "pending_fight" not in run.flags
    assert run.flags["credited_rooms"] == ["garage"]


@pytest.mark.asyncio
async def test_choice_failure_combat_retry_replays_branch_not_choice(async_session: AsyncSession, monkeypatch):
    """A choice-failure combat defeat retries the branch's enemies, never the choice."""
    random.seed(77)
    _, _, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
    await expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    defeated = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="sneak")
    )
    assert defeated.defeated is True
    assert defeated.room_index == 1
    assert defeated.outcome is not None
    assert "Overpowered by Giant Radscorpion" in defeated.outcome.text

    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run is not None
    assert run.flags["pending_fight"]["room_id"] == "aisles"
    assert [enemy["name"] for enemy in run.flags["pending_fight"]["enemies"]] == ["Giant Radscorpion"]

    # Even if the original check would now succeed, the retry fights the branch's enemies.
    monkeypatch.setattr(expedition_module, "roll_check", lambda *args, **kwargs: True)
    random.seed(32)
    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.room_index == 2
    assert view.defeated is False
    assert view.outcome is not None
    assert "Giant Radscorpion" in view.outcome.text


@pytest.mark.asyncio
async def test_enemies_encountered_credited_once_across_defeat_and_push_on(async_session: AsyncSession):
    """XP for a room's pack is credited once on clear, not per attempted fight."""
    random.seed(0)
    _, _, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm"))
    defeated = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert defeated.defeated is True

    random.seed(32)
    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.room_index == 2

    refreshed = await crud.exploration.get(async_session, exploration.id)
    assert refreshed.enemies_encountered == 3


@pytest.mark.asyncio
async def test_combat_reports_per_enemy_entries_and_live_dweller_hp(async_session: AsyncSession):
    """A resolved combat room reports each engagement and the dweller's live HP."""
    random.seed(42)
    _, dweller, exploration = await _make_exploration(async_session)
    # The factory randomises radiation; zero it so effective max health is deterministic.
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.commit()

    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm"))

    random.seed(570)
    view = await _push_on_until(async_session, exploration.id, room_index=2)

    assert view.outcome is not None
    assert len(view.outcome.combat) == 3
    assert all(entry.enemy and isinstance(entry.victory, bool) for entry in view.outcome.combat)
    assert view.dweller_max_health == 100
    assert 0 < view.dweller_health < view.dweller_max_health
