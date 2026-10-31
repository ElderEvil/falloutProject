"""Tests for arena service logic — experimental dweller-vs-dweller fighting."""

from itertools import pairwise
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ArenaMode
from app.crud.arena_state import arena_state_crud
from app.models.arena_match_event import ArenaMatchEvent
from app.models.arena_state import ArenaState
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.catalog_service import load_enemies
from app.services.combat.arena_participants import (
    ArenaParticipant,
    charge_per_second,
    participant_from_dweller,
    persist_creature_hp,
)
from app.services.combat.arena_service import ArenaService
from app.services.combat.attack_service import resolve_attacks
from app.services.dweller_service import dweller_service
from app.utils.combat import combat_power
from app.utils.exceptions import ValidationException

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("image_url", [None, "/static/pet_images/custom-dog.png"])
async def test_arena_fighter_includes_equipped_pet_appearance(async_session, arena_room, fighter_a, image_url):
    fighter_a.room_id = arena_room.id
    async_session.add(fighter_a)
    await async_session.commit()
    await crud.pet.create(
        async_session,
        {
            "name": "CX404",
            "rarity": RarityEnum.COMMON,
            "value": 100,
            "dweller_id": fighter_a.id,
            "image_url": image_url,
        },
    )
    async_session.expire(fighter_a, ["pet"])
    service = ArenaService()
    await service.set_fighters(
        async_session, arena_room.id, fighter_a.id, None, mode=ArenaMode.HUNT, opponent_keys=["radroach-swarm"]
    )
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    assert view.team_a[0].pet.name == "CX404"
    assert view.team_a[0].pet.image_url == (image_url or "/static/pet_images/FOS CX404.png")
    assert len(view.team_a) == 1
    assert len(view.team_b) == 1
    assert view.team_b[0].pet is None


async def finish_match(service, session, room, team_a, team_b, *, state=None):
    """Play alternating turns until the reward/settlement boundary under test."""
    for _ in range(100):
        result = await service._resolve_round(session, room, team_a, team_b, 1000, state=state)
        if result["status"] == "finished":
            return result
    pytest.fail("Arena match did not settle")


def test_arena_catalog_replaces_raiders_with_training_robots():
    creatures = {creature["key"]: creature for creature in ArenaService.list_creatures()}
    assert "raider-gang" not in creatures
    assert creatures["training-eyebot"]["name"] == "Training Eyebot"
    assert creatures["training-mr-handy"]["name"] == "Training Mr. Handy"
    assert (creatures["training-eyebot"]["power"], creatures["training-eyebot"]["max_hp"]) == (30, 20)
    assert (creatures["training-mr-handy"]["power"], creatures["training-mr-handy"]["max_hp"]) == (20, 30)
    assert (creatures["training-protectron"]["power"], creatures["training-protectron"]["max_hp"]) == (10, 60)
    assert "Raider gang" in {enemy["name"] for enemy in load_enemies()}


def test_training_robots_are_valid_hunt_opponents():
    opponents = ArenaService._hunt_opponents(["training-eyebot", "training-mr-handy"])
    assert [opponent["name"] for opponent in opponents] == ["Training Eyebot", "Training Mr. Handy"]
    assert all(opponent["hp"] == opponent["max_hp"] > 0 for opponent in opponents)
    with pytest.raises(ValidationException, match="Unknown hunt opponent"):
        ArenaService._hunt_opponents(["raider-gang"])


def test_arena_wildlife_preserves_exploration_catalog_and_reserves_brahmin():
    creatures = {creature["key"]: creature for creature in ArenaService.list_creatures()}
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
    with pytest.raises(ValidationException, match="Unknown hunt opponent"):
        ArenaService._hunt_opponents(["brahmin"])


async def test_hunt_duplicate_enemy_labels_and_ids_survive_knockouts(async_session, arena_room, fighter_a):
    vault_id = arena_room.vault_id
    fighter_a.room_id = arena_room.id
    async_session.add(fighter_a)
    await async_session.commit()
    service = ArenaService()
    await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        None,
        mode=ArenaMode.HUNT,
        opponent_keys=["radroach-swarm", "radroach-swarm"],
    )
    before = (await service.get_arena_state(async_session, vault_id)).rooms[0].team_b
    expected = [("radroach-swarm#0", "Radroach swarm 1"), ("radroach-swarm#1", "Radroach swarm 2")]
    assert [(fighter.id, fighter.name) for fighter in before] == expected

    state = await arena_state_crud.get(async_session, arena_room.id)
    state.opponents = [{**entry, "hp": 0 if index == 0 else entry["hp"]} for index, entry in enumerate(state.opponents)]
    async_session.add(state)
    await async_session.commit()
    async_session.expire_all()

    after = (await ArenaService().get_arena_state(async_session, vault_id)).rooms[0].team_b
    assert [(fighter.id, fighter.name) for fighter in after] == expected
    assert after[0].health == 0
    assert after[1].health == before[1].health


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
    async_session,
    arena_room,
    fighter_a,
    fighter_c,
    monkeypatch,
    keys,
    two_dwellers,
    bot,
    knocked_out,
    xp_rate,
    expected,
):
    from app.core.game_config import game_config

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
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    reward = next(event.message for event in view.events if event.kind == "reward")
    for dweller, xp in zip(dwellers, expected, strict=True):
        assert f"{dweller.first_name} +{xp} XP" in reward
    assert "Eyebot +" not in reward
    assert (await service.process_arena_ticks(async_session, 3600))["arena"]["rounds"] == []
    for dweller, xp in zip(dwellers, expected, strict=True):
        await async_session.refresh(dweller)
        assert dweller.experience == xp


async def test_defeated_hunters_receive_no_xp(async_session, arena_room, fighter_a):
    fighter_a.room_id = arena_room.id
    fighter_a.experience = 0
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        None,
        mode=ArenaMode.HUNT,
        opponent_keys=["yao-guai"],
    )
    team_a, team_b = await service.get_teams(async_session, arena_room)
    team_a[0].power = 0
    team_a[0].health = 1
    state.next_attack_team = "B"
    assert (await service._resolve_round(async_session, arena_room, team_a, team_b, 2, state=state))[
        "status"
    ] == "finished"
    assert fighter_a.experience == 0
    await async_session.commit()
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    assert "XP" not in next(event.message for event in view.events if event.kind == "reward")


@pytest.mark.parametrize("mode", [ArenaMode.DUEL, ArenaMode.BRAWL])
async def test_dweller_matches_keep_existing_xp_per_winner(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, mode
):
    from app.core.game_config import game_config

    for dweller in (fighter_a, fighter_b, fighter_c, fighter_d):
        dweller.room_id = arena_room.id
        dweller.experience = 0
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id,
        mode=mode,
        fighter_c_id=fighter_c.id if mode == ArenaMode.BRAWL else None,
        fighter_d_id=fighter_d.id if mode == ArenaMode.BRAWL else None,
    )
    team_a, team_b = await service.get_teams(async_session, arena_room)
    team_a[0].power = 10000
    for participant in team_b:
        participant.power = 0
    await finish_match(service, async_session, arena_room, team_a, team_b, state=state)
    assert fighter_a.experience == game_config.combat.xp_per_difficulty * 2
    assert fighter_c.experience == (game_config.combat.xp_per_difficulty * 2 if mode == ArenaMode.BRAWL else 0)
    assert fighter_b.experience == fighter_d.experience == 0


@pytest_asyncio.fixture(name="arena_room")
async def arena_room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """Create an arena room for testing."""
    room_in = RoomCreate(
        name="Arena",
        category=RoomTypeEnum.ARENA,
        ability=SPECIALEnum.STRENGTH,
        base_cost=800,
        incremental_cost=200,
        t2_upgrade_cost=3000,
        t3_upgrade_cost=9000,
        size_min=6,
        size_max=6,
        tier=3,
        coordinate_x=0,
        coordinate_y=1,
        vault_id=vault.id,
    )
    return await crud_create_room(async_session, room_in)


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
    fighter_a.room_id = arena_room.id
    await async_session.commit()
    service = ArenaService()
    await service.set_fighters(
        async_session, arena_room.id, fighter_a.id, None, mode=ArenaMode.HUNT, opponent_keys=["deathclaw"]
    )
    # A complete legacy Hunt selection must not enable starting below tier 3.
    arena_room.tier = tier
    await async_session.commit()
    state = await service.get_arena_state(async_session, vault.id)
    assert state.rooms[0].available_modes == expected
    assert state.rooms[0].can_start is (tier == 3)
    assert state.rooms[0].fight_ready is (tier == 3)


