"""Game loop service: pause/resume, tick phases, relationship drift, births, aging.

Names imported *inside* a method are patched at their source module; module-level
imports can be patched on ``app.services.game_loop_service``.
"""

import asyncio
import logging
from contextlib import ExitStack, asynccontextmanager, contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    AgeGroupEnum,
    DwellerStatusEnum,
    OutfitTypeEnum,
    RarityEnum,
    RelationshipTypeEnum,
    RoomTypeEnum,
    SPECIALEnum,
    TrainingStatus,
)
from app.core.game_config import game_config
from app.crud import training as training_crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.notification import Notification
from app.models.outfit import Outfit
from app.models.training import Training
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.vault import ResourceTickEvents
from app.services.dweller_service import dweller_service
from app.services.game_loop_service import game_loop_service
from app.services.game_tick.family_tick import _deliver_due_baby
from app.services.relationship_service import relationship_service
from app.services.training_service import training_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.rooms import create_fake_room
from app.utils.exceptions import NoLivingSpaceError, VaultOperationException
from app.utils.time import utcnow


async def _make_room(session, vault, *, name="Weight room", category=RoomTypeEnum.TRAINING, **extra):
    data = create_fake_room() | {"name": name, "category": category, "ability": SPECIALEnum.STRENGTH, **extra}
    return await crud.room.create(session, RoomCreate(**data, vault_id=vault.id))


async def _make_dweller(session, vault, *, room=None, name=None, **fields):
    data = create_fake_dweller() | fields
    if name is not None:
        data["first_name"] = name
    dweller = await crud.dweller.create(session, DwellerCreate(**data, vault_id=vault.id))
    if room is not None:
        dweller.room_id = room.id
        session.add(dweller)
    return dweller


@asynccontextmanager
async def _one_shot_db_failure(async_session, predicate, broken_sql):
    """Make the first statement matching ``predicate`` hit a missing table."""
    connection = await async_session.connection()
    state = {"failed": False}

    def hook(_conn, _cursor, statement, parameters, _context, _many):
        if predicate(statement) and not state["failed"]:
            state["failed"] = True
            return broken_sql, ()
        return statement, parameters

    event.listen(connection.sync_connection, "before_cursor_execute", hook, retval=True)
    try:
        yield state
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", hook)


_PAIR = {"happiness": 50, "charisma": 5, "age_group": AgeGroupEnum.ADULT}


async def _link(session, first, second, affinity=10):
    relationship = await relationship_service.get_or_create_relationship(session, first.id, second.id)
    relationship.affinity = affinity
    session.add(relationship)
    await session.commit()
    return relationship


@contextmanager
def _active_vaults(vaults, fake_tick):
    with (
        patch.object(game_loop_service, "_get_active_vaults", new=AsyncMock(return_value=vaults)),
        patch.object(game_loop_service, "process_vault_tick", new=fake_tick),
    ):
        yield


def _pair_mocks():
    rel = MagicMock(dweller_1_id="d-1", dweller_2_id="d-2")
    d1, d2 = MagicMock(id="d-1", charisma=5), MagicMock(id="d-2", charisma=5)
    return d1, d2, {("d-1", "d-2"): rel, ("d-2", "d-1"): rel}


class TestPauseResume:
    async def test_resume_and_status_contract(self, async_session, vault):
        await game_loop_service.pause_vault(async_session, vault.id)
        result = await game_loop_service.resume_vault(async_session, vault.id)
        assert result.is_paused is False
        assert result.resumed_at is not None

        await game_loop_service.process_vault_tick(async_session, vault.id)
        status = await game_loop_service.get_vault_status(async_session, vault.id)
        assert status["vault_id"] == str(vault.id)
        assert status["is_active"] is True
        assert status["is_paused"] is False
        assert {"total_game_time", "last_tick_time", "offline_time"} <= status.keys()


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


def _fake_session_maker():
    return _FakeSession()


