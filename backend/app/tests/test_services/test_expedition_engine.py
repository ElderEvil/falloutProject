"""Tests for the expedition site resolution engine (SQLite, seeded RNG)."""

import random
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExpeditionRun, ExpeditionRunStatus, ExplorationStatus
from app.schemas.dweller import DwellerCreate
from app.schemas.expedition import EnemySpec, ExpeditionResolveRequest, ItemRollSpec, NodeBranch, SiteNode
from app.schemas.exploration_event import JunkSchema
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services import catalog_service as data_loader
from app.services.catalog_service import resolve_enemy_spec, validate_site_content
from app.services.exploration import expedition as expedition_module
from app.services.exploration.checks import success_odds
from app.services.exploration.expedition import (
    expedition_service,
    roll_gear,
)
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ValidationException


async def test_site_combat_includes_pet_without_adding_a_fighter(async_session):
    _, dweller, exploration = await _make_exploration(async_session)
    await crud.pet.create(
        async_session,
        {
            "name": "CX404",
            "rarity": "common",
            "value": 100,
            "dweller_id": dweller.id,
        },
    )
    async_session.expire(dweller, ["pet"])
    entered = await expedition_service.enter_run(async_session, exploration.id, "collapsed_subway")
    fighters = entered.combat_state.fighters
    assert fighters[0].pet.name == "CX404"
    assert fighters[0].pet.image_url == "/static/pet_images/FOS CX404.png"
    assert len(fighters) == len(entered.node.enemy_names) + 1
    assert all(fighter.pet is None for fighter in fighters[1:])


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


async def _second_exploration(async_session: AsyncSession, vault):
    """A second active exploration in the same vault, for cross-journey cooldown checks."""
    dweller_data = create_fake_adult_dweller() | {"level": 10, "health": 100, "max_health": 100}
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)),
    )
    return await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)


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


def test_roll_gear_attempts_keep_luck_weighted_pick(monkeypatch):
    common = JunkSchema(name="Common scrap", rarity="Common", value=1)
    rare = JunkSchema(name="Rare scrap", rarity="Rare", value=50)
    rolled = iter((common, rare))
    floors: list[str | None] = []

    def pick(_luck: int, _item_type: str, min_rarity: str | None = None) -> JunkSchema:
        floors.append(min_rarity)
        return next(rolled)

    monkeypatch.setattr(expedition_module.loot_calculator, "roll_item", pick)
    assert roll_gear(5, "junk", "rare", attempts=2) == rare
    assert floors == [None, None]


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
async def test_enter_same_site_is_idempotent(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    first = await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    second = await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    assert second.site_id == "red_rocket"
    assert second.room_index == first.room_index
    assert second.status == "in_room"


@pytest.mark.asyncio
async def test_enter_different_site_conflicts(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    with pytest.raises(ResourceConflictException, match="already has an open expedition run"):
        await expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")


@pytest.mark.asyncio
async def test_enter_after_recent_clear_conflicts(async_session: AsyncSession):
    from datetime import datetime

    vault, dweller, exploration = await _make_exploration(async_session)
    prior = await _second_exploration(async_session, vault)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=prior.id,
        vault_id=vault.id,
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
    vault, _, prior = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, prior.id, "red_rocket")
    view = await expedition_service.retreat_run(async_session, prior.id)
    assert view.status == "retreated"
    fresh = await _second_exploration(async_session, vault)
    with pytest.raises(ResourceConflictException, match="quiet"):
        await expedition_service.enter_run(async_session, fresh.id, "red_rocket")


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
    prior = await _second_exploration(async_session, vault)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=prior.id,
        vault_id=vault.id,
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


def test_item_roll_rejects_ambiguous_or_ineffective_attempts():
    with pytest.raises(ValidationError):
        ItemRollSpec(type="junk", floor=None, rolls=2)
    with pytest.raises(ValidationError, match="rarity floor"):
        ItemRollSpec(type="junk", floor=None, attempts=2)


@pytest.mark.parametrize("kind", ["cache", "skill_check"])
def test_site_node_rejects_unshipped_standalone_kinds(kind: str):
    with pytest.raises(ValidationError):
        SiteNode(kind=kind, prompt="Unused node")


def test_site_node_rejects_removed_cache_field():
    with pytest.raises(ValidationError):
        SiteNode(kind="choice", prompt="Unused cache", cache_tier="rich")


def test_validate_site_content_rejects_unsatisfiable_floor(monkeypatch):
    site = data_loader.get_expedition_site("super_duper_mart")
    assert site is not None
    monkeypatch.setattr(
        data_loader,
        "load_weapons",
        lambda: [{"name": "Rusty Pipe", "rarity": "Common", "value": 10}],
    )
    with pytest.raises(ValidationException, match="no weapon at or above rarity"):
        validate_site_content(site)


def test_validate_site_content_checks_choice_branches(monkeypatch):
    site = data_loader.get_expedition_site("red_rocket").model_copy(deep=True)
    site.rooms[0].node.options[0].success = NodeBranch(cache_tier="rich", cache_item="weapon", cache_floor="legendary")
    monkeypatch.setattr(expedition_module.loot_calculator, "has_eligible", lambda *_: False)

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
async def test_resolve_after_exploration_completed_raises(async_session: AsyncSession):
    """Resolving a room on a finished exploration is rejected under the lock (Gap 1)."""
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    exploration.status = ExplorationStatus.COMPLETED
    async_session.add(exploration)
    await async_session.commit()
    with pytest.raises(ValidationException, match="Expedition sites need an active exploration"):
        await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())