async def test_arena_uses_dweller_display_name_and_portraits(async_session, arena_room, vault, fighter_a, fighter_b):
    fighter_a.last_name = None
    fighter_a.image_url = "/static/dweller_images/champ.png"
    fighter_a.thumbnail_url = "/static/dweller_images/champ-thumb.png"
    for fighter in (fighter_a, fighter_b):
        fighter.room_id = arena_room.id
    await async_session.commit()
    service = ArenaService()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    state = (await service.get_arena_state(async_session, vault.id)).rooms[0]
    for entry in [state.team_a[0], state.fighters[0], next(d for d in state.roster if d.id == str(fighter_a.id))]:
        assert entry.name == fighter_a.first_name
        assert entry.image_url == fighter_a.image_url
        assert entry.thumbnail_url == fighter_a.thumbnail_url


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
    for fighter in (fighter_a, fighter_b, fighter_c, fighter_d):
        fighter.room_id = arena_room.id
    await async_session.commit()
    service = ArenaService()
    await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id if mode == ArenaMode.BRAWL else None,
        mode=mode,
        fighter_c_id=fighter_c.id,
        fighter_d_id=fighter_d.id if mode == ArenaMode.BRAWL else None,
        opponent_keys=["radroach-swarm", "mole-rat-pack"] if mode == ArenaMode.HUNT else None,
    )
    async_session.add(
        ArenaMatchEvent(room_id=arena_room.id, kind="finish", message=f"{winner_label} defeated opponents!")
    )
    await async_session.commit()
    state = (await service.get_arena_state(async_session, vault.id)).rooms[0]
    winning_team = state.team_b if side_b_wins else state.team_a
    assert state.winner_name == " & ".join(fighter.name for fighter in winning_team)


async def crud_create_room(db_session: AsyncSession, room_in: RoomCreate) -> Room:
    from app import crud

    return await crud.room.create(db_session=db_session, obj_in=room_in)


async def configure_arena(db_session: AsyncSession, room: Room, **fields: object) -> ArenaState:
    state = await arena_state_crud.get_or_create(db_session, room.id)
    for key, value in fields.items():
        setattr(state, key, value)
    await db_session.commit()
    return state


@pytest_asyncio.fixture(name="fighter_a")
async def fighter_a_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Strong fighter."""
    from app import crud

    return await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Arena",
            last_name="Champ",
            vault_id=vault.id,
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=5,
            max_health=100,
            health=100,
            strength=10,
            perception=1,
            endurance=10,
            charisma=1,
            intelligence=1,
            agility=1,
            luck=1,
        ),
    )


@pytest_asyncio.fixture(name="fighter_b")
async def fighter_b_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Weak fighter."""
    from app import crud

    return await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Arena",
            last_name="Jobber",
            vault_id=vault.id,
            gender=GenderEnum.FEMALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=1,
            max_health=50,
            health=50,
            strength=1,
            perception=1,
            endurance=1,
            charisma=1,
            intelligence=1,
            agility=1,
            luck=1,
        ),
    )


@pytest_asyncio.fixture(name="fighter_c")
async def fighter_c_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Team A's second brawler."""
    return await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Arena",
            last_name="Second",
            vault_id=vault.id,
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=3,
            max_health=80,
            health=80,
            strength=3,
            endurance=3,
            agility=3,
        ),
    )


