"""Tests for the expedition site resolution engine (SQLite, seeded RNG)."""

import random
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExpeditionRunStatus, ExplorationStatus
from app.models.exploration import ExpeditionRun
from app.schemas.dweller import DwellerCreate
from app.schemas.expedition import EnemySpec, ExpeditionResolveRequest, ItemRollSpec, NodeBranch, SiteNode
from app.schemas.exploration_event import JunkSchema
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services import catalog_service as data_loader
from app.services.catalog_service import resolve_enemy_spec, validate_site_content
from app.services.exploration import expedition as expedition_module
from app.services.exploration.checks import success_odds
from app.services.exploration.expedition import expedition_service, roll_gear
from app.services.exploration.site_combat_service import initial_combat
from app.services.exploration.trivia import ordered_options, question_weight
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.time import utcnow

es = expedition_service
R = ExpeditionResolveRequest
STATS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")
# Weak stats: combat success chance 0.36, so seeded defeats/victories are easy to arrange.
WEAK_STATS = dict.fromkeys(STATS, 1) | {"endurance": 10}


async def _save(db, *objs):
    for obj in objs:
        db.add(obj)
    await db.commit()


def _all_stats(value: int = 10) -> dict:
    return dict.fromkeys(STATS, value)


async def _make_exploration(async_session: AsyncSession, level: int = 10, stats: dict | None = None):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    dweller_data = create_fake_adult_dweller() | {"level": level, "health": 100, "max_health": 100}
    if stats:
        dweller_data |= stats
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)))
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    return vault, dweller, exploration


async def _second_exploration(async_session: AsyncSession, vault):
    dweller_data = create_fake_adult_dweller() | {"level": 10, "health": 100, "max_health": 100}
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)))
    return await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)


async def _push_on_until(async_session: AsyncSession, exploration_id, room_index: int, max_attempts: int = 8):
    view = await es.resolve_node(async_session, exploration_id, R())
    for _ in range(max_attempts):
        if view.room_index >= room_index:
            return view
        view = await es.resolve_node(async_session, exploration_id, R())
    return view


async def _enter(async_session: AsyncSession, exploration, site_id: str):
    return await es.enter_run(async_session, exploration.id, site_id)


async def _resolve(async_session: AsyncSession, exploration_id, **kwargs):
    return await es.resolve_node(async_session, exploration_id, R(**kwargs))


async def _open_run(async_session: AsyncSession, exploration_id):
    return await crud.expedition_run.get_open_for_exploration(async_session, exploration_id)


async def _red_rocket_to_finale(async_session: AsyncSession, exploration):
    await _resolve(async_session, exploration.id, choice_id="disarm")
    random.seed(570)
    return await _push_on_until(async_session, exploration.id, room_index=2)


async def _open_trivia_question(async_session: AsyncSession, exploration_id):
    run = await _open_run(async_session, exploration_id)
    site = data_loader.get_expedition_site(run.site_id)
    pinned = next(iter(run.flags["trivia_questions"].values()))
    ids = [pinned] if isinstance(pinned, str) else pinned
    answered = next(iter(run.flags.get("trivia_answered", {}).values()), 0)
    question = next(question for question in site.encounter.node.trivia_questions if question.id == ids[answered])
    return question, run


async def _open_trivia_raider(run):
    raider_id = next(iter(run.flags["trivia_raiders"].values()))
    return next(raider for raider in data_loader.load_trivia_raiders() if raider.id == raider_id)


