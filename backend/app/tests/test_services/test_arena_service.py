"""Tests for arena service logic — experimental dweller-vs-dweller fighting."""

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
from app.services.combat.arena_service import ArenaParticipant, ArenaService, participant_from_dweller
from app.services.dweller_service import dweller_service
from app.services.exploration.data_loader import load_enemies
from app.utils.combat import combat_power
from app.utils.exceptions import ValidationException

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def test_arena_catalog_replaces_raiders_with_training_robots():
    creatures = {creature["key"]: creature for creature in ArenaService.list_creatures()}
    assert "raider-gang" not in creatures
    assert creatures["training-eyebot"]["name"] == "Training Eyebot"
    assert creatures["training-mr-handy"]["name"] == "Training Mr. Handy"
    assert creatures["training-eyebot"]["power"] < creatures["training-mr-handy"]["power"]
    assert "Raider gang" in {enemy["name"] for enemy in load_enemies()}


def test_training_robots_are_valid_hunt_opponents():
    opponents = ArenaService._hunt_opponents(["training-eyebot", "training-mr-handy"])
    assert [opponent["name"] for opponent in opponents] == ["Training Eyebot", "Training Mr. Handy"]
    assert all(opponent["hp"] == opponent["max_hp"] > 0 for opponent in opponents)
    with pytest.raises(ValidationException, match="Unknown hunt opponent"):
        ArenaService._hunt_opponents(["raider-gang"])


def test_team_damage_ignores_knocked_out_attackers():
    team = [
        ArenaParticipant(key="down", name="Down", short_name="Down", power=100.0, health=0, max_health=100),
        ArenaParticipant(key="up", name="Up", short_name="Up", power=20.0, health=10, max_health=100),
    ]
    assert ArenaService._team_damage(team, 1) == pytest.approx(4.0)


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
    [(1, [ArenaMode.DUEL]), (2, [ArenaMode.DUEL, ArenaMode.BRAWL]), (3, list(ArenaMode))],
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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
        assert fighter_a.happiness == 60  # 50 + 10
        assert fighter_b.happiness == 40  # 50 - 10

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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
    async def test_process_arena_fights_skips_understaffed_room(self, async_session, arena_room, fighter_a, vault):
        fighter_a.room_id = arena_room.id
        service = ArenaService()
        result = await service.process_arena_fights(async_session, vault.id, 60)
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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
        assert fighter_a.health == fighter_a.effective_max_health
        assert fighter_b.health == fighter_b.effective_max_health

        # Regression (PR #534): get_arena_state must serialize effective_max_health
        # as max_health, or irradiated dwellers show wrong health ratios to clients.
        state = await service.get_arena_state(async_session, vault.id)
        room_state = state.rooms[0]
        fighters_by_id = {f.id: f for f in room_state.fighters}
        for fighter in (fighter_a, fighter_b):
            serialized = fighters_by_id[str(fighter.id)]
            assert serialized.max_health == fighter.effective_max_health
            assert serialized.max_health != fighter.max_health
        roster_by_id = {r.id: r for r in room_state.roster}
        for fighter in (fighter_a, fighter_b):
            serialized = roster_by_id[str(fighter.id)]
            assert serialized.max_health == fighter.effective_max_health
            assert serialized.max_health != fighter.max_health

    @pytest.mark.asyncio
    async def test_set_fighters_rejects_dweller_not_in_room(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
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
    async def test_resolve_round_1v1_matches_legacy_math(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        power_a = combat_power(fighter_a)
        power_b = combat_power(fighter_b)
        expected_a_damage = int(power_b / 5 * 1)
        expected_b_damage = int(power_a / 5 * 1)

        service = ArenaService()
        result = await service._resolve_round(
            async_session,
            arena_room,
            [participant_from_dweller(fighter_a)],
            [participant_from_dweller(fighter_b)],
            1,
        )

        assert result["status"] == "ongoing"
        assert result["fighter_a_hp"] == fighter_a.health
        assert result["fighter_b_hp"] == fighter_b.health
        assert fighter_a.health == max(0, 100 - expected_a_damage)
        assert fighter_b.health == max(0, 50 - expected_b_damage)
        assert service._damage_carry[(str(arena_room.id), str(fighter_a.id))] == power_b / 5 * 1 - expected_a_damage
        assert service._damage_carry[(str(arena_room.id), str(fighter_b.id))] == power_a / 5 * 1 - expected_b_damage

    @pytest.mark.asyncio
    async def test_resolve_round_focus_fire_spills_and_carries_per_member(self, async_session, arena_room):
        service = ArenaService()
        attacker = ArenaParticipant(
            key="hero", name="Hero One", short_name="Hero", power=43.5, health=100, max_health=100
        )
        weak = ArenaParticipant(key="weak", name="Weak", short_name="Weak", power=1.0, health=5, max_health=50)
        strong = ArenaParticipant(
            key="strong", name="Strong", short_name="Strong", power=1.0, health=200, max_health=200
        )
        expected_carry = 43.5 / 5 * 1 - int(43.5 / 5 * 1)

        result = await service._resolve_round(async_session, arena_room, [attacker], [weak, strong], 1)

        assert result["status"] == "ongoing"
        assert weak.health == 0
        assert strong.health == 197
        assert service._damage_carry[(str(arena_room.id), "weak")] == expected_carry

        await service._resolve_round(async_session, arena_room, [attacker], [weak, strong], 1)

        assert weak.health == 0
        assert strong.health == 189
        assert service._damage_carry[(str(arena_room.id), "strong")] == expected_carry

    @pytest.mark.asyncio
    async def test_resolve_round_defeated_creature_stops_dealing_damage(self, async_session, arena_room):
        service = ArenaService()
        hero = ArenaParticipant(key="hero", name="Hero", short_name="Hero", power=100.0, health=1000, max_health=1000)
        weak = ArenaParticipant(
            key="weak", name="Weak", short_name="Weak", power=50.0, health=5, max_health=5, is_creature=True
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

        # Only the surviving creature attacks: 100 / 5 = 20, not (100 + 50) / 5 = 30.
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

        result = await service.process_arena_ticks(async_session, 1)

        assert result["arena"]["rounds"][0]["status"] == "finished"
        assert result["arena"]["rounds"][0]["winner"] == "Deathclaw"
        await async_session.refresh(fighter_a)
        assert fighter_a.health == 1
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        # The creature survives and its damaged HP is not floored.
        assert arena_state is not None
        assert arena_state.opponents[0]["hp"] == 48

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
        assert 0 < first_hp < 10
        assert arena_state.last_fight_at is None

        await service.process_arena_ticks(async_session, 1)
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        second_hp = arena_state.opponents[0]["hp"]
        assert 0 < second_hp < first_hp

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "opponent_keys", [["radroach-swarm", "mole-rat-pack"], ["training-eyebot", "training-mr-handy"]]
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

        result = await service.process_arena_ticks(async_session, 3600)

        assert result["arena"]["rounds"][0]["status"] == "finished"
        assert result["arena"]["rounds"][0]["winner"] == "Arena Champ"
        arena_state = await arena_state_crud.get(async_session, arena_room.id)
        assert arena_state is not None
        assert [opponent["hp"] for opponent in arena_state.opponents] == [0, 0]
        state = (await service.get_arena_state(async_session, arena_room.vault_id)).rooms[0]
        assert next(event.message for event in state.events if event.kind == "finish") == "Dwellers defeated Creatures!"