@pytest_asyncio.fixture(name="fighter_d")
async def fighter_d_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Team B's second brawler."""
    return await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Arena",
            last_name="Fourth",
            vault_id=vault.id,
            gender=GenderEnum.FEMALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=2,
            max_health=60,
            health=60,
            strength=2,
            endurance=2,
            agility=2,
        ),
    )


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestArenaService:
    @pytest.mark.asyncio
    async def test_fight_round_ongoing_keeps_both_fighters(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        # Preload weapon relationship (avoids lazy-load outside async greenlet)
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        service = ArenaService()
        result = await service._resolve_round(
            async_session,
            arena_room,
            [participant_from_dweller(fighter_a)],
            [participant_from_dweller(fighter_b)],
            1,
        )
        assert result["status"] == "ongoing"
        # Weak fighter takes far more damage
        assert fighter_a.health > fighter_b.health

    @pytest.mark.asyncio
    async def test_fight_round_finishes_and_rewards_winner(
        self, async_session, arena_room, fighter_a, fighter_b, vault
    ):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        # Strong fighter can survive the round, weak one cannot -> single KO
        fighter_a.health = 1200
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        service = ArenaService()
        result = await service._resolve_round(
            async_session,
            arena_room,
            [participant_from_dweller(fighter_a)],
            [participant_from_dweller(fighter_b)],
            1000,
        )
        assert result["status"] == "finished"
        assert result["winner"] == "Arena Champ"
        assert result["loser"] == "Arena Jobber"
        # Both stay standing (no death); the loser is left at 1 HP
        assert fighter_b.health == 1
        assert fighter_a.health >= 1
        # The match is marked done so it never re-runs until fighters are re-picked
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        assert arena_state.last_fight_at is not None
        # Winner gains happiness, loser loses it (uncommitted session state)
        assert fighter_a.happiness == 61  # 50 + 10 swing + 1 vault-wide morale
        assert fighter_b.happiness == 41  # 50 - 10 swing + 1 vault-wide morale

    @pytest.mark.asyncio
    async def test_process_arena_ticks_fights_once_then_stops(self, async_session, arena_room, fighter_a, fighter_b):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await configure_arena(
            async_session,
            arena_room,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
            fight_started_at=datetime.utcnow() - timedelta(seconds=10),
        )
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        await async_session.commit()
        service = ArenaService()
        result = await service.process_arena_ticks(async_session, 3600)
        assert result["arena"]["rooms"] == 1
        assert result["arena"]["rounds"]
        assert result["arena"]["rounds"][0]["status"] == "finished"
        # The room is done after one match: the next tick must not re-fight it
        result_2 = await service.process_arena_ticks(async_session, 3600)
        assert result_2["arena"]["rooms"] == 1
        assert result_2["arena"]["rounds"] == []

    @pytest.mark.asyncio
    async def test_arena_tick_respects_countdown(self, async_session, arena_room, fighter_a, fighter_b):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await configure_arena(
            async_session,
            arena_room,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
            fight_started_at=datetime.utcnow() - timedelta(seconds=1),
        )
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        await async_session.commit()
        service = ArenaService()
        # Still inside the 3s countdown: no combat yet
        result = await service.process_arena_ticks(async_session, 3600)
        assert result["arena"]["rounds"] == []

    @pytest.mark.asyncio
    async def test_start_fight_requires_two_adults(self, async_session, arena_room, fighter_a):
        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.start_fight(async_session, arena_room.id)

    @pytest.mark.asyncio
    async def test_start_fight_rejects_room_outside_vault(self, async_session, arena_room):
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.start_fight(async_session, arena_room.id, uuid4())

    @pytest.mark.asyncio
    async def test_start_fight_arms_room(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await configure_arena(async_session, arena_room, fighter_a_id=fighter_a.id, fighter_b_id=fighter_b.id)
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        await async_session.commit()
        service = ArenaService()
        room = await service.start_fight(async_session, arena_room.id)
        arena_state = await arena_state_crud.get(async_session, room.id)
        assert arena_state is not None
        assert arena_state.fight_started_at is not None
        # A second start is rejected
        with pytest.raises(ValidationException):
            await service.start_fight(async_session, arena_room.id)

    @pytest.mark.asyncio
    async def test_process_arena_ticks_skips_understaffed_room(self, async_session, arena_room, fighter_a):
        fighter_a.room_id = arena_room.id
        service = ArenaService()
        result = await service.process_arena_ticks(async_session, 60)
        assert result["arena"]["rooms"] == 1
        assert result["arena"]["rounds"] == []

    @pytest.mark.asyncio
    async def test_set_fighters_picks_and_resets_match(self, async_session, arena_room, fighter_a, fighter_b, vault):
        from datetime import datetime

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await configure_arena(
            async_session, arena_room, last_fight_at=datetime.utcnow(), fight_started_at=datetime.utcnow()
        )
        fighter_a.health = 40
        fighter_b.health = 1
        # Irradiate both fighters so effective_max_health differs from base max_health
        fighter_a.radiation = 20
        fighter_b.radiation = 10
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        await async_session.commit()

        service = ArenaService()
        room_arena_state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)

        await async_session.refresh(room_arena_state)
        assert room_arena_state.fighter_a_id == fighter_a.id
        assert room_arena_state.fighter_b_id == fighter_b.id
        assert room_arena_state.last_fight_at is None
        assert room_arena_state.fight_started_at is None
        await async_session.refresh(fighter_a)
        await async_session.refresh(fighter_b)
        assert fighter_a.health == 40
        assert fighter_b.health == 1
        assert (fighter_a.radiation, fighter_b.radiation) == (20, 10)

        # Regression (PR #534): get_arena_state must serialize effective_max_health
        # as max_health, or irradiated dwellers show wrong health ratios to clients.
        state = await service.get_arena_state(async_session, vault.id)
        room_state = state.rooms[0]
        fighters_by_id = {f.id: f for f in room_state.fighters}
        for fighter in (fighter_a, fighter_b):
            serialized = fighters_by_id[str(fighter.id)]
            assert serialized.health == fighter.health
            assert serialized.max_health == fighter.effective_max_health
            assert serialized.max_health != fighter.max_health
        roster_by_id = {r.id: r for r in room_state.roster}
        for fighter in (fighter_a, fighter_b):
            serialized = roster_by_id[str(fighter.id)]
            assert serialized.health == fighter.health
            assert serialized.max_health == fighter.effective_max_health
            assert serialized.max_health != fighter.max_health

    @pytest.mark.parametrize("mode", list(ArenaMode))
    async def test_assignment_and_repeated_selection_preserve_injuries(
        self, async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, mode
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

    @pytest.mark.asyncio
    async def test_set_fighters_rejects_dweller_not_in_room(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        await async_session.commit()
        service = ArenaService()
        # fighter_b is not assigned to the arena room
        with pytest.raises(ValidationException):
            await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)

    @pytest.mark.asyncio
    async def test_clear_journal_deletes_events(self, async_session, arena_room, fighter_a, fighter_b):
        from app.models.arena_match_event import ArenaMatchEvent

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        service = ArenaService()
        await service._resolve_round(
            async_session,
            arena_room,
            [participant_from_dweller(fighter_a)],
            [participant_from_dweller(fighter_b)],
            3600,
        )
        await async_session.commit()

        before = list(
            (await async_session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == arena_room.id)))
            .scalars()
            .all()
        )
        assert before

        cleared = await service.clear_journal(async_session, arena_room.id)
        assert cleared == len(before)

        after = list(
            (await async_session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == arena_room.id)))
            .scalars()
            .all()
        )
        assert after == []

    @pytest.mark.asyncio
    async def test_arena_slot_cleared_when_fighter_moved_out(
        self, async_session, arena_room, fighter_a, fighter_b, vault
    ):
        """A fighter leaving the arena room must not leave a stale slot behind.

        Regression: slots point at dwellers who moved out, so picking a new
        fighter sends the stale id along and set_fighters rejects the whole
        request with "Both fighters must be adult dwellers assigned to the Arena".
        """
        from datetime import datetime

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await configure_arena(
            async_session,
            arena_room,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
            fight_started_at=datetime.utcnow(),
        )
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        await async_session.commit()

        replacement = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(
                first_name="Arena",
                last_name="Replacement",
                vault_id=vault.id,
                gender=GenderEnum.MALE,
                rarity=RarityEnum.COMMON,
                age_group=AgeGroupEnum.ADULT,
                level=3,
                max_health=80,
                health=80,
                strength=5,
                endurance=5,
                agility=5,
            ),
        )
        replacement.room_id = arena_room.id
        await async_session.commit()

        other_room = await crud.room.create(
            async_session,
            obj_in=RoomCreate(
                name="Power Generator",
                category=RoomTypeEnum.PRODUCTION,
                ability=SPECIALEnum.STRENGTH,
                base_cost=100,
                incremental_cost=50,
                t2_upgrade_cost=500,
                t3_upgrade_cost=1500,
                size_min=3,
                size_max=6,
                coordinate_x=2,
                coordinate_y=1,
                vault_id=vault.id,
            ),
        )
        await dweller_service.move_to_room(async_session, dweller_id=fighter_a.id, room_id=other_room.id)

        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        assert arena_state.fighter_a_id is None
        assert arena_state.fighter_b_id == fighter_b.id
        assert arena_state.fight_started_at is None

        service = ArenaService()
        arena_state = await service.set_fighters(async_session, arena_room.id, replacement.id, fighter_b.id)
        assert arena_state.fighter_a_id == replacement.id

    @pytest.mark.asyncio
    async def test_resolve_round_1v1_alternates_with_full_damage(self, async_session, arena_room, fighter_a, fighter_b):
        for fighter in (fighter_a, fighter_b):
            fighter.room_id = arena_room.id
            await async_session.refresh(fighter, ["weapon", "outfit"])
        a, b = [participant_from_dweller(fighter_a)], [participant_from_dweller(fighter_b)]
        state = await configure_arena(async_session, arena_room, fighter_a_id=fighter_a.id, fighter_b_id=fighter_b.id)
        service = ArenaService()
        damage_b = min(combat_power(fighter_a) / 5, 50 * 0.05)
        await service._resolve_round(async_session, arena_room, a, b, 1, state=state)
        assert fighter_a.health == 100
        assert fighter_b.health == 50 - int(damage_b)
        assert service._damage_carry[str(arena_room.id)][str(fighter_b.id)] == pytest.approx(damage_b % 1)
        assert state.next_attack_team == "B"
        await async_session.commit()
        # A fresh worker resumes B rather than restarting with A.
        await async_session.refresh(state)
        damage_a = min(combat_power(fighter_b) / 5, 100 * 0.05)
        await ArenaService()._resolve_round(async_session, arena_room, a, b, 1, state=state)
        assert fighter_a.health == 100 - int(damage_a)
        assert fighter_b.health == 50 - int(damage_b)
        assert state.next_attack_team == "A"
        await async_session.commit()
        view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
        assert [event.message for event in view.events if event.kind == "turn"] == ["Team A attacks", "Team B attacks"]

    @pytest.mark.asyncio
    async def test_resolve_round_pairs_targets_and_preserves_fractional_carry(self, async_session, arena_room):
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

    @pytest.mark.asyncio
    async def test_resolve_round_defeated_creature_stops_dealing_damage(self, async_session, arena_room):
        service = ArenaService()
        hero = ArenaParticipant(key="hero", name="Hero", short_name="Hero", power=100.0, health=1000, max_health=1000)
        weak = ArenaParticipant(
            key="weak", name="Weak", short_name="Weak", power=50.0, health=1, max_health=100, is_creature=True
        )
        strong = ArenaParticipant(
            key="strong",
            name="Strong",
            short_name="Strong",
            power=100.0,
            health=1000,
            max_health=1000,
            is_creature=True,
        )

        await service._resolve_round(async_session, arena_room, [hero], [weak, strong], 1)
        assert weak.health == 0
        after_first = hero.health

        await service._resolve_round(async_session, arena_room, [hero], [weak, strong], 1)

        # Only the surviving creature attacks on B's turn.
        # Arena ordinary attacks deal 20% power per second.
        assert hero.health == after_first - 20

    @pytest.mark.asyncio
    async def test_brawl_knockout_keeps_fighter_alive_and_match_running(
        self, async_session, db_connection, arena_room, fighter_a, fighter_b, fighter_c, fighter_d
    ):
        from datetime import datetime, timedelta

        for fighter in (fighter_a, fighter_b, fighter_c, fighter_d):
            fighter.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            fighter_b.id,
            mode=ArenaMode.BRAWL,
            fighter_c_id=fighter_c.id,
            fighter_d_id=fighter_d.id,
        )
        fighter_a.health = 1000
        fighter_c.health = 1000
        fighter_b.health = 1
        fighter_d.health = 1000
        await configure_arena(async_session, arena_room, fight_started_at=datetime.utcnow() - timedelta(seconds=10))

        await service.process_arena_ticks(async_session, 1)
        await async_session.refresh(fighter_b)
        await async_session.refresh(fighter_d)

        # One knockout must not end the match early...
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        assert arena_state.last_fight_at is None
        # ...nor leave the dweller lethally at 0 HP (the vault health tick kills those).
        assert fighter_b.health >= 1
        assert fighter_d.health > 0

        # A fresh worker service and raw SQLAlchemy session still see the persisted KO.
        fresh = ArenaService()
        async with RawAsyncSession(
            bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as worker_session:
            team_a, team_b = await fresh.get_teams(worker_session, arena_room)
            assert len(team_a) == 2
            assert len(team_b) == 2
            knocked_out = next(p for p in team_b if p.key == str(fighter_b.id))
            assert knocked_out.health == 0

            # The next tick still resolves a round: a lone KO must not freeze the match.
            result = await fresh.process_arena_ticks(worker_session, 1)
            assert result["arena"]["rounds"]
            assert result["arena"]["rounds"][0]["status"] == "ongoing"

    @pytest.mark.asyncio
    async def test_resolve_round_team_defeat_reports_winner_and_loser(self, async_session, arena_room):
        service = ArenaService()
        hero = ArenaParticipant(key="hero", name="Hero One", short_name="Hero", power=100.0, health=100, max_health=100)
        ally = ArenaParticipant(key="ally", name="Ally Two", short_name="Ally", power=50.0, health=100, max_health=100)
        enemy = ArenaParticipant(key="enemy", name="Enemy", short_name="Enemy", power=1.0, health=10, max_health=10)

        result = await service._resolve_round(async_session, arena_room, [hero, ally], [enemy], 10)

        assert result["status"] == "finished"
        assert result["winner_id"] == "hero"
        assert result["winner"] == "Hero One"
        assert result["loser_id"] == "enemy"
        assert result["loser"] == "Enemy"
        assert enemy.health == 1
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        assert arena_state.last_fight_at is not None

    @pytest.mark.asyncio
    async def test_set_fighters_brawl_requires_four(self, async_session, arena_room, fighter_a, fighter_b, fighter_c):
        for fighter in (fighter_a, fighter_b, fighter_c):
            fighter.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                fighter_b.id,
                mode=ArenaMode.BRAWL,
                fighter_c_id=fighter_c.id,
            )

    @pytest.mark.asyncio
    async def test_set_fighters_duel_rejects_extra_slots(
        self, async_session, arena_room, fighter_a, fighter_b, fighter_c
    ):
        for fighter in (fighter_a, fighter_b, fighter_c):
            fighter.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                fighter_b.id,
                mode=ArenaMode.DUEL,
                fighter_c_id=fighter_c.id,
            )

    @pytest.mark.asyncio
    async def test_set_fighters_hunt_requires_a_dweller(self, async_session, arena_room):
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(
                async_session,
                arena_room.id,
                None,
                None,
                mode=ArenaMode.HUNT,
                opponent_keys=["radroach-swarm"],
            )

    @pytest.mark.asyncio
    async def test_set_fighters_hunt_rejects_dweller_on_creature_side(
        self, async_session, arena_room, fighter_a, fighter_b
    ):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                fighter_b.id,
                mode=ArenaMode.HUNT,
                opponent_keys=["radroach-swarm"],
            )

    @pytest.mark.asyncio
    async def test_set_fighters_hunt_rejects_unknown_opponent(self, async_session, arena_room, fighter_a):
        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                None,
                mode=ArenaMode.HUNT,
                opponent_keys=["firesnake"],
            )

    @pytest.mark.asyncio
    async def test_set_fighters_hunt_rejects_too_many_dwellers(
        self, async_session, arena_room, fighter_a, fighter_c, fighter_d
    ):
        for fighter in (fighter_a, fighter_c, fighter_d):
            fighter.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                None,
                mode=ArenaMode.HUNT,
                fighter_c_id=fighter_c.id,
                fighter_d_id=fighter_d.id,
                opponent_keys=["radroach-swarm"],
            )

    @pytest.mark.asyncio
    async def test_set_fighters_hunt_persists_opponents(self, async_session, arena_room, fighter_a, fighter_c):
        fighter_a.room_id = arena_room.id
        fighter_c.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        arena_state = await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            None,
            mode=ArenaMode.HUNT,
            fighter_c_id=fighter_c.id,
            opponent_keys=["radroach-swarm", "deathclaw"],
        )
        assert arena_state.mode == ArenaMode.HUNT
        assert arena_state.fighter_b_id is None
        assert arena_state.fighter_d_id is None
        assert [opponent["key"] for opponent in arena_state.opponents] == ["radroach-swarm", "deathclaw"]
        assert all(opponent["hp"] == opponent["max_hp"] for opponent in arena_state.opponents)
        assert arena_state.opponents[1]["power"] == 50

    @pytest.mark.asyncio
    async def test_set_fighters_rejects_duplicate_fighter(self, async_session, arena_room, fighter_a):
        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_a.id)

    @pytest.mark.asyncio
    async def test_set_fighters_rejects_non_adult(self, async_session, arena_room, fighter_a, vault):
        child = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(
                first_name="Arena",
                last_name="Kid",
                vault_id=vault.id,
                gender=GenderEnum.MALE,
                rarity=RarityEnum.COMMON,
                age_group=AgeGroupEnum.CHILD,
                level=1,
                max_health=50,
                health=50,
            ),
        )
        fighter_a.room_id = arena_room.id
        child.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        with pytest.raises(ValidationException):
            await service.set_fighters(async_session, arena_room.id, fighter_a.id, child.id)

    @pytest.mark.asyncio
    async def test_get_arena_state_duel_teams(self, async_session, arena_room, fighter_a, fighter_b, vault):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)

        room_state = (await service.get_arena_state(async_session, vault.id)).rooms[0]

        assert room_state.mode == "duel"
        assert [f.id for f in room_state.team_a] == [str(fighter_a.id)]
        assert [f.id for f in room_state.team_b] == [str(fighter_b.id)]
        assert [f.id for f in room_state.fighters] == [str(fighter_a.id), str(fighter_b.id)]
        assert room_state.can_start is True
        assert room_state.fight_ready is True

    @pytest.mark.asyncio
    async def test_get_arena_state_brawl_teams(
        self, async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d, vault
    ):
        for fighter in (fighter_a, fighter_b, fighter_c, fighter_d):
            fighter.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        arena_state = await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            fighter_b.id,
            mode=ArenaMode.BRAWL,
            fighter_c_id=fighter_c.id,
            fighter_d_id=fighter_d.id,
        )
        assert arena_state.mode == ArenaMode.BRAWL
        assert arena_state.fighter_c_id == fighter_c.id
        assert arena_state.fighter_d_id == fighter_d.id

        room_state = (await service.get_arena_state(async_session, vault.id)).rooms[0]

        assert room_state.mode == "brawl"
        assert [f.id for f in room_state.team_a] == [str(fighter_a.id), str(fighter_c.id)]
        assert [f.id for f in room_state.team_b] == [str(fighter_b.id), str(fighter_d.id)]
        assert [f.id for f in room_state.fighters] == [str(fighter_a.id), str(fighter_b.id)]
        assert room_state.can_start is True
        assert room_state.fight_ready is True

    @pytest.mark.asyncio
    async def test_get_arena_state_brawl_incomplete_not_ready(
        self, async_session, arena_room, fighter_a, fighter_b, vault
    ):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await configure_arena(
            async_session, arena_room, mode=ArenaMode.BRAWL, fighter_a_id=fighter_a.id, fighter_b_id=fighter_b.id
        )
        service = ArenaService()

        room_state = (await service.get_arena_state(async_session, vault.id)).rooms[0]

        assert room_state.mode == "brawl"
        assert room_state.team_a == []
        assert room_state.team_b == []
        assert room_state.can_start is False

    @pytest.mark.asyncio
    async def test_process_arena_ticks_brawl_resolves_winner(
        self, async_session, arena_room, fighter_a, fighter_b, fighter_c, fighter_d
    ):
        from datetime import datetime, timedelta

        for fighter in (fighter_a, fighter_b, fighter_c, fighter_d):
            fighter.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            fighter_b.id,
            mode=ArenaMode.BRAWL,
            fighter_c_id=fighter_c.id,
            fighter_d_id=fighter_d.id,
        )
        fighter_a.health = 1000
        fighter_c.health = 1000
        fighter_b.health = 1
        fighter_d.health = 1
        await configure_arena(async_session, arena_room, fight_started_at=datetime.utcnow() - timedelta(seconds=10))

        result = await service.process_arena_ticks(async_session, 5)

        assert result["arena"]["rooms"] == 1
        assert result["arena"]["rounds"][0]["status"] == "finished"
        assert result["arena"]["rounds"][0]["winner"] == "Arena Champ"
        await async_session.refresh(fighter_b)
        await async_session.refresh(fighter_d)
        assert fighter_b.health == 1
        assert fighter_d.health == 1
        state = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
        assert state.winner_name == f"{fighter_a.display_name} & {fighter_c.display_name}"
        assert next(event.message for event in state.events if event.kind == "finish") == "Team A defeated Team B!"

    @pytest.mark.asyncio
    async def test_get_arena_state_hunt_teams(self, async_session, arena_room, fighter_a, fighter_c, vault):
        fighter_a.room_id = arena_room.id
        fighter_c.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            None,
            mode=ArenaMode.HUNT,
            fighter_c_id=fighter_c.id,
            opponent_keys=["radroach-swarm", "mole-rat-pack"],
        )

        room_state = (await service.get_arena_state(async_session, vault.id)).rooms[0]

        assert room_state.mode == "hunt"
        assert [f.id for f in room_state.team_a] == [str(fighter_a.id), str(fighter_c.id)]
        assert [f.is_creature for f in room_state.team_a] == [False, False]
        assert [f.name for f in room_state.team_b] == ["Radroach swarm", "Mole Rat pack"]
        assert all(f.is_creature for f in room_state.team_b)
        assert [f.health for f in room_state.team_b] == [10, 20]
        assert [f.max_health for f in room_state.team_b] == [10, 20]
        assert [f.power for f in room_state.team_b] == [10, 20]
        assert room_state.can_start is True
        assert room_state.fight_ready is True

    @pytest.mark.asyncio
    async def test_get_arena_state_hunt_without_opponents_not_ready(self, async_session, arena_room, fighter_a, vault):
        fighter_a.room_id = arena_room.id
        await configure_arena(async_session, arena_room, mode=ArenaMode.HUNT, fighter_a_id=fighter_a.id)
        service = ArenaService()

        room_state = (await service.get_arena_state(async_session, vault.id)).rooms[0]

        assert room_state.mode == "hunt"
        assert room_state.team_a == []
        assert room_state.team_b == []
        assert room_state.can_start is False

    @pytest.mark.asyncio
    async def test_process_arena_ticks_hunt_defeats_creature(self, async_session, arena_room, fighter_a):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            None,
            mode=ArenaMode.HUNT,
            opponent_keys=["radroach-swarm"],
        )
        fighter_a.health = 100000
        await configure_arena(async_session, arena_room, fight_started_at=datetime.utcnow() - timedelta(seconds=10))

        result = await service.process_arena_ticks(async_session, 3600)

        assert result["arena"]["rounds"][0]["status"] == "finished"
        assert result["arena"]["rounds"][0]["winner"] == "Arena Champ"
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        assert arena_state.opponents[0]["hp"] == 0
        assert arena_state.last_fight_at is not None
        await async_session.refresh(fighter_a)
        assert fighter_a.health >= 1

    @pytest.mark.asyncio
    async def test_process_arena_ticks_hunt_dweller_floored_by_creature(self, async_session, arena_room, fighter_a):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            None,
            mode=ArenaMode.HUNT,
            opponent_keys=["deathclaw"],
        )
        fighter_a.health = 1
        await configure_arena(async_session, arena_room, fight_started_at=datetime.utcnow() - timedelta(seconds=10))

        first = await service.process_arena_ticks(async_session, 2)
        assert first["arena"]["rounds"][0]["status"] == "ongoing"
        result = await service.process_arena_ticks(async_session, 2)
        assert result["arena"]["rounds"][0]["status"] == "finished"
        assert result["arena"]["rounds"][0]["winner"] == "Deathclaw"
        await async_session.refresh(fighter_a)
        assert fighter_a.health == 1
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        # The creature survives and its damaged HP is not floored.
        assert arena_state is not None
        assert arena_state.opponents[0]["hp"] == 45

    @pytest.mark.asyncio
    async def test_process_arena_ticks_hunt_creature_hp_persists(self, async_session, arena_room, fighter_a):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            None,
            mode=ArenaMode.HUNT,
            opponent_keys=["radroach-swarm", "radroach-swarm"],
        )
        fighter_a.health = 100000
        await configure_arena(async_session, arena_room, fight_started_at=datetime.utcnow() - timedelta(seconds=10))

        await service.process_arena_ticks(async_session, 1)
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        first_hp = arena_state.opponents[0]["hp"]
        assert 0 < first_hp <= 10
        assert arena_state.last_fight_at is None

        await service.process_arena_ticks(async_session, 1)
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state.opponents[0]["hp"] == first_hp  # Only B attacks this turn.
        await service.process_arena_ticks(async_session, 2)
        assert 0 < arena_state.opponents[0]["hp"] < first_hp

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "opponent_keys",
        [
            ["radroach-swarm", "mole-rat-pack"],
            ["training-eyebot", "training-mr-handy"],
            ["bloatfly", "radstag"],
            ["night-stalker", "mirelurk"],
            ["yao-guai", "radstag"],
        ],
    )
    async def test_process_arena_ticks_hunt_two_creatures_defeated(
        self, async_session, arena_room, fighter_a, opponent_keys
    ):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            None,
            mode=ArenaMode.HUNT,
            opponent_keys=opponent_keys,
        )
        fighter_a.health = 100000
        await configure_arena(async_session, arena_room, fight_started_at=datetime.utcnow() - timedelta(seconds=10))

        for _ in range(3):
            result = await service.process_arena_ticks(async_session, 3600)

        assert result["arena"]["rounds"][0]["status"] == "finished"
        assert result["arena"]["rounds"][0]["winner"] == "Arena Champ"
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        assert [opponent["hp"] for opponent in arena_state.opponents] == [0, 0]
        state = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
        assert next(event.message for event in state.events if event.kind == "finish") == "Dwellers defeated Creatures!"


