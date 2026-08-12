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

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.game_loop import game_loop_service

# ═════════════════════════════════════════════════════════════════════
# pause_vault / resume_vault / get_vault_status / _get_or_create
# ═════════════════════════════════════════════════════════════════════


class TestPauseResume:
    """Tests for pause_vault, resume_vault, and get_vault_status."""

    @pytest.mark.asyncio
    async def test_pause_vault_sets_is_paused_true(self, async_session: AsyncSession, vault: Vault):
        result = await game_loop_service.pause_vault(async_session, vault.id)
        assert result.is_paused is True
        assert result.paused_at is not None

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

    @pytest.mark.asyncio
    async def test_get_or_create_game_state_creates_new(self, async_session: AsyncSession, vault: Vault):
        gs = await game_loop_service._get_or_create_game_state(async_session, vault.id)
        assert gs is not None
        assert gs.vault_id == vault.id
        assert gs.is_active is True

    @pytest.mark.asyncio
    async def test_get_or_create_game_state_returns_existing(self, async_session: AsyncSession, vault: Vault):
        gs1 = await game_loop_service._get_or_create_game_state(async_session, vault.id)
        gs2 = await game_loop_service._get_or_create_game_state(async_session, vault.id)
        assert gs1.id == gs2.id


# ═════════════════════════════════════════════════════════════════════
# process_game_tick
# ═════════════════════════════════════════════════════════════════════