class TestExpeditionEngine:
    pytestmark = pytest.mark.asyncio

    async def test_site_combat_includes_pet_without_adding_a_fighter(self, async_session):
        _, dweller, exploration = await _make_exploration(async_session)
        await crud.pet.create(
            async_session, {"name": "CX404", "rarity": "common", "value": 100, "dweller_id": dweller.id}
        )
        async_session.expire(dweller, ["pet"])
        entered = await _enter(async_session, exploration, "collapsed_subway")
        fighters = entered.combat_state.fighters
        assert (fighters[0].pet.name, fighters[0].pet.image_url) == ("CX404", "/static/pet_images/FOS CX404.png")
        assert len(fighters) == len(entered.node.enemy_names) + 1
        assert all(fighter.pet is None for fighter in fighters[1:])

    @pytest.mark.parametrize(
        ("level", "site_id", "error"),
        [(10, "no_such_site", "Unknown expedition site"), (1, "red_rocket", "needs dweller level")],
    )
    async def test_enter_rejects_unknown_site_or_gated_level(self, async_session, level, site_id, error):
        _, _, exploration = await _make_exploration(async_session, level=level)
        with pytest.raises(ValidationException, match=error):
            await _enter(async_session, exploration, site_id)

    async def test_enter_run_is_idempotent_and_conflicts(self, async_session):
        vault, _dweller, exploration = await _make_exploration(async_session)
        first = await _enter(async_session, exploration, "red_rocket")
        second = await _enter(async_session, exploration, "red_rocket")
        assert (second.site_id, second.room_index, second.status) == ("red_rocket", first.room_index, "in_room")
        with pytest.raises(ResourceConflictException, match="already has an open expedition run"):
            await _enter(async_session, exploration, "super_duper_mart")
        exploration2 = await _second_exploration(async_session, vault)
        with pytest.raises(ResourceConflictException, match="red_rocket already has an open expedition run"):
            await _enter(async_session, exploration2, "red_rocket")

    @pytest.mark.parametrize(
        ("status", "age", "blocked"),
        [(ExpeditionRunStatus.CLEARED, timedelta(0), True), (ExpeditionRunStatus.RETREATED, timedelta(days=8), False)],
    )
    async def test_site_cooldown_gates_entry(self, async_session, status, age, blocked):
        vault, _dweller, exploration = await _make_exploration(async_session)
        prior = await _second_exploration(async_session, vault)
        run = await crud.expedition_run.create_run(
            async_session, exploration_id=prior.id, vault_id=vault.id, site_id="red_rocket"
        )
        run.status, run.finished_at = status, utcnow() - age
        await _save(async_session, run)
        if blocked:
            with pytest.raises(ResourceConflictException, match="quiet"):
                await _enter(async_session, exploration, "red_rocket")
            return
        assert "red_rocket" in {site.id for site in await es.list_available_sites(async_session, exploration.id)}
        assert (await _enter(async_session, exploration, "red_rocket")).site_id == "red_rocket"

    async def test_enter_after_retreat_blocked_by_cooldown(self, async_session):
        vault, _dweller, prior = await _make_exploration(async_session)
        await _enter(async_session, prior, "red_rocket")
        assert (await es.retreat_run(async_session, prior.id)).status == "retreated"
        fresh = await _second_exploration(async_session, vault)
        with pytest.raises(ResourceConflictException, match="quiet"):
            await _enter(async_session, fresh, "red_rocket")

    async def test_full_red_rocket_clear(self, async_session):
        random.seed(42)
        _, _, exploration = await _make_exploration(async_session)
        view = await _enter(async_session, exploration, "red_rocket")
        assert (view.site_id, view.room_total, view.node.kind, view.can_retreat) == ("red_rocket", 3, "trap", True)
        view = await _resolve(async_session, exploration.id, choice_id="disarm")
        assert (view.room_index, view.node.kind, view.outcome is not None) == (1, "combat", True)
        view = await _red_rocket_to_finale(async_session, exploration)
        assert (view.room_index, view.node.kind) == (2, "finale")
        view = await _resolve(async_session, exploration.id)
        assert (view.status, view.finale_paid, view.outcome is not None, view.can_retreat) == (
            "cleared",
            True,
            True,
            False,
        )
        assert view.outcome.caps_gained > 0
        refreshed = await crud.exploration.get(async_session, exploration.id)
        assert (refreshed.total_caps_found > 0, bool(refreshed.loot_collected)) == (True, True)

    async def test_resolve_and_retreat_require_an_open_run(self, async_session):
        _, _, exploration = await _make_exploration(async_session)
        assert await es.current_view(async_session, exploration.id) is None
        await _enter(async_session, exploration, "red_rocket")
        with pytest.raises(ValidationException, match="needs a choice"):
            await _resolve(async_session, exploration.id)
        with pytest.raises(ValidationException, match="Unknown choice"):
            await _resolve(async_session, exploration.id, choice_id="nope")
        assert (await es.retreat_run(async_session, exploration.id)).status == "retreated"
        with pytest.raises(ValidationException, match="No open expedition run"):
            await _resolve(async_session, exploration.id)

    async def test_combat_death_ends_run(self, async_session):
        random.seed(1)
        _, dweller, exploration = await _make_exploration(async_session)
        await crud.dweller.update(async_session, dweller.id, {"health": 1}, commit=True)
        await _enter(async_session, exploration, "red_rocket")
        view = await _resolve(async_session, exploration.id, choice_id="tank")
        assert (view.status, view.outcome is not None, "died" in view.outcome.text) == ("died", True, True)

    async def test_mart_trade_without_caps_falls_back(self, async_session):
        random.seed(3)
        _, _, exploration = await _make_exploration(async_session, level=10)
        await _enter(async_session, exploration, "super_duper_mart")
        assert (await _push_on_until(async_session, exploration.id, room_index=1)).room_index == 1
        view = await _resolve(async_session, exploration.id, choice_id="call_out")
        assert (view.room_index, view.outcome is not None) == (2, True)

    @pytest.mark.parametrize("action", ["resolve_node", "retreat_run"])
    async def test_completed_exploration_rejects_site_actions(self, async_session, action):
        _, _, exploration = await _make_exploration(async_session)
        await _enter(async_session, exploration, "red_rocket")
        exploration.status = ExplorationStatus.COMPLETED
        await _save(async_session, exploration)

        async def attempt():
            if action == "resolve_node":
                await _resolve(async_session, exploration.id)
            else:
                await es.retreat_run(async_session, exploration.id)

        with pytest.raises(ValidationException, match="Expedition sites need an active exploration"):
            await attempt()

    async def test_return_leg_allows_listing_and_retreating(self, async_session):
        _, _, exploration = await _make_exploration(async_session)
        await _enter(async_session, exploration, "red_rocket")
        exploration.status, exploration.return_started_at = ExplorationStatus.RETURNING, utcnow()
        exploration.return_completes_at = utcnow() + timedelta(minutes=1)
        await _save(async_session, exploration)
        assert isinstance(await es.list_available_sites(async_session, exploration.id), list)
        assert (await es.retreat_run(async_session, exploration.id)).status == "retreated"

    async def test_finale_payout_blocked_by_recent_terminal(self, async_session):
        random.seed(42)
        vault, _dweller, exploration = await _make_exploration(async_session)
        await _enter(async_session, exploration, "red_rocket")
        await _red_rocket_to_finale(async_session, exploration)
        terminal = ExpeditionRun(
            exploration_id=exploration.id,
            vault_id=vault.id,
            site_id="red_rocket",
            status=ExpeditionRunStatus.CLEARED,
            finished_at=utcnow(),
        )
        await _save(async_session, terminal)
        with pytest.raises(ValidationException, match="quiet"):
            await _resolve(async_session, exploration.id)

    async def test_defeat_then_push_on_refights_and_credits_enemies_once(self, async_session):
        random.seed(0)
        _, _, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
        await _enter(async_session, exploration, "red_rocket")
        await _resolve(async_session, exploration.id, choice_id="disarm")
        view = await _resolve(async_session, exploration.id)
        assert (view.room_index, view.status, view.defeated, view.outcome is not None) == (1, "in_room", True, True)
        assert "Overpowered by" in view.outcome.text
        assert "Raider gang" not in view.outcome.text
        run = await _open_run(async_session, exploration.id)
        assert (run is not None, run.room_cursor) == (True, 1)
        pending = run.flags["pending_fight"]
        assert (pending["room_id"], [enemy["name"] for enemy in pending["enemies"]]) == (
            "garage",
            ["Mole Rat pack", "Mole Rat pack", "Raider gang"],
        )
        assert (await crud.exploration.get(async_session, exploration.id)).enemies_encountered == 0
        random.seed(32)
        view = await _resolve(async_session, exploration.id)
        assert (view.room_index, view.status, view.defeated, view.outcome is not None) == (2, "in_room", False, True)
        assert "Defeated" in view.outcome.text
        run = await _open_run(async_session, exploration.id)
        assert ("pending_fight" not in run.flags, run.flags["credited_rooms"]) == (True, ["garage"])
        assert (await crud.exploration.get(async_session, exploration.id)).enemies_encountered == 3

    async def test_choice_failure_combat_retry_replays_branch_not_choice(self, async_session, monkeypatch):
        random.seed(77)
        _, _, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
        await _enter(async_session, exploration, "super_duper_mart")
        await _resolve(async_session, exploration.id)
        defeated = await _resolve(async_session, exploration.id, choice_id="sneak")
        assert (defeated.defeated, defeated.room_index, defeated.outcome is not None) == (True, 1, True)
        assert "Overpowered by Giant Radscorpion" in defeated.outcome.text
        run = await _open_run(async_session, exploration.id)
        pending = run.flags["pending_fight"]
        assert (pending["room_id"], [enemy["name"] for enemy in pending["enemies"]]) == (
            "aisles",
            ["Giant Radscorpion"],
        )
        # Even if the original check would now succeed, the retry fights the branch's enemies.
        monkeypatch.setattr(expedition_module, "roll_check", lambda *args, **kwargs: True)
        random.seed(32)
        view = await _resolve(async_session, exploration.id)
        assert (view.room_index, view.defeated, view.outcome is not None) == (2, False, True)
        assert "Giant Radscorpion" in view.outcome.text

    async def test_combat_reports_per_enemy_entries_and_live_dweller_hp(self, async_session):
        random.seed(42)
        _, dweller, exploration = await _make_exploration(async_session)
        # The factory randomises radiation; zero it so effective max health is deterministic.
        dweller.radiation = 0
        await _save(async_session, dweller)
        await _enter(async_session, exploration, "red_rocket")
        view = await _red_rocket_to_finale(async_session, exploration)
        assert (view.outcome is not None, len(view.outcome.combat), view.dweller_max_health) == (True, 3, 100)
        assert all(entry.enemy and isinstance(entry.victory, bool) for entry in view.outcome.combat)
        assert 0 < view.dweller_health < view.dweller_max_health

    async def test_site_damage_triggers_auto_use_supplies(self, async_session):
        random.seed(42)
        _, dweller, exploration = await _make_exploration(async_session, stats=WEAK_STATS)
        dweller.health, dweller.max_health, dweller.radiation = 30, 100, 40
        async_session.add(dweller)
        exploration.stimpaks, exploration.radaways = 1, 1
        await _save(async_session, exploration)
        await _enter(async_session, exploration, "red_rocket")
        # "tank" always succeeds with endurance 10, dealing 1-3 damage.
        view = await _resolve(async_session, exploration.id, choice_id="tank")
        assert (view.outcome is not None, view.outcome.damage_taken > 0) == (True, True)
        refreshed = await crud.exploration.get(async_session, exploration.id)
        assert (refreshed.stimpaks, refreshed.radaways) == (0, 0)
        dweller_refreshed = await crud.dweller.get(async_session, dweller.id)
        assert dweller_refreshed.radiation == 0  # 40 rad >= 25% of 100: one RadAway clears 50% of max health
        assert (dweller_refreshed.health > 30, view.dweller_health > 30) == (True, True)

    @pytest.mark.parametrize(
        ("stats", "choice", "expect_loss"), [(WEAK_STATS, "tank", True), ({"perception": 10}, "disarm", False)]
    )
    async def test_site_event_logs_health_loss(self, async_session, stats, choice, expect_loss):
        random.seed(42)
        _, dweller, exploration = await _make_exploration(async_session, stats=stats)
        dweller.radiation = 0
        await _save(async_session, dweller)
        await _enter(async_session, exploration, "red_rocket")
        view = await _resolve(async_session, exploration.id, choice_id=choice)
        assert view.outcome is not None
        refreshed = await crud.exploration.get(async_session, exploration.id)
        site_events = [event for event in refreshed.events if event["type"] == "site"]
        if expect_loss:
            # "tank" always succeeds with endurance 10, dealing 1-3 damage.
            assert (view.outcome.damage_taken > 0, site_events[-1]["health_loss"]) == (True, view.outcome.damage_taken)
        else:
            # "disarm" always succeeds with perception 10: cache only, no damage.
            assert (view.outcome.damage_taken, "health_loss" in site_events[-1]) == (0, False)

    @pytest.mark.parametrize("site_id", ["abandoned_campsite", "roadside_supply_truck", "forgotten_shack"])
    async def test_loot_only_sites_pay_once_without_combat_or_damage(self, async_session, site_id):
        _, dweller, exploration = await _make_exploration(async_session, level=1)
        site = data_loader.get_expedition_site(site_id)
        before_hp, before_caps = dweller.health, exploration.total_caps_found
        entry = await _enter(async_session, exploration, site_id)
        assert entry.node.kind == "finale"
        view = await _resolve(async_session, exploration.id)
        assert (view.status, view.finale_paid, view.outcome.damage_taken, bool(view.outcome.combat)) == (
            "cleared",
            True,
            0,
            False,
        )
        assert (dweller.health, bool(view.outcome.loot_gained)) == (before_hp, True)
        assert site.reward_vault.caps_min <= exploration.total_caps_found - before_caps <= site.reward_vault.caps_max
        with pytest.raises((ResourceConflictException, ValidationException)):
            await _enter(async_session, exploration, site_id)

    @pytest.mark.parametrize(("site_id", "single"), [("red_rocket", False), ("collapsed_subway", True)])
    async def test_legacy_journey_picker_matches_actual_entry_mode(self, async_session, site_id, single):
        _, dweller, exploration = await _make_exploration(async_session)
        dweller.level = 20
        await _save(async_session, dweller)
        offered = next(
            site for site in await es.list_available_sites(async_session, exploration.id) if site.id == site_id
        )
        entered = await _enter(async_session, exploration, site_id)
        assert entered.room_total == offered.room_total
        assert (entered.combat_state is not None, bool(offered.enemy_names), offered.threat is not None) == (
            single,
            single,
            single,
        )

    async def test_trivia_entry_persists_one_question_without_the_answer_key(self, async_session):
        _, _, exploration = await _make_exploration(async_session, level=5)
        entry = await _enter(async_session, exploration, "raider_tollbooth")
        assert (entry.node.kind, bool(entry.node.question), entry.combat_state, bool(entry.node.options)) == (
            "trivia",
            True,
            None,
            True,
        )
        assert all(
            option.stat is None and option.difficulty is None and option.success_odds is None
            for option in entry.node.options
        )
        question, run = await _open_trivia_question(async_session, exploration.id)
        raider = await _open_trivia_raider(run)
        assert question.correct_option_id in {option.id for option in entry.node.options}
        assert question.correct_option_id not in {option.label for option in entry.node.options}
        assert (raider.intro in entry.node.prompt, entry.node.enemy_names, entry.node.raider_image_url) == (
            True,
            [raider.name],
            raider.image_url,
        )
        assert entry.node.raider_alt_image_url == raider.alt_image_url
        again = await _enter(async_session, exploration, "raider_tollbooth")
        run_again = await _open_run(async_session, exploration.id)
        assert (again.node.question, again.node.prompt) == (entry.node.question, entry.node.prompt)
        assert run_again.flags["trivia_questions"] == run.flags["trivia_questions"]
        assert run_again.flags["trivia_raiders"] == run.flags["trivia_raiders"]

    async def test_trivia_correct_answer_pays_once(self, async_session):
        _, _, exploration = await _make_exploration(async_session, level=5)
        entry = await _enter(async_session, exploration, "raider_tollbooth")
        before_caps = (await crud.exploration.get(async_session, exploration.id)).total_caps_found
        view = None
        for _ in range(entry.node.question_total or 1):
            question, run = await _open_trivia_question(async_session, exploration.id)
            raider = await _open_trivia_raider(run)
            view = await _resolve(
                async_session, exploration.id, choice_id=question.correct_option_id, question_id=question.id
            )
            if view.status != "in_room":
                break
        assert view is not None
        assert (view.status, view.finale_paid, view.outcome is not None, view.node.options) == (
            "cleared",
            True,
            True,
            [],
        )
        assert raider.name in view.outcome.text
        assert view.outcome.caps_gained >= 40
        after_caps = (await crud.exploration.get(async_session, exploration.id)).total_caps_found
        assert after_caps > before_caps
        with pytest.raises((ResourceConflictException, ValidationException)):
            await _resolve(async_session, exploration.id, choice_id=question.correct_option_id, question_id=question.id)
        assert (await crud.exploration.get(async_session, exploration.id)).total_caps_found == after_caps

    async def test_trivia_invalid_answer_leaves_the_encounter_untouched(self, async_session):
        _, _, exploration = await _make_exploration(async_session, level=5)
        await _enter(async_session, exploration, "raider_tollbooth")
        question, run = await _open_trivia_question(async_session, exploration.id)
        with pytest.raises(ValidationException, match="Unknown answer"):
            await _resolve(async_session, exploration.id, choice_id="not-an-option", question_id=question.id)
        run_after = await _open_run(async_session, exploration.id)
        assert (run_after.status, "combat" in run_after.flags) == (ExpeditionRunStatus.IN_ROOM, False)
        assert run_after.flags["trivia_questions"] == run.flags["trivia_questions"]

    async def test_trivia_wrong_answer_starts_combat_then_pays_on_a_win(self, async_session):
        _, _, exploration = await _make_exploration(async_session, level=10, stats=_all_stats())
        await _enter(async_session, exploration, "raider_tollbooth")
        question, run = await _open_trivia_question(async_session, exploration.id)
        raider = await _open_trivia_raider(run)
        wrong_id = next(option.id for option in question.options if option.id != question.correct_option_id)
        view = await _resolve(async_session, exploration.id, choice_id=wrong_id, question_id=question.id)
        assert (view.status, view.combat_state is not None, view.node.options) == ("in_room", True, [])
        assert (view.combat_state.fighters[1].name, view.combat_state.fighters[1].image_url) == (
            raider.name,
            raider.alt_image_url,
        )
        assert view.outcome is not None
        assert (raider.name in view.outcome.text, "Wrong answer" in view.outcome.text) == (True, True)
        run_after = await _open_run(async_session, exploration.id)
        assert run_after.flags["combat"]
        assert (run_after.flags["trivia_questions"], run_after.flags["trivia_raiders"]) == (
            run.flags["trivia_questions"],
            run.flags["trivia_raiders"],
        )
        current = await es.current_view(async_session, exploration.id)
        assert (current is not None, current.combat_state is not None, current.node.options) == (True, True, [])
        assert current.combat_state.round == view.combat_state.round
        with pytest.raises(ValidationException, match="do not accept"):
            await _resolve(async_session, exploration.id, choice_id=wrong_id)
        for _ in range(60):
            if view.status != "in_room":
                break
            view = await _resolve(async_session, exploration.id)
        assert (view.status, view.finale_paid, view.outcome is not None) == ("cleared", True, True)
        assert view.outcome.caps_gained >= 40

    async def test_scene_combat_damage_is_not_floored_to_one(self, async_session):
        _, _, exploration = await _make_exploration(async_session, level=10, stats=_all_stats(8))
        view = await _enter(async_session, exploration, "gloomwater_bog")
        assert view.combat_state is not None
        damages: list[int] = []
        turns = 0
        for _ in range(30):
            if view.status != "in_room":
                break
            view = await _resolve(async_session, exploration.id)
            turns += 1
            damages.extend(
                int(event.message.rsplit(" for ", 1)[1])
                for event in view.combat_state.events
                if " for " in event.message
            )
        assert damages
        assert max(damages) > 1, f"site combat still floors damage to 1: {damages}"
        assert turns <= 8, f"scaled site fight took {turns} turns"

    async def test_trivia_encounter_can_ask_multiple_questions(self, async_session):
        _, _, exploration = await _make_exploration(async_session, level=10)
        entry = await _enter(async_session, exploration, "raider_tollbooth")
        assert (entry.node.kind, entry.node.question_total is not None, entry.node.question_index) == (
            "trivia",
            True,
            1,
        )
        assert entry.node.question_total >= 2
        first_question, _run = await _open_trivia_question(async_session, exploration.id)
        view = await _resolve(
            async_session, exploration.id, choice_id=first_question.correct_option_id, question_id=first_question.id
        )
        assert (view.status, view.finale_paid) == ("in_room", False)
        assert view.node.question
        assert view.node.question != entry.node.question
        assert (view.node.question_index, bool(view.node.options)) == (2, True)
        second_question, _ = await _open_trivia_question(async_session, exploration.id)
        assert second_question.id != first_question.id
        cleared = await _resolve(
            async_session, exploration.id, choice_id=second_question.correct_option_id, question_id=second_question.id
        )
        if entry.node.question_total == 2:
            assert (cleared.status, cleared.finale_paid) == ("cleared", True)

    async def test_trivia_rejects_a_stale_question(self, async_session):
        _, _, exploration = await _make_exploration(async_session, level=10)
        await _enter(async_session, exploration, "rusted_midway")
        run = await _open_run(async_session, exploration.id)
        room_id = next(iter(run.flags["trivia_questions"]))
        run.flags = {**run.flags, "trivia_questions": {room_id: ["grognak", "silver_shroud"]}, "trivia_answered": {}}
        await _save(async_session, run)
        advanced = await _resolve(async_session, exploration.id, choice_id="grognak", question_id="grognak")
        assert (advanced.status, advanced.node.question_index) == ("in_room", 2)
        with pytest.raises(ResourceConflictException):
            await _resolve(async_session, exploration.id, choice_id="grognak", question_id="grognak")
        run_after = await _open_run(async_session, exploration.id)
        assert (run_after.status, "combat" in run_after.flags) == (ExpeditionRunStatus.IN_ROOM, False)
        assert run_after.flags["trivia_answered"][room_id] == 1


