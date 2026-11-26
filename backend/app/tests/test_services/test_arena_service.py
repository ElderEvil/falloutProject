from datetime import UTC, datetime, timedelta
from itertools import pairwise
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    AgeGroupEnum,
    ArenaMode,
    DwellerStatusEnum,
    GenderEnum,
    LifecycleEnum,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.event_bus import event_bus
from app.core.game_config import game_config
from app.crud.arena_state import arena_state_crud
from app.crud.dweller import determine_status_for_room
from app.crud.notification import notification as notification_crud
from app.models.arena_match_event import ArenaMatchEvent
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.arena import ArenaFightersRequest
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.catalog_service import load_enemies, load_outfits, load_weapons
from app.services.combat.arena_participants import (
    ArenaParticipant,
    charge_per_second,
    participant_from_dweller,
    persist_creature_hp,
)
from app.services.combat.arena_service import ArenaService
from app.services.combat.attack_service import resolve_attacks
from app.services.combat.weapon_skill import UNARMED_SKILL, weapon_skill
from app.services.dweller_assignment_service import dweller_assignment_service
from app.services.dweller_service import dweller_service
from app.services.exit_request_service import exit_request_service
from app.services.game_loop_service import game_loop_service
from app.services.notification_service import NotificationService
from app.utils.combat import combat_power
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.item_factory import build_outfit, build_weapon
from app.utils.serialize import serialize_utc_datetime
from app.utils.time import utcnow


async def _place(session, room, *fighters):
    for fighter in fighters:
        fighter.room_id = room.id
    await session.commit()


async def _gear(session, *fighters):
    for fighter in fighters:
        await session.refresh(fighter, ["weapon", "outfit"])


async def _select(session, room, a, b=None, *, c=None, d=None, keys=None, **selection):
    """Place the chosen fighters, preload gear, and persist the arena selection."""
    await _place(session, room, *(f for f in (a, b, c, d) if f is not None))
    await _gear(session, *(f for f in (a, b) if f is not None))
    state = await ArenaService().set_fighters(
        session,
        room.id,
        a.id if a else None,
        b.id if b else None,
        fighter_c_id=c.id if c else None,
        fighter_d_id=d.id if d else None,
        opponent_keys=keys,
        **selection,
    )
    await session.commit()
    return state


async def _live(session, room, a, b=None, *, elapsed=60, health=(), c=None, d=None, keys=None, **selection):
    """Arm and start a match, back-dating the countdown so the next tick fights."""
    for fighter, hp in zip((a, b, c, d), health, strict=False):
        if fighter is not None:
            fighter.health = hp
    state = await _select(session, room, a, b, c=c, d=d, keys=keys, **selection)
    await ArenaService().start_fight(session, room.id)
    state.fight_started_at = utcnow() - timedelta(seconds=elapsed)
    await session.commit()
    return state


async def _view(session, room):
    return (await ArenaService().get_arena_state(session, room.vault_id)).rooms[0]


async def _events(session, room):
    return list((await session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == room.id))).scalars())


async def finish_match(service, session, room, team_a, team_b, *, state=None):
    """Play alternating turns until the reward/settlement boundary under test."""
    for _ in range(100):
        result = await service._resolve_round(session, room, team_a, team_b, 1000, state=state)
        if result["status"] == "finished":
            return result
    pytest.fail("Arena match did not settle")


async def configure_arena(db_session, room, **fields):
    state = await arena_state_crud.get_or_create(db_session, room.id)
    for key, value in fields.items():
        setattr(state, key, value)
    await db_session.commit()
    return state


async def _dweller(
    session, vault_id, *, first, last, hp, gender=GenderEnum.MALE, level=1, age=AgeGroupEnum.ADULT, **stats
):
    data = DwellerCreate(
        first_name=first,
        last_name=last,
        vault_id=vault_id,
        gender=gender,
        rarity=RarityEnum.COMMON,
        age_group=age,
        level=level,
        max_health=hp,
        health=hp,
        **stats,
    )
    return await crud.dweller.create(db_session=session, obj_in=data)


async def _room(session, vault_id, size_max=6, **fields):
    data = RoomCreate(
        name="Power Generator",
        category=RoomTypeEnum.PRODUCTION,
        ability=SPECIALEnum.STRENGTH,
        base_cost=100,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=3,
        size_max=size_max,
        vault_id=vault_id,
        **fields,
    )
    return await crud.room.create(db_session=session, obj_in=data)


async def _morale_bystander(session, vault_id, surname, happiness):
    """An idle vault resident who never enters the arena."""
    stats = dict.fromkeys(("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"), 5)
    dweller = await _dweller(session, vault_id, first="Morale", last=surname, hp=100, gender=GenderEnum.FEMALE, **stats)
    dweller.happiness = happiness
    return dweller


async def _morale_round(session, room, a, b, *, a_hp=1200, b_hp=1):
    for fighter in (a, b):
        fighter.room_id = room.id
        await session.refresh(fighter, ["weapon", "outfit"])
    a.health, b.health = a_hp, b_hp
    await session.commit()
    a, b = [participant_from_dweller(a)], [participant_from_dweller(b)]
    return await ArenaService()._resolve_round(session, room, a, b, 1000)


async def prepare_newcomers(session, room, fighters):
    source = Room(**room.model_dump(exclude={"id", "created_at", "updated_at"}))
    source.name = "Power Generator"
    source.category = RoomTypeEnum.PRODUCTION
    session.add(source)
    await session.flush()
    room.size = 9
    for fighter in fighters:
        fighter.room_id = source.id
        fighter.status = DwellerStatusEnum.WORKING
    await session.commit()
    return source


@pytest_asyncio.fixture(name="arena_room")
async def arena_room_fixture(async_session, vault):
    room = {
        "name": "Arena",
        "category": RoomTypeEnum.ARENA,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": 800,
        "incremental_cost": 200,
        "t2_upgrade_cost": 3000,
        "t3_upgrade_cost": 9000,
        "size_min": 6,
        "size_max": 6,
        "tier": 3,
        "coordinate_x": 0,
        "coordinate_y": 1,
    }
    return await crud.room.create(db_session=async_session, obj_in=RoomCreate(**room, vault_id=vault.id))


@pytest_asyncio.fixture(name="fighter_a")
async def fighter_a_fixture(async_session, vault):
    """Strong fighter."""
    stats = {"strength": 10, "perception": 1, "endurance": 10, "charisma": 1, "intelligence": 1, "agility": 1, "luck": 1}
    return await _dweller(async_session, vault.id, first="Arena", last="Champ", hp=100, level=5, **stats)


@pytest_asyncio.fixture(name="fighter_b")
async def fighter_b_fixture(async_session, vault):
    """Weak fighter."""
    stats = dict.fromkeys(("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"), 1)
    return await _dweller(
        async_session, vault.id, first="Arena", last="Jobber", hp=50, gender=GenderEnum.FEMALE, **stats
    )


@pytest_asyncio.fixture(name="fighter_c")
async def fighter_c_fixture(async_session, vault):
    stats = {"strength": 3, "endurance": 3, "agility": 3}
    return await _dweller(async_session, vault.id, first="Arena", last="Second", hp=80, level=3, **stats)


@pytest_asyncio.fixture(name="fighter_d")
async def fighter_d_fixture(async_session, vault):
    stats = {"strength": 2, "endurance": 2, "agility": 2}
    return await _dweller(
        async_session, vault.id, first="Arena", last="Fourth", hp=60, level=2, gender=GenderEnum.FEMALE, **stats
    )


@pytest.mark.parametrize("image_url", [None, "/static/pet_images/custom-dog.png"])
async def test_arena_fighter_includes_equipped_pet_appearance(async_session, arena_room, fighter_a, image_url):
    await _place(async_session, arena_room, fighter_a)
    pet = {"name": "CX404", "rarity": RarityEnum.COMMON, "value": 100, "dweller_id": fighter_a.id, "image_url": image_url}
    await crud.pet.create(async_session, pet)
    async_session.expire(fighter_a, ["pet"])
    await ArenaService().set_fighters(
        async_session, arena_room.id, fighter_a.id, None, mode=ArenaMode.HUNT, opponent_keys=["radroach-swarm"]
    )
    view = await _view(async_session, arena_room)
    assert view.team_a[0].pet.name == "CX404"
    assert view.team_a[0].pet.image_url == (image_url or "/static/pet_images/FOS CX404.png")
    assert (len(view.team_a), len(view.team_b), view.team_b[0].pet) == (1, 1, None)


def test_arena_catalog_offers_wildlife_and_training_robots():
    creatures = {creature["key"]: creature for creature in ArenaService.list_creatures()}
    assert "raider-gang" not in creatures
    assert (creatures["training-eyebot"]["name"], creatures["training-mr-handy"]["name"]) == (
        "Training Eyebot",
        "Training Mr. Handy",
    )
    assert (creatures["training-eyebot"]["power"], creatures["training-eyebot"]["max_hp"]) == (30, 20)
    assert (creatures["training-mr-handy"]["power"], creatures["training-mr-handy"]["max_hp"]) == (20, 30)
    assert (creatures["training-protectron"]["power"], creatures["training-protectron"]["max_hp"]) == (10, 60)
    assert "Raider gang" in {enemy["name"] for enemy in load_enemies()}
    keys = ["bloatfly", "radstag", "night-stalker", "mirelurk", "yao-guai"]
    assert set(keys).issubset(creatures)
    assert all(not creatures[key]["is_robot"] for key in keys)
    assert (
        creatures["bloatfly"]["power"]
        < creatures["radstag"]["power"]
        < creatures["night-stalker"]["power"]
        < creatures["mirelurk"]["power"]
        == creatures["yao-guai"]["power"]
        < creatures["deathclaw"]["power"]
    )
    assert not {creatures[key]["name"] for key in keys} & {enemy["name"] for enemy in load_enemies()}


@pytest.mark.parametrize("reserved", ["raider-gang", "brahmin"])
def test_hunt_opponents_resolve_catalog_keys_and_reject_reserved_ones(reserved):
    opponents = ArenaService._hunt_opponents(["training-eyebot", "training-mr-handy"])
    assert [opponent["name"] for opponent in opponents] == ["Training Eyebot", "Training Mr. Handy"]
    assert all(opponent["hp"] == opponent["max_hp"] > 0 for opponent in opponents)
    with pytest.raises(ValidationException, match="Unknown hunt opponent"):
        ArenaService._hunt_opponents([reserved])