class TestProcessGameTick:
    """Tests for the main game tick processing loop."""

    @pytest.mark.asyncio
    async def test_paused_vaults_excluded(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.pause_vault(async_session, vault.id)
        with patch.object(game_loop_service, "process_vault_tick", new_callable=AsyncMock) as mock_tick:
            stats = await game_loop_service.process_game_tick(async_session)
            mock_tick.assert_not_called()
        assert "vaults_processed" in stats
        assert "errors" in stats
        assert "total_time" in stats

    @pytest.mark.asyncio
    async def test_active_vault_processed(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.process_vault_tick(async_session, vault.id)
        with patch.object(game_loop_service, "process_vault_tick", new_callable=AsyncMock) as mock_tick:
            mock_tick.return_value = {"status": "ok"}
            stats = await game_loop_service.process_game_tick(async_session)
            assert stats["vaults_processed"] >= 1
            assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_counts_errors(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.process_vault_tick(async_session, vault.id)
        with patch.object(game_loop_service, "process_vault_tick", new_callable=AsyncMock) as mock_tick:
            mock_tick.side_effect = RuntimeError("Simulated error")
            stats = await game_loop_service.process_game_tick(async_session)
            assert stats["errors"] >= 1

    @pytest.mark.usefixtures("vault")
    @pytest.mark.asyncio
    async def test_no_active_vaults(self, async_session: AsyncSession):
        stats = await game_loop_service.process_game_tick(async_session)
        assert stats["vaults_processed"] == 0
        assert stats["errors"] == 0
        assert "total_time" in stats


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
            patch.object(game_loop_service, "_process_incidents", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_dwellers", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_training", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_happiness", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_breeding", new_callable=AsyncMock, return_value={}),
        ):
            mr.return_value = (mock_update, {"production": {}})
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
    async def test_includes_all_phases(self, async_session: AsyncSession, vault: Vault):
        result = await self._patched_tick(async_session, vault)
        for phase in [
            "resources",
            "incidents",
            "explorations",
            "dwellers",
            "training",
            "happiness",
            "breeding",
            "events",
        ]:
            assert phase in result["updates"]

    @pytest.mark.asyncio
    async def test_resource_error_does_not_propagate(self, async_session: AsyncSession, vault: Vault):
        # resource phase except catches (SQLAlchemyError, ResourceNotFoundException, VaultOperationException)
        from app.utils.exceptions import VaultOperationException

        with (
            patch.object(game_loop_service.resource_manager, "process_vault_resources", new_callable=AsyncMock) as mr,
            patch.object(game_loop_service, "_process_incidents", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_dwellers", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_training", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_happiness", new_callable=AsyncMock, return_value={}),
            patch.object(game_loop_service, "_process_breeding", new_callable=AsyncMock, return_value={}),
        ):
            mr.side_effect = VaultOperationException("Resource processing failed")
            result = await game_loop_service.process_vault_tick(async_session, vault.id)
        assert "error" in result["updates"]["resources"]
        assert "incidents" in result["updates"]

    @pytest.mark.asyncio
    async def test_paused_vault_short_circuits(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.pause_vault(async_session, vault.id)
        with patch.object(game_loop_service.resource_manager, "process_vault_resources", new_callable=AsyncMock) as mr:
            result = await game_loop_service.process_vault_tick(async_session, vault.id)
        assert result["status"] == "paused"
        mr.assert_not_called()

    @pytest.mark.asyncio
    async def test_sse_publish_error_does_not_propagate(self, async_session: AsyncSession, vault: Vault):
        mock_update = MagicMock()
        mock_update.power = 100
        mock_update.food = 50
        mock_update.water = 75
        with patch.object(game_loop_service.resource_manager, "process_vault_resources", new_callable=AsyncMock) as mr:
            mr.return_value = (mock_update, {"production": {}})
            with patch("app.services.game_loop.sse_manager.publish", new_callable=AsyncMock) as mock_publish:
                mock_publish.side_effect = ConnectionError("SSE connection lost")
                result = await game_loop_service.process_vault_tick(async_session, vault.id)
        assert result is not None
        assert "updates" in result


# ═════════════════════════════════════════════════════════════════════
# _get_active_vaults
# ═════════════════════════════════════════════════════════════════════


class TestGetActiveVaults:
    """Tests for _get_active_vaults."""

    @pytest.mark.asyncio
    async def test_no_game_states(self, async_session: AsyncSession):
        vaults = await game_loop_service._get_active_vaults(async_session)
        assert vaults == []

    @pytest.mark.asyncio
    async def test_returns_active(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.process_vault_tick(async_session, vault.id)
        vaults = await game_loop_service._get_active_vaults(async_session)
        assert any(v.id == vault.id for v in vaults)

    @pytest.mark.asyncio
    async def test_excludes_paused(self, async_session: AsyncSession, vault: Vault):
        await game_loop_service.process_vault_tick(async_session, vault.id)
        await game_loop_service.pause_vault(async_session, vault.id)
        vaults = await game_loop_service._get_active_vaults(async_session)
        assert not any(v.id == vault.id for v in vaults)


# ═════════════════════════════════════════════════════════════════════
# _process_incidents
# ═════════════════════════════════════════════════════════════════════
#
# incident_service is imported LOCALLY inside _process_incidents:
# So we patch app.services.incident_service.incident_service
#
# incident_crud is imported at MODULE level:
# So we patch app.services.game_loop.incident_crud
# ═════════════════════════════════════════════════════════════════════


class TestProcessIncidents:
    """Tests for incident management within the game loop."""

    @pytest.mark.asyncio
    async def test_no_spawn_no_active(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.incident_service.incident_service") as mock_is:
            mock_is.should_spawn_incident = AsyncMock(return_value=False)
            with patch("app.services.game_loop.incident_crud") as mock_crud:
                mock_crud.get_active_by_vault = AsyncMock(return_value=[])
                result = await game_loop_service._process_incidents(async_session, vault.id, 60)
        assert result["spawned"] == 0
        assert result["processed"] == 0
        assert result["resolved"] == 0
        assert result["active_count"] == 0
        assert result["caps_earned"] == 0

    @pytest.mark.asyncio
    async def test_spawns_new_incident(self, async_session: AsyncSession, vault: Vault):
        mock_incident = MagicMock()
        mock_incident.type = "raider_attack"
        with patch("app.services.incident_service.incident_service") as mock_is:
            mock_is.should_spawn_incident = AsyncMock(return_value=True)
            mock_is.spawn_incident = AsyncMock(return_value=mock_incident)
            with patch("app.services.game_loop.incident_crud") as mock_crud:
                mock_crud.get_active_by_vault = AsyncMock(return_value=[])
                result = await game_loop_service._process_incidents(async_session, vault.id, 60)
        assert result["spawned"] == 1
        assert result["active_count"] == 0

    @pytest.mark.asyncio
    async def test_spawn_returns_none(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.incident_service.incident_service") as mock_is:
            mock_is.should_spawn_incident = AsyncMock(return_value=True)
            mock_is.spawn_incident = AsyncMock(return_value=None)
            with patch("app.services.game_loop.incident_crud") as mock_crud:
                mock_crud.get_active_by_vault = AsyncMock(return_value=[])
                result = await game_loop_service._process_incidents(async_session, vault.id, 60)
        assert result["spawned"] == 0

    @pytest.mark.asyncio
    async def test_processes_active(self, async_session: AsyncSession, vault: Vault):
        mock_incident = MagicMock()
        mock_incident.status = MagicMock()
        mock_incident.status.value = "resolved"
        mock_incident.id = "inc-1"
        import app.services.game_loop as gl_mod

        saved_crud = gl_mod.incident_crud
        saved_vc = gl_mod.vault_crud
        try:
            gl_mod.incident_crud = MagicMock()
            gl_mod.incident_crud.get_active_by_vault = AsyncMock(return_value=[mock_incident])
            gl_mod.vault_crud = MagicMock()
            gl_mod.vault_crud.get = AsyncMock(return_value=vault)
            gl_mod.vault_crud.deposit_caps = AsyncMock()
            with patch("app.services.incident_service.incident_service") as mock_is:
                mock_is.should_spawn_incident = AsyncMock(return_value=False)
                mock_is.process_incident = AsyncMock(return_value={"caps_earned": 50, "skipped": False})
                # _process_incidents calls db_session.refresh(incident) — mock it
                with patch.object(async_session, "refresh", new_callable=AsyncMock):
                    result = await game_loop_service._process_incidents(async_session, vault.id, 60)
        finally:
            gl_mod.incident_crud = saved_crud
            gl_mod.vault_crud = saved_vc
        assert result["active_count"] == 1
        assert result["processed"] == 1
        assert result["resolved"] == 1
        assert result["caps_earned"] == 50

    @pytest.mark.asyncio
    async def test_skips_skipped_result(self, async_session: AsyncSession, vault: Vault):
        mock_incident = MagicMock()
        mock_incident.id = "inc-1"
        import app.services.game_loop as gl_mod

        saved_crud = gl_mod.incident_crud
        try:
            gl_mod.incident_crud = MagicMock()
            gl_mod.incident_crud.get_active_by_vault = AsyncMock(return_value=[mock_incident])
            with patch("app.services.incident_service.incident_service") as mock_is:
                mock_is.should_spawn_incident = AsyncMock(return_value=False)
                mock_is.process_incident = AsyncMock(return_value={"skipped": True})
                result = await game_loop_service._process_incidents(async_session, vault.id, 60)
        finally:
            gl_mod.incident_crud = saved_crud
        assert result["active_count"] == 1
        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_error_in_one_does_not_stop(self, async_session: AsyncSession, vault: Vault):
        inc1 = MagicMock()
        inc1.id = "inc-1"
        inc2 = MagicMock()
        inc2.id = "inc-2"
        inc2.status = MagicMock()
        inc2.status.value = "active"

        call_count = [0]

        async def process_side_effect(db_session, incident, seconds_passed):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated error")
            return {"caps_earned": 0, "skipped": False}

        import app.services.game_loop as gl_mod

        saved_crud = gl_mod.incident_crud
        try:
            gl_mod.incident_crud = MagicMock()
            gl_mod.incident_crud.get_active_by_vault = AsyncMock(return_value=[inc1, inc2])
            with patch("app.services.incident_service.incident_service") as mock_is:
                mock_is.should_spawn_incident = AsyncMock(return_value=False)
                mock_is.process_incident = AsyncMock(side_effect=process_side_effect)
                with patch.object(async_session, "refresh", new_callable=AsyncMock):
                    result = await game_loop_service._process_incidents(async_session, vault.id, 60)
        finally:
            gl_mod.incident_crud = saved_crud
        assert result["active_count"] == 2

    @pytest.mark.asyncio
    async def test_outer_exception_set_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.services.incident_service.incident_service") as mock_is:
            mock_is.should_spawn_incident = AsyncMock(side_effect=SQLAlchemyError("DB down"))
            result = await game_loop_service._process_incidents(async_session, vault.id, 60)
        assert "error" in result


# ═════════════════════════════════════════════════════════════════════
# _award_work_xp
# ═════════════════════════════════════════════════════════════════════
#
# local imports: leveling_service, game_config
# ═════════════════════════════════════════════════════════════════════


class TestAwardWorkXp:
    """Tests for awarding work XP to dwellers."""

    @pytest.mark.asyncio
    async def test_non_production_room_returns_zero(self, async_session: AsyncSession):
        from app.schemas.common import RoomTypeEnum, SPECIALEnum

        mock_dweller = MagicMock()
        mock_room = MagicMock()
        mock_room.category = RoomTypeEnum.TRAINING
        mock_room.ability = SPECIALEnum.STRENGTH
        stats = await game_loop_service._award_work_xp(async_session, mock_dweller, mock_room)
        assert stats["xp_awarded"] == 0
        assert stats["leveled_up"] == 0

    @pytest.mark.usefixtures("async_session")
    @pytest.mark.asyncio
    async def test_production_room_awards_xp(self):
        import app.services.leveling_service as ls_mod
        from app.schemas.common import RoomTypeEnum, SPECIALEnum

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_dweller = MagicMock()
        mock_dweller.experience = 0
        mock_dweller.strength = 3
        mock_dweller.vault_id = None
        mock_dweller.name = "Test"
        mock_dweller.level = 1
        mock_room = MagicMock()
        mock_room.category = RoomTypeEnum.PRODUCTION
        mock_room.ability = SPECIALEnum.STRENGTH
        saved = ls_mod.leveling_service.check_level_up
        ls_mod.leveling_service.check_level_up = AsyncMock(return_value=(False, 0))
        try:
            stats = await game_loop_service._award_work_xp(mock_db, mock_dweller, mock_room)
        finally:
            ls_mod.leveling_service.check_level_up = saved
        assert stats["xp_awarded"] == 2
        assert stats["leveled_up"] == 0

    @pytest.mark.usefixtures("async_session")
    @pytest.mark.asyncio
    async def test_production_room_with_ability_awards_nonzero_xp(self):
        from app.schemas.common import RoomTypeEnum, SPECIALEnum

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_dweller = MagicMock()
        mock_dweller.experience = 0
        mock_dweller.strength = 5
        mock_dweller.vault_id = None
        mock_dweller.name = "Worker"
        mock_dweller.level = 1
        mock_room = MagicMock()
        mock_room.category = RoomTypeEnum.PRODUCTION
        mock_room.ability = SPECIALEnum.STRENGTH
        stats = await game_loop_service._award_work_xp(mock_db, mock_dweller, mock_room)
        assert stats["xp_awarded"] > 0

    @pytest.mark.usefixtures("async_session")
    @pytest.mark.asyncio
    async def test_triggers_level_up(self):
        import app.services.leveling_service as ls_mod
        from app.schemas.common import RoomTypeEnum, SPECIALEnum

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_dweller = MagicMock()
        mock_dweller.experience = 500
        mock_dweller.strength = 5
        mock_dweller.vault_id = None
        mock_dweller.name = "Leveler"
        mock_dweller.level = 5
        mock_room = MagicMock()
        mock_room.category = RoomTypeEnum.PRODUCTION
        mock_room.ability = SPECIALEnum.STRENGTH
        saved = ls_mod.leveling_service.check_level_up
        ls_mod.leveling_service.check_level_up = AsyncMock(return_value=(True, 2))
        try:
            stats = await game_loop_service._award_work_xp(mock_db, mock_dweller, mock_room)
        finally:
            ls_mod.leveling_service.check_level_up = saved
        assert stats["xp_awarded"] == 2
        assert stats["leveled_up"] == 2

    @pytest.mark.usefixtures("async_session")
    @pytest.mark.asyncio
    async def test_level_up_emits_event(self):
        from uuid import uuid4

        import app.services.leveling_service as ls_mod
        from app.schemas.common import RoomTypeEnum, SPECIALEnum
        from app.services.event_bus import event_bus

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        vault_id = uuid4()
        mock_dweller = MagicMock()
        mock_dweller.experience = 500
        mock_dweller.strength = 5
        mock_dweller.vault_id = vault_id
        mock_dweller.id = uuid4()
        mock_dweller.name = "Eventer"
        mock_dweller.level = 5
        mock_room = MagicMock()
        mock_room.category = RoomTypeEnum.PRODUCTION
        mock_room.ability = SPECIALEnum.STRENGTH
        saved_ls = ls_mod.leveling_service.check_level_up
        saved_eb = event_bus.emit
        mock_emit = AsyncMock()
        ls_mod.leveling_service.check_level_up = AsyncMock(return_value=(True, 1))
        event_bus.emit = mock_emit
        try:
            stats = await game_loop_service._award_work_xp(mock_db, mock_dweller, mock_room)
        finally:
            ls_mod.leveling_service.check_level_up = saved_ls
            event_bus.emit = saved_eb
        assert stats["leveled_up"] == 1
        mock_emit.assert_called_once()

    @pytest.mark.usefixtures("async_session")
    @pytest.mark.asyncio
    async def test_negative_experience_normalized(self):
        import app.services.leveling_service as ls_mod
        from app.schemas.common import RoomTypeEnum, SPECIALEnum

        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_dweller = MagicMock()
        mock_dweller.experience = -10
        mock_dweller.strength = 5
        mock_dweller.vault_id = None
        mock_dweller.name = "Neg XP"
        mock_dweller.level = 1
        mock_room = MagicMock()
        mock_room.category = RoomTypeEnum.PRODUCTION
        mock_room.ability = SPECIALEnum.STRENGTH
        saved = ls_mod.leveling_service.check_level_up
        ls_mod.leveling_service.check_level_up = AsyncMock(return_value=(False, 0))
        try:
            stats = await game_loop_service._award_work_xp(mock_db, mock_dweller, mock_room)
        finally:
            ls_mod.leveling_service.check_level_up = saved
        assert stats["xp_awarded"] == 2
        assert mock_dweller.experience >= 0


# ═════════════════════════════════════════════════════════════════════
# _process_dwellers
# ═════════════════════════════════════════════════════════════════════
#
# local imports: death_service
# ═════════════════════════════════════════════════════════════════════


class TestProcessDwellers:
    """Tests for dweller processing within the game loop."""

    @pytest.mark.asyncio
    async def test_empty_vault(self, async_session: AsyncSession, vault: Vault):
        result = await game_loop_service._process_dwellers(async_session, vault.id)
        assert result["health_updated"] == 0
        assert result["leveled_up"] == 0
        assert result["xp_awarded"] == 0
        assert result["deaths"] == 0

    @pytest.mark.asyncio
    async def test_skips_dead_dwellers(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        from app.schemas.common import DwellerStatusEnum

        dweller.is_dead = True
        dweller.status = DwellerStatusEnum.DEAD
        async_session.add(dweller)
        await async_session.commit()
        with patch("app.services.death_service.death_service.mark_as_dead", new_callable=AsyncMock) as mock_death:
            result = await game_loop_service._process_dwellers(async_session, vault.id)
        mock_death.assert_not_called()
        assert result["deaths"] == 0

    @pytest.mark.asyncio
    async def test_detects_health_death(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        dweller.health = 0
        async_session.add(dweller)
        await async_session.commit()
        with patch("app.services.death_service.death_service.mark_as_dead", new_callable=AsyncMock) as mock_death:
            result = await game_loop_service._process_dwellers(async_session, vault.id)
        mock_death.assert_called_once()
        assert result["deaths"] == 1

    @pytest.mark.asyncio
    async def test_detects_radiation_death(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        dweller.health = 100
        dweller.radiation = 1000
        async_session.add(dweller)
        await async_session.commit()
        with patch("app.services.death_service.death_service.mark_as_dead", new_callable=AsyncMock) as mock_death:
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
        await crud.dweller.move_to_room(async_session, dweller.id, room.id)
        await async_session.commit()
        with patch("app.services.death_service.death_service.mark_as_dead", new_callable=AsyncMock):
            import app.services.leveling_service as ls_mod

            saved = ls_mod.leveling_service.check_level_up
            ls_mod.leveling_service.check_level_up = AsyncMock(return_value=(False, 0))
            try:
                result = await game_loop_service._process_dwellers(async_session, vault.id)
            finally:
                ls_mod.leveling_service.check_level_up = saved
        assert result["xp_awarded"] > 0

    @pytest.mark.asyncio
    async def test_error_in_one_does_not_stop(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        from app import crud
        from app.schemas.common import RoomTypeEnum, SPECIALEnum
        from app.schemas.dweller import DwellerCreate
        from app.schemas.room import RoomCreate
        from app.tests.factory.dwellers import create_fake_dweller

        dweller.health = 100
        dweller.radiation = 0
        room = await crud.room.create(
            async_session,
            RoomCreate(
                name="Water",
                category=RoomTypeEnum.PRODUCTION,
                ability=SPECIALEnum.PERCEPTION,
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
        d_data["radiation"] = 1000
        d_data["health"] = 100
        d2 = await crud.dweller.create(async_session, DwellerCreate(**d_data))
        await crud.dweller.move_to_room(async_session, d2.id, room.id)
        await async_session.commit()
        with patch("app.services.death_service.death_service.mark_as_dead", new_callable=AsyncMock) as mock_death:
            result = await game_loop_service._process_dwellers(async_session, vault.id)
        assert mock_death.call_count >= 1
        assert result["deaths"] >= 1


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
    async def test_no_active_trainings(self, async_session: AsyncSession, vault: Vault):
        with patch("app.crud.training.training.get_active_by_vault", new_callable=AsyncMock) as mag:
            mag.return_value = []
            result = await game_loop_service._process_training(async_session, vault.id)
        assert result["active_count"] == 0
        assert result["sessions_updated"] == 0
        assert result["completed"] == 0

    @pytest.mark.asyncio
    async def test_with_active_training(self, async_session: AsyncSession, vault: Vault):
        mt = MagicMock()
        mt.id = "t-1"
        mt.dweller_id = "d-1"
        mu = MagicMock()
        mu.is_completed = MagicMock(return_value=False)
        with patch("app.crud.training.training.get_active_by_vault", new_callable=AsyncMock) as mag:
            mag.return_value = [mt]
            with patch("app.crud.training.training.get_dwellers_for_trainings", new_callable=AsyncMock) as md:
                md.return_value = {mt.dweller_id: MagicMock()}
                with patch(
                    "app.services.training_service.training_service.update_training_progress", new_callable=AsyncMock
                ) as mu_async:
                    mu_async.return_value = mu
                    result = await game_loop_service._process_training(async_session, vault.id)
        assert result["active_count"] == 1
        assert result["sessions_updated"] == 1
        assert result["completed"] == 0

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


class TestProcessHappiness:
    """Tests for happiness processing within the game loop."""

    @pytest.mark.asyncio
    async def test_delegates_to_service(self, async_session: AsyncSession, vault: Vault):
        expected = {"average_happiness": 75.0, "updated_count": 10}
        with patch("app.services.game_loop.happiness_service.update_vault_happiness", new_callable=AsyncMock) as mh:
            mh.return_value = expected
            result = await game_loop_service._process_happiness(async_session, vault.id, 60)
        mh.assert_called_once_with(async_session, vault.id, 60)
        assert result == expected


# ═════════════════════════════════════════════════════════════════════
# _process_breeding
# ═════════════════════════════════════════════════════════════════════


class TestProcessBreeding:
    """Tests for breeding processing within the game loop."""

    @pytest.mark.asyncio
    async def test_combines_all_stats(self, async_session: AsyncSession, vault: Vault):
        with (
            patch.object(
                game_loop_service,
                "_update_room_relationships",
                new_callable=AsyncMock,
                return_value={"relationships_updated": 3},
            ),
            patch.object(
                game_loop_service,
                "_process_pregnancies_and_births",
                new_callable=AsyncMock,
                return_value={"conceptions": 1, "births": 0},
            ),
            patch.object(game_loop_service, "_age_children", new_callable=AsyncMock, return_value={"children_aged": 2}),
        ):
            result = await game_loop_service._process_breeding(async_session, vault.id)
        assert result["relationships_updated"] == 3
        assert result["conceptions"] == 1
        assert result["births"] == 0
        assert result["children_aged"] == 2


# ═════════════════════════════════════════════════════════════════════
# _update_room_relationships
# ═════════════════════════════════════════════════════════════════════


class TestUpdateRoomRelationships:
    """Tests for relationship updates within the game loop."""

    @pytest.mark.asyncio
    async def test_no_dwellers_in_rooms(self, async_session: AsyncSession, vault: Vault):
        with patch.object(game_loop_service, "_get_dwellers_in_rooms", new_callable=AsyncMock, return_value=[]):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0

    @pytest.mark.asyncio
    async def test_single_dweller_skips(self, async_session: AsyncSession, vault: Vault):
        md = MagicMock()
        md.id = "d-1"
        with (
            patch.object(game_loop_service, "_get_dwellers_in_rooms", new_callable=AsyncMock, return_value=[md]),
            patch.object(game_loop_service, "_group_dwellers_by_room", return_value={"r-1": [md]}),
        ):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0

    @pytest.mark.asyncio
    async def test_processes_pairs(self, async_session: AsyncSession, vault: Vault):
        d1 = MagicMock()
        d1.id = "d-1"
        d2 = MagicMock()
        d2.id = "d-2"
        with (
            patch.object(game_loop_service, "_get_dwellers_in_rooms", new_callable=AsyncMock, return_value=[d1, d2]),
            patch.object(game_loop_service, "_group_dwellers_by_room", return_value={"r-1": [d1, d2]}),
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

        with patch.object(
            game_loop_service, "_get_dwellers_in_rooms", new_callable=AsyncMock, side_effect=SQLAlchemyError("DB error")
        ):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0

    @pytest.mark.asyncio
    async def test_handles_value_error(self, async_session: AsyncSession, vault: Vault):
        with patch.object(
            game_loop_service, "_get_dwellers_in_rooms", new_callable=AsyncMock, side_effect=ValueError("Invalid")
        ):
            result = await game_loop_service._update_room_relationships(async_session, vault.id)
        assert result["relationships_updated"] == 0


# ═════════════════════════════════════════════════════════════════════
# _get_dwellers_in_rooms
# ═════════════════════════════════════════════════════════════════════


class TestGetDwellersInRooms:
    """Tests for fetching dwellers in rooms."""

    @pytest.mark.asyncio
    async def test_empty(self, async_session: AsyncSession, vault: Vault):
        result = await game_loop_service._get_dwellers_in_rooms(async_session, vault.id)
        assert result == []

    @pytest.mark.usefixtures("dweller")
    @pytest.mark.asyncio
    async def test_excludes_dwellers_without_room(self, async_session: AsyncSession, vault: Vault):
        result = await game_loop_service._get_dwellers_in_rooms(async_session, vault.id)
        assert len(result) == 0


# ═════════════════════════════════════════════════════════════════════
# Relationship helper methods
# ═════════════════════════════════════════════════════════════════════
#
# _update_pair_affinity:   local import relationship_service
# _create_new_relationships: local import relationship_service
# ═════════════════════════════════════════════════════════════════════


class TestRelationshipHelpers:
    """Tests for relationship helper methods."""

    def test_group_dwellers_by_room_delegates(self):
        mock_dwellers = [MagicMock()]
        mock_dwellers[0].room_id = "r-1"
        with patch("app.services.game_loop.group_dwellers_by_room") as mg:
            mg.return_value = {"r-1": mock_dwellers}
            result = game_loop_service._group_dwellers_by_room(mock_dwellers)
        mg.assert_called_once_with(mock_dwellers)
        assert result == {"r-1": mock_dwellers}

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

    def test_build_relationships_map_empty(self):
        assert game_loop_service._build_relationships_map([]) == {}

    @pytest.mark.usefixtures("vault")
    @pytest.mark.asyncio
    async def test_fetch_existing_relationships(self, async_session: AsyncSession):
        result = await game_loop_service._fetch_existing_relationships(async_session, set())
        assert result == []

    @pytest.mark.asyncio
    async def test_update_pair_affinity_new_relationship(self, async_session: AsyncSession):
        from app.schemas.common import RelationshipTypeEnum

        d1 = MagicMock()
        d1.id = "d-1"
        d2 = MagicMock()
        d2.id = "d-2"
        new_rels = []
        result = await game_loop_service._update_pair_affinity(async_session, d1, d2, {}, new_rels)
        assert result == 0
        assert len(new_rels) == 1
        assert new_rels[0].dweller_1_id == "d-1"
        assert new_rels[0].dweller_2_id == "d-2"
        assert new_rels[0].relationship_type == RelationshipTypeEnum.ACQUAINTANCE

    @pytest.mark.asyncio
    async def test_update_pair_affinity_existing(self, async_session: AsyncSession):
        mr = MagicMock()
        mr.dweller_1_id = "d-1"
        mr.dweller_2_id = "d-2"
        d1 = MagicMock()
        d1.id = "d-1"
        d2 = MagicMock()
        d2.id = "d-2"
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
        d2 = MagicMock()
        d2.id = "d-2"
        new_rels = [mr]
        rel_map = {("d-1", "d-2"): mr, ("d-2", "d-1"): mr}
        with patch(
            "app.services.relationship_service.relationship_service.increase_affinity", new_callable=AsyncMock
        ) as mi:
            result = await game_loop_service._update_pair_affinity(async_session, d1, d2, rel_map, new_rels)
        mi.assert_not_called()
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_new_relationships_empty(self, async_session: AsyncSession):
        result = await game_loop_service._create_new_relationships(async_session, [])
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
            result = await game_loop_service._create_new_relationships(async_session, [r1, r2])
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
    async def test_no_conceptions_no_due(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=[])
            mbs.check_due_pregnancies = AsyncMock(return_value=[])
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 0
        assert result["births"] == 0

    @pytest.mark.asyncio
    async def test_detects_conceptions(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=["p1", "p2"])
            mbs.check_due_pregnancies = AsyncMock(return_value=[])
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 2
        assert result["births"] == 0

    @pytest.mark.asyncio
    async def test_delivers_babies(self, async_session: AsyncSession, vault: Vault):
        mp = MagicMock()
        mp.id = "p-1"
        mb = MagicMock()
        mb.first_name = "Test"
        mb.last_name = "Baby"
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=[])
            mbs.check_due_pregnancies = AsyncMock(return_value=[mp])
            mbs.deliver_baby = AsyncMock(return_value=mb)
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 0
        assert result["births"] == 1

    @pytest.mark.asyncio
    async def test_deliver_baby_returns_none(self, async_session: AsyncSession, vault: Vault):
        mp = MagicMock()
        mp.id = "p-1"
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=[])
            mbs.check_due_pregnancies = AsyncMock(return_value=[mp])
            mbs.deliver_baby = AsyncMock(return_value=None)
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
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

        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(return_value=[])
            mbs.check_due_pregnancies = AsyncMock(return_value=[p1, p2])
            mbs.deliver_baby = AsyncMock(side_effect=deliver_side)
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["births"] == 1

    @pytest.mark.asyncio
    async def test_conception_db_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(side_effect=SQLAlchemyError("DB down"))
            mbs.check_due_pregnancies = AsyncMock(return_value=[])
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 0

    @pytest.mark.asyncio
    async def test_conception_value_error(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.check_for_conception = AsyncMock(side_effect=ValueError("Invalid"))
            mbs.check_due_pregnancies = AsyncMock(return_value=[])
            result = await game_loop_service._process_pregnancies_and_births(async_session, vault.id)
        assert result["conceptions"] == 0

    @pytest.mark.asyncio
    async def test_due_pregnancies_db_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.services.breeding_service.breeding_service") as mbs:
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
    async def test_none_to_age(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(return_value=[])
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == 0

    @pytest.mark.asyncio
    async def test_success(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(return_value=["c1", "c2"])
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == 2

    @pytest.mark.asyncio
    async def test_db_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(side_effect=SQLAlchemyError("DB error"))
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == 0

    @pytest.mark.asyncio
    async def test_value_error(self, async_session: AsyncSession, vault: Vault):
        with patch("app.services.breeding_service.breeding_service") as mbs:
            mbs.age_children = AsyncMock(side_effect=ValueError("Invalid"))
            result = await game_loop_service._age_children(async_session, vault.id)
        assert result["children_aged"] == 0