async def _morale_bystander(session: AsyncSession, vault_id, surname: str, happiness: int) -> Dweller:
    """An idle vault resident who never enters the arena."""
    dweller = await crud.dweller.create(
        db_session=session,
        obj_in=DwellerCreate(
            first_name="Morale",
            last_name=surname,
            vault_id=vault_id,
            gender=GenderEnum.FEMALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=1,
            max_health=100,
            health=100,
            strength=5,
            perception=5,
            endurance=5,
            charisma=5,
            intelligence=5,
            agility=5,
            luck=5,
        ),
    )
    dweller.happiness = happiness
    return dweller


class TestArenaMoraleBonus:
    """Vault-wide +1 morale on match completion (issue #999), through the real finish path."""

    @pytest.mark.asyncio
    async def test_finished_match_grants_morale_to_every_living_dweller(
        self, async_session, arena_room, fighter_a, fighter_b, vault
    ):
        """Winner/loser keep their ±10 swing and everyone — fighters included — gains +1."""
        for fighter in (fighter_a, fighter_b):
            fighter.room_id = arena_room.id
            fighter.happiness = 50
        bystander = await _morale_bystander(async_session, vault.id, "Bystander", 50)
        fighter_a.health = 1200
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        service = ArenaService()
        result = await service._resolve_round(
            async_session,
            arena_room,
            [participant_from_dweller(fighter_a)],
            [participant_from_dweller(fighter_b)],
            1000,
        )
        assert result["status"] == "finished"
        assert fighter_a.happiness == 61
        assert fighter_b.happiness == 41
        assert bystander.happiness == 51

    @pytest.mark.asyncio
    async def test_second_match_inside_cooldown_grants_nothing(
        self, async_session, arena_room, fighter_a, fighter_b, vault
    ):
        """A completion inside the vault-wide window keeps the ±10 swing but skips the +1."""
        from datetime import UTC, datetime

        vault.arena_morale_awarded_at = datetime.now(UTC).replace(tzinfo=None)
        async_session.add(vault)
        for fighter in (fighter_a, fighter_b):
            fighter.room_id = arena_room.id
            fighter.happiness = 50
        bystander = await _morale_bystander(async_session, vault.id, "Bystander", 50)
        fighter_a.health = 1200
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        service = ArenaService()
        result = await service._resolve_round(
            async_session,
            arena_room,
            [participant_from_dweller(fighter_a)],
            [participant_from_dweller(fighter_b)],
            1000,
        )
        assert result["status"] == "finished"
        assert fighter_a.happiness == 60
        assert fighter_b.happiness == 40
        assert bystander.happiness == 50

    @pytest.mark.asyncio
    async def test_morale_grant_clamps_at_100(self, async_session, arena_room, fighter_a, fighter_b, vault):
        """Nobody exceeds the dweller happiness cap when the swing and the bonus stack."""
        for fighter in (fighter_a, fighter_b):
            fighter.room_id = arena_room.id
        fighter_a.happiness = 95
        fighter_b.happiness = 50
        bystander = await _morale_bystander(async_session, vault.id, "Capped", 100)
        fighter_a.health = 1200
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        service = ArenaService()
        result = await service._resolve_round(
            async_session,
            arena_room,
            [participant_from_dweller(fighter_a)],
            [participant_from_dweller(fighter_b)],
            1000,
        )
        assert result["status"] == "finished"
        assert fighter_a.happiness == 100
        assert bystander.happiness == 100

    @pytest.mark.asyncio
    async def test_arena_tick_delivers_morale_toast_after_commit(
        self, async_session, arena_room, fighter_a, fighter_b, vault
    ):
        """The actual tick drains deferred notifications: the bell row gets its live toast."""
        from datetime import datetime, timedelta
        from unittest.mock import AsyncMock, patch

        from app.crud.notification import notification as notification_crud
        from app.services.notification_service import NotificationService

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await configure_arena(
            async_session,
            arena_room,
            fighter_a_id=fighter_a.id,
            fighter_b_id=fighter_b.id,
            fight_started_at=datetime.utcnow() - timedelta(seconds=10),
        )
        await async_session.refresh(fighter_a, ["weapon", "outfit"])
        await async_session.refresh(fighter_b, ["weapon", "outfit"])
        await async_session.commit()
        service = ArenaService()
        with patch.object(NotificationService, "_deliver", new=AsyncMock()) as deliver:
            result = await service.process_arena_ticks(async_session, 3600)
        assert result["arena"]["rounds"][0]["status"] == "finished"
        rows = await notification_crud.get_user_notifications(async_session, vault.user_id)
        morale = [row for row in rows if row.notification_type == "arena_morale_boost"]
        assert len(morale) == 1
        assert deliver.await_count == 1
        user_id, payload = deliver.await_args.args
        assert user_id == vault.user_id
        assert payload["notification"]["notification_type"] == "arena_morale_boost"