@pytest.mark.asyncio
async def test_return_leg_allows_listing_and_retreating(async_session: AsyncSession):
    """A returning journey may still list and act on its open encounter (return-leg access)."""
    _, _, exploration = await _make_exploration(async_session)
    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_started_at = datetime.utcnow()
    exploration.return_completes_at = datetime.utcnow() + timedelta(minutes=1)
    async_session.add(exploration)
    await async_session.commit()

    available = await expedition_service.list_available_sites(async_session, exploration.id)
    assert isinstance(available, list)

    view = await expedition_service.retreat_run(async_session, exploration.id)
    assert view.status == "retreated"


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


@pytest.mark.asyncio
async def test_site_damage_triggers_auto_use_supplies(async_session: AsyncSession):
    """Resolving a damaging site room consumes carried stimpak/radaway via the shared auto-heal."""
    random.seed(42)
    _, dweller, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
    dweller.health = 30
    dweller.max_health = 100
    dweller.radiation = 40
    async_session.add(dweller)
    exploration.stimpaks = 1
    exploration.radaways = 1
    async_session.add(exploration)
    await async_session.commit()

    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    # "tank" always succeeds with endurance 10, dealing 1-3 damage.
    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="tank")
    )

    assert view.outcome is not None
    assert view.outcome.damage_taken > 0
    refreshed = await crud.exploration.get(async_session, exploration.id)
    assert refreshed.stimpaks == 0
    assert refreshed.radaways == 0
    dweller_refreshed = await crud.dweller.get(async_session, dweller.id)
    assert dweller_refreshed.radiation == 0  # 40 rad >= 25% of 100: one RadAway clears 50% of max health
    assert dweller_refreshed.health > 30
    assert view.dweller_health > 30  # build_view reflects the healed dweller


@pytest.mark.asyncio
async def test_site_event_logs_health_loss(async_session: AsyncSession):
    """The logged site event carries the room's damage as health_loss."""
    random.seed(42)
    _, dweller, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.commit()

    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="tank")
    )

    assert view.outcome is not None
    assert view.outcome.damage_taken > 0
    refreshed = await crud.exploration.get(async_session, exploration.id)
    site_events = [event for event in refreshed.events if event["type"] == "site"]
    assert site_events[-1]["health_loss"] == view.outcome.damage_taken