async def test_hunt_duplicate_enemy_labels_and_ids_survive_knockouts(async_session, arena_room, fighter_a):
    vault_id = arena_room.vault_id
    await _select(async_session, arena_room, fighter_a, mode=ArenaMode.HUNT, keys=["radroach-swarm"] * 2)
    before = (await _view(async_session, arena_room)).team_b
    expected = [("radroach-swarm#0", "Radroach swarm 1"), ("radroach-swarm#1", "Radroach swarm 2")]
    assert [(fighter.id, fighter.name) for fighter in before] == expected
    state = await arena_state_crud.get(async_session, arena_room.id)
    state.opponents = [{**entry, "hp": 0 if index == 0 else entry["hp"]} for index, entry in enumerate(state.opponents)]
    await async_session.commit()
    async_session.expire_all()
    after = (await ArenaService().get_arena_state(async_session, vault_id)).rooms[0].team_b
    assert [(fighter.id, fighter.name) for fighter in after] == expected
    assert (after[0].health, after[1].health) == (0, before[1].health)


@pytest.mark.parametrize(("seconds", "expected"), [(-1, 0), (0, 0), (1, 4), (2, 8)])
def test_attacks_use_twenty_percent_power_per_second_and_ignore_knockouts(seconds, expected):
    team = [
        ArenaParticipant(key="down", name="Down", short_name="Down", power=100.0, health=0, max_health=100),
        ArenaParticipant(key="up", name="Up", short_name="Up", power=20.0, health=10, max_health=100),
    ]
    target = ArenaParticipant(key="target", name="Target", short_name="Target", power=0, health=100, max_health=100)
    attacks = resolve_attacks(team, [target], seconds, set(), {})
    assert target.health == 100 - expected
    assert [attack.action.actor_id for attack in attacks] == (["up"] if expected else [])


@pytest.mark.parametrize(
    ("keys", "two_dwellers", "bot", "knocked_out", "xp_rate", "expected"),
    [
        (["radroach-swarm", "bloatfly"], False, False, False, 30, [60]),
        (["mole-rat-pack", "night-stalker"], False, False, False, 30, [150]),
        (["mirelurk", "yao-guai"], False, False, False, 30, [240]),
        (["mirelurk", "yao-guai"], True, False, False, 30, [120, 120]),
        (["mirelurk", "yao-guai"], False, True, False, 30, [240]),
        (["mirelurk", "yao-guai"], True, False, True, 30, [120, 120]),
        (["night-stalker"], True, False, False, 1, [2, 1]),
        (["bloatfly"], False, False, False, 0, [0]),
    ],
)
async def test_hunt_xp_pool_is_split_and_reported_once(
    async_session, arena_room, fighter_a, fighter_c, monkeypatch, keys, two_dwellers, bot, knocked_out, xp_rate, expected
):
    monkeypatch.setattr(game_config.combat, "xp_per_difficulty", xp_rate)
    dwellers = [fighter_a, fighter_c] if two_dwellers else [fighter_a]
    for dweller in dwellers:
        dweller.room_id = arena_room.id
        dweller.experience = 0
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        None,
        mode=ArenaMode.HUNT,
        fighter_c_id=fighter_c.id if two_dwellers else None,
        opponent_keys=keys,
    )
    team_a, team_b = await service.get_teams(async_session, arena_room)
    team_a[0].power = 1000
    if bot:
        # Legacy Team A support is ignored, including for XP distribution.
        state.support_bots = {"A": service._hunt_opponents(["training-eyebot"])[0]}
        team_a, team_b = await service.get_teams(async_session, arena_room)
        team_a[0].power = 1000
        assert len(team_a) == len(dwellers)
    for hunter in team_a:
        hunter.health = hunter.max_health = 100000
    if knocked_out:
        team_a[1].health = 0
    result = await finish_match(service, async_session, arena_room, team_a, team_b, state=state)
    assert result["status"] == "finished"
    assert [dweller.experience for dweller in dwellers] == expected
    await async_session.commit()
    reward = next(event.message for event in (await _view(async_session, arena_room)).events if event.kind == "reward")
    for dweller, xp in zip(dwellers, expected, strict=True):
        assert f"{dweller.first_name} +{xp} XP" in reward
    assert "Eyebot +" not in reward
    assert (await service.process_arena_ticks(async_session, 3600))["arena"]["rounds"] == []
    for dweller, xp in zip(dwellers, expected, strict=True):
        await async_session.refresh(dweller)
        assert dweller.experience == xp


async def test_defeated_hunters_receive_no_xp(async_session, arena_room, fighter_a):
    fighter_a.experience = 0
    await _place(async_session, arena_room, fighter_a)
    service = ArenaService()
    state = await _select(async_session, arena_room, fighter_a, mode=ArenaMode.HUNT, keys=["yao-guai"])
    team_a, team_b = await service.get_teams(async_session, arena_room)
    team_a[0].power, team_a[0].health = 0, 1
    state.next_attack_team = "B"
    result = await service._resolve_round(async_session, arena_room, team_a, team_b, 2, state=state)
    assert (result["status"], fighter_a.experience) == ("finished", 0)
    await async_session.commit()
    view = await _view(async_session, arena_room)
    assert "XP" not in next(event.message for event in view.events if event.kind == "reward")


@pytest.mark.parametrize("mode", [ArenaMode.DUEL, ArenaMode.BRAWL])
async def test_dweller_matches_keep_existing_xp_per_winner(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, mode
):
    for dweller in (fighter_a, fighter_b, fighter_c, fighter_d):
        dweller.room_id = arena_room.id
        dweller.experience = 0
    await async_session.commit()
    brawl = mode == ArenaMode.BRAWL
    service = ArenaService()
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id,
        mode=mode,
        fighter_c_id=fighter_c.id if brawl else None,
        fighter_d_id=fighter_d.id if brawl else None,
    )
    team_a, team_b = await service.get_teams(async_session, arena_room)
    team_a[0].power = 10000
    for participant in team_b:
        participant.power = 0
    await finish_match(service, async_session, arena_room, team_a, team_b, state=state)
    assert fighter_a.experience == game_config.combat.xp_per_difficulty * 2
    assert fighter_c.experience == (game_config.combat.xp_per_difficulty * 2 if brawl else 0)
    assert fighter_b.experience == fighter_d.experience == 0


@pytest.mark.parametrize(("tier", "mode"), [(1, ArenaMode.BRAWL), (1, ArenaMode.HUNT), (2, ArenaMode.HUNT)])
async def test_locked_arena_mode_rejects_selection_and_start(async_session, arena_room, tier, mode):
    arena_room.tier = tier
    await async_session.commit()
    service = ArenaService()
    with pytest.raises(ValidationException, match="requires Arena tier"):
        await service.set_fighters(async_session, arena_room.id, None, None, mode=mode)
    await configure_arena(async_session, arena_room, mode=mode)
    with pytest.raises(ValidationException, match="requires Arena tier"):
        await service.start_fight(async_session, arena_room.id)


@pytest.mark.parametrize(
    ("tier", "expected"),
    [(1, [ArenaMode.DUEL]), (2, [ArenaMode.DUEL, ArenaMode.BRAWL, ArenaMode.TRAINING]), (3, list(ArenaMode))],
)
async def test_arena_state_reports_tier_unlocks(async_session, arena_room, vault, fighter_a, tier, expected):
    await _select(async_session, arena_room, fighter_a, mode=ArenaMode.HUNT, keys=["deathclaw"])
    # A complete legacy Hunt selection must not enable starting below tier 3.
    arena_room.tier = tier
    await async_session.commit()
    state = (await ArenaService().get_arena_state(async_session, vault.id)).rooms[0]
    assert state.available_modes == expected
    assert (state.can_start, state.fight_ready) == (tier == 3, tier == 3)


async def test_arena_uses_dweller_display_name_and_portraits(async_session, arena_room, vault, fighter_a, fighter_b):
    fighter_a.last_name = None
    fighter_a.image_url = "/static/dweller_images/champ.png"
    fighter_a.thumbnail_url = "/static/dweller_images/champ-thumb.png"
    await _select(async_session, arena_room, fighter_a, fighter_b)
    state = (await ArenaService().get_arena_state(async_session, vault.id)).rooms[0]
    for entry in [state.team_a[0], state.fighters[0], next(d for d in state.roster if d.id == str(fighter_a.id))]:
        assert (entry.name, entry.image_url, entry.thumbnail_url) == (
            fighter_a.first_name,
            fighter_a.image_url,
            fighter_a.thumbnail_url,
        )


@pytest.mark.parametrize(
    ("mode", "winner_label", "side_b_wins"),
    [
        (ArenaMode.HUNT, "Arena", False),
        (ArenaMode.HUNT, "Dwellers", False),
        (ArenaMode.HUNT, "Creatures", True),
        (ArenaMode.BRAWL, "Team A", False),
        (ArenaMode.BRAWL, "Team B", True),
    ],
)
async def test_team_result_names_every_winner(
    async_session, arena_room, vault, fighter_a, fighter_b, fighter_c, fighter_d, mode, winner_label, side_b_wins
):
    await _place(async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d)
    brawl = mode == ArenaMode.BRAWL
    await ArenaService().set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id if brawl else None,
        mode=mode,
        fighter_c_id=fighter_c.id,
        fighter_d_id=fighter_d.id if brawl else None,
        opponent_keys=["radroach-swarm", "mole-rat-pack"] if mode == ArenaMode.HUNT else None,
    )
    async_session.add(ArenaMatchEvent(room_id=arena_room.id, kind="finish", message=f"{winner_label} defeated opponents!"))
    await async_session.commit()
    state = (await ArenaService().get_arena_state(async_session, vault.id)).rooms[0]
    winning_team = state.team_b if side_b_wins else state.team_a
    assert state.winner_name == " & ".join(fighter.name for fighter in winning_team)


async def test_fight_round_ongoing_keeps_both_fighters(async_session, arena_room, fighter_a, fighter_b):
    await _place(async_session, arena_room, fighter_a, fighter_b)
    await _gear(async_session, fighter_a, fighter_b)
    a, b = [participant_from_dweller(fighter_a)], [participant_from_dweller(fighter_b)]
    result = await ArenaService()._resolve_round(async_session, arena_room, a, b, 1)
    assert result["status"] == "ongoing"
    assert fighter_a.health > fighter_b.health