class TestProcessGameTick:
    async def test_skips_paused_vaults_and_counts_errors(self, async_session, session_factory, vault):
        await game_loop_service.pause_vault(async_session, vault.id)
        with patch.object(game_loop_service, "process_vault_tick", new_callable=AsyncMock) as mock_tick:
            stats = await game_loop_service.process_game_tick(session_factory)
            mock_tick.assert_not_called()
        assert {"vaults_processed", "errors", "total_time"} <= stats.keys()

        await game_loop_service.resume_vault(async_session, vault.id)
        with patch.object(game_loop_service, "process_vault_tick", new_callable=AsyncMock) as mock_tick:
            mock_tick.side_effect = VaultOperationException("Simulated error")
            stats = await game_loop_service.process_game_tick(session_factory)
            assert stats["errors"] >= 1

    async def test_runs_vaults_with_bounded_parallelism(self):
        vaults = [SimpleNamespace(id=uuid4()) for _ in range(6)]
        active = max_active = 0
        sessions = []

        async def fake_tick(session, _vault_id):
            nonlocal active, max_active
            sessions.append(session)
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1

        with _active_vaults(vaults, fake_tick):
            stats = await game_loop_service.process_game_tick(_fake_session_maker, max_concurrency=3)

        assert max_active == 3
        assert len({id(session) for session in sessions}) == len(vaults)
        assert stats["vaults_processed"] == len(vaults)
        assert stats["errors"] == 0

    @pytest.mark.parametrize("scenario", ["isolated", "unexpected", "logged"])
    async def test_vault_failure_handling(self, caplog, scenario):
        vaults = [SimpleNamespace(id=uuid4()) for _ in range(3)]
        processed: list = []

        async def fake_tick(_session, vault_id):
            if scenario == "logged":
                raise RuntimeError(f"boom {vault_id}")
            if vault_id == vaults[0].id:
                if scenario == "isolated":
                    raise VaultOperationException("Simulated failure")
                raise RuntimeError("boom")
            if scenario == "unexpected":
                await asyncio.sleep(0.01)
            processed.append(vault_id)

        stack = ExitStack()
        stack.enter_context(_active_vaults(vaults, fake_tick))
        if scenario == "isolated":
            stack.enter_context(patch("app.services.game_loop_service.recover_session", new=AsyncMock()))
        else:
            stack.enter_context(caplog.at_level(logging.ERROR, logger="app.services.game_loop_service"))
            stack.enter_context(pytest.raises(RuntimeError, match="boom"))
        with stack:
            result = await game_loop_service.process_game_tick(_fake_session_maker, max_concurrency=2)

        if scenario == "logged":
            logged = [r.getMessage() for r in caplog.records if "Unexpected error processing vault" in r.getMessage()]
            assert len(logged) == 2
            return
        assert sorted(processed) == sorted(v.id for v in vaults[1:])
        if scenario == "isolated":
            assert result["vaults_processed"] == 2
            assert result["errors"] == 1


