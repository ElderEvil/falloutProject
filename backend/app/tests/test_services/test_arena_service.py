"""Tests for arena service logic — experimental dweller-vs-dweller fighting."""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.arena_service import ArenaService
from app.utils.exceptions import ValidationException

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        coordinate_x=0,
        coordinate_y=1,
        vault_id=vault.id,
    )
    return await crud_create_room(async_session, room_in)


async def crud_create_room(db_session: AsyncSession, room_in: RoomCreate) -> Room:
    from app import crud

    return await crud.room.create(db_session=db_session, obj_in=room_in)


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


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestArenaService:
    def test_combat_power_scales_with_stats_and_level(self):
        service = ArenaService()
        dweller = Dweller(
            strength=10,
            endurance=10,
            agility=10,
            level=5,
            weapon=None,
        )
        power = service._combat_power(dweller)
        # stat contribution (10*0.4 + 10*0.3 + 10*0.3 = 10) + level (5*2 = 10)
        assert power == 20

    @pytest.mark.asyncio
    async def test_fight_round_ongoing_keeps_both_fighters(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        # Preload weapon relationship (avoids lazy-load outside async greenlet)
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        service = ArenaService()
        result = await service._run_round(async_session, arena_room, [fighter_a, fighter_b], 1)
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
        result = await service._run_round(async_session, arena_room, [fighter_a, fighter_b], 1000)
        assert result["status"] == "finished"
        assert result["winner"] == "Arena Champ"
        assert result["loser"] == "Arena Jobber"
        # Both stay standing (no death); the loser is left at 1 HP
        assert fighter_b.health == 1
        assert fighter_a.health >= 1
        # Room is marked done so the match never re-runs until fighters are re-picked
        assert arena_room.arena_last_fight_at is not None
        # Winner gains happiness, loser loses it (uncommitted session state)
        assert fighter_a.happiness == 60  # 50 + 10
        assert fighter_b.happiness == 40  # 50 - 10

    @pytest.mark.asyncio
    async def test_double_ko_uses_luck_roll(self, async_session, arena_room, fighter_a, fighter_b):
        from unittest.mock import patch

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        # Both will drop to 0 in the same round -> double KO
        fighter_a.health = 1
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        service = ArenaService()
        with patch("app.services.arena_service.random.choice", return_value=fighter_b) as mock_choice:
            result = await service._run_round(async_session, arena_room, [fighter_a, fighter_b], 3600)
        assert result["status"] == "finished"
        assert result["winner"] == "Arena Jobber"
        mock_choice.assert_called_once_with([fighter_a, fighter_b])

    @pytest.mark.asyncio
    async def test_process_arena_ticks_fights_once_then_stops(self, async_session, arena_room, fighter_a, fighter_b):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        arena_room.arena_fighter_a_id = fighter_a.id
        arena_room.arena_fighter_b_id = fighter_b.id
        arena_room.arena_fight_started_at = datetime.utcnow() - timedelta(seconds=10)
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
    async def test_arena_tick_skips_unarmed_room(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        arena_room.arena_fighter_a_id = fighter_a.id
        arena_room.arena_fighter_b_id = fighter_b.id
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        await async_session.commit()
        service = ArenaService()
        # No FIGHT button pressed: the tick must not fight the room
        result = await service.process_arena_ticks(async_session, 3600)
        assert result["arena"]["rounds"] == []

    @pytest.mark.asyncio
    async def test_arena_tick_respects_countdown(self, async_session, arena_room, fighter_a, fighter_b):
        from datetime import datetime, timedelta

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        arena_room.arena_fighter_a_id = fighter_a.id
        arena_room.arena_fighter_b_id = fighter_b.id
        arena_room.arena_fight_started_at = datetime.utcnow() - timedelta(seconds=1)
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
    async def test_start_fight_arms_room(self, async_session, arena_room, fighter_a, fighter_b):
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        arena_room.arena_fighter_a_id = fighter_a.id
        arena_room.arena_fighter_b_id = fighter_b.id
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        await async_session.commit()
        service = ArenaService()
        room = await service.start_fight(async_session, arena_room.id)
        assert room.arena_fight_started_at is not None
        # A second start is rejected
        with pytest.raises(ValidationException):
            await service.start_fight(async_session, arena_room.id)

    @pytest.mark.asyncio
    async def test_finish_writes_journal_events(self, async_session, arena_room, fighter_a, fighter_b):
        from app.models.arena_match_event import ArenaMatchEvent

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        service = ArenaService()
        result = await service._run_round(async_session, arena_room, [fighter_a, fighter_b], 3600)
        assert result["status"] == "finished"
        await async_session.commit()

        events_result = await async_session.execute(
            select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == arena_room.id)
        )
        events = list(events_result.scalars().all())
        kinds = [e.kind for e in events]
        assert "hit" in kinds
        assert "finish" in kinds
        assert "reward" in kinds
        assert any("happiness" in e.message for e in events)

    @pytest.mark.asyncio
    async def test_process_arena_fights_no_rooms(self, async_session, vault):
        service = ArenaService()
        result = await service.process_arena_fights(async_session, vault.id, 60)
        assert result["arena"]["rooms"] == 0
        assert result["arena"]["rounds"] == []

    @pytest.mark.asyncio
    async def test_process_arena_fights_skips_understaffed_room(self, async_session, arena_room, fighter_a, vault):
        fighter_a.room_id = arena_room.id
        service = ArenaService()
        result = await service.process_arena_fights(async_session, vault.id, 60)
        assert result["arena"]["rooms"] == 1
        assert result["arena"]["rounds"] == []

    @pytest.mark.asyncio
    async def test_set_fighters_picks_and_resets_match(self, async_session, arena_room, fighter_a, fighter_b):
        from datetime import datetime

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        arena_room.arena_last_fight_at = datetime.utcnow()
        arena_room.arena_fight_started_at = datetime.utcnow()
        fighter_a.health = 40
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        await async_session.commit()

        service = ArenaService()
        room = await service.set_fighters(async_session, arena_room.id, fighter_a.id, fighter_b.id)

        await async_session.refresh(room)
        assert room.arena_fighter_a_id == fighter_a.id
        assert room.arena_fighter_b_id == fighter_b.id
        assert room.arena_last_fight_at is None
        assert room.arena_fight_started_at is None
        await async_session.refresh(fighter_a)
        await async_session.refresh(fighter_b)
        assert fighter_a.health == fighter_a.max_health
        assert fighter_b.health == fighter_b.max_health

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
    async def test_ticks_fight_only_selected_pair(self, async_session, arena_room, fighter_a, fighter_b, vault):
        from datetime import datetime, timedelta

        # A third dweller parked in the arena but NOT selected as a fighter
        bystander = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(
                first_name="Bystander",
                last_name="Watcher",
                vault_id=vault.id,
                gender=GenderEnum.MALE,
                rarity=RarityEnum.COMMON,
                age_group=AgeGroupEnum.ADULT,
                level=5,
                max_health=100,
                health=100,
                strength=10,
                endurance=10,
                agility=10,
            ),
        )
        bystander.room_id = arena_room.id
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        arena_room.arena_fighter_a_id = fighter_a.id
        arena_room.arena_fighter_b_id = fighter_b.id
        arena_room.arena_fight_started_at = datetime.utcnow() - timedelta(seconds=10)
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        await async_session.commit()

        service = ArenaService()
        result = await service.process_arena_ticks(async_session, 3600)
        assert result["arena"]["rounds"]
        await async_session.refresh(bystander)
        assert bystander.health == 100  # untouched

    @pytest.mark.asyncio
    async def test_clear_journal_deletes_events(self, async_session, arena_room, fighter_a, fighter_b):
        from app.models.arena_match_event import ArenaMatchEvent

        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        fighter_b.health = 1
        await async_session.refresh(fighter_a, ["weapon"])
        await async_session.refresh(fighter_b, ["weapon"])
        service = ArenaService()
        await service._run_round(async_session, arena_room, [fighter_a, fighter_b], 3600)
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
        fighter_a.room_id = arena_room.id
        fighter_b.room_id = arena_room.id
        arena_room.arena_fighter_a_id = fighter_a.id
        arena_room.arena_fighter_b_id = fighter_b.id
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
        await crud.dweller.move_to_room(async_session, dweller_id=fighter_a.id, room_id=other_room.id)

        await async_session.refresh(arena_room)
        assert arena_room.arena_fighter_a_id is None
        assert arena_room.arena_fighter_b_id == fighter_b.id

        service = ArenaService()
        room = await service.set_fighters(async_session, arena_room.id, replacement.id, fighter_b.id)
        assert room.arena_fighter_a_id == replacement.id