class TestArenaBotSupport:
    @pytest.mark.parametrize("mode", [ArenaMode.HUNT, ArenaMode.BRAWL])
    async def test_team_a_rejects_bots_in_every_mode(self, async_session, arena_room, fighter_a, fighter_b, mode):
        with pytest.raises(ValidationException, match="Team A only supports dweller"):
            await ArenaService().set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                fighter_b.id if mode == ArenaMode.BRAWL else None,
                mode=mode,
                team_a_bot_key="training-eyebot",
            )

    @pytest.mark.parametrize("robot", ["deathclaw", "unknown"])
    async def test_only_training_bots_can_assist(self, async_session, arena_room, fighter_a, robot):
        with pytest.raises(ValidationException, match="training bot"):
            await ArenaService().set_fighters(
                async_session, arena_room.id, fighter_a.id, None, mode=ArenaMode.BRAWL, team_b_bot_key=robot
            )

    async def test_dweller_and_bot_cannot_share_second_slot(self, async_session, arena_room, fighter_a, fighter_b):
        with pytest.raises(ValidationException, match="second slot"):
            await ArenaService().set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                None,
                mode=ArenaMode.BRAWL,
                fighter_d_id=fighter_b.id,
                team_b_bot_key="training-eyebot",
            )

    async def test_team_b_bot_health_survives_worker_reload(
        self, async_session, arena_room, fighter_a, fighter_b, fighter_c
    ):
        from datetime import datetime, timedelta

        for fighter in (fighter_a, fighter_b, fighter_c):
            fighter.room_id = arena_room.id
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
        await service.start_fight(async_session, arena_room.id)
        state.fight_started_at = datetime.utcnow() - timedelta(seconds=20)
        await async_session.commit()
        await service.process_arena_ticks(async_session, 2)
        _, team_b = await service.get_teams(async_session, arena_room)
        hp = team_b[1].health
        assert 0 < hp < 60
        async_session.expunge_all()
        room = await crud.room.get(async_session, arena_room.id)
        _, reloaded = await ArenaService().get_teams(async_session, room)
        assert reloaded[1].health == hp

    async def test_bots_are_not_allowed_in_duels(self, async_session, arena_room, fighter_a, fighter_b):
        with pytest.raises(ValidationException, match="only available"):
            await ArenaService().set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                fighter_b.id,
                team_b_bot_key="training-eyebot",
            )

    async def test_brawl_requires_two_team_a_dwellers_and_team_b_lead(self, async_session, arena_room, fighter_a):
        with pytest.raises(ValidationException, match="two Team A dwellers"):
            await ArenaService().set_fighters(
                async_session,
                arena_room.id,
                fighter_a.id,
                None,
                mode=ArenaMode.BRAWL,
                team_b_bot_key="training-protectron",
            )

    async def test_team_b_bot_resets_on_reselection(self, async_session, arena_room, fighter_a, fighter_b, fighter_c):
        for fighter in (fighter_a, fighter_b, fighter_c):
            fighter.room_id = arena_room.id
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
        assert len(a) == len(b) == 2
        assert all(p.dweller is not None for p in a)
        assert (b[1].name, b[1].power, b[1].health) == ("Training Eyebot", 30, 20)
        b[1].health = 0
        persist_creature_hp(state, a, b)
        await async_session.commit()
        _, b = await ArenaService().get_teams(async_session, arena_room)
        assert b[1].health == 0
        target = ArenaParticipant(
            key="target", name="Target", short_name="Target", power=0, health=10000, max_health=10000
        )
        attacks = resolve_attacks(b, [target], 2, set(), {})
        assert len(attacks) == 1
        assert attacks[0].action.actor_id == b[0].key
        assert attacks[0].action.targets[0].damage == int(b[0].power * 0.4)
        await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            fighter_b.id,
            mode=ArenaMode.BRAWL,
            fighter_c_id=fighter_c.id,
            team_b_bot_key="training-eyebot",
        )
        _, b = await service.get_teams(async_session, arena_room)
        assert b[1].health == 20
        await service.start_fight(async_session, arena_room.id)

    async def test_team_b_bot_win_rewards_only_its_dweller(
        self, async_session, arena_room, fighter_a, fighter_b, fighter_c
    ):
        from app.core.game_config import game_config

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
        for p in a:
            p.power = 0
            p.health = 1
        state.next_attack_team = "B"
        result = await finish_match(service, async_session, arena_room, a, b, state=state)
        assert result["winner_id"] in {p.key for p in b}
        assert fighter_b.experience == game_config.combat.xp_per_difficulty * 2
        assert fighter_a.experience == fighter_c.experience == 0
        assert fighter_b.happiness == 61
        assert await crud.dweller.count_in_room(async_session, arena_room.id) == 3

    async def test_legacy_robot_opponent_keeps_stats_and_gets_facing_metadata(
        self, async_session, arena_room, fighter_a
    ):
        fighter_a.room_id = arena_room.id
        await async_session.commit()
        service = ArenaService()
        state = await service.set_fighters(
            async_session,
            arena_room.id,
            fighter_a.id,
            None,
            mode=ArenaMode.HUNT,
            opponent_keys=["training-eyebot"],
        )
        state.opponents = [{"key": "training-eyebot", "name": "Training Eyebot", "power": 20, "max_hp": 20, "hp": 12}]
        await async_session.commit()
        _, opponents = await service.get_teams(async_session, arena_room)
        assert opponents[0].is_robot
        assert (opponents[0].power, opponents[0].health, opponents[0].max_health) == (20, 12, 20)