class TestProcessVaultTick:
    async def _patched_tick(self, async_session, vault, resource_error=None):
        """Run process_vault_tick with all internal phases mocked."""
        update = MagicMock(power=100, food=50, water=75)
        with (
            patch.object(game_loop_service.resource_manager, "process_vault_resources", new_callable=AsyncMock) as mr,
            patch.object(game_loop_service, "_process_dwellers", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_training", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_happiness", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_breeding", new_callable=AsyncMock, return_value={}),
        ):
            mr.return_value = (update, ResourceTickEvents())
            mr.side_effect = resource_error
            return await game_loop_service.process_vault_tick(async_session, vault.id)

    async def test_caps_offline_time(self, async_session, vault):
        gs = await game_loop_service._get_or_create_game_state(async_session, vault.id)
        gs.last_tick_time = utcnow() - timedelta(hours=2)
        async_session.add(gs)
        await async_session.commit()
        result = await self._patched_tick(async_session, vault)
        assert result["seconds_passed"] <= 3600

    async def test_resource_error_does_not_propagate(self, async_session, vault):
        # The resource phase catches SQLAlchemyError, ResourceNotFoundException and VaultOperationException.
        error = VaultOperationException("Resource processing failed")
        result = await self._patched_tick(async_session, vault, resource_error=error)
        assert "error" in result["updates"]["resources"]


class TestProcessDwellers:
    @pytest.mark.parametrize(("dead", "expected"), [(True, 0), (False, 1)], ids=["already_dead", "health_zero"])
    async def test_death_handling(self, async_session, vault, dweller, dead, expected):
        if dead:
            dweller.is_dead = True
            dweller.status = DwellerStatusEnum.DEAD
        else:
            dweller.health = 0
        async_session.add(dweller)
        await async_session.commit()
        with patch(
            "app.services.family.death_service.death_service.mark_as_dead", new_callable=AsyncMock
        ) as mock_death:
            result = await game_loop_service._process_dwellers(async_session, vault.id)
        assert mock_death.await_count == expected
        assert result["deaths"] == expected

    async def test_awards_xp_to_working_dwellers(self, async_session, vault):
        room = await _make_room(
            async_session, vault, name="Power Gen", category=RoomTypeEnum.PRODUCTION, capacity=4, size=2
        )
        dweller = await _make_dweller(async_session, vault, strength=5, health=100, radiation=0)
        await dweller_service.move_to_room(async_session, dweller.id, room.id)
        await async_session.commit()
        with (
            patch("app.services.family.death_service.death_service.mark_as_dead", new_callable=AsyncMock),
            patch(
                "app.services.leveling_service.leveling_service.check_level_up",
                new=AsyncMock(return_value=(False, 0)),
            ),
        ):
            result = await game_loop_service._process_dwellers(async_session, vault.id)
        assert result["xp_awarded"] > 0


class TestDehydrationRadiation:
    """Deprivation radiation is driven by persisted counters and stops at the quarter-health floor."""

    async def _prepare(self, async_session, vault, dweller, water, *, water_deprived_minutes=0, radiation=0):
        vault.water = water
        vault.food = max(vault.food_max, 100)
        dweller.max_health = 100
        dweller.health = 100
        dweller.radiation = radiation
        async_session.add_all(
            [vault, dweller, GameState(vault_id=vault.id, water_deprived_ms=water_deprived_minutes * 60_000)]
        )
        await async_session.commit()

    async def test_away_dwellers_are_exempt(self, async_session, vault, dweller):
        await self._prepare(async_session, vault, dweller, water=0, water_deprived_minutes=40)
        dweller.status = DwellerStatusEnum.EXPLORING
        async_session.add(dweller)
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id)
        assert result["irradiated"] == 0
        await async_session.refresh(dweller)
        assert dweller.radiation == 0

    @pytest.mark.parametrize(
        ("max_health", "radiation_start", "deprived_minutes", "seconds", "irradiated", "radiation", "floor"),
        [
            (100, 0, 0, 120, 0, 0, None),
            (200, 0, 40, 600, 1, 3, None),
            (100, 74, 499, 600, 1, 75, 25),
        ],
        ids=["grace_period", "rate_follows_deprived_minutes", "stops_at_the_deprivation_floor"],
    )
    async def test_rate_grace_and_floor(
        self,
        async_session,
        vault,
        dweller,
        max_health,
        radiation_start,
        deprived_minutes,
        seconds,
        irradiated,
        radiation,
        floor,
    ):
        await self._prepare(
            async_session, vault, dweller, water=0, water_deprived_minutes=deprived_minutes, radiation=radiation_start
        )
        dweller.max_health = max_health
        async_session.add(dweller)
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=seconds)
        assert result["irradiated"] == irradiated
        await async_session.refresh(dweller)
        assert dweller.radiation == radiation
        if floor is not None:
            assert dweller.effective_max_health == floor

    @pytest.mark.parametrize(
        ("name", "rarity", "outfit_type"),
        [
            ("T-51d power armor", RarityEnum.LEGENDARY, OutfitTypeEnum.POWER_ARMOR),
            ("Hazmat suit", RarityEnum.RARE, OutfitTypeEnum.RARE),
        ],
        ids=["power_armor", "hazmat"],
    )
    async def test_outfits_do_not_block_ingested_water_radiation(
        self, async_session, vault, dweller, name, rarity, outfit_type
    ):
        await self._prepare(async_session, vault, dweller, water=0, water_deprived_minutes=40)
        async_session.add(Outfit(name=name, rarity=rarity, outfit_type=outfit_type, dweller_id=dweller.id))
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=600)
        assert result["irradiated"] == 1
        await async_session.refresh(dweller)
        assert dweller.radiation == 2  # 10 post-grace minutes at 0.15% of max health, armor ignored