async def test_fight_round_finishes_and_rewards_winner(async_session, arena_room, fighter_a, fighter_b):
    await _place(async_session, arena_room, fighter_a, fighter_b)
    # Strong fighter survives the round, weak one cannot -> single KO
    fighter_a.health, fighter_b.health = 1200, 1
    await _gear(async_session, fighter_a, fighter_b)
    a, b = [participant_from_dweller(fighter_a)], [participant_from_dweller(fighter_b)]
    result = await ArenaService()._resolve_round(async_session, arena_room, a, b, 1000)
    assert (result["status"], result["winner"], result["loser"]) == ("finished", "Arena Champ", "Arena Jobber")
    assert (fighter_b.health, fighter_a.health >= 1) == (1, True)
    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    assert arena_state is not None
    assert arena_state.last_fight_at is not None
    assert fighter_a.happiness == 61  # 50 + 10 swing + 1 vault-wide morale
    assert fighter_b.happiness == 41  # 50 - 10 swing + 1 vault-wide morale


async def test_process_arena_ticks_fights_once_then_stops(async_session, arena_room, fighter_a, fighter_b):
    await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=10)
    service = ArenaService()
    result = await service.process_arena_ticks(async_session, 3600)
    assert (result["arena"]["rooms"], bool(result["arena"]["rounds"])) == (1, True)
    assert result["arena"]["rounds"][0]["status"] == "finished"
    # The room is done after one match: the next tick must not re-fight it
    result_2 = await service.process_arena_ticks(async_session, 3600)
    assert (result_2["arena"]["rooms"], result_2["arena"]["rounds"]) == (1, [])


async def test_arena_tick_respects_countdown_and_understaffed_room(async_session, arena_room, fighter_a, fighter_b):
    await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=1)
    # Still inside the 3s countdown: no combat yet
    assert (await ArenaService().process_arena_ticks(async_session, 3600))["arena"]["rounds"] == []
    await ArenaService().stop_fight(async_session, arena_room.id, arena_room.vault_id)
    await configure_arena(async_session, arena_room, fighter_a_id=None, fighter_b_id=None)
    assert (await ArenaService().process_arena_ticks(async_session, 60))["arena"] == {"rooms": 1, "rounds": []}


async def test_start_fight_validates_then_arms_the_room(async_session, arena_room, fighter_a, fighter_b):
    await _place(async_session, arena_room, fighter_a)
    service = ArenaService()
    with pytest.raises(ValidationException):
        await service.start_fight(async_session, arena_room.id)
    with pytest.raises(ValidationException):
        await service.start_fight(async_session, arena_room.id, uuid4())

    await _select(async_session, arena_room, fighter_a, fighter_b)
    room = await service.start_fight(async_session, arena_room.id)
    arena_state = await arena_state_crud.get(async_session, room.id)
    assert arena_state is not None
    assert arena_state.fight_started_at is not None
    # A second start is rejected
    with pytest.raises(ValidationException):
        await service.start_fight(async_session, arena_room.id)


async def test_set_fighters_picks_and_resets_match(async_session, arena_room, fighter_a, fighter_b, vault):
    await _place(async_session, arena_room, fighter_a, fighter_b)
    await configure_arena(async_session, arena_room, last_fight_at=utcnow(), fight_started_at=utcnow())
    fighter_a.health, fighter_b.health = 40, 1
    # Irradiate both fighters so effective_max_health differs from base max_health
    fighter_a.radiation, fighter_b.radiation = 20, 10
    await _gear(async_session, fighter_a, fighter_b)
    await async_session.commit()

    service = ArenaService()
    room_arena_state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await async_session.refresh(room_arena_state)
    assert (room_arena_state.fighter_a_id, room_arena_state.fighter_b_id) == (fighter_a.id, fighter_b.id)
    assert (room_arena_state.last_fight_at, room_arena_state.fight_started_at) == (None, None)
    await async_session.refresh(fighter_a)
    await async_session.refresh(fighter_b)
    assert (fighter_a.health, fighter_b.health, fighter_a.radiation, fighter_b.radiation) == (40, 1, 20, 10)

    # Regression (PR #534): get_arena_state must serialize effective_max_health
    # as max_health, or irradiated dwellers show wrong health ratios to clients.
    room_state = (await service.get_arena_state(async_session, vault.id)).rooms[0]
    fighters_by_id = {f.id: f for f in room_state.fighters}
    roster_by_id = {r.id: r for r in room_state.roster}
    for fighter in (fighter_a, fighter_b):
        for serialized in (fighters_by_id[str(fighter.id)], roster_by_id[str(fighter.id)]):
            assert (serialized.health, serialized.max_health) == (fighter.health, fighter.effective_max_health)
            assert serialized.max_health != fighter.max_health


@pytest.mark.parametrize("mode", list(ArenaMode))
async def test_assignment_and_repeated_selection_preserve_injuries(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, mode
):
    fighters = (fighter_a, fighter_b, fighter_c, fighter_d)
    health = (40, 1, 35, 7)
    for fighter, hp in zip(fighters, health, strict=True):
        fighter.health = hp
    await async_session.commit()
    for fighter in fighters:
        await dweller_service.move_to_room(async_session, fighter.id, arena_room.id)
        await async_session.refresh(fighter)
    assert tuple(fighter.health for fighter in fighters) == health

    selection = {"mode": mode}
    if mode == ArenaMode.BRAWL:
        selection.update(fighter_c_id=fighter_c.id, fighter_d_id=fighter_d.id)
    elif mode in (ArenaMode.HUNT, ArenaMode.TRAINING):
        selection.update(fighter_c_id=fighter_c.id, opponent_keys=["training-eyebot", "training-protectron"])
    service = ArenaService()
    for _ in range(2):
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            fighter_b.id if mode not in (ArenaMode.HUNT, ArenaMode.TRAINING) else None,
            **selection,
        )
        for fighter in fighters:
            await async_session.refresh(fighter)
        assert tuple(fighter.health for fighter in fighters) == health


async def test_set_fighters_rejects_dweller_not_in_room(async_session, arena_room, fighter_a, fighter_b):
    await _place(async_session, arena_room, fighter_a)
    await _gear(async_session, fighter_a, fighter_b)
    await async_session.commit()
    # fighter_b is not assigned to the arena room
    with pytest.raises(ValidationException):
        await ArenaService().set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)


async def test_arena_slot_cleared_when_fighter_moved_out(async_session, arena_room, fighter_a, fighter_b, vault):
    """A fighter leaving the arena room must not leave a stale slot behind.

    Regression: slots point at dwellers who moved out, so picking a new
    fighter sends the stale id along and set_fighters rejects the whole
    request with "Both fighters must be adult dwellers assigned to the Arena".
    """
    await _select(async_session, arena_room, fighter_a, fighter_b)
    await configure_arena(
        async_session, arena_room, fighter_a_id=fighter_a.id, fighter_b_id=fighter_b.id, fight_started_at=utcnow()
    )
    stats = {"strength": 5, "endurance": 5, "agility": 5}
    replacement = await _dweller(async_session, vault.id, first="Arena", last="Replacement", hp=80, level=3, **stats)
    replacement.room_id = arena_room.id
    await async_session.commit()
    other_room = await _room(async_session, vault.id, incremental_cost=50, coordinate_x=2, coordinate_y=1)
    await dweller_service.move_to_room(async_session, dweller_id=fighter_a.id, room_id=other_room.id)

    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    assert (arena_state.fighter_a_id, arena_state.fighter_b_id, arena_state.fight_started_at) == (
        None,
        fighter_b.id,
        None,
    )
    arena_state = await ArenaService().set_fighters(async_session, arena_room.id, replacement.id, fighter_b.id)
    assert arena_state.fighter_a_id == replacement.id


async def test_resolve_round_1v1_alternates_with_full_damage(async_session, arena_room, fighter_a, fighter_b):
    await _place(async_session, arena_room, fighter_a, fighter_b)
    await _gear(async_session, fighter_a, fighter_b)
    a, b = [participant_from_dweller(fighter_a)], [participant_from_dweller(fighter_b)]
    state = await configure_arena(async_session, arena_room, fighter_a_id=fighter_a.id, fighter_b_id=fighter_b.id)
    service = ArenaService()
    damage_b = min(combat_power(fighter_a) / 5, 50 * 0.05)
    await service._resolve_round(async_session, arena_room, a, b, 1, state=state)
    assert (fighter_a.health, fighter_b.health) == (100, 50 - int(damage_b))
    assert service._damage_carry[str(arena_room.id)][str(fighter_b.id)] == pytest.approx(damage_b % 1)
    assert state.next_attack_team == "B"
    await async_session.commit()
    # A fresh worker resumes B rather than restarting with A.
    await async_session.refresh(state)
    damage_a = min(combat_power(fighter_b) / 5, 100 * 0.05)
    await ArenaService()._resolve_round(async_session, arena_room, a, b, 1, state=state)
    assert (fighter_a.health, fighter_b.health) == (100 - int(damage_a), 50 - int(damage_b))
    assert state.next_attack_team == "A"
    await async_session.commit()
    view = await _view(async_session, arena_room)
    assert [e.message for e in view.events if e.kind == "turn"] == ["Team A attacks", "Team B attacks"]


async def test_resolve_round_pairs_targets_and_preserves_fractional_carry(async_session, arena_room):
    service = ArenaService()
    heroes = [
        ArenaParticipant(key=k, name=k, short_name=k, power=p, health=100, max_health=100)
        for k, p in [("hero", 43.5), ("ally", 20)]
    ]
    weak = ArenaParticipant(key="weak", name="Weak", short_name="Weak", power=0, health=5, max_health=50)
    strong = ArenaParticipant(key="strong", name="Strong", short_name="Strong", power=0, health=200, max_health=200)
    await service._resolve_round(async_session, arena_room, heroes, [weak, strong], 1)
    assert (weak.health, strong.health) == (3, 196)
    assert service._damage_carry[str(arena_room.id)]["weak"] == 0.5
    await service._resolve_round(async_session, arena_room, heroes, [weak, strong], 1)
    assert (weak.health, strong.health) == (3, 196)  # B's turn cannot hurt B.
    await service._resolve_round(async_session, arena_room, heroes, [weak, strong], 1)
    assert (weak.health, strong.health) == (0, 192)
    assert service._damage_carry[str(arena_room.id)]["weak"] == 0
    # Once one enemy remains, both attackers may share it.
    await service._resolve_round(async_session, arena_room, heroes, [weak, strong], 1)
    await service._resolve_round(async_session, arena_room, heroes, [weak, strong], 1)
    assert strong.health == 180


async def test_resolve_round_defeated_creature_stops_dealing_damage(async_session, arena_room):
    service = ArenaService()
    hero = ArenaParticipant(key="hero", name="Hero", short_name="Hero", power=100.0, health=1000, max_health=1000)
    weak = ArenaParticipant(key="weak", name="Weak", short_name="Weak", power=50.0, health=1, max_health=100, is_creature=True)
    strong = ArenaParticipant(
        key="strong", name="Strong", short_name="Strong", power=100.0, health=1000, max_health=1000, is_creature=True
    )
    await service._resolve_round(async_session, arena_room, [hero], [weak, strong], 1)
    assert weak.health == 0
    after_first = hero.health
    await service._resolve_round(async_session, arena_room, [hero], [weak, strong], 1)
    # Only the surviving creature attacks on B's turn: 20% power per second.
    assert hero.health == after_first - 20