async def test_match_status_lifecycle(async_session, arena_room, fighter_a, fighter_b, fighter_c):
    from app.crud.dweller import determine_status_for_room

    assert determine_status_for_room(RoomTypeEnum.ARENA) == DwellerStatusEnum.IDLE
    for fighter in (fighter_a, fighter_b, fighter_c):
        fighter.room_id = arena_room.id
        fighter.status = DwellerStatusEnum.IDLE
    await async_session.commit()
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
    from datetime import datetime, timedelta

    from app.services.exit_request_service import exit_request_service

    service = ArenaService()
    fighters = (fighter_a, fighter_b, fighter_c, fighter_d)
    for fighter in fighters:
        fighter.room_id = arena_room.id
        fighter.status = DwellerStatusEnum.IDLE
        fighter.health = 100
        fighter.max_health = 100
        fighter.radiation = 7
    await async_session.commit()
    state = await service.set_fighters(
        async_session,
        arena_room.id,
        fighter_a.id,
        fighter_b.id if mode not in (ArenaMode.HUNT, ArenaMode.TRAINING) else None,
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
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=60)
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
        assert fighter.status == DwellerStatusEnum.IDLE
        assert fighter.radiation == 7
        assert fighter.health <= 100
    assert exit_request_service._eligibility_reason(fighter_a) is None
    injuries = [fighter.health for fighter in fighters]
    await service.process_arena_ticks(async_session, 3600)
    assert [fighter.health for fighter in fighters] == injuries