class TestProcessTraining:
    async def _seed_trainings(self, async_session, vault, count: int = 3):
        room = await _make_room(async_session, vault)
        now = utcnow()
        trainings = []
        for index in range(count):
            dweller = await _make_dweller(async_session, vault, name=f"Trainee{index}")
            training = Training(
                dweller_id=dweller.id,
                room_id=room.id,
                vault_id=vault.id,
                stat_being_trained=SPECIALEnum.STRENGTH,
                current_stat_value=1,
                target_stat_value=2,
                goal_stat_value=10,
                started_at=now,
                estimated_completion_at=now + timedelta(hours=1),
                status=TrainingStatus.ACTIVE,
            )
            async_session.add(training)
            trainings.append(training)
        await async_session.commit()
        return trainings

    @pytest.mark.parametrize("scenario", ["completed", "second_survives", "load_error"])
    async def test_session_outcomes(self, async_session, vault, scenario):
        if scenario == "load_error":
            with patch("app.crud.training.training.get_active_by_vault", new_callable=AsyncMock) as mag:
                mag.side_effect = SQLAlchemyError("Failed to load trainings")
                result = await game_loop_service._process_training(async_session, vault.id)
            assert "error" in result
            return

        first = MagicMock(id="t-1", dweller_id="d-1")
        completed = MagicMock(is_completed=MagicMock(return_value=True), target_stat_value=7)
        completed.stat_being_trained = MagicMock(value="strength")
        pending = MagicMock(is_completed=MagicMock(return_value=False))
        calls = [0]

        async def update_side(db_session, training, dweller=None, **kwargs):
            calls[0] += 1
            if scenario == "second_survives" and calls[0] == 1:
                raise RuntimeError("Training failed")
            return completed if scenario == "completed" else pending

        with (
            patch("app.crud.training.training.get_active_by_vault", new_callable=AsyncMock) as mag,
            patch("app.crud.training.training.get_dwellers_for_trainings", new_callable=AsyncMock) as md,
            patch("app.services.training_service.training_service.update_training_progress", side_effect=update_side),
        ):
            mag.return_value = [first] if scenario == "completed" else [first, MagicMock(id="t-2", dweller_id="d-2")]
            md.return_value = {first.dweller_id: MagicMock()} if scenario == "completed" else {}
            result = await game_loop_service._process_training(async_session, vault.id)

        if scenario == "completed":
            assert result["sessions_updated"] == 1
            assert result["completed"] == 1
        else:
            assert result["active_count"] == 2