async def test_brawl_knockout_keeps_fighter_alive_and_match_running(
    async_session, db_connection, arena_room, fighter_a, fighter_b, fighter_c, fighter_d
):
    await _live(
        async_session,
        arena_room,
        fighter_a,
        fighter_b,
        elapsed=10,
        health=(1000, 1, 1000, 1000),
        mode=ArenaMode.BRAWL,
        c=fighter_c,
        d=fighter_d,
    )
    await ArenaService().process_arena_ticks(async_session, 1)
    await async_session.refresh(fighter_b)
    await async_session.refresh(fighter_d)

    # One knockout must not end the match early...
    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    assert arena_state is not None
    assert arena_state.last_fight_at is None
    # ...nor leave the dweller lethally at 0 HP (the vault health tick kills those).
    assert (fighter_b.health >= 1, fighter_d.health > 0) == (True, True)

    # A fresh worker service and raw SQLAlchemy session still see the persisted KO.
    fresh = ArenaService()
    async with RawAsyncSession(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as worker_session:
        team_a, team_b = await fresh.get_teams(worker_session, arena_room)
        assert (len(team_a), len(team_b)) == (2, 2)
        assert next(p for p in team_b if p.key == str(fighter_b.id)).health == 0
        # The next tick still resolves a round: a lone KO must not freeze the match.
        result = await fresh.process_arena_ticks(worker_session, 1)
        assert result["arena"]["rounds"][0]["status"] == "ongoing"


async def test_resolve_round_team_defeat_reports_winner_and_loser(async_session, arena_room):
    service = ArenaService()
    hero = ArenaParticipant(key="hero", name="Hero One", short_name="Hero", power=100.0, health=100, max_health=100)
    ally = ArenaParticipant(key="ally", name="Ally Two", short_name="Ally", power=50.0, health=100, max_health=100)
    enemy = ArenaParticipant(key="enemy", name="Enemy", short_name="Enemy", power=1.0, health=10, max_health=10)
    result = await service._resolve_round(async_session, arena_room, [hero, ally], [enemy], 10)
    assert (result["status"], result["winner_id"], result["winner"]) == ("finished", "hero", "Hero One")
    assert (result["loser_id"], result["loser"], enemy.health) == ("enemy", "Enemy", 1)
    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    assert arena_state is not None
    assert arena_state.last_fight_at is not None


@pytest.mark.parametrize(
    ("mode", "slots", "keys"),
    [
        (ArenaMode.DUEL, (0, 1, 2, None), None),
        (ArenaMode.BRAWL, (0, 1, 2, None), None),
        (ArenaMode.DUEL, (0, 0, None, None), None),  # same dweller twice
        (ArenaMode.HUNT, (None, None, None, None), ["radroach-swarm"]),
        (ArenaMode.HUNT, (0, 1, None, None), ["radroach-swarm"]),
        (ArenaMode.HUNT, (0, None, None, None), ["firesnake"]),
        (ArenaMode.HUNT, (0, None, 2, 3), ["radroach-swarm"]),
    ],
)
async def test_set_fighters_rejects_invalid_selection(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, mode, slots, keys
):
    agents = (fighter_a, fighter_b, fighter_c, fighter_d)
    await _place(async_session, arena_room, *agents)
    ids = [agents[index].id if index is not None else None for index in slots]
    with pytest.raises(ValidationException):
        await ArenaService().set_fighters(
            async_session,
            arena_room.id,
            ids[0],
            ids[1],
            mode=mode,
            fighter_c_id=ids[2],
            fighter_d_id=ids[3],
            opponent_keys=keys,
        )


async def test_set_fighters_rejects_non_adult(async_session, arena_room, fighter_a, vault):
    child = await _dweller(async_session, vault.id, first="Arena", last="Kid", hp=50, age=AgeGroupEnum.CHILD)
    await _place(async_session, arena_room, fighter_a, child)
    with pytest.raises(ValidationException):
        await ArenaService().set_fighters(async_session, arena_room.id, fighter_a.id, child.id)


async def test_set_fighters_hunt_persists_opponents(async_session, arena_room, fighter_a, fighter_c):
    arena_state = await _select(async_session, arena_room, fighter_a, mode=ArenaMode.HUNT, c=fighter_c, keys=["radroach-swarm", "deathclaw"])
    assert (arena_state.mode, arena_state.fighter_b_id, arena_state.fighter_d_id) == (ArenaMode.HUNT, None, None)
    assert [opponent["key"] for opponent in arena_state.opponents] == ["radroach-swarm", "deathclaw"]
    assert all(opponent["hp"] == opponent["max_hp"] for opponent in arena_state.opponents)
    assert arena_state.opponents[1]["power"] == 50


async def test_set_fighters_accepts_behemoth(async_session, arena_room, fighter_a, fighter_b):
    fighter_a.visual_attributes = {"race": "super_mutant", "state_of_being": "behemoth"}
    state = await _select(async_session, arena_room, fighter_a, fighter_b)
    assert (state.fighter_a_id, state.fighter_b_id) == (fighter_a.id, fighter_b.id)


@pytest.mark.parametrize("mode", [ArenaMode.DUEL, ArenaMode.BRAWL, ArenaMode.HUNT])
async def test_arena_state_projects_teams_per_mode(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, vault, mode
):
    await _place(async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d)
    huntish = mode == ArenaMode.HUNT
    brawl = mode == ArenaMode.BRAWL
    selection = {
        "mode": mode,
        "fighter_c_id": fighter_c.id if mode != ArenaMode.DUEL else None,
        "fighter_d_id": fighter_d.id if brawl else None,
        "opponent_keys": ["radroach-swarm", "mole-rat-pack"] if huntish else None,
    }
    state = await ArenaService().set_fighters(
        async_session, arena_room.id, fighter_a.id, None if huntish else fighter_b.id, **selection
    )
    assert state.mode == mode
    room_state = (await ArenaService().get_arena_state(async_session, vault.id)).rooms[0]
    assert room_state.mode == mode.value
    squad = [str(fighter_a.id)] + ([str(fighter_c.id)] if brawl or huntish else [])
    assert [f.id for f in room_state.team_a] == squad
    if huntish:
        assert [f.name for f in room_state.team_b] == ["Radroach swarm", "Mole Rat pack"]
        assert all(f.is_creature for f in room_state.team_b)
        assert [f.is_creature for f in room_state.team_a] == [False, False]
        assert [(f.health, f.max_health, f.power) for f in room_state.team_b] == [(10, 10, 10), (20, 20, 20)]
    else:
        assert [f.id for f in room_state.team_b] == [str(fighter_b.id)] + ([str(fighter_d.id)] if brawl else [])
        assert [f.id for f in room_state.fighters] == [str(fighter_a.id), str(fighter_b.id)]
    assert (room_state.can_start, room_state.fight_ready) == (True, True)


@pytest.mark.parametrize(("mode", "second"), [(ArenaMode.BRAWL, True), (ArenaMode.HUNT, False)])
async def test_incomplete_selection_is_not_ready(async_session, arena_room, fighter_a, fighter_b, vault, mode, second):
    await _place(async_session, arena_room, fighter_a, fighter_b)
    fields = {"mode": mode, "fighter_a_id": fighter_a.id}
    if second:
        fields["fighter_b_id"] = fighter_b.id
    await configure_arena(async_session, arena_room, **fields)
    room_state = (await ArenaService().get_arena_state(async_session, vault.id)).rooms[0]
    assert (room_state.mode, room_state.team_a, room_state.team_b, room_state.can_start) == (mode.value, [], [], False)


async def test_process_arena_ticks_brawl_resolves_winner(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d
):
    await _live(
        async_session,
        arena_room,
        fighter_a,
        fighter_b,
        elapsed=10,
        health=(1000, 1, 1000, 1),
        mode=ArenaMode.BRAWL,
        c=fighter_c,
        d=fighter_d,
    )
    service = ArenaService()
    result = await service.process_arena_ticks(async_session, 5)
    assert result["arena"]["rooms"] == 1
    assert (result["arena"]["rounds"][0]["status"], result["arena"]["rounds"][0]["winner"]) == ("finished", "Arena Champ")
    await async_session.refresh(fighter_b)
    await async_session.refresh(fighter_d)
    assert (fighter_b.health, fighter_d.health) == (1, 1)
    state = await _view(async_session, arena_room)
    assert state.winner_name == f"{fighter_a.display_name} & {fighter_c.display_name}"
    assert next(e.message for e in state.events if e.kind == "finish") == "Team A defeated Team B!"


@pytest.mark.parametrize(("keys", "expected_hp"), [(["radroach-swarm"], [0]), (["yao-guai", "radstag"], [0, 0])])
async def test_process_arena_ticks_hunt_defeats_creatures(async_session, arena_room, fighter_a, keys, expected_hp):
    await _live(async_session, arena_room, fighter_a, elapsed=10, health=(100000,), mode=ArenaMode.HUNT, keys=keys)
    service = ArenaService()
    for _ in range(3):
        result = await service.process_arena_ticks(async_session, 3600)
        if result["arena"]["rounds"][0]["status"] == "finished":
            break
    assert (result["arena"]["rounds"][0]["status"], result["arena"]["rounds"][0]["winner"]) == (
        "finished",
        "Arena Champ",
    )
    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    assert [opponent["hp"] for opponent in arena_state.opponents] == expected_hp
    assert arena_state.last_fight_at is not None
    await async_session.refresh(fighter_a)
    assert fighter_a.health >= 1
    state = await _view(async_session, arena_room)
    assert next(e.message for e in state.events if e.kind == "finish") == "Dwellers defeated Creatures!"


async def test_process_arena_ticks_hunt_dweller_floored_by_creature(async_session, arena_room, fighter_a):
    await _live(async_session, arena_room, fighter_a, elapsed=10, health=(1,), mode=ArenaMode.HUNT, keys=["deathclaw"])
    service = ArenaService()
    first = await service.process_arena_ticks(async_session, 2)
    assert first["arena"]["rounds"][0]["status"] == "ongoing"
    result = await service.process_arena_ticks(async_session, 2)
    assert (result["arena"]["rounds"][0]["status"], result["arena"]["rounds"][0]["winner"]) == ("finished", "Deathclaw")
    await async_session.refresh(fighter_a)
    assert fighter_a.health == 1
    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    # The creature survives and its damaged HP is not floored.
    assert arena_state.opponents[0]["hp"] == 45


async def test_process_arena_ticks_hunt_creature_hp_persists(async_session, arena_room, fighter_a):
    await _live(async_session, arena_room, fighter_a, elapsed=10, health=(100000,), mode=ArenaMode.HUNT, keys=["radroach-swarm"] * 2)
    service = ArenaService()
    await service.process_arena_ticks(async_session, 1)
    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    first_hp = arena_state.opponents[0]["hp"]
    assert 0 < first_hp <= 10
    assert arena_state.last_fight_at is None
    await service.process_arena_ticks(async_session, 1)
    arena_state = await arena_state_crud.get(async_session, arena_room.id)
    assert arena_state.opponents[0]["hp"] == first_hp  # Only B attacks this turn.
    await service.process_arena_ticks(async_session, 2)
    assert 0 < arena_state.opponents[0]["hp"] < first_hp


@pytest.mark.parametrize(
    ("cooldown", "happiness", "bystander_hp", "surname", "expected"),
    [
        (False, (50, 50), 50, "Bystander", (61, 41, 51)),
        (True, (50, 50), 50, "Bystander", (60, 40, 50)),
        (False, (95, 50), 100, "Capped", (100, None, 100)),
    ],
)
async def test_morale_bonus_applies_once_and_clamps(
    async_session, arena_room, fighter_a, fighter_b, vault, cooldown, happiness, bystander_hp, surname, expected
):
    if cooldown:
        vault.arena_morale_awarded_at = datetime.now(UTC)
        async_session.add(vault)
    fighter_a.happiness, fighter_b.happiness = happiness
    bystander = await _morale_bystander(async_session, arena_room.vault_id, surname, bystander_hp)
    result = await _morale_round(async_session, arena_room, fighter_a, fighter_b)
    assert result["status"] == "finished"
    assert fighter_a.happiness == expected[0]
    if expected[1] is not None:
        assert fighter_b.happiness == expected[1]
    assert bystander.happiness == expected[2]


async def test_arena_tick_delivers_morale_toast_after_commit(async_session, arena_room, fighter_a, fighter_b, vault):
    await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=10)
    with patch.object(NotificationService, "_deliver", new=AsyncMock()) as deliver:
        result = await ArenaService().process_arena_ticks(async_session, 3600)
    assert result["arena"]["rounds"][0]["status"] == "finished"
    rows = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert len([row for row in rows if row.notification_type == "arena_morale_boost"]) == 1
    assert deliver.await_count == 1
    user_id, payload = deliver.await_args.args
    assert (user_id, payload["notification"]["notification_type"]) == (vault.user_id, "arena_morale_boost")