@pytest.mark.asyncio
async def test_site_event_logs_no_health_loss_when_undamaged(async_session: AsyncSession):
    """A room that deals no damage logs a site event with health_loss None."""
    random.seed(42)
    _, dweller, exploration = await _make_exploration(async_session, stats={"perception": 10})
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.commit()

    await expedition_service.enter_run(async_session, exploration.id, "red_rocket")
    # "disarm" always succeeds with perception 10: cache only, no damage.
    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id="disarm")
    )

    assert view.outcome is not None
    assert view.outcome.damage_taken == 0
    refreshed = await crud.exploration.get(async_session, exploration.id)
    site_events = [event for event in refreshed.events if event["type"] == "site"]
    assert "health_loss" not in site_events[-1]  # add_event omits None-valued fields


@pytest.mark.parametrize("site_id", ["abandoned_campsite", "roadside_supply_truck", "forgotten_shack"])
async def test_loot_only_sites_pay_once_without_combat_or_damage(async_session, site_id):
    _, dweller, exploration = await _make_exploration(async_session, level=1)
    site = data_loader.get_expedition_site(site_id)
    before_hp = dweller.health
    before_caps = exploration.total_caps_found
    entry = await expedition_service.enter_run(async_session, exploration.id, site_id)
    assert entry.node.kind == "finale"
    view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.status == "cleared"
    assert view.finale_paid
    assert view.outcome.damage_taken == 0
    assert not view.outcome.combat
    assert dweller.health == before_hp
    assert site.reward_vault.caps_min <= exploration.total_caps_found - before_caps <= site.reward_vault.caps_max
    assert view.outcome.loot_gained
    with pytest.raises((ResourceConflictException, ValidationException)):
        await expedition_service.enter_run(async_session, exploration.id, site_id)


@pytest.mark.parametrize(("site_id", "single"), [("red_rocket", False), ("collapsed_subway", True)])
async def test_legacy_journey_picker_matches_actual_entry_mode(async_session, site_id, single):
    _, dweller, exploration = await _make_exploration(async_session)
    dweller.level = 20
    async_session.add(dweller)
    await async_session.commit()
    available = await expedition_service.list_available_sites(async_session, exploration.id)
    offered = next(site for site in available if site.id == site_id)
    entered = await expedition_service.enter_run(async_session, exploration.id, site_id)
    assert entered.room_total == offered.room_total
    assert (entered.combat_state is not None) == single
    assert bool(offered.enemy_names) == single
    assert (offered.threat is not None) == single


async def _open_trivia_question(async_session: AsyncSession, exploration_id):
    """The question pinned on the open trivia run, plus the run row."""
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration_id)
    site = data_loader.get_expedition_site(run.site_id)
    question_id = next(iter(run.flags["trivia_questions"].values()))
    question = next(question for question in site.encounter.node.trivia_questions if question.id == question_id)
    return question, run


async def _open_trivia_raider(run):
    """The raider persona pinned alongside the question on the same run."""
    raider_id = next(iter(run.flags["trivia_raiders"].values()))
    return next(raider for raider in data_loader.load_trivia_raiders() if raider.id == raider_id)


@pytest.mark.asyncio
async def test_trivia_entry_persists_one_question_without_the_answer_key(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session, level=5)
    entry = await expedition_service.enter_run(async_session, exploration.id, "raider_tollbooth")
    assert entry.node.kind == "trivia"
    assert entry.node.question
    assert entry.combat_state is None
    assert entry.node.options
    assert all(
        option.stat is None and option.difficulty is None and option.success_odds is None
        for option in entry.node.options
    )

    question, run = await _open_trivia_question(async_session, exploration.id)
    raider = await _open_trivia_raider(run)
    assert question.correct_option_id in {option.id for option in entry.node.options}
    assert question.correct_option_id not in {option.label for option in entry.node.options}
    assert raider.intro in entry.node.prompt
    assert entry.node.enemy_names == [raider.name]
    assert entry.node.raider_image_url == raider.image_url
    assert entry.node.raider_alt_image_url == raider.alt_image_url

    again = await expedition_service.enter_run(async_session, exploration.id, "raider_tollbooth")
    run_again = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert again.node.question == entry.node.question
    assert again.node.prompt == entry.node.prompt
    assert run_again.flags["trivia_questions"] == run.flags["trivia_questions"]
    assert run_again.flags["trivia_raiders"] == run.flags["trivia_raiders"]