class TestUpdateRoomRelationships:
    async def test_single_dweller_skips(self, async_session, vault):
        md = MagicMock(id="d-1", room_id="r-1")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [md]
        with (
            patch.object(async_session, "execute", new_callable=AsyncMock, return_value=mock_result),
            patch("app.services.game_tick.family_tick.group_dwellers_by_room", return_value={"r-1": [md]}),
            patch.object(game_loop_service, "_fetch_existing_relationships", new_callable=AsyncMock, return_value=[]),
        ):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0

    @pytest.mark.parametrize("existing", [False, True], ids=["new", "existing"])
    async def test_pairs_use_loaded_relationship_and_commit_once(self, async_session, vault, existing):
        room = await _make_room(async_session, vault, name="Living Quarters", category=RoomTypeEnum.CAPACITY)
        members = [await _make_dweller(async_session, vault, room=room, name=f"Pair{i}", **_PAIR) for i in range(4)]
        await async_session.commit()
        if existing:
            for index, first in enumerate(members):
                for second in members[index + 1 :]:
                    await relationship_service.get_or_create_relationship(async_session, first.id, second.id)

        commit = AsyncMock(wraps=async_session.commit)
        with (
            patch.object(relationship_crud, "get_by_dweller_pair", new_callable=AsyncMock) as pair_lookup,
            patch.object(async_session, "commit", commit),
        ):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)

        assert result["relationships_updated"] == 6
        pair_lookup.assert_not_awaited()
        assert commit.await_count == 1

    async def test_processes_pairs(self, async_session, vault):
        d1 = MagicMock(id="d-1", room_id="r-1")
        d2 = MagicMock(id="d-2", room_id="r-1")
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [d1, d2]
        with (
            patch.object(async_session, "execute", new_callable=AsyncMock, return_value=mock_result),
            patch("app.services.game_tick.family_tick.group_dwellers_by_room", return_value={"r-1": [d1, d2]}),
            patch.object(game_loop_service, "_fetch_existing_relationships", new_callable=AsyncMock, return_value=[]),
            patch.object(game_loop_service, "_build_relationships_map", return_value={}),
            patch.object(game_loop_service, "_update_pair_affinity", new_callable=AsyncMock, return_value=0),
            patch.object(game_loop_service, "_create_new_relationships", new_callable=AsyncMock, return_value=1),
        ):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 1

    @pytest.mark.parametrize("error", [SQLAlchemyError("DB error"), ValueError("Invalid")], ids=["db", "value"])
    async def test_handles_execute_errors(self, async_session, vault, error):
        with patch.object(async_session, "execute", new_callable=AsyncMock, side_effect=error):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0

    @staticmethod
    async def _apart_pair_setup(async_session, vault, relationship_type=None, affinity=10):
        """An acquainted pair in two different rooms, plus those rooms."""
        lq = await _make_room(async_session, vault, name="Living Quarters", category=RoomTypeEnum.CAPACITY)
        plant = await _make_room(async_session, vault, name="Power Plant", category=RoomTypeEnum.PRODUCTION)
        dwellers = [
            await _make_dweller(async_session, vault, room=room, name=f"Apart{index}", **_PAIR)
            for index, room in enumerate((lq, plant))
        ]
        relationship = await _link(async_session, dwellers[0], dwellers[1], affinity)
        if relationship_type is not None:
            relationship.relationship_type = relationship_type
            await async_session.commit()
            await async_session.refresh(relationship)
        return dwellers, relationship, (lq, plant)

    @staticmethod
    async def _apart_tick(async_session, vault):
        with patch.object(async_session, "commit", AsyncMock(wraps=async_session.commit)) as commit:
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        return result, commit

    @pytest.mark.parametrize(
        ("rel_type", "affinity", "decay", "dead", "expected_affinity", "updated", "commits"),
        [
            (None, 10, None, False, 9, 1, 1),
            (RelationshipTypeEnum.PARTNER, 5, None, False, 4, None, None),
            (RelationshipTypeEnum.PARTNER, 0, None, False, 0, 0, 0),
            (None, 10, 0, False, 10, None, None),
            (RelationshipTypeEnum.RIVAL, -30, None, False, -30, None, None),
            (RelationshipTypeEnum.EX, -30, None, False, -30, None, None),
            (None, 10, None, True, 10, None, None),
        ],
        ids=[
            "acquaintance",
            "partner_decays",
            "partner_floor_skipped",
            "decay_disabled",
            "rival_frozen",
            "ex_frozen",
            "dead_partner_frozen",
        ],
    )
    async def test_apart_pair_drift(
        self, async_session, vault, monkeypatch, rel_type, affinity, decay, dead, expected_affinity, updated, commits
    ):
        dwellers, relationship, _ = await self._apart_pair_setup(async_session, vault, rel_type, affinity)
        if decay is not None:
            monkeypatch.setattr(game_config.relationship, "apart_affinity_decay_per_tick", decay)
        if dead:
            dwellers[0].is_dead = True
            async_session.add(dwellers[0])
            await async_session.commit()
        result, commit = await self._apart_tick(async_session, vault)

        await async_session.refresh(relationship)
        assert relationship.affinity == expected_affinity
        assert relationship.relationship_type == (rel_type or RelationshipTypeEnum.ACQUAINTANCE)
        if updated is not None:
            assert result["relationships_updated"] == updated
        if commits is not None:
            assert commit.await_count == commits

    async def test_co_located_pair_is_not_decayed_by_the_apart_pass(self, async_session, vault):
        dwellers, apart_relationship, (lq, _plant) = await self._apart_pair_setup(async_session, vault)
        third = await _make_dweller(async_session, vault, room=lq, name="Third", **_PAIR)
        co_located = await _link(async_session, dwellers[0], third)

        with patch("app.services.relationship_service.affinity_change", return_value=2):
            await self._apart_tick(async_session, vault)

        await async_session.refresh(co_located)
        await async_session.refresh(apart_relationship)
        # Co-located pairs follow the chemistry rule (+2), not the apart decay.
        assert co_located.affinity == 12
        assert apart_relationship.affinity == 9

    async def test_roomless_pair_decays(self, async_session, vault):
        dwellers = [await _make_dweller(async_session, vault, name=f"Scout{i}", **_PAIR) for i in range(2)]
        relationship = await _link(async_session, dwellers[0], dwellers[1])
        result, _ = await self._apart_tick(async_session, vault)

        await async_session.refresh(relationship)
        assert result["relationships_updated"] == 1
        assert relationship.affinity == 9

    async def test_same_room_non_living_quarters_pair_does_not_decay(self, async_session, vault):
        _, apart_relationship, (_lq, plant) = await self._apart_pair_setup(async_session, vault)
        pair = [await _make_dweller(async_session, vault, room=plant, name=f"Worker{i}", **_PAIR) for i in range(2)]
        co_located = await _link(async_session, pair[0], pair[1])
        await self._apart_tick(async_session, vault)

        await async_session.refresh(co_located)
        await async_session.refresh(apart_relationship)
        # Working side by side counts as together: no decay for this pair.
        assert co_located.affinity == 10
        assert apart_relationship.affinity == 9

    async def test_rolls_back_apart_decay_on_commit_failure(self, async_session, vault):
        _, relationship, _ = await self._apart_pair_setup(async_session, vault)
        relationship_id, original_type = relationship.id, relationship.relationship_type
        with patch.object(async_session, "commit", new_callable=AsyncMock, side_effect=SQLAlchemyError("late failure")):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)

        assert result["relationships_updated"] == 1
        reloaded = await relationship_crud.get(async_session, relationship_id)
        assert reloaded.affinity == 10
        assert reloaded.relationship_type == original_type
        notifications = (await async_session.execute(select(Notification))).scalars().all()
        assert not [
            row for row in notifications if row.meta_data and row.meta_data.get("event") == "relationship_demoted"
        ]
        assert async_session.info.get("deferred_notification_deliveries") is None