@pytest.mark.parametrize(
    ("match", "mode", "b_lead", "bots"),
    [
        ("Team A only supports dweller", ArenaMode.HUNT, False, {"team_a_bot_key": "training-eyebot"}),
        ("Team A only supports dweller", ArenaMode.BRAWL, True, {"team_a_bot_key": "training-eyebot"}),
        ("training bot", ArenaMode.BRAWL, False, {"team_b_bot_key": "deathclaw"}),
        ("training bot", ArenaMode.BRAWL, False, {"team_b_bot_key": "unknown"}),
        ("second slot", ArenaMode.BRAWL, False, {"fighter_d_id": 1, "team_b_bot_key": "training-eyebot"}),
        ("only available", ArenaMode.DUEL, True, {"team_b_bot_key": "training-eyebot"}),
        ("two Team A dwellers", ArenaMode.BRAWL, False, {"team_b_bot_key": "training-protectron"}),
    ],
)
async def test_bot_selection_rejections(async_session, arena_room, fighter_a, fighter_b, match, mode, b_lead, bots):
    bots = {key: fighter_b.id if value == 1 else value for key, value in bots.items()}
    with pytest.raises(ValidationException, match=match):
        await ArenaService().set_fighters(
            async_session, arena_room.id, fighter_a.id, fighter_b.id if b_lead else None, mode=mode, **bots
        )


async def test_team_b_bot_health_survives_worker_reload(async_session, arena_room, fighter_a, fighter_b, fighter_c):
    service = ArenaService()
    await _live(
        async_session,
        arena_room,
        fighter_a,
        fighter_b,
        elapsed=20,
        mode=ArenaMode.BRAWL,
        c=fighter_c,
        team_b_bot_key="training-protectron",
    )
    await service.process_arena_ticks(async_session, 2)
    _, team_b = await service.get_teams(async_session, arena_room)
    hp = team_b[1].health
    assert 0 < hp < 60
    async_session.expunge_all()
    room = await crud.room.get(async_session, arena_room.id)
    _, reloaded = await ArenaService().get_teams(async_session, room)
    assert reloaded[1].health == hp


async def test_team_b_bot_resets_on_reselection(async_session, arena_room, fighter_a, fighter_b, fighter_c):
    await _place(async_session, arena_room, fighter_a, fighter_b, fighter_c)
    service = ArenaService()
    selection = {"mode": ArenaMode.BRAWL, "fighter_c_id": fighter_c.id, "team_b_bot_key": "training-eyebot"}
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id, **selection)
    a, b = await service.get_teams(async_session, arena_room)
    assert len(a) == len(b) == 2
    assert all(p.dweller is not None for p in a)
    assert (b[1].name, b[1].power, b[1].health) == ("Training Eyebot", 30, 20)
    b[1].health = 0
    persist_creature_hp(state, a, b)
    await async_session.commit()
    _, b = await ArenaService().get_teams(async_session, arena_room)
    assert b[1].health == 0
    target = ArenaParticipant(key="target", name="Target", short_name="Target", power=0, health=10000, max_health=10000)
    attacks = resolve_attacks(b, [target], 2, set(), {})
    assert len(attacks) == 1
    assert attacks[0].action.actor_id == b[0].key
    assert attacks[0].action.targets[0].damage == int(b[0].power * 0.4)
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id, **selection)
    _, b = await service.get_teams(async_session, arena_room)
    assert b[1].health == 20
    await service.start_fight(async_session, arena_room.id)


async def test_team_b_bot_win_rewards_only_its_dweller(async_session, arena_room, fighter_a, fighter_b, fighter_c):
    for fighter in (fighter_a, fighter_b, fighter_c):
        fighter.room_id = arena_room.id
        fighter.experience = 0
        fighter.happiness = 50
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id,
        mode=ArenaMode.BRAWL,
        fighter_c_id=fighter_c.id,
        team_b_bot_key="training-eyebot",
    )
    a, b = await service.get_teams(async_session, arena_room)
    for participant in a:
        participant.power, participant.health = 0, 1
    state.next_attack_team = "B"
    result = await finish_match(service, async_session, arena_room, a, b, state=state)
    assert result["winner_id"] in {p.key for p in b}
    assert fighter_b.experience == game_config.combat.xp_per_difficulty * 2
    assert fighter_a.experience == fighter_c.experience == 0
    assert fighter_b.happiness == 61
    assert await crud.dweller.count_in_room(async_session, arena_room.id) == 3


async def test_legacy_robot_opponent_keeps_stats_and_gets_facing_metadata(async_session, arena_room, fighter_a):
    service = ArenaService()
    state = await _select(async_session, arena_room, fighter_a, mode=ArenaMode.HUNT, keys=["training-eyebot"])
    state.opponents = [{"key": "training-eyebot", "name": "Training Eyebot", "power": 20, "max_hp": 20, "hp": 12}]
    await async_session.commit()
    _, opponents = await service.get_teams(async_session, arena_room)
    assert opponents[0].is_robot
    assert (opponents[0].power, opponents[0].health, opponents[0].max_health) == (20, 12, 20)


async def test_match_status_lifecycle(async_session, arena_room, fighter_a, fighter_b, fighter_c):
    assert determine_status_for_room(RoomTypeEnum.ARENA) == DwellerStatusEnum.IDLE
    for fighter in (fighter_a, fighter_b, fighter_c):
        fighter.status = DwellerStatusEnum.IDLE
    await _place(async_session, arena_room, fighter_a, fighter_b, fighter_c)
    service = ArenaService()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    assert fighter_a.status == fighter_b.status == DwellerStatusEnum.IDLE
    await service.start_fight(async_session, arena_room.id)
    await async_session.refresh(fighter_a)
    await async_session.refresh(fighter_b)
    assert fighter_a.status == fighter_b.status == DwellerStatusEnum.FIGHTING
    assert fighter_c.status == DwellerStatusEnum.IDLE
    await service.set_fighters(async_session, arena_room.id, fighter_c.id, fighter_b.id)
    await async_session.refresh(fighter_a)
    await async_session.refresh(fighter_b)
    assert fighter_a.status == fighter_b.status == DwellerStatusEnum.IDLE


async def test_tick_snapshot_is_read_only(async_session, arena_room, vault):
    service = ArenaService()
    expected = {"rooms": [{"room_id": str(arena_room.id), "fight_started": False, "match_done": False, "events": []}]}
    assert await service.get_tick_snapshot(async_session, vault.id) == expected
    assert await service.get_tick_snapshot(async_session, vault.id) == expected
    assert await arena_state_crud.get(async_session, arena_room.id) is None
    assert await service.get_tick_snapshot(async_session, uuid4()) == {"rooms": []}


@pytest.mark.parametrize("mode", list(ArenaMode))
async def test_match_finish_releases_only_participants(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, mode
):
    service = ArenaService()
    fighters = (fighter_a, fighter_b, fighter_c, fighter_d)
    for fighter in fighters:
        fighter.room_id = arena_room.id
        fighter.status = DwellerStatusEnum.IDLE
        fighter.health = 100
        fighter.max_health = 100
        fighter.radiation = 7
    await async_session.commit()
    huntish = mode in (ArenaMode.HUNT, ArenaMode.TRAINING)
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id if not huntish else None,
        mode=mode,
        fighter_c_id=fighter_c.id if mode != ArenaMode.DUEL else None,
        fighter_d_id=fighter_d.id if mode == ArenaMode.BRAWL else None,
        opponent_keys=(
            ["training-eyebot", "training-protectron"]
            if mode == ArenaMode.TRAINING
            else ["deathclaw"]
            if mode == ArenaMode.HUNT
            else None
        ),
    )
    selected = service._fighter_ids(state)
    await service.start_fight(async_session, arena_room.id)
    # Countdown never resolves a round, but selected dwellers are already busy.
    assert (await service.process_arena_ticks(async_session, 1))["arena"]["rounds"] == []
    for fighter in fighters:
        await async_session.refresh(fighter)
        assert fighter.status == (DwellerStatusEnum.FIGHTING if fighter.id in selected else DwellerStatusEnum.IDLE)
    assert exit_request_service._eligibility_reason(fighter_a) == "Dweller is busy in an arena match"
    state.fight_started_at = utcnow() - timedelta(seconds=60)
    await async_session.commit()
    ongoing = await service.process_arena_ticks(async_session, 1)
    assert ongoing["arena"]["rounds"][0]["status"] == "ongoing"
    assert fighter_a.status == DwellerStatusEnum.FIGHTING
    for _ in range(3):
        result = await service.process_arena_ticks(async_session, 3600)
        if result["arena"]["rounds"][0]["status"] == "finished":
            break
    assert result["arena"]["rounds"][0]["status"] == "finished"
    for fighter in fighters:
        await async_session.refresh(fighter)
        assert (fighter.status, fighter.radiation, fighter.health <= 100) == (DwellerStatusEnum.IDLE, 7, True)
    assert exit_request_service._eligibility_reason(fighter_a) is None
    injuries = [fighter.health for fighter in fighters]
    await service.process_arena_ticks(async_session, 3600)
    assert [fighter.health for fighter in fighters] == injuries