@pytest.mark.parametrize("departure", ["move", "unassign", "bulk_unassign"])
async def test_departure_cancels_match_and_releases_teammate(
    async_session, arena_room, fighter_a, fighter_b, departure
):
    from app.services.dweller_assignment_service import dweller_assignment_service

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
        target = await crud_create_room(
            async_session,
            RoomCreate(
                name="Power Generator",
                category=RoomTypeEnum.PRODUCTION,
                ability=SPECIALEnum.STRENGTH,
                base_cost=100,
                t2_upgrade_cost=500,
                t3_upgrade_cost=1500,
                size_min=3,
                size_max=9,
                vault_id=arena_room.vault_id,
            ),
        )
        await dweller_service.move_to_room(async_session, fighter_a.id, target.id)
    elif departure == "unassign":
        await dweller_service.update_dweller(async_session, fighter_a.id, {"room_id": None})
    else:
        await dweller_assignment_service.unassign_all_dwellers(async_session, arena_room.vault_id)
    state = await arena_state_crud.get(async_session, arena_room.id)
    assert state.fighter_a_id is None
    assert state.fight_started_at is None
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
    from datetime import datetime

    from app.core.enums import LifecycleEnum

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
        last_fight_at=datetime.utcnow() if completed else None,
    )
    for _ in range(2):
        await ArenaService().process_arena_ticks(async_session, 1)
        for fighter in (fighter_a, fighter_b, fighter_c):
            await async_session.refresh(fighter)
        assert fighter_a.status == DwellerStatusEnum.IDLE
        assert fighter_b.status == DwellerStatusEnum.EXPLORING
        assert fighter_c.status == DwellerStatusEnum.DEAD
        assert all(fighter.health == 17 and fighter.radiation == 4 for fighter in (fighter_a, fighter_b, fighter_c))
    assert (state.last_fight_at is not None) is completed


async def test_reconciliation_refreshes_newer_active_selection(
    async_session, db_connection, arena_room, fighter_a, fighter_b
):
    from datetime import datetime

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
    from datetime import datetime, timedelta

    service = ArenaService()
    for fighter in (fighter_a, fighter_b):
        fighter.room_id = arena_room.id
        fighter.health = 19
    state = await configure_arena(
        async_session,
        arena_room,
        fighter_a_id=fighter_a.id,
        fighter_b_id=fighter_b.id,
        fight_started_at=datetime.utcnow(),
        last_fight_at=datetime.utcnow() if finished else None,
    )
    events = [
        ArenaMatchEvent(
            room_id=arena_room.id,
            round_seq=i,
            kind="hit",
            message=str(i),
            created_at=datetime.utcnow() + timedelta(seconds=i),
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
    assert room["fight_started"] is True
    assert room["match_done"] is finished
    assert [event["id"] for event in room["events"]] == [str(event.id) for event in events[-40:]]
    assert [event["round_seq"] for event in room["events"]] == list(range(5, 45))
    from datetime import UTC

    assert room["events"][0]["created_at"] == events[5].created_at.replace(tzinfo=UTC).isoformat()
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
    await service.clear_journal(async_session, arena_room.id)
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
    from app.services.game_loop import game_loop_service

    fighter_a.room_id = None
    await async_session.commit()
    await dweller_service.move_to_room(async_session, fighter_a.id, arena_room.id)
    before = fighter_a.experience
    result = await game_loop_service._process_dwellers(async_session, arena_room.vault_id)
    await async_session.refresh(fighter_a)
    assert result["xp_awarded"] == 0
    assert fighter_a.experience == before
    assert fighter_a.status == DwellerStatusEnum.IDLE


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
    for fighter in (fighter_a, fighter_b):
        fighter.room_id = arena_room.id
    await async_session.commit()
    service = ArenaService()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await service.clear_fighter_slots_for_dweller(async_session, fighter_a.id, commit=False)
    await service.clear_fighter_slots_for_dweller(async_session, fighter_b.id, commit=False)
    await async_session.commit()
    state = await arena_state_crud.get(async_session, arena_room.id)
    assert state.fighter_a_id is None
    assert state.fighter_b_id is None


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
    from app.services.combat.weapon_skill import weapon_skill
    from app.utils.item_factory import build_weapon

    dweller = Dweller()
    dweller.weapon = build_weapon(
        {"name": "Arena test weapon", "weapon_type": weapon_type, "weapon_subtype": subtype}, "common"
    )
    skill = weapon_skill(dweller)
    assert (skill.name, skill.area) == (name, area)
    assert skill.icon == f"{weapon_type}-{subtype}"


def test_skill_icons_cover_the_weapon_catalog_and_unarmed():
    from app.services.catalog_service import load_weapons
    from app.services.combat.weapon_skill import UNARMED_SKILL, weapon_skill
    from app.utils.item_factory import build_weapon

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
    from datetime import datetime, timedelta

    for dweller in (fighter_a, fighter_b):
        dweller.room_id = arena_room.id
        dweller.health = dweller.max_health = 1000
        dweller.perception = 5
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await service.start_fight(async_session, arena_room.id)
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=60)
    await async_session.commit()
    for _ in range(13):
        await service.process_arena_ticks(async_session, 2)
    service = ArenaService()
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    assert view.team_a[0].active_skill.charge == 100
    assert view.team_a[0].active_skill.name == "Haymaker"
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
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    skills = [event for event in view.events if event.kind == "skill"]
    assert len(skills) == 1
    assert any(
        event.kind == "hit" and event.round_seq == skills[0].round_seq and event.message.startswith("Arena hits")
        for event in view.events
    )
    assert view.team_a[0].active_skill.charge > 0
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    assert state.skill_charge is None
    assert state.queued_skill_ids is None


@pytest.mark.parametrize(
    "blocked", ["idle", "countdown", "uncharged", "foreign", "knocked_out", "finished", "wrong_vault"]
)
async def test_active_skill_rejects_invalid_actions(async_session, arena_room, fighter_a, fighter_b, blocked):
    from datetime import datetime, timedelta

    for dweller in (fighter_a, fighter_b):
        dweller.room_id = arena_room.id
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    state.skill_charge = {str(fighter_a.id): 100}
    if blocked != "idle":
        state.fight_started_at = datetime.utcnow() - timedelta(seconds=60)
    if blocked == "countdown":
        state.fight_started_at = datetime.utcnow()
    if blocked == "uncharged":
        state.skill_charge = None
    if blocked == "knocked_out":
        state.knocked_out_ids = [str(fighter_a.id)]
    if blocked == "finished":
        state.last_fight_at = datetime.utcnow()
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
    from datetime import datetime, timedelta

    from app.utils.item_factory import build_weapon

    for dweller in (fighter_a, fighter_b, fighter_c):
        dweller.room_id = arena_room.id
    fighter_a.weapon = build_weapon(
        {"name": "Arena test weapon", "weapon_type": "gun", "weapon_subtype": "shotgun" if area else "rifle"}, "common"
    )
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
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=60)
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
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    assert len([event for event in view.events if event.kind == "skill"]) == (2 if area else 1)
    skill_actions = [event.action for event in view.events if event.kind == "skill" and event.action]
    assert len(skill_actions) == 1
    assert skill_actions[0].skill == ("Scattershot" if area else "Aimed Shot")
    assert skill_actions[0].skill_icon == ("gun-shotgun" if area else "gun-rifle")
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
    from datetime import datetime, timedelta

    for dweller in (fighter_a, fighter_b):
        dweller.room_id = arena_room.id
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=60)
    state.skill_charge = {str(fighter_a.id): 100}
    await async_session.commit()
    url = f"/arena/vault/{arena_room.vault_id}/rooms/{arena_room.id}/skill"
    payload = {"fighter_id": str(fighter_a.id)}
    forbidden = await async_client.post(url, json=payload, headers=normal_user_token_headers)
    assert forbidden.status_code == 403
    assert state.skill_charge[str(fighter_a.id)] == 100
    accepted = await async_client.post(url, json=payload, headers=superuser_token_headers)
    assert accepted.status_code == 200
    assert accepted.json() == {"room_id": str(arena_room.id), "fighter_id": str(fighter_a.id)}
    repeated = await async_client.post(url, json=payload, headers=superuser_token_headers)
    assert repeated.status_code == 400
    assert state.queued_skill_ids == [str(fighter_a.id)]