class TestRelationshipHelpers:
    def test_build_relationships_map_bidirectional(self):
        r1 = MagicMock(dweller_1_id="d1", dweller_2_id="d2")
        r2 = MagicMock(dweller_1_id="d3", dweller_2_id="d4")
        result = game_loop_service._build_relationships_map([r1, r2])
        assert result["d1", "d2"] == r1
        assert result["d2", "d1"] == r1
        assert result["d3", "d4"] == r2
        assert result["d4", "d3"] == r2

    @pytest.mark.usefixtures("vault")
    async def test_fetch_existing_relationships(self, async_session):
        result = await game_loop_service._fetch_existing_relationships(async_session, set())
        assert result == []

    @pytest.mark.parametrize(("delta", "method"), [(2, "increase_affinity"), (-2, "decrease_affinity")])
    async def test_update_pair_affinity_dispatch(self, async_session, delta, method):
        d1, d2, rel_map = _pair_mocks()
        with (
            patch("app.services.relationship_service.affinity_change", return_value=delta),
            patch(f"app.services.relationship_service.relationship_service.{method}", new_callable=AsyncMock) as mock,
        ):
            result = await game_loop_service._update_pair_affinity(async_session, d1, d2, rel_map, [])
        mock.assert_awaited_once()
        assert result == 1
        if delta < 0:
            assert mock.await_args.args[3] == 2

    async def test_rolls_back_staged_demotion_on_commit_failure(self, async_session, vault):
        room = await _make_room(async_session, vault, name="Living Quarters", category=RoomTypeEnum.CAPACITY)
        dwellers = [await _make_dweller(async_session, vault, room=room, name=f"Drift{i}", **_PAIR) for i in range(2)]
        relationship = await _link(async_session, dwellers[0], dwellers[1])
        relationship_id = relationship.id
        relationship.relationship_type = RelationshipTypeEnum.ROMANTIC
        relationship.affinity = game_config.relationship.romantic_demotion_threshold
        await async_session.commit()

        with (
            patch("app.services.relationship_service.affinity_change", return_value=-1),
            patch.object(async_session, "commit", new_callable=AsyncMock, side_effect=SQLAlchemyError("late failure")),
        ):
            await game_loop_service._update_room_relationships(async_session, vault.id)

        reloaded = await relationship_crud.get(async_session, relationship_id)
        assert reloaded.relationship_type == RelationshipTypeEnum.ROMANTIC
        assert reloaded.affinity == game_config.relationship.romantic_demotion_threshold
        notifications = (await async_session.execute(select(Notification))).scalars().all()
        assert not [
            row for row in notifications if row.meta_data and row.meta_data.get("event") == "relationship_demoted"
        ]
        assert async_session.info.get("deferred_notification_deliveries") is None

    async def test_update_pair_affinity_new_in_list_skipped(self, async_session):
        d1, d2, rel_map = _pair_mocks()
        new_rels = [(rel_map["d-1", "d-2"], game_config.relationship.affinity_increase_per_tick)]
        with patch(
            "app.services.relationship_service.relationship_service.increase_affinity", new_callable=AsyncMock
        ) as mi:
            result = await game_loop_service._update_pair_affinity(async_session, d1, d2, rel_map, new_rels)
        mi.assert_not_called()
        assert result == 0

    async def test_create_new_relationships_with_rels(self, async_session):
        r1 = MagicMock(dweller_1_id="d1", dweller_2_id="d2")
        r2 = MagicMock(dweller_1_id="d3", dweller_2_id="d4")
        increase = game_config.relationship.affinity_increase_per_tick
        with (
            patch("app.services.relationship_service.relationship_service.increase_affinity", new_callable=AsyncMock),
            patch.object(async_session, "commit", new_callable=AsyncMock),
            patch.object(async_session, "add_all"),
        ):
            result = await game_loop_service._create_new_relationships(async_session, [(r1, increase), (r2, increase)])
        assert result == 2