@pytest.mark.asyncio
async def test_trivia_correct_answer_pays_once(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session, level=5)
    await expedition_service.enter_run(async_session, exploration.id, "raider_tollbooth")
    question, run = await _open_trivia_question(async_session, exploration.id)
    raider = await _open_trivia_raider(run)
    before_caps = (await crud.exploration.get(async_session, exploration.id)).total_caps_found

    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id=question.correct_option_id)
    )
    assert view.status == "cleared"
    assert view.finale_paid is True
    assert view.outcome is not None
    assert raider.name in view.outcome.text
    assert view.outcome.caps_gained >= 40
    assert view.node.options == []

    after_caps = (await crud.exploration.get(async_session, exploration.id)).total_caps_found
    assert after_caps > before_caps
    with pytest.raises((ResourceConflictException, ValidationException)):
        await expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest(choice_id=question.correct_option_id)
        )
    assert (await crud.exploration.get(async_session, exploration.id)).total_caps_found == after_caps


@pytest.mark.asyncio
async def test_trivia_invalid_answer_leaves_the_encounter_untouched(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session, level=5)
    await expedition_service.enter_run(async_session, exploration.id, "raider_tollbooth")
    _, run = await _open_trivia_question(async_session, exploration.id)

    with pytest.raises(ValidationException, match="Unknown answer"):
        await expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest(choice_id="not-an-option")
        )

    run_after = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run_after.status == ExpeditionRunStatus.IN_ROOM
    assert "combat" not in run_after.flags
    assert run_after.flags["trivia_questions"] == run.flags["trivia_questions"]


@pytest.mark.asyncio
async def test_trivia_wrong_answer_starts_combat_then_pays_on_a_win(async_session: AsyncSession):
    stats = dict.fromkeys(("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"), 10)
    _, _, exploration = await _make_exploration(async_session, level=10, stats=stats)
    await expedition_service.enter_run(async_session, exploration.id, "raider_tollbooth")
    question, run = await _open_trivia_question(async_session, exploration.id)
    raider = await _open_trivia_raider(run)
    wrong_id = next(option.id for option in question.options if option.id != question.correct_option_id)

    view = await expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(choice_id=wrong_id)
    )
    assert view.status == "in_room"
    assert view.combat_state is not None
    assert view.combat_state.fighters[1].name == raider.name
    assert view.combat_state.fighters[1].image_url == raider.alt_image_url
    assert view.node.options == []
    assert view.outcome is not None
    assert raider.name in view.outcome.text
    assert "Wrong answer" in view.outcome.text
    run_after = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run_after.flags["combat"]
    assert run_after.flags["trivia_questions"] == run.flags["trivia_questions"]
    assert run_after.flags["trivia_raiders"] == run.flags["trivia_raiders"]

    current = await expedition_service.current_view(async_session, exploration.id)
    assert current is not None
    assert current.combat_state is not None
    assert current.node.options == []
    assert current.combat_state.round == view.combat_state.round

    with pytest.raises(ValidationException, match="do not accept"):
        await expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest(choice_id=wrong_id)
        )

    for _ in range(60):
        if view.status != "in_room":
            break
        view = await expedition_service.resolve_node(async_session, exploration.id, ExpeditionResolveRequest())
    assert view.status == "cleared"
    assert view.finale_paid is True
    assert view.outcome is not None
    assert view.outcome.caps_gained >= 40