async def test_both_queued_skills_resolve_once_on_their_own_team_turn(async_session, arena_room, fighter_a, fighter_b):
    from datetime import datetime, timedelta

    for dweller in (fighter_a, fighter_b):
        dweller.room_id = arena_room.id
        dweller.health = dweller.max_health = 1000
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await service.start_fight(async_session, arena_room.id)
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=60)
    state.skill_charge = {str(fighter_a.id): 100, str(fighter_b.id): 100}
    await async_session.commit()
    for fighter in (fighter_a, fighter_b):
        await service.queue_skill(async_session, arena_room.id, fighter.id, arena_room.vault_id)

    await service.process_arena_ticks(async_session, 2)
    assert fighter_a.health == 1000
    assert fighter_b.health < 1000
    assert state.queued_skill_ids == [str(fighter_b.id)]
    after_a_turn = fighter_b.health

    # A new worker must preserve B's pending skill and the next attacking side.
    service = ArenaService()
    await service.process_arena_ticks(async_session, 2)
    assert fighter_a.health < 1000
    assert fighter_b.health == after_a_turn
    assert not state.queued_skill_ids
    await service.process_arena_ticks(async_session, 2)
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    skills = [event for event in view.events if event.kind == "skill"]
    assert len(skills) == 2
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
        key="x",
        name="X",
        short_name="X",
        power=1,
        health=100,
        max_health=100,
        dweller=Dweller(perception=perception),
    )
    assert charge_per_second(participant) == pytest.approx(expected)


async def test_stop_fight_cancels_without_reward(async_session, arena_room, fighter_a, fighter_b):
    from datetime import datetime, timedelta

    for dweller, health in ((fighter_a, 40), (fighter_b, 30)):
        dweller.room_id = arena_room.id
        dweller.health = health
        async_session.add(dweller)
    await async_session.commit()

    service = ArenaService()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await service.start_fight(async_session, arena_room.id)
    state = await arena_state_crud.get(async_session, arena_room.id)
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=10)
    state.skill_charge = {str(fighter_a.id): 50}
    await async_session.commit()

    await service.stop_fight(async_session, arena_room.id, arena_room.vault_id)
    await async_session.refresh(state)
    await async_session.refresh(fighter_a)
    await async_session.refresh(fighter_b)

    assert state.fight_started_at is None
    assert state.last_fight_at is None
    assert state.skill_charge is None
    assert state.next_attack_team == "A"
    assert fighter_a.health == 40
    assert fighter_b.health == 30
    assert fighter_a.status == DwellerStatusEnum.IDLE
    events = (
        (await async_session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == arena_room.id)))
        .scalars()
        .all()
    )
    assert events == []

    with pytest.raises(ValidationException):
        await service.stop_fight(async_session, arena_room.id, arena_room.vault_id)


async def test_attack_events_include_actor_id(async_session, arena_room, fighter_a, fighter_b):
    from datetime import datetime, timedelta

    for dweller in (fighter_a, fighter_b):
        dweller.room_id = arena_room.id
        dweller.health = 100
        async_session.add(dweller)
    await async_session.commit()

    service = ArenaService()
    await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    await service.start_fight(async_session, arena_room.id)
    state = await arena_state_crud.get(async_session, arena_room.id)
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=10)
    await async_session.commit()

    await service.process_arena_ticks(async_session, 2)
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
    attacks = [event for event in view.events if event.kind in ("hit", "skill")]
    assert attacks
    assert attacks[0].actor_id == str(fighter_a.id)
    assert attacks[0].action is not None
    assert attacks[0].action.actor_id == str(fighter_a.id)
    impact = attacks[0].action.targets[0]
    assert impact.target_id == str(fighter_b.id)
    assert impact.health_before == 100
    assert impact.health_after == view.team_b[0].health
    assert impact.damage == impact.health_before - impact.health_after


async def test_arena_tick_failure_rolls_back_actions_damage_and_skill(
    async_session, arena_room, fighter_a, fighter_b, monkeypatch
):
    from datetime import datetime, timedelta

    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError

    from app.services.notification_service import NotificationService

    for dweller in (fighter_a, fighter_b):
        dweller.room_id = arena_room.id
        dweller.health = 100
    await async_session.commit()
    service = ArenaService()
    state = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)
    state.fight_started_at = datetime.utcnow() - timedelta(seconds=60)
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
    assert reloaded_state.queued_skill_ids == [actor_id]
    assert reloaded_state.next_attack_team == "A"
    assert not delivered
    view = (await service.get_arena_state(async_session, vault_id)).rooms[0]
    assert not any(event.action for event in view.events)


async def test_round_snapshots_race_and_power_armor(async_session, arena_room, fighter_a, fighter_b):
    from app.services.catalog_service import load_outfits
    from app.utils.item_factory import build_outfit

    for fighter in (fighter_a, fighter_b):
        await async_session.refresh(fighter, ["weapon", "outfit"])
        fighter.health = fighter.max_health = 1000
    fighter_a.visual_attributes = {"race": "ghoul", "state_of_being": "sane"}
    fighter_b.visual_attributes = {"race": "super_mutant", "state_of_being": "behemoth"}
    data = next(data for data in load_outfits() if data["outfit_type"] == "power_armor")
    fighter_b.outfit = build_outfit(data, data["rarity"])
    async_session.add(fighter_b.outfit)
    await async_session.flush()
    await ArenaService()._resolve_round(
        async_session, arena_room, [participant_from_dweller(fighter_a)], [participant_from_dweller(fighter_b)], 10
    )
    await async_session.flush()
    events = (
        await async_session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == arena_room.id))
    ).scalars()
    action = next(event.action for event in events if event.action)
    assert action["actor_body"] == "ghoul"
    assert action["effect"] == "punch"
    assert action["targets"][0]["body"] == "power-armor"


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


async def test_start_preset_assigns_newcomers_and_starts_two_bot_team(async_session, arena_room, fighter_a, fighter_b):
    from app.schemas.arena import ArenaFightersRequest

    source = await prepare_newcomers(async_session, arena_room, (fighter_a, fighter_b))
    service = ArenaService()
    view = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
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
        assert fighter.room_id == arena_room.id
        assert fighter.status == DwellerStatusEnum.FIGHTING
    teams = await service.get_teams(async_session, arena_room)
    assert [len(team) for team in teams] == [2, 2]
    assert all(participant.is_robot for participant in teams[1])


@pytest.mark.parametrize("failure", ["capacity", "late_write"])
async def test_preset_start_failure_rolls_back_moves_and_match(
    async_session, arena_room, fighter_a, fighter_b, fighter_c, monkeypatch, failure
):
    from unittest.mock import AsyncMock

    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.event_bus import event_bus
    from app.schemas.arena import ArenaFightersRequest
    from app.utils.exceptions import ResourceConflictException

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
        assert reloaded.room_id == source_id
        assert reloaded.status == DwellerStatusEnum.WORKING
    state = await arena_state_crud.get(async_session, room_id)
    assert state is None or (state.fighter_a_id is None and state.fight_started_at is None)
    deliver.assert_not_called()


@pytest.mark.parametrize("invalid", ["child", "busy", "dead", "duplicate", "wrong_opponent", "cross_vault"])
async def test_new_preset_rejects_ineligible_lineup_without_moves(
    async_session, arena_room, fighter_a, fighter_b, invalid
):
    from app.schemas.arena import ArenaFightersRequest

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
    from sqlalchemy import event

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