def test_success_odds_boundaries():
    assert success_odds(10, 1) == 0.95
    assert success_odds(1, 5) == pytest.approx(0.15)
    assert 0.05 < success_odds(5, 3) < 0.95


def test_resolve_enemy_spec_variants():
    boss = resolve_enemy_spec(EnemySpec(name="Raider Boss", difficulty=4, min_damage=25, max_damage=45))
    assert (boss.name, boss.min_damage, resolve_enemy_spec(EnemySpec(name="Mole Rat pack")).difficulty) == (
        "Raider Boss",
        25,
        2,
    )
    with pytest.raises(ValidationException, match="Unknown expedition enemy"):
        resolve_enemy_spec(EnemySpec(name="No Such Thing"))


def test_site_content_validates():
    for site in data_loader.load_expedition_sites():
        validate_site_content(site)


def test_roll_gear_respects_floor():
    random.seed(7)
    assert roll_gear(1, "weapon", "rare", attempts=5).rarity.lower() in ("rare", "legendary")
    for item_type in ("weapon", "outfit", "junk"):
        for _ in range(20):
            assert roll_gear(1, item_type, "rare", attempts=3).rarity.lower() in ("rare", "legendary")


def test_roll_gear_attempts_keep_luck_weighted_pick(monkeypatch):
    common = JunkSchema(name="Common scrap", rarity="Common", value=1)
    rare = JunkSchema(name="Rare scrap", rarity="Rare", value=50)
    rolled = iter((common, rare))
    floors: list[str | None] = []

    def pick(_luck: int, _item_type: str, min_rarity: str | None = None) -> JunkSchema:
        floors.append(min_rarity)
        return next(rolled)

    monkeypatch.setattr(expedition_module.loot_calculator, "roll_item", pick)
    assert (roll_gear(5, "junk", "rare", attempts=2), floors) == (rare, [None, None])