@pytest.mark.parametrize("departure", ["move", "unassign", "bulk_unassign"])
async def test_departure_cancels_match_and_releases_teammate(async_session, arena_room, fighter_a, fighter_b, departure):
    service = ArenaService()
    for fighter in (fighter_a, fighter_b):
        fighter.room_id = arena_room.id
        fighter.status = DwellerStatusEnum.IDLE
        fighter.health = 23
        fighter.radiation = 11
    await async_session.commit()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await service.start_fight(async_session, arena_room.id)
    if departure == "move":
        target = await _room(async_session, arena_room.vault_id, size_max=9)
        await dweller_service.move_to_room(async_session, fighter_a.id, target.id)
    elif departure == "unassign":
        await dweller_service.update_dweller(async_session, fighter_a.id, {"room_id": None})
    else:
        await dweller_assignment_service.unassign_all_dwellers(async_session, arena_room.vault_id)
    state = await arena_state_crud.get(async_session, arena_room.id)
    assert (state.fighter_a_id, state.fight_started_at) == (None, None)
    await async_session.refresh(fighter_a)
    await async_session.refresh(fighter_b)
    assert fighter_b.status == DwellerStatusEnum.IDLE
    assert fighter_a.status == (DwellerStatusEnum.WORKING if departure == "move" else DwellerStatusEnum.IDLE)
    assert fighter_a.health == fighter_b.health == 23
    assert fighter_a.radiation == fighter_b.radiation == 11
    await service.clear_fighter_slots_for_dweller(async_session, fighter_a.id)
    assert (await service.process_arena_ticks(async_session, 3600))["arena"]["rounds"] == []


@pytest.mark.parametrize("completed", [False, True])
async def test_stale_cleanup_preserves_moved_and_dead_dwellers(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, completed
):
    for fighter in (fighter_a, fighter_b, fighter_c):
        fighter.room_id = arena_room.id
        fighter.status = DwellerStatusEnum.FIGHTING
        fighter.health = 17
        fighter.radiation = 4
    fighter_b.room_id = None
    fighter_b.status = DwellerStatusEnum.EXPLORING
    fighter_c.lifecycle = LifecycleEnum.DEAD_REVIVABLE
    fighter_c.is_dead = True
    fighter_c.status = DwellerStatusEnum.DEAD
    state = await configure_arena(
        async_session,
        arena_room,
        fighter_a_id=fighter_a.id,
        fighter_b_id=fighter_b.id,
        fighter_c_id=fighter_c.id,
        last_fight_at=utcnow() if completed else None,
    )
    for _ in range(2):
        await ArenaService().process_arena_ticks(async_session, 1)
        for fighter in (fighter_a, fighter_b, fighter_c):
            await async_session.refresh(fighter)
        assert (fighter_a.status, fighter_b.status, fighter_c.status) == (
            DwellerStatusEnum.IDLE,
            DwellerStatusEnum.EXPLORING,
            DwellerStatusEnum.DEAD,
        )
        assert all(fighter.health == 17 and fighter.radiation == 4 for fighter in (fighter_a, fighter_b, fighter_c))
    assert (state.last_fight_at is not None) is completed