class TestProcessPregnancies:
    @pytest.mark.parametrize(
        ("conception", "due", "expected"),
        [
            ({"return_value": ["p1", "p2"]}, {"return_value": []}, {"conceptions": 2, "births": 0}),
            ({"side_effect": SQLAlchemyError("DB down")}, {"return_value": []}, {"conceptions": 0}),
            ({"side_effect": ValueError("Invalid")}, {"return_value": []}, {"conceptions": 0}),
            ({"return_value": []}, {"side_effect": SQLAlchemyError("DB error")}, {"births": 0}),
        ],
        ids=["conceptions", "conception_db_error", "conception_value_error", "due_db_error"],
    )
    async def test_phase_results(self, async_session, vault, conception, due, expected):
        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(**conception)
            mbs.check_due_pregnancies = AsyncMock(**due)
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        for key, value in expected.items():
            assert result[key] == value

    async def test_error_in_delivery_does_not_stop(self, async_session, vault):
        p1 = MagicMock(id="p-1")
        p2 = MagicMock(id="p-2")
        baby = MagicMock(first_name="OK", last_name="Baby")
        calls = [0]

        async def deliver_side(db_session, pregnancy_id):
            calls[0] += 1
            if calls[0] == 1:
                raise ValueError("Delivery failed")
            return [baby]

        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=[])
            mbs.check_due_pregnancies = AsyncMock(return_value=[p1, p2])
            mbs.deliver_baby = AsyncMock(side_effect=deliver_side)
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["births"] == 1

    async def test_capacity_deferral_logs_info_not_error(self, async_session, vault, caplog):
        defer = NoLivingSpaceError("No living space available for a newborn")
        with (
            patch(
                "app.services.family.breeding_service.breeding_service.deliver_baby", new=AsyncMock(side_effect=defer)
            ),
            caplog.at_level(logging.INFO, logger="app.services.game_tick.family_tick"),
        ):
            delivered = await _deliver_due_baby(async_session, vault.id, uuid4())

        assert delivered is False
        assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
        assert any(
            record.levelno == logging.INFO and "deferring due pregnancy" in record.getMessage()
            for record in caplog.records
        )


class TestAgeChildren:
    @pytest.mark.parametrize(
        ("call", "expected"),
        [
            ({"return_value": ["c1", "c2"]}, 2),
            ({"side_effect": SQLAlchemyError("DB error")}, 0),
            ({"side_effect": ValueError("Invalid")}, 0),
        ],
        ids=["success", "db_error", "value_error"],
    )
    async def test_age_children(self, async_session, vault, call, expected):
        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(**call)
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == expected


async def test_process_vault_tick_dedupes_report_arena_and_preserves_paused_contract(async_session, vault):
    first = await game_loop_service.process_vault_tick(async_session, vault.id, tick_id="dispatch-1")
    assert first["updates"]["arena"] == {"rooms": []}
    state = await game_loop_service._get_or_create_game_state(async_session, vault.id)
    first_tick_time = state.last_tick_time
    first_total_time = state.total_game_time

    duplicate = await game_loop_service.process_vault_tick(async_session, vault.id, tick_id="dispatch-1")

    assert duplicate == {"status": "duplicate"}
    await async_session.refresh(state)
    assert state.last_tick_time == first_tick_time
    assert state.total_game_time == first_total_time
    assert "dispatch-1" in state.recent_tick_ids

    next_tick = await game_loop_service.process_vault_tick(async_session, vault.id, tick_id="dispatch-2")

    assert next_tick["vault_id"] == str(vault.id)
    await async_session.refresh(state)
    assert state.recent_tick_ids[-2:] == ["dispatch-1", "dispatch-2"]
    assert first["vault_id"] == str(vault.id)

    await game_loop_service.pause_vault(async_session, vault.id)
    paused = await game_loop_service.process_vault_tick(async_session, vault.id)
    assert paused == {"status": "paused"}


