"""Comprehensive tests for GameLoopService covering all public and internal methods.

Covers pause/resume, game tick processing, incident management, dweller processing,
training, happiness, breeding, relationships, and edge cases.

Uses real in-memory SQLite DB fixtures for game_state/vault/dweller queries and
mocked external services for complex dependencies.

IMPORTANT: Methods with local-from imports (e.g. `from app.services.X import Y`)
need patches at the SOURCE module (e.g. `app.services.X.Y`), NOT at
`app.services.game_loop.Y`. Methods with module-level imports can use
`app.services.game_loop.Y` directly.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.vault import Vault
from app.schemas.incident import IncidentRoundResult
from app.schemas.vault import ResourceTickEvents
from app.services.dweller_service import dweller_service
from app.services.game_loop import game_loop_service
from app.utils.exceptions import VaultOperationException

# ═════════════════════════════════════════════════════════════════════
# pause_vault / resume_vault / get_vault_status / _get_or_create
# ═════════════════════════════════════════════════════════════════════


class TestPauseResume:
    """Tests for pause_vault, resume_vault, and get_vault_status."""

    @pytest.mark.asyncio
    async def test_resume_vault_sets_is_paused_false(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.pause_vault(async_session, vault.id)
        result = await game_loop_service.resume_vault(async_session, vault.id)
        assert result.is_paused is False
        assert result.resumed_at is not None

    @pytest.mark.asyncio
    async def test_get_vault_status_returns_correct_fields(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.process_vault_tick(async_session, vault.id)
        status = await game_loop_service.get_vault_status(async_session, vault.id)
        assert status["vault_id"] == str(vault.id)
        assert status["is_active"] is True
        assert status["is_paused"] is False
        assert "total_game_time" in status
        assert "last_tick_time" in status
        assert "offline_time" in status


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


def _fake_session_maker():
    return _FakeSession()


# ═════════════════════════════════════════════════════════════════════
# process_game_tick
# ═════════════════════════════════════════════════════════════════════


class TestProcessGameTick:
    """Tests for the main game tick processing loop."""

    @pytest.mark.asyncio
    async def test_paused_vaults_excluded(self, async_session: AsyncSession, session_factory, vault: Vault):
        await game_loop_service.pause_vault(async_session, vault.id)
        with patch.object(game_loop_service, "process_vault_tick", new_callable=AsyncMock) as mock_tick:
            stats = await game_loop_service.process_game_tick(session_factory)
            mock_tick.assert_not_called()
        assert "vaults_processed" in stats
        assert "errors" in stats
        assert "total_time" in stats

    @pytest.mark.asyncio
    async def test_counts_errors(self, async_session: AsyncSession, session_factory, vault: Vault):
        await game_loop_service.process_vault_tick(async_session, vault.id)
        with patch.object(game_loop_service, "process_vault_tick", new_callable=AsyncMock) as mock_tick:
            mock_tick.side_effect = VaultOperationException("Simulated error")
            stats = await game_loop_service.process_game_tick(session_factory)
            assert stats["errors"] >= 1

    @pytest.mark.asyncio
    async def test_runs_vaults_with_bounded_parallelism(self):
        vaults = [SimpleNamespace(id=uuid4()) for _ in range(6)]
        active = 0
        max_active = 0
        sessions = []

        async def fake_tick(session, _vault_id):
            nonlocal active, max_active
            sessions.append(session)
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1

        with (
            patch.object(game_loop_service, "_get_active_vaults", new=AsyncMock(return_value=vaults)),
            patch.object(game_loop_service, "process_vault_tick", new=fake_tick),
        ):
            stats = await game_loop_service.process_game_tick(_fake_session_maker, max_concurrency=3)

        assert max_active == 3
        assert len({id(session) for session in sessions}) == len(vaults)
        assert stats["vaults_processed"] == len(vaults)
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_isolates_single_vault_failures(self):
        vaults = [SimpleNamespace(id=uuid4()) for _ in range(3)]
        processed: list = []

        async def fake_tick(_session, vault_id):
            if vault_id == vaults[0].id:
                raise VaultOperationException("Simulated failure")
            processed.append(vault_id)

        with (
            patch.object(game_loop_service, "_get_active_vaults", new=AsyncMock(return_value=vaults)),
            patch.object(game_loop_service, "process_vault_tick", new=fake_tick),
            patch("app.services.game_loop.recover_session", new=AsyncMock()),
        ):
            stats = await game_loop_service.process_game_tick(_fake_session_maker, max_concurrency=2)

        assert sorted(processed) == sorted(vault.id for vault in vaults[1:])
        assert stats["vaults_processed"] == 2
        assert stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_unexpected_failure_waits_for_sibling_vaults(self):
        vaults = [SimpleNamespace(id=uuid4()) for _ in range(3)]
        completed: list = []

        async def fake_tick(_session, vault_id):
            if vault_id == vaults[0].id:
                raise RuntimeError("boom")
            await asyncio.sleep(0.01)
            completed.append(vault_id)

        with (
            patch.object(game_loop_service, "_get_active_vaults", new=AsyncMock(return_value=vaults)),
            patch.object(game_loop_service, "process_vault_tick", new=fake_tick),
            pytest.raises(RuntimeError, match="boom"),
        ):
            await game_loop_service.process_game_tick(_fake_session_maker, max_concurrency=2)

        assert sorted(completed) == sorted(vault.id for vault in vaults[1:])

    @pytest.mark.asyncio
    async def test_logs_every_unexpected_vault_failure(self, caplog):
        vaults = [SimpleNamespace(id=uuid4()) for _ in range(3)]

        async def fake_tick(_session, vault_id):
            raise RuntimeError(f"boom {vault_id}")

        with (
            patch.object(game_loop_service, "_get_active_vaults", new=AsyncMock(return_value=vaults)),
            patch.object(game_loop_service, "process_vault_tick", new=fake_tick),
            caplog.at_level(logging.ERROR, logger="app.services.game_loop"),
            pytest.raises(RuntimeError, match="boom"),
        ):
            await game_loop_service.process_game_tick(_fake_session_maker, max_concurrency=2)

        logged = [
            record.getMessage()
            for record in caplog.records
            if "Unexpected error processing vault" in record.getMessage()
        ]
        assert len(logged) == 2


# ═════════════════════════════════════════════════════════════════════
# process_vault_tick edge cases
# ═════════════════════════════════════════════════════════════════════


class TestProcessVaultTick:
    """Tests for individual vault tick processing."""

    async def _patched_tick(self, async_session, vault):
        """Run process_vault_tick with all internal methods mocked."""
        mock_update = MagicMock()
        mock_update.power = 100
        mock_update.food = 50
        mock_update.water = 75

        with (
            patch.object(game_loop_service.resource_manager, "process_vault_resources", new_callable=AsyncMock) as mr,
            patch.object(game_loop_service, "_process_dwellers", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_training", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_happiness", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_breeding", new_callable=AsyncMock, return_value={}),
        ):
            mr.return_value = (mock_update, ResourceTickEvents())
            return await game_loop_service.process_vault_tick(async_session, vault.id)

    @pytest.mark.asyncio
    async def test_caps_offline_time(self, async_session: AsyncSession, vault: Vault):
        gs = await game_loop_service._get_or_create_game_state(async_session, vault.id)
        gs.last_tick_time = datetime.utcnow() - timedelta(hours=2)
        async_session.add(gs)
        await async_session.commit()
        result = await self._patched_tick(async_session, vault)
        assert result["seconds_passed"] <= 3600

    @pytest.mark.asyncio
    async def test_resource_error_does_not_propagate(self, async_session: AsyncSession, vault: Vault):
        # resource phase except catches (SQLAlchemyError, ResourceNotFoundException, VaultOperationException)
        from app.utils.exceptions import VaultOperationException

        with (
            patch.object(game_loop_service.resource_manager, "process_vault_resources", new_callable=AsyncMock) as mr,
            patch.object(game_loop_service, "_process_dwellers", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_training", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_happiness", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_breeding", new_callable=AsyncMock, return_value={}),
        ):
            mr.side_effect = VaultOperationException("Resource processing failed")
            result = await game_loop_service.process_vault_tick(async_session, vault.id)
        assert "error" in result["updates"]["resources"]


# ═════════════════════════════════════════════════════════════════════
# _get_active_vaults
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# _process_incidents
# ═════════════════════════════════════════════════════════════════════
#
# incident_service is imported LOCALLY inside _process_incidents:
# So we patch app.services.combat.incident_service.incident_service
#
# incident_crud is imported at MODULE level:
# So we patch app.services.game_loop.incident_crud
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# _process_dwellers
# ═════════════════════════════════════════════════════════════════════
#
# local imports: death_service
# ═════════════════════════════════════════════════════════════════════


class TestProcessDwellers:
    """Tests for dweller processing within the game loop."""

    @pytest.mark.asyncio
    async def test_skips_dead_dwellers(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        from app.schemas.common import DwellerStatusEnum

        dweller.is_dead = True
        dweller.status = DwellerStatusEnum.DEAD
        async_session.add(dweller)
        await async_session.commit()
        with patch(
            "app.services.family.death_service.death_service.mark_as_dead", new_callable=AsyncMock
        ) as mock_death:
            result = await game_loop_service._process_dwellers(async_session, vault.id)
        mock_death.assert_not_called()
        assert result["deaths"] == 0

    @pytest.mark.asyncio
    async def test_detects_health_death(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        dweller.health = 0
        async_session.add(dweller)
        await async_session.commit()
        with patch(
            "app.services.family.death_service.death_service.mark_as_dead", new_callable=AsyncMock
        ) as mock_death:
            result = await game_loop_service._process_dwellers(async_session, vault.id)
        mock_death.assert_called_once()
        assert result["deaths"] == 1

    @pytest.mark.asyncio
    async def test_awards_xp_to_working_dwellers(self, async_session: AsyncSession, vault: Vault):
        from app import crud
        from app.schemas.common import RoomTypeEnum, SPECIALEnum
        from app.schemas.dweller import DwellerCreate
        from app.schemas.room import RoomCreate
        from app.tests.factory.dwellers import create_fake_dweller

        room = await crud.room.create(
            async_session,
            RoomCreate(
                name="Power Gen",
                category=RoomTypeEnum.PRODUCTION,
                ability=SPECIALEnum.STRENGTH,
                base_cost=100,
                incremental_cost=50,
                capacity=4,
                size=2,
                tier=1,
                t2_upgrade_cost=500,
                t3_upgrade_cost=1500,
                vault_id=vault.id,
                coordinate_x=0,
                coordinate_y=0,
                size_min=1,
                size_max=3,
            ),
        )
        d_data = create_fake_dweller()
        d_data["vault_id"] = vault.id
        d_data["strength"] = 5
        d_data["health"] = 100
        d_data["radiation"] = 0
        dweller = await crud.dweller.create(async_session, DwellerCreate(**d_data))
        await dweller_service.move_to_room(async_session, dweller.id, room.id)
        await async_session.commit()
        with patch("app.services.family.death_service.death_service.mark_as_dead", new_callable=AsyncMock):
            import app.services.leveling_service as ls_mod

            saved = ls_mod.leveling_service.check_level_up
            ls_mod.leveling_service.check_level_up = AsyncMock(return_value=(False, 0))
            try:
                result = await game_loop_service._process_dwellers(async_session, vault.id)
            finally:
                ls_mod.leveling_service.check_level_up = saved
        assert result["xp_awarded"] > 0


# ═════════════════════════════════════════════════════════════════════
# _process_dwellers — dehydration radiation
# ═════════════════════════════════════════════════════════════════════


class TestDehydrationRadiation:
    """Tests for radiation applied while the vault has no water."""

    @pytest.mark.asyncio
    async def _prepare(self, async_session: AsyncSession, vault: Vault, dweller: Dweller, water: int) -> None:
        vault.water = water
        dweller.max_health = 100
        dweller.health = 100
        dweller.radiation = 0
        async_session.add_all([vault, dweller])
        await async_session.commit()

    @pytest.mark.asyncio
    async def test_away_dwellers_are_exempt(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        from app.schemas.common import DwellerStatusEnum

        await self._prepare(async_session, vault, dweller, water=0)
        dweller.status = DwellerStatusEnum.EXPLORING
        async_session.add(dweller)
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id)
        assert result["irradiated"] == 0
        await async_session.refresh(dweller)
        assert dweller.radiation == 0

    @pytest.mark.asyncio
    async def test_radiation_saturates_at_max_health(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await self._prepare(async_session, vault, dweller, water=0)
        dweller.radiation = 99
        async_session.add(dweller)
        async_session.add(GameState(vault_id=vault.id, water_empty_since=datetime.utcnow() - timedelta(minutes=10)))
        await async_session.commit()

        await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=600)
        await async_session.refresh(dweller)
        assert dweller.radiation == dweller.max_health
        assert dweller.effective_max_health == 1

    @pytest.mark.asyncio
    async def test_rate_is_one_percent_per_tick(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await self._prepare(async_session, vault, dweller, water=0)
        dweller.max_health = 200
        async_session.add(dweller)
        async_session.add(GameState(vault_id=vault.id, water_empty_since=datetime.utcnow() - timedelta(minutes=10)))
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=120)
        assert result["irradiated"] == 1
        await async_session.refresh(dweller)
        assert dweller.radiation == 4  # 1% of 200 per tick x 2 ticks

    @pytest.mark.asyncio
    async def test_grace_period_applies_no_radiation(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await self._prepare(async_session, vault, dweller, water=0)
        async_session.add(GameState(vault_id=vault.id, water_empty_since=datetime.utcnow()))
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=120)
        assert result["irradiated"] == 0
        await async_session.refresh(dweller)
        assert dweller.radiation == 0

    @pytest.mark.asyncio
    async def test_armor_does_not_block_ingested_water_radiation(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        from app.core.enums import OutfitTypeEnum, RarityEnum
        from app.models.outfit import Outfit

        await self._prepare(async_session, vault, dweller, water=0)
        async_session.add(GameState(vault_id=vault.id, water_empty_since=datetime.utcnow() - timedelta(minutes=10)))
        async_session.add(
            Outfit(
                name="T-51d power armor",
                rarity=RarityEnum.LEGENDARY,
                outfit_type=OutfitTypeEnum.POWER_ARMOR,
                dweller_id=dweller.id,
            )
        )
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=600)
        assert result["irradiated"] == 1
        await async_session.refresh(dweller)
        assert dweller.radiation == 5  # 5 post-grace ticks x 1% of 100, armor ignored

    @pytest.mark.asyncio
    async def test_hazmat_suit_does_not_block_ingested_water_radiation(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        from app.core.enums import OutfitTypeEnum, RarityEnum
        from app.models.outfit import Outfit

        await self._prepare(async_session, vault, dweller, water=0)
        async_session.add(GameState(vault_id=vault.id, water_empty_since=datetime.utcnow() - timedelta(minutes=10)))
        async_session.add(
            Outfit(
                name="Hazmat suit",
                rarity=RarityEnum.RARE,
                outfit_type=OutfitTypeEnum.RARE,
                dweller_id=dweller.id,
            )
        )
        await async_session.commit()

        result = await game_loop_service._process_dwellers(async_session, vault.id, seconds_passed=600)
        assert result["irradiated"] == 1
        await async_session.refresh(dweller)
        assert dweller.radiation == 5


# ═════════════════════════════════════════════════════════════════════
# _process_training
# ═════════════════════════════════════════════════════════════════════
#
# local imports: training_crud (from app.crud import training as training_crud)
#                training_service (from app.services.training_service import)
#          app.services.training_service.training_service
# ═════════════════════════════════════════════════════════════════════


class TestProcessTraining:
    """Tests for training processing within the game loop."""

    @pytest.mark.asyncio
    async def test_detects_completion(self, async_session: AsyncSession, vault: Vault):
        mt = MagicMock()
        mt.id = "t-1"
        mt.dweller_id = "d-1"
        mu = MagicMock()
        mu.is_completed = MagicMock(return_value=True)
        mu.stat_being_trained = MagicMock()
        mu.stat_being_trained.value = "strength"
        mu.target_stat_value = 7
        with patch("app.crud.training.training.get_active_by_vault", new_callable=AsyncMock) as mag:
            mag.return_value = [mt]
            with patch("app.crud.training.training.get_dwellers_for_trainings", new_callable=AsyncMock) as md:
                md.return_value = {mt.dweller_id: MagicMock()}
                with patch(
                    "app.services.training_service.training_service.update_training_progress", new_callable=AsyncMock
                ) as mu_async:
                    mu_async.return_value = mu
                    result = await game_loop_service._process_training(async_session, vault.id)
        assert result["sessions_updated"] == 1
        assert result["completed"] == 1

    @pytest.mark.asyncio
    async def test_error_in_one_does_not_stop(self, async_session: AsyncSession, vault: Vault):
        t1 = MagicMock()
        t1.id = "t-1"
        t1.dweller_id = "d-1"
        t2 = MagicMock()
        t2.id = "t-2"
        t2.dweller_id = "d-2"
        t2u = MagicMock()
        t2u.is_completed = MagicMock(return_value=False)
        call_count = [0]

        async def update_side(db_session, training, dweller=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Training failed")
            return t2u

        with patch("app.crud.training.training.get_active_by_vault", new_callable=AsyncMock) as mag:
            mag.return_value = [t1, t2]
            with (
                patch("app.crud.training.training.get_dwellers_for_trainings", new_callable=AsyncMock, return_value={}),
                patch(
                    "app.services.training_service.training_service.update_training_progress",
                    new_callable=AsyncMock,
                    side_effect=update_side,
                ),
            ):
                result = await game_loop_service._process_training(async_session, vault.id)
        assert result["active_count"] == 2

    @pytest.mark.asyncio
    async def test_outer_exception_set_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.crud.training.training.get_active_by_vault", new_callable=AsyncMock) as mag:
            mag.side_effect = SQLAlchemyError("Failed to load trainings")
            result = await game_loop_service._process_training(async_session, vault.id)
        assert "error" in result


# ═════════════════════════════════════════════════════════════════════
# _process_happiness
# ═════════════════════════════════════════════════════════════════════
#
# happiness_service is imported at module level
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# _process_breeding
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# _update_room_relationships
# ═════════════════════════════════════════════════════════════════════


class TestUpdateRoomRelationships:
    """Tests for relationship updates within the game loop."""

    @pytest.mark.asyncio
    async def test_single_dweller_skips(self, async_session: AsyncSession, vault: Vault):
        md = MagicMock()
        md.id = "d-1"
        md.room_id = "r-1"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [md]
        with (
            patch.object(async_session, "execute", new_callable=AsyncMock, return_value=mock_result),
            patch("app.services.game_tick.family_tick.group_dwellers_by_room", return_value={"r-1": [md]}),
            patch.object(game_loop_service, "_fetch_existing_relationships", new_callable=AsyncMock, return_value=[]),
        ):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0

    @pytest.mark.asyncio
    async def test_processes_pairs(self, async_session: AsyncSession, vault: Vault):
        d1 = MagicMock()
        d1.id = "d-1"
        d1.room_id = "r-1"
        d2 = MagicMock()
        d2.id = "d-2"
        d2.room_id = "r-1"
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

    @pytest.mark.asyncio
    async def test_handles_db_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch.object(async_session, "execute", new_callable=AsyncMock, side_effect=SQLAlchemyError("DB error")):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0

    @pytest.mark.asyncio
    async def test_handles_value_error(self, async_session: AsyncSession, vault: Vault):
        with patch.object(async_session, "execute", new_callable=AsyncMock, side_effect=ValueError("Invalid")):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0


# ═════════════════════════════════════════════════════════════════════
# Relationship helper methods
# ═════════════════════════════════════════════════════════════════════
#
# _update_pair_affinity:   local import relationship_service
# _create_new_relationships: local import relationship_service
# ═════════════════════════════════════════════════════════════════════


class TestRelationshipHelpers:
    """Tests for relationship helper methods."""

    def test_build_relationships_map_bidirectional(self):
        r1 = MagicMock()
        r1.dweller_1_id = "d1"
        r1.dweller_2_id = "d2"
        r2 = MagicMock()
        r2.dweller_1_id = "d3"
        r2.dweller_2_id = "d4"
        result = game_loop_service._build_relationships_map([r1, r2])
        assert result[("d1", "d2")] == r1
        assert result[("d2", "d1")] == r1
        assert result[("d3", "d4")] == r2
        assert result[("d4", "d3")] == r2

    @pytest.mark.usefixtures("vault")
    @pytest.mark.asyncio
    async def test_fetch_existing_relationships(self, async_session: AsyncSession):
        result = await game_loop_service._fetch_existing_relationships(async_session, set())
        assert result == []

    @pytest.mark.asyncio
    async def test_update_pair_affinity_existing(self, async_session: AsyncSession):
        mr = MagicMock()
        mr.dweller_1_id = "d-1"
        mr.dweller_2_id = "d-2"
        d1 = MagicMock()
        d1.id = "d-1"
        d1.charisma = 5
        d2 = MagicMock()
        d2.id = "d-2"
        d2.charisma = 5
        rel_map = {("d-1", "d-2"): mr, ("d-2", "d-1"): mr}
        with patch(
            "app.services.relationship_service.relationship_service.increase_affinity", new_callable=AsyncMock
        ) as mi:
            result = await game_loop_service._update_pair_affinity(async_session, d1, d2, rel_map, [])
        mi.assert_called_once()
        assert result == 1

    @pytest.mark.asyncio
    async def test_update_pair_affinity_new_in_list_skipped(self, async_session: AsyncSession):
        mr = MagicMock()
        mr.dweller_1_id = "d-1"
        mr.dweller_2_id = "d-2"
        d1 = MagicMock()
        d1.id = "d-1"
        d1.charisma = 5
        d2 = MagicMock()
        d2.id = "d-2"
        d2.charisma = 5
        new_rels = [(mr, game_config.relationship.affinity_increase_per_tick)]
        rel_map = {("d-1", "d-2"): mr, ("d-2", "d-1"): mr}
        with patch(
            "app.services.relationship_service.relationship_service.increase_affinity", new_callable=AsyncMock
        ) as mi:
            result = await game_loop_service._update_pair_affinity(async_session, d1, d2, rel_map, new_rels)
        mi.assert_not_called()
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_new_relationships_with_rels(self, async_session: AsyncSession):
        r1 = MagicMock()
        r1.dweller_1_id = "d1"
        r1.dweller_2_id = "d2"
        r2 = MagicMock()
        r2.dweller_1_id = "d3"
        r2.dweller_2_id = "d4"
        with (
            patch("app.services.relationship_service.relationship_service.increase_affinity", new_callable=AsyncMock),
            patch.object(async_session, "commit", new_callable=AsyncMock),
            patch.object(async_session, "add_all"),
        ):
            result = await game_loop_service._create_new_relationships(
                async_session,
                [
                    (r1, game_config.relationship.affinity_increase_per_tick),
                    (r2, game_config.relationship.affinity_increase_per_tick),
                ],
            )
        assert result == 2


# ═════════════════════════════════════════════════════════════════════
# _process_pregnancies_and_births
# ═════════════════════════════════════════════════════════════════════
#
# local import: breeding_service
# ═════════════════════════════════════════════════════════════════════


class TestProcessPregnancies:
    """Tests for pregnancy and birth processing."""

    @pytest.mark.asyncio
    async def test_detects_conceptions(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=["p1", "p2"])
            mbs.check_due_pregnancies = AsyncMock(return_value=[])
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 2
        assert result["births"] == 0

    @pytest.mark.asyncio
    async def test_error_in_delivery_does_not_stop(self, async_session: AsyncSession, vault: Vault):
        p1 = MagicMock()
        p1.id = "p-1"
        p2 = MagicMock()
        p2.id = "p-2"
        mb = MagicMock()
        mb.first_name = "OK"
        mb.last_name = "Baby"
        call_count = [0]

        async def deliver_side(db_session, pregnancy_id):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("Delivery failed")
            return mb

        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=[])
            mbs.check_due_pregnancies = AsyncMock(return_value=[p1, p2])
            mbs.deliver_baby = AsyncMock(side_effect=deliver_side)
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["births"] == 1

    @pytest.mark.asyncio
    async def test_conception_db_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(side_effect=SQLAlchemyError("DB down"))
            mbs.check_due_pregnancies = AsyncMock(return_value=[])
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 0

    @pytest.mark.asyncio
    async def test_conception_value_error(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(side_effect=ValueError("Invalid"))
            mbs.check_due_pregnancies = AsyncMock(return_value=[])
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 0

    @pytest.mark.asyncio
    async def test_due_pregnancies_db_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=[])
            mbs.check_due_pregnancies = AsyncMock(side_effect=SQLAlchemyError("DB error"))
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["births"] == 0


# ═════════════════════════════════════════════════════════════════════
# _age_children
# ═════════════════════════════════════════════════════════════════════
#
# local import: breeding_service
# ═════════════════════════════════════════════════════════════════════


class TestAgeChildren:
    """Tests for aging children to adults."""

    @pytest.mark.asyncio
    async def test_success(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(return_value=["c1", "c2"])
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == 2

    @pytest.mark.asyncio
    async def test_db_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(side_effect=SQLAlchemyError("DB error"))
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == 0

    @pytest.mark.asyncio
    async def test_value_error(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.family.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(side_effect=ValueError("Invalid"))
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == 0


@pytest.mark.asyncio
async def test_tick_reports_arena_and_preserves_paused_contract(async_session, vault):
    result = await game_loop_service.process_vault_tick(async_session, vault.id)
    assert result["updates"]["arena"] == {"rooms": []}
    await game_loop_service.pause_vault(async_session, vault.id)
    result = await game_loop_service.process_vault_tick(async_session, vault.id)
    assert result == {"status": "paused"}


@pytest.mark.asyncio
async def test_arena_snapshot_database_failure_recovers_for_events(async_session, vault):
    from sqlalchemy import event

    from app import crud
    from app.core.enums import RoomTypeEnum, SPECIALEnum
    from app.models.arena_match_event import ArenaMatchEvent
    from app.models.room import Room
    from app.schemas.room import RoomCreate

    room = await crud.room.create(
        async_session,
        RoomCreate(
            name="Arena",
            category=RoomTypeEnum.ARENA,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=6,
            size_max=6,
            vault_id=vault.id,
        ),
    )
    async_session.add(ArenaMatchEvent(room_id=room.id, round_seq=1, kind="hit", message="saved"))
    await async_session.commit()
    vault_id = vault.id
    connection = await async_session.connection()
    failed = False

    # Fail at the database boundary, once; exercise recovery and later phases for real.
    def break_snapshot(conn, cursor, statement, parameters, context, executemany):
        nonlocal failed
        if "row_number() OVER" in statement and not failed:
            failed = True
            return "SELECT * FROM missing_arena_snapshot_table", ()
        return statement, parameters

    event.listen(connection.sync_connection, "before_cursor_execute", break_snapshot, retval=True)
    try:
        result = await game_loop_service.process_vault_tick(async_session, vault_id)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", break_snapshot)
    assert failed
    assert result["updates"]["arena"]["rooms"] == []
    assert "error" in result["updates"]["arena"]
    assert "error" not in result["updates"]["events"]
    # Session remains usable after recovery, and the persisted journal survived.
    from app.services.combat.arena_service import arena_service

    assert (await arena_service.get_tick_snapshot(async_session, vault_id))["rooms"][0]["events"][0][
        "message"
    ] == "saved"


@pytest.mark.parametrize(("start_offset", "elapsed"), [(-20, 20), (400, 0)])
async def test_resume_preserves_incident_response_time_and_does_not_shift_twice(
    async_session, room_in_vault, start_offset, elapsed
):
    from app import crud
    from app.models.incident import IncidentType

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room_in_vault.vault_id,
        room_id=room_in_vault.id,
        incident_type=IncidentType.FIRE,
        difficulty=1,
    )
    state = await game_loop_service.pause_vault(async_session, room_in_vault.vault_id)
    state.paused_at = datetime.utcnow() - timedelta(minutes=10)
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
    """Resume preserves only the unprocessed active time, even if a paused tick ran."""
    state = await game_loop_service.pause_vault(async_session, vault.id)
    paused_at = datetime.utcnow() - timedelta(minutes=10)
    state.paused_at = paused_at
    state.last_tick_time = paused_at + timedelta(seconds=tick_offset)
    await async_session.commit()
    await game_loop_service.resume_vault(async_session, vault.id)
    assert max(0, -tick_offset - 1) <= state.calculate_offline_time() <= max(0, -tick_offset) + 1
    last_tick = state.last_tick_time
    await game_loop_service.resume_vault(async_session, vault.id)
    assert state.last_tick_time == last_tick


async def test_storage_database_failure_recovers_before_remaining_tick_phases(async_session, vault, monkeypatch):
    from sqlalchemy import event

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
    connection = await async_session.connection()
    failed = False

    def break_trial_query(conn, cursor, statement, parameters, context, executemany):
        nonlocal failed
        if "FROM weapon" in statement and "weapon.last_maintenance_trial_at" in statement and not failed:
            failed = True
            return "SELECT * FROM missing_storage_trial_table", ()
        return statement, parameters

    event.listen(connection.sync_connection, "before_cursor_execute", break_trial_query, retval=True)
    try:
        with patch("app.services.game_loop.sse_manager.publish", new_callable=AsyncMock) as publish:
            result = await game_loop_service.process_vault_tick(async_session, vault_id)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", break_trial_query)
    assert failed
    assert result["updates"]["storage"] == {"checked": 0, "changed": 0}
    assert {"happiness", "radio", "breeding", "events"} <= result["updates"].keys()
    assert "error" not in result["updates"]["events"]
    publish.assert_awaited_once()
    await async_session.refresh(weapon)
    assert weapon.name == "Gauss pistol"
    assert weapon.last_maintenance_trial_at is None