async def test_reconciliation_refreshes_newer_active_selection(
    async_session, db_connection, arena_room, fighter_a, fighter_b
):
    for fighter in (fighter_a, fighter_b):
        fighter.room_id = arena_room.id
        fighter.status = DwellerStatusEnum.IDLE
    state = await configure_arena(async_session, arena_room, fighter_a_id=fighter_a.id, fighter_b_id=fighter_b.id)
    assert state.fight_started_at is None
    # A second session starts a match after the actor loaded an inactive state.
    async with AsyncSession(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as other:
        await ArenaService().start_fight(other, arena_room.id)
    assert state.fight_started_at is None  # deliberately stale identity-map entry
    await ArenaService().process_arena_ticks(async_session, 1)
    for fighter in (fighter_a, fighter_b):
        await async_session.refresh(fighter)
        assert fighter.status == DwellerStatusEnum.FIGHTING
    assert state.fight_started_at is not None


@pytest.mark.parametrize("finished", [False, True])
async def test_snapshot_bounds_and_clears_journal_without_mutation(
    async_session, arena_room, vault, fighter_a, fighter_b, finished
):
    service = ArenaService()
    for fighter in (fighter_a, fighter_b):
        fighter.room_id = arena_room.id
        fighter.health = 19
    state = await configure_arena(
        async_session,
        arena_room,
        fighter_a_id=fighter_a.id,
        fighter_b_id=fighter_b.id,
        fight_started_at=utcnow(),
        last_fight_at=utcnow() if finished else None,
    )
    events = [
        ArenaMatchEvent(
            room_id=arena_room.id, round_seq=i, kind="hit", message=str(i), created_at=utcnow() + timedelta(seconds=i)
        )
        for i in range(45)
    ]
    async_session.add_all(events)
    await async_session.commit()
    before = (state.fight_started_at, state.last_fight_at, fighter_a.health, fighter_a.experience, vault.bottle_caps)
    # Task sessions are raw SQLAlchemy AsyncSessions, without .exec().
    async with RawAsyncSession(
        bind=async_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as raw:
        snapshot = await service.get_tick_snapshot(raw, vault.id)
    assert await service.get_tick_snapshot(async_session, vault.id) == snapshot
    room = snapshot["rooms"][0]
    assert (room["fight_started"], room["match_done"]) == (True, finished)
    assert [event["id"] for event in room["events"]] == [str(event.id) for event in events[-40:]]
    assert [event["round_seq"] for event in room["events"]] == list(range(5, 45))
    assert room["events"][0]["created_at"] == serialize_utc_datetime(events[5].created_at)
    api_room = (await service.get_arena_state(async_session, vault.id)).rooms[0]
    assert api_room.events[0].created_at == events[5].created_at.replace(tzinfo=UTC)
    assert await service.get_tick_snapshot(async_session, uuid4()) == {"rooms": []}
    assert (
        state.fight_started_at,
        state.last_fight_at,
        fighter_a.health,
        fighter_a.experience,
        vault.bottle_caps,
    ) == before
    assert await service.clear_journal(async_session, arena_room.id) == len(events)
    assert await _events(async_session, arena_room) == []
    assert (await service.get_tick_snapshot(async_session, vault.id))["rooms"][0]["events"] == []
    async_session.add(ArenaMatchEvent(room_id=arena_room.id, round_seq=1, kind="hit", message="new"))
    await async_session.commit()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    assert (await service.get_tick_snapshot(async_session, vault.id))["rooms"][0] == {
        "room_id": str(arena_room.id),
        "fight_started": False,
        "match_done": False,
        "events": [],
    }


async def test_idle_arena_occupants_do_not_earn_work_xp(async_session, arena_room, fighter_a):
    fighter_a.room_id = None
    await async_session.commit()
    await dweller_service.move_to_room(async_session, fighter_a.id, arena_room.id)
    before = fighter_a.experience
    result = await game_loop_service._process_dwellers(async_session, arena_room.vault_id)
    await async_session.refresh(fighter_a)
    assert (result["xp_awarded"], fighter_a.experience, fighter_a.status) == (0, before, DwellerStatusEnum.IDLE)


async def test_same_room_update_keeps_active_fighter_busy(async_session, arena_room, fighter_a, fighter_b):
    for fighter in (fighter_a, fighter_b):
        fighter.room_id = arena_room.id
        fighter.status = DwellerStatusEnum.IDLE
    await async_session.commit()
    service = ArenaService()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await service.start_fight(async_session, arena_room.id)
    await dweller_service.update_dweller(async_session, fighter_a.id, {"room_id": arena_room.id})
    await async_session.refresh(fighter_a)
    assert fighter_a.status == DwellerStatusEnum.FIGHTING
    assert (await arena_state_crud.get(async_session, arena_room.id)).fight_started_at is not None


async def test_batched_departures_do_not_restore_cleared_slots(async_session, arena_room, fighter_a, fighter_b):
    await _select(async_session, arena_room, fighter_a, fighter_b)
    service = ArenaService()
    await service.clear_fighter_slots_for_dweller(async_session, fighter_a.id, commit=False)
    await service.clear_fighter_slots_for_dweller(async_session, fighter_b.id, commit=False)
    await async_session.commit()
    state = await arena_state_crud.get(async_session, arena_room.id)
    assert (state.fighter_a_id, state.fighter_b_id) == (None, None)


@pytest.mark.parametrize(
    ("weapon_type", "subtype", "name", "area"),
    [
        ("melee", "blunt", "Crushing Blow", False),
        ("melee", "edged", "Cleave", True),
        ("melee", "pointed", "Piercing Strike", False),
        ("gun", "pistol", "Quick Draw", False),
        ("gun", "rifle", "Aimed Shot", False),
        ("gun", "shotgun", "Scattershot", True),
        ("energy", "pistol", "Overcharge", False),
        ("energy", "rifle", "Beam Sweep", True),
        ("heavy", "automatic", "Full Auto", False),
        ("heavy", "flamer", "Firestorm", True),
        ("heavy", "explosive", "Blast Wave", True),
    ],
)
def test_active_skill_uses_weapon_type_and_subtype(weapon_type, subtype, name, area):
    dweller = Dweller()
    data = {"name": "Arena test weapon", "weapon_type": weapon_type, "weapon_subtype": subtype}
    dweller.weapon = build_weapon(data, "common")
    skill = weapon_skill(dweller)
    assert (skill.name, skill.area, skill.icon) == (name, area, f"{weapon_type}-{subtype}")


def test_skill_icons_cover_the_weapon_catalog_and_unarmed():
    assert UNARMED_SKILL.icon == "unarmed"
    icons = {UNARMED_SKILL.icon}
    for data in load_weapons():
        dweller = Dweller()
        dweller.weapon = build_weapon(data, data["rarity"])
        skill = weapon_skill(dweller)
        assert skill.icon == f"{data['weapon_type'].lower()}-{data['weapon_subtype'].lower()}"
        icons.add(skill.icon)
    assert len(icons) == 12


async def test_skill_charge_persists_and_queued_attack_resolves_once(async_session, arena_room, fighter_a, fighter_b):
    for dweller in (fighter_a, fighter_b):
        dweller.max_health, dweller.perception = 1000, 5
    service = ArenaService()
    state = await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=60, health=(1000, 1000))
    for _ in range(13):
        await service.process_arena_ticks(async_session, 2)
    service = ArenaService()
    view = await _view(async_session, arena_room)
    assert (view.team_a[0].active_skill.charge, view.team_a[0].active_skill.name) == (100, "Haymaker")
    assert view.team_a[0].active_skill.icon == "unarmed"
    before = fighter_b.health
    await service.queue_skill(async_session, arena_room.id, fighter_a.id, arena_room.vault_id)
    assert state.skill_charge[str(fighter_a.id)] == 0
    with pytest.raises(ValidationException, match="already queued"):
        await service.queue_skill(async_session, arena_room.id, fighter_a.id, arena_room.vault_id)
    await service.process_arena_ticks(async_session, 2)
    assert state.queued_skill_ids == [str(fighter_a.id)]  # B's turn leaves A queued.
    assert fighter_b.health == before
    async with RawAsyncSession(
        bind=async_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as raw:
        await ArenaService().process_arena_ticks(raw, 2)
    await async_session.refresh(fighter_b)
    await async_session.refresh(state)
    assert fighter_b.health < before - int(combat_power(fighter_a) / 5 * 2)
    assert not state.queued_skill_ids
    await service.process_arena_ticks(async_session, 2)
    view = await _view(async_session, arena_room)
    skills = [event for event in view.events if event.kind == "skill"]
    assert len(skills) == 1
    assert any(
        event.kind == "hit" and event.round_seq == skills[0].round_seq and event.message.startswith("Arena hits")
        for event in view.events
    )
    assert view.team_a[0].active_skill.charge > 0
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    assert (state.skill_charge, state.queued_skill_ids) == (None, None)


@pytest.mark.parametrize("blocked", ["idle", "countdown", "uncharged", "foreign", "knocked_out", "finished", "wrong_vault"])
async def test_active_skill_rejects_invalid_actions(async_session, arena_room, fighter_a, fighter_b, blocked):
    await _place(async_session, arena_room, fighter_a, fighter_b)
    service = ArenaService()
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    state.skill_charge = {str(fighter_a.id): 100}
    if blocked != "idle":
        state.fight_started_at = utcnow() - timedelta(seconds=60)
    if blocked == "countdown":
        state.fight_started_at = utcnow()
    if blocked == "uncharged":
        state.skill_charge = None
    if blocked == "knocked_out":
        state.knocked_out_ids = [str(fighter_a.id)]
    if blocked == "finished":
        state.last_fight_at = utcnow()
    await async_session.commit()
    with pytest.raises(ValidationException):
        await service.queue_skill(
            async_session,
            arena_room.id,
            uuid4() if blocked == "foreign" else fighter_a.id,
            uuid4() if blocked == "wrong_vault" else arena_room.vault_id,
        )
    assert not state.queued_skill_ids


@pytest.mark.parametrize("area", [False, True])
async def test_active_skill_targeting_and_nonlethal_finish(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, area
):
    for dweller in (fighter_a, fighter_b, fighter_c):
        dweller.room_id = arena_room.id
    data = {"name": "Arena test weapon", "weapon_type": "gun", "weapon_subtype": "shotgun" if area else "rifle"}
    fighter_a.weapon = build_weapon(data, "common")
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id,
        mode=ArenaMode.BRAWL,
        fighter_c_id=fighter_c.id,
        team_b_bot_key="training-protectron",
    )
    state.skill_charge = {str(fighter_a.id): 100}
    state.fight_started_at = utcnow() - timedelta(seconds=60)
    await async_session.commit()
    await service.queue_skill(async_session, arena_room.id, fighter_a.id, arena_room.vault_id)
    team_a, team_b = await service.get_teams(async_session, arena_room)
    team_a[0].power = 1000
    team_a[1].power = 0
    for target in team_b:
        target.power = 0
    team_b[0].health = 1
    result = await service._resolve_round(async_session, arena_room, team_a, team_b, 2, state=state)
    assert fighter_b.health == 1
    assert team_b[1].health == (49 if area else 54)
    assert result["status"] == "ongoing"
    await finish_match(service, async_session, arena_room, team_a, team_b, state=state)
    await async_session.commit()
    view = await _view(async_session, arena_room)
    assert len([event for event in view.events if event.kind == "skill"]) == (2 if area else 1)
    skill_actions = [event.action for event in view.events if event.kind == "skill" and event.action]
    assert len(skill_actions) == 1
    assert (skill_actions[0].skill, skill_actions[0].skill_icon) == (
        "Scattershot" if area else "Aimed Shot",
        "gun-shotgun" if area else "gun-rifle",
    )
    assert len(skill_actions[0].targets) == (2 if area else 1)
    assert skill_actions[0].targets[0].health_after == 0
    assert skill_actions[0].targets[0].target_id == str(fighter_b.id)
    ordinary = [event.action for event in view.events if event.kind == "hit" and event.actor_id == str(fighter_a.id)]
    assert ordinary[0].targets[0].target_id == team_b[1].key
    assert view.match_done
    assert state.skill_charge is None
    assert fighter_b.health == 1


async def test_skill_endpoint_authorizes_vault_and_queues_once(
    async_session, async_client, superuser_token_headers, normal_user_token_headers, arena_room, fighter_a, fighter_b
):
    service = ArenaService()
    state = await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=60)
    state.skill_charge = {str(fighter_a.id): 100}
    await async_session.commit()
    url = f"/arena/vault/{arena_room.vault_id}/rooms/{arena_room.id}/skill"
    payload = {"fighter_id": str(fighter_a.id)}
    forbidden = await async_client.post(url, json=payload, headers=normal_user_token_headers)
    assert (forbidden.status_code, state.skill_charge[str(fighter_a.id)]) == (403, 100)
    accepted = await async_client.post(url, json=payload, headers=superuser_token_headers)
    assert accepted.status_code == 200
    assert accepted.json() == {"room_id": str(arena_room.id), "fighter_id": str(fighter_a.id)}
    repeated = await async_client.post(url, json=payload, headers=superuser_token_headers)
    assert (repeated.status_code, state.queued_skill_ids) == (400, [str(fighter_a.id)])


async def test_both_queued_skills_resolve_once_on_their_own_team_turn(async_session, arena_room, fighter_a, fighter_b):
    for dweller in (fighter_a, fighter_b):
        dweller.max_health = 1000
    service = ArenaService()
    state = await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=60, health=(1000, 1000))
    state.skill_charge = {str(fighter_a.id): 100, str(fighter_b.id): 100}
    await async_session.commit()
    for fighter in (fighter_a, fighter_b):
        await service.queue_skill(async_session, arena_room.id, fighter.id, arena_room.vault_id)

    await service.process_arena_ticks(async_session, 2)
    assert (fighter_a.health, fighter_b.health < 1000) == (1000, True)
    assert state.queued_skill_ids == [str(fighter_b.id)]
    after_a_turn = fighter_b.health

    # A new worker must preserve B's pending skill and the next attacking side.
    service = ArenaService()
    await service.process_arena_ticks(async_session, 2)
    assert (fighter_a.health < 1000, fighter_b.health) == (True, after_a_turn)
    assert not state.queued_skill_ids
    await service.process_arena_ticks(async_session, 2)
    view = await _view(async_session, arena_room)
    assert len([event for event in view.events if event.kind == "skill"]) == 2
    turns = [(index, event) for index, event in enumerate(view.events) if event.kind == "turn"]
    assert [event.message for _, event in turns] == ["Team A attacks", "Team B attacks", "Team A attacks"]
    for turn, next_turn in pairwise(turns):
        actions = view.events[turn[0] + 1 : next_turn[0]]
        assert [event.kind for event in actions].count("skill") == 1
        assert any(event.kind == "hit" for event in actions)
    assert not any(event.kind == "skill" for event in view.events[turns[-1][0] + 1 :])


@pytest.mark.parametrize(("perception", "expected"), [(1, 2.4), (5, 4.0), (10, 6.0)])
def test_skill_charge_rate_scales_with_perception(perception, expected):
    participant = ArenaParticipant(
        key="x", name="X", short_name="X", power=1, health=100, max_health=100, dweller=Dweller(perception=perception)
    )
    assert charge_per_second(participant) == pytest.approx(expected)


async def test_stop_fight_cancels_without_reward(async_session, arena_room, fighter_a, fighter_b):
    service = ArenaService()
    state = await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=10, health=(40, 30))
    state.skill_charge = {str(fighter_a.id): 50}
    await async_session.commit()

    await service.stop_fight(async_session, arena_room.id, arena_room.vault_id)
    for row in (state, fighter_a, fighter_b):
        await async_session.refresh(row)

    assert (state.fight_started_at, state.last_fight_at) == (None, None)
    assert (state.skill_charge, state.next_attack_team) == (None, "A")
    assert (fighter_a.health, fighter_b.health, fighter_a.status) == (40, 30, DwellerStatusEnum.IDLE)
    assert await _events(async_session, arena_room) == []
    with pytest.raises(ValidationException):
        await service.stop_fight(async_session, arena_room.id, arena_room.vault_id)


async def test_attack_events_include_actor_id(async_session, arena_room, fighter_a, fighter_b):
    service = ArenaService()
    await _live(async_session, arena_room, fighter_a, fighter_b, elapsed=10, health=(100, 100))
    await service.process_arena_ticks(async_session, 2)
    view = await _view(async_session, arena_room)
    attacks = [event for event in view.events if event.kind in ("hit", "skill")]
    assert attacks
    assert (attacks[0].actor_id, attacks[0].action is not None, attacks[0].action.actor_id) == (
        str(fighter_a.id),
        True,
        str(fighter_a.id),
    )
    impact = attacks[0].action.targets[0]
    assert impact.target_id == str(fighter_b.id)
    assert impact.health_before == 100
    assert impact.health_after == view.team_b[0].health
    assert impact.damage == impact.health_before - impact.health_after