async def test_arena_snapshot_database_failure_recovers_for_events(async_session, vault):
    from app.models.arena_match_event import ArenaMatchEvent
    from app.services.combat.arena_service import arena_service

    room = await _make_room(async_session, vault, name="Arena", category=RoomTypeEnum.ARENA, size_min=6, size_max=6)
    async_session.add(ArenaMatchEvent(room_id=room.id, round_seq=1, kind="hit", message="saved"))
    await async_session.commit()
    vault_id = vault.id

    # Fail at the DB boundary once; recovery and later phases then run for real.
    async with _one_shot_db_failure(
        async_session, lambda sql: "row_number() OVER" in sql, "SELECT * FROM missing_arena_snapshot_table"
    ) as failure:
        result = await game_loop_service.process_vault_tick(async_session, vault_id)
    assert failure["failed"]
    assert result["updates"]["arena"]["rooms"] == []
    assert "error" in result["updates"]["arena"]
    assert "error" not in result["updates"]["events"]
    # Session stays usable after recovery, and the persisted journal survived.
    snapshot = await arena_service.get_tick_snapshot(async_session, vault_id)
    assert snapshot["rooms"][0]["events"][0]["message"] == "saved"


@pytest.mark.parametrize(("start_offset", "elapsed"), [(-20, 20), (400, 0)])
async def test_resume_preserves_incident_response_time_and_does_not_shift_twice(
    async_session, room_in_vault, start_offset, elapsed
):
    from app.core.enums import IncidentType

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room_in_vault.vault_id,
        room_id=room_in_vault.id,
        incident_type=IncidentType.FIRE,
        difficulty=1,
    )
    state = await game_loop_service.pause_vault(async_session, room_in_vault.vault_id)
    state.paused_at = utcnow() - timedelta(minutes=10)
    incident.start_time = state.paused_at + timedelta(seconds=start_offset)
    await async_session.commit()
    await game_loop_service.pause_vault(async_session, room_in_vault.vault_id)
    await game_loop_service.resume_vault(async_session, room_in_vault.vault_id)
    await async_session.refresh(incident)
    assert max(0, elapsed - 1) <= incident.elapsed_time() <= elapsed + 1
    shifted_start = incident.start_time
    await game_loop_service.resume_vault(async_session, room_in_vault.vault_id)
    assert incident.start_time == shifted_start


@pytest.mark.parametrize("tick_offset", [-20, 120])
async def test_resume_excludes_paused_time_without_counting_it_twice(async_session, vault, tick_offset):
    state = await game_loop_service.pause_vault(async_session, vault.id)
    paused_at = utcnow() - timedelta(minutes=10)
    state.paused_at = paused_at
    state.last_tick_time = paused_at + timedelta(seconds=tick_offset)
    await async_session.commit()
    await game_loop_service.resume_vault(async_session, vault.id)
    assert max(0, -tick_offset - 1) <= state.calculate_offline_time() <= max(0, -tick_offset) + 1
    last_tick = state.last_tick_time
    await game_loop_service.resume_vault(async_session, vault.id)
    assert state.last_tick_time == last_tick


async def test_storage_database_failure_recovers_before_remaining_tick_phases(async_session, vault, monkeypatch):
    from app.models.storage import Storage
    from app.services.catalog_service import load_weapons
    from app.utils.item_factory import build_weapon

    monkeypatch.setattr(game_config.storage, "maintenance_enabled", True)
    storage = Storage(vault_id=vault.id)
    entry = next(entry for entry in load_weapons() if entry["name"] == "Gauss pistol")
    weapon = build_weapon(entry, entry["rarity"], storage.id)
    async_session.add_all([storage, weapon])
    await async_session.commit()
    vault_id = vault.id

    def is_trial_query(sql):
        return "FROM weapon" in sql and "weapon.last_maintenance_trial_at" in sql

    async with _one_shot_db_failure(
        async_session, is_trial_query, "SELECT * FROM missing_storage_trial_table"
    ) as failure:
        with patch("app.services.game_loop_service.sse_manager.publish", new_callable=AsyncMock) as publish:
            result = await game_loop_service.process_vault_tick(async_session, vault_id)
    assert failure["failed"]
    assert result["updates"]["storage"] == {"checked": 0, "changed": 0}
    assert {"happiness", "radio", "breeding", "events"} <= result["updates"].keys()
    assert "error" not in result["updates"]["events"]
    publish.assert_awaited_once()
    await async_session.refresh(weapon)
    assert weapon.name == "Gauss pistol"
    assert weapon.last_maintenance_trial_at is None