def test_item_roll_rejects_ambiguous_or_ineffective_attempts():
    with pytest.raises(ValidationError):
        ItemRollSpec(type="junk", floor=None, rolls=2)
    with pytest.raises(ValidationError, match="rarity floor"):
        ItemRollSpec(type="junk", floor=None, attempts=2)


@pytest.mark.parametrize("kind", ["cache", "skill_check", "choice"])
def test_site_node_rejects_unshipped_kinds(kind: str):
    extra = {"cache_tier": "rich"} if kind == "choice" else {}
    with pytest.raises(ValidationError):
        SiteNode(kind=kind, prompt="Unused node", **extra)


def test_validate_site_content_rejects_unsatisfiable_floor(monkeypatch):
    site = data_loader.get_expedition_site("super_duper_mart")
    assert site is not None
    monkeypatch.setattr(data_loader, "load_weapons", lambda: [{"name": "Rusty Pipe", "rarity": "Common", "value": 10}])
    with pytest.raises(ValidationException, match="no weapon at or above rarity"):
        validate_site_content(site)
    branch_site = data_loader.get_expedition_site("red_rocket").model_copy(deep=True)
    branch_site.rooms[0].node.options[0].success = NodeBranch(
        cache_tier="rich", cache_item="weapon", cache_floor="legendary"
    )
    monkeypatch.setattr(expedition_module.loot_calculator, "has_eligible", lambda *_: False)
    with pytest.raises(ValidationException, match="no weapon at or above rarity"):
        validate_site_content(branch_site)


def test_higher_level_sites_field_two_enemies():
    for site_id in ("super_duper_mart", "gloomwater_bog_night"):
        site = data_loader.get_expedition_site(site_id)
        assert site is not None
        assert len(initial_combat(site)["opponents"]) == 2


def test_trivia_ordering_and_difficulty_weights():
    # The answer key is always option index 0 in content; ordering must break that.
    site = data_loader.get_expedition_site("raider_tollbooth")
    assert site is not None
    question = site.encounter.node.trivia_questions[0]
    positions = {
        [option.id for option in ordered_options(SimpleNamespace(id=uuid4()), question)].index(
            question.correct_option_id
        )
        for _ in range(24)
    }
    assert len(positions) > 1, f"correct answer never moved from one slot: {positions}"
    assert question_weight(1, 1) > question_weight(5, 1)
    assert question_weight(5, 5) > question_weight(1, 5)