async def test_arena_tick_failure_rolls_back_actions_damage_and_skill(
    async_session, arena_room, fighter_a, fighter_b, monkeypatch
):
    for dweller in (fighter_a, fighter_b):
        dweller.room_id = arena_room.id
        dweller.health = 100
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    state.fight_started_at = utcnow() - timedelta(seconds=60)
    state.skill_charge = {str(fighter_a.id): 100}
    await async_session.commit()
    await service.queue_skill(async_session, arena_room.id, fighter_a.id, arena_room.vault_id)
    fighter_id, state_id, actor_id, vault_id = fighter_b.id, state.room_id, str(fighter_a.id), arena_room.vault_id
    delivered = []

    async def record_delivery(*args):
        delivered.append(True)

    monkeypatch.setattr(NotificationService, "deliver_deferred_notifications", record_delivery)
    connection = (await async_session.connection()).sync_connection
    writes = set()

    def fail_after_writes(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO arena_match_event"):
            writes.add("action")
        if statement.startswith("UPDATE dweller") and "health" in statement:
            writes.add("health")
        if writes == {"action", "health"}:
            raise SQLAlchemyError("late tick failure")

    event.listen(connection, "after_cursor_execute", fail_after_writes)
    try:
        with pytest.raises(SQLAlchemyError, match="late tick failure"):
            await service.process_arena_ticks(async_session, 2)
    finally:
        event.remove(connection, "after_cursor_execute", fail_after_writes)
    await async_session.rollback()
    reloaded = await crud.dweller.get(async_session, fighter_id)
    reloaded_state = await arena_state_crud.get(async_session, state_id)
    assert reloaded.health == 100
    assert (reloaded_state.queued_skill_ids, reloaded_state.next_attack_team) == ([actor_id], "A")
    assert not delivered
    view = (await service.get_arena_state(async_session, vault_id)).rooms[0]
    assert not any(event.action for event in view.events)


async def test_round_snapshots_race_and_power_armor(async_session, arena_room, fighter_a, fighter_b):
    for fighter in (fighter_a, fighter_b):
        await async_session.refresh(fighter, ["weapon", "outfit"])
        fighter.health = fighter.max_health = 1000
    fighter_a.visual_attributes = {"race": "ghoul", "state_of_being": "sane"}
    fighter_b.visual_attributes = {"race": "super_mutant", "state_of_being": "behemoth"}
    data = next(data for data in load_outfits() if data["outfit_type"] == "power_armor")
    fighter_b.outfit = build_outfit(data, data["rarity"])
    async_session.add(fighter_b.outfit)
    await async_session.flush()
    a, b = [participant_from_dweller(fighter_a)], [participant_from_dweller(fighter_b)]
    await ArenaService()._resolve_round(async_session, arena_room, a, b, 10)
    await async_session.flush()
    events = await async_session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == arena_room.id))
    action = next(event.action for event in events.scalars() if event.action)
    assert (action["actor_body"], action["effect"], action["targets"][0]["body"]) == ("ghoul", "punch", "power-armor")


async def test_start_preset_assigns_newcomers_and_starts_two_bot_team(async_session, arena_room, fighter_a, fighter_b):
    source = await prepare_newcomers(async_session, arena_room, (fighter_a, fighter_b))
    service = ArenaService()
    view = await _view(async_session, arena_room)
    assert {entry.room_name for entry in view.candidates} == {source.name}
    assert all(
        entry.active_skill and entry.active_skill.icon == "unarmed" and entry.active_skill.charge == 0
        for entry in view.candidates
    )
    selection = ArenaFightersRequest(
        mode=ArenaMode.TRAINING,
        fighter_a_id=fighter_a.id,
        fighter_c_id=fighter_b.id,
        opponent_keys=["training-eyebot", "training-protectron"],
    )
    await service.start_fight(async_session, arena_room.id, arena_room.vault_id, selection=selection)
    for fighter in (fighter_a, fighter_b):
        await async_session.refresh(fighter)
        assert (fighter.room_id, fighter.status) == (arena_room.id, DwellerStatusEnum.FIGHTING)
    teams = await service.get_teams(async_session, arena_room)
    assert [len(team) for team in teams] == [2, 2]
    assert all(participant.is_robot for participant in teams[1])


@pytest.mark.parametrize("failure", ["capacity", "late_write"])
async def test_preset_start_failure_rolls_back_moves_and_match(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, monkeypatch, failure
):
    source = await prepare_newcomers(async_session, arena_room, (fighter_a, fighter_b))
    if failure == "capacity":
        arena_room.size = 3
        fighter_c.room_id = arena_room.id
        await async_session.commit()
    room_id, source_id = arena_room.id, source.id
    fighter_ids = [fighter_a.id, fighter_b.id]
    deliver = AsyncMock()
    monkeypatch.setattr(event_bus, "emit", deliver)
    connection = (await async_session.connection()).sync_connection
    moved = []

    def fail_late(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE dweller"):
            moved.append(True)
        if failure == "late_write" and moved and statement.startswith("UPDATE arena_state"):
            raise SQLAlchemyError("late lineup failure")

    event.listen(connection, "before_cursor_execute", fail_late)
    try:
        with pytest.raises(ResourceConflictException if failure == "capacity" else SQLAlchemyError):
            await ArenaService().start_fight(
                async_session,
                room_id,
                selection=ArenaFightersRequest(
                    mode=ArenaMode.TRAINING,
                    fighter_a_id=fighter_a.id,
                    fighter_c_id=fighter_b.id,
                    opponent_keys=["training-eyebot", "training-protectron"],
                ),
            )
    finally:
        event.remove(connection, "before_cursor_execute", fail_late)
    await async_session.rollback()
    for fighter_id in fighter_ids:
        reloaded = await crud.dweller.get(async_session, fighter_id)
        assert (reloaded.room_id, reloaded.status) == (source_id, DwellerStatusEnum.WORKING)
    state = await arena_state_crud.get(async_session, room_id)
    assert state is None or (state.fighter_a_id is None and state.fight_started_at is None)
    deliver.assert_not_called()


@pytest.mark.parametrize("invalid", ["child", "busy", "dead", "duplicate", "wrong_opponent", "cross_vault"])
async def test_new_preset_rejects_ineligible_lineup_without_moves(async_session, arena_room, fighter_a, fighter_b, invalid):
    source = await prepare_newcomers(async_session, arena_room, (fighter_a, fighter_b))
    if invalid == "child":
        fighter_b.age_group = AgeGroupEnum.CHILD
    elif invalid == "busy":
        fighter_b.status = DwellerStatusEnum.QUESTING
    elif invalid == "dead":
        fighter_b.is_dead = True
    elif invalid == "cross_vault":
        fighter_b.vault_id = None
    await async_session.commit()
    ids, source_id, room_id = [fighter_a.id, fighter_b.id], source.id, arena_room.id
    selection = ArenaFightersRequest(
        mode=ArenaMode.TRAINING,
        fighter_a_id=fighter_a.id,
        fighter_c_id=fighter_a.id if invalid == "duplicate" else fighter_b.id,
        opponent_keys=["deathclaw", "bloatfly"]
        if invalid == "wrong_opponent"
        else ["training-eyebot", "training-protectron"],
    )
    with pytest.raises(ValidationException):
        await ArenaService().start_fight(async_session, room_id, selection=selection)
    await async_session.rollback()
    assert [(await crud.dweller.get(async_session, id)).room_id for id in ids] == [source_id, source_id]
    assert await arena_state_crud.get(async_session, room_id) is None


async def test_bot_training_is_incomplete_after_a_fighter_leaves(async_session, arena_room, fighter_a, fighter_b):
    source = await prepare_newcomers(async_session, arena_room, (fighter_a, fighter_b))
    for fighter in (fighter_a, fighter_b):
        await dweller_service.move_to_room(async_session, fighter.id, arena_room.id)
    service = ArenaService()
    await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        None,
        mode=ArenaMode.TRAINING,
        fighter_c_id=fighter_b.id,
        opponent_keys=["training-eyebot", "training-protectron"],
    )
    await dweller_service.move_to_room(async_session, fighter_b.id, source.id)
    assert await service.get_teams(async_session, arena_room) == ([], [])
    with pytest.raises(ValidationException, match="Bot training needs two dwellers and two training bots"):
        await service.start_fight(async_session, arena_room.id)


async def test_arena_candidates_load_once_and_preserve_room_eligibility(
    async_session, arena_room, fighter_a, fighter_b, fighter_c
):
    second = Room(**arena_room.model_dump(exclude={"id", "created_at", "updated_at"}))
    second.coordinate_y = 2
    async_session.add(second)
    await async_session.flush()
    fighter_a.room_id, fighter_a.status = arena_room.id, DwellerStatusEnum.FIGHTING
    fighter_b.room_id, fighter_b.status = None, DwellerStatusEnum.IDLE
    fighter_c.room_id, fighter_c.status = second.id, DwellerStatusEnum.FIGHTING
    await async_session.commit()
    queries = []
    connection = (await async_session.connection()).sync_connection

    def count_candidates(conn, cursor, statement, parameters, context, executemany):
        if "dweller.status IN" in statement and "ORDER BY dweller.created_at" in statement:
            queries.append(statement)

    event.listen(connection, "before_cursor_execute", count_candidates)
    try:
        view = await ArenaService().get_arena_state(async_session, arena_room.vault_id)
    finally:
        event.remove(connection, "before_cursor_execute", count_candidates)
    candidates = {room.room_id: {entry.id for entry in room.candidates} for room in view.rooms}
    assert candidates[str(arena_room.id)] == {str(fighter_a.id), str(fighter_b.id)}
    assert candidates[str(second.id)] == {str(fighter_b.id), str(fighter_c.id)}
    assert len(queries) == 1


def test_damage_carry_isolated_by_room_and_reset_only_clears_its_room():
    service = ArenaService()
    attacker = ArenaParticipant(key="attacker", name="A", short_name="A", power=1, health=100, max_health=100)
    defender = ArenaParticipant(key="shared-fighter", name="B", short_name="B", power=1, health=100, max_health=100)
    for room in ("room-a", "room-b"):
        resolve_attacks([attacker], [defender], 2, set(), service._damage_carry.setdefault(room, {}))
    assert defender.health == 100
    service._clear_room_state("room-a")
    assert "room-a" not in service._damage_carry
    resolve_attacks([attacker], [defender], 2, set(), service._damage_carry["room-b"])
    resolve_attacks([attacker], [defender], 2, set(), service._damage_carry["room-b"])
    assert defender.health == 99
