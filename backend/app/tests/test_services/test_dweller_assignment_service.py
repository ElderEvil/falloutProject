"""Tests for DwellerAssignmentService — unit tests with mocked DB."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.services.dweller_assignment_service import (
    ABILITY_TO_STAT_MAP,
    MEDSCI_ABILITIES,
    PRODUCTION_ABILITIES,
    RADIO_ABILITIES,
    TRAINING_ABILITIES,
    DwellerAssignmentService,
)

# ---------------------------------------------------------------------------
# Stable UUIDs for deterministic test IDs
# ---------------------------------------------------------------------------

_D1 = uuid.UUID("15a0766e-8c61-4e42-a7bb-fed34ed0a7ee")
_D2 = uuid.UUID("e5cf820c-e7e6-4e4a-95f0-c12a9f96984a")
_D3 = uuid.UUID("77ba2369-f980-4523-84b8-5e7d7f48d9cf")
_D4 = uuid.UUID("4c3436ea-1daa-4689-858c-a5c7292bf1ae")
_D5 = uuid.UUID("85286379-3647-4e62-b926-1a0d21a7f550")
_DSTRONG = uuid.UUID("50a1f0ba-b512-44b9-8e40-91762d652baf")
_DWEAK = uuid.UUID("49d03e23-72e1-485f-aa62-7959ed2dd63a")

_R1 = uuid.UUID("b378c18e-3e8f-4203-9537-46c13d0ec7bc")
_R2 = uuid.UUID("c0a89001-25a9-4787-a406-e86b162bc942")
_R3 = uuid.UUID("9792b400-42ee-4110-98fb-365901d1788f")
_R4 = uuid.UUID("d912e26c-4665-4258-9771-dc802d89f6b4")
_R_STR = uuid.UUID("ca4d8588-ce0a-487b-bbc3-c2e0cc4db770")
_R_AGI = uuid.UUID("e8add549-6c49-4ba5-b64a-7029698d6745")
_R_PROD = uuid.UUID("7b847537-b55b-4b6e-940c-b468f7d4e02f")
_R_TRAIN = uuid.UUID("39856d32-88de-4138-b2e1-1355cb753cba")
_R_MED = uuid.UUID("0a00b469-9e82-427b-944b-b8c0c04b5e03")
_R_RADIO = uuid.UUID("d78c2ead-faef-4c77-b4d5-37094526be31")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dweller(
    _id: UUID4 = _D1,
    *,
    strength: int = 5,
    perception: int = 5,
    endurance: int = 5,
    charisma: int = 5,
    intelligence: int = 5,
    agility: int = 5,
    luck: int = 5,
    room_id: UUID4 | None = None,
    vault_id: UUID4 | None = None,
    is_deleted: bool = False,
    is_dead: bool = False,
) -> MagicMock:
    """Create a MagicMock dweller with SPECIAL stats."""
    d = MagicMock(spec=Dweller)
    d.id = _id
    d.strength = strength
    d.perception = perception
    d.endurance = endurance
    d.charisma = charisma
    d.intelligence = intelligence
    d.agility = agility
    d.luck = luck
    d.room_id = room_id
    d.vault_id = vault_id
    d.is_deleted = is_deleted
    d.is_dead = is_dead
    return d


def _make_room(
    _id: UUID4 = _R1,
    *,
    name: str = "Test Room",
    category: RoomTypeEnum = RoomTypeEnum.PRODUCTION,
    ability: SPECIALEnum = SPECIALEnum.STRENGTH,
    size: int | None = 3,
    size_min: int = 3,
    size_max: int = 6,
    vault_id: UUID4 | None = None,
) -> MagicMock:
    """Create a MagicMock room."""
    r = MagicMock(spec=Room)
    r.id = _id
    r.name = name
    r.category = category
    r.ability = ability
    r.size = size
    r.size_min = size_min
    r.size_max = size_max
    r.vault_id = vault_id
    return r


def _make_exec_result(items: list) -> MagicMock:
    """Build a mock db execute result returning scalars().all() = items."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = list(items)
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc() -> DwellerAssignmentService:
    """Return a fresh service instance."""
    return DwellerAssignmentService()


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncMock for AsyncSession."""
    return AsyncMock(spec=AsyncSession)


# ===================================================================
# _calculate_room_capacity
# ===================================================================


# ===================================================================
# _filter_rooms_by_abilities
# ===================================================================


# ===================================================================
# _get_available_slots
# ===================================================================


# ===================================================================
# _assign_dweller_to_room
# ===================================================================


# ===================================================================
# _calculate_total_slots
# ===================================================================


# ===================================================================
# _assign_ability_dwellers
# ===================================================================


class TestAssignAbilityDwellers:
    """Tests for _assign_ability_dwellers."""

    @pytest.mark.asyncio
    async def test_no_ability_specific_rooms_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.AGILITY)
        dwellers = [_make_dweller(_id=_D1, strength=7)]
        result = await svc._assign_ability_dwellers(SPECIALEnum.STRENGTH, [r1], mock_db, dwellers, [], set(), 1)
        assert len(result) == 1
        assert result[0].id == _D1

    @pytest.mark.asyncio
    async def test_no_available_slots_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH, size=3)
        dwellers = [_make_dweller(_id=_D1, strength=7)]
        with patch(
            "app.services.dweller_assignment_service.crud.dweller.count_in_room",
            new_callable=AsyncMock,
            return_value=2,
        ):
            result = await svc._assign_ability_dwellers(SPECIALEnum.STRENGTH, [r1], mock_db, dwellers, [], set(), 1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_skips_dwellers_at_training_stat_maximum(self, svc, mock_db):
        room = _make_room(
            _id=_R_TRAIN,
            category=RoomTypeEnum.TRAINING,
            ability=SPECIALEnum.PERCEPTION,
            size=3,
        )
        capped_dweller = _make_dweller(_id=_D1, perception=10)
        assignments: list[dict[str, str]] = []

        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        with patch(
            "app.services.dweller_assignment_service.training_service.start_training", new_callable=AsyncMock
        ) as mock_start_training:
            result = await svc._assign_ability_dwellers(
                SPECIALEnum.PERCEPTION,
                [room],
                mock_db,
                [capped_dweller],
                assignments,
                set(),
                1,
            )

        assert result == [capped_dweller]
        assert assignments == []
        mock_start_training.assert_not_awaited()


# ===================================================================
# _assign_to_rooms_proportional
# ===================================================================


class TestAssignToRoomsProportional:
    """Tests for _assign_to_rooms_proportional."""

    @pytest.mark.asyncio
    async def test_no_matching_ability_rooms_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.CHARISMA)
        dwellers = [_make_dweller(_id=_D1, strength=5)]
        result = await svc._assign_to_rooms_proportional([r1], MEDSCI_ABILITIES, mock_db, dwellers, [], set())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_zero_total_slots_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH, size=3)
        dwellers = [_make_dweller(_id=_D1, strength=5)]
        with patch(
            "app.services.dweller_assignment_service.crud.dweller.count_in_room",
            new_callable=AsyncMock,
            return_value=2,
        ):
            result = await svc._assign_to_rooms_proportional([r1], PRODUCTION_ABILITIES, mock_db, dwellers, [], set())
        assert len(result) == 1


# ===================================================================
# unassign_all_dwellers
# ===================================================================


class TestUnassignAllDwellers:
    """Tests for unassign_all_dwellers."""

    @pytest.mark.asyncio
    async def test_updates_to_idle_status(self, svc, mock_db):
        d = _make_dweller(_id=_D1, room_id=_R1)
        with (
            patch("app.services.dweller_assignment_service.crud.dweller.get_multi_by_vault") as mock_get,
            patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update,
            patch(
                "app.services.dweller_assignment_service.crud.room.get_by_category",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            mock_get.return_value = [d]
            await svc.unassign_all_dwellers(mock_db, "v1")

        call_args = mock_update.call_args
        assert call_args[0][0] is mock_db
        assert call_args[0][1] == _D1
        update_schema = call_args[0][2]
        assert update_schema.room_id is None
        assert update_schema.status == DwellerStatusEnum.IDLE


# ===================================================================
# auto_assign_production_rooms
# ===================================================================


class TestAutoAssignProductionRooms:
    """Tests for auto_assign_production_rooms."""

    @pytest.mark.asyncio
    async def test_full_rooms_skipped(self, svc, mock_db):
        r_str = _make_room(_id=_R_STR, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        d1 = _make_dweller(_id=_D1, strength=5)

        with (
            patch(
                "app.services.dweller_assignment_service.crud.room.get_by_category",
                new_callable=AsyncMock,
                return_value=[r_str],
            ),
            patch(
                "app.services.dweller_assignment_service.crud.dweller.get_unassigned_adults",
                new_callable=AsyncMock,
                return_value=[d1],
            ),
            patch(
                "app.services.dweller_assignment_service.crud.dweller.count_in_room",
                new_callable=AsyncMock,
                return_value=2,
            ),
            patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update,
        ):
            result = await svc.auto_assign_production_rooms(mock_db, "v1")

        assert result["assigned_count"] == 0
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_ability_priority_order(self, svc, mock_db):
        """Strength rooms filled first, even if dweller has higher agility."""
        r_str = _make_room(_id=_R_STR, ability=SPECIALEnum.STRENGTH, size=3)
        r_agi = _make_room(_id=_R_AGI, ability=SPECIALEnum.AGILITY, size=3)

        d_weak = _make_dweller(_id=_DWEAK, strength=2, agility=9)

        with (
            patch(
                "app.services.dweller_assignment_service.crud.room.get_by_category",
                new_callable=AsyncMock,
                return_value=[r_str, r_agi],
            ),
            patch(
                "app.services.dweller_assignment_service.crud.dweller.get_unassigned_adults",
                new_callable=AsyncMock,
                return_value=[d_weak],
            ),
            patch(
                "app.services.dweller_assignment_service.crud.dweller.count_in_room",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update,
        ):
            result = await svc.auto_assign_production_rooms(mock_db, "v1")

        assert result["assigned_count"] == 1
        last_call_args = mock_update.call_args
        assert last_call_args[0][1] == _DWEAK
        update_schema = last_call_args[0][2]
        assert update_schema.room_id == _R_STR  # assigned to first-priority room


# ===================================================================
# auto_assign_training_rooms
# ===================================================================


class TestAutoAssignTrainingRooms:
    """Tests for auto_assign_training_rooms."""

    @pytest.mark.asyncio
    async def test_assigns_lowest_eligible_stat_first(self, svc, mock_db):
        room = _make_room(
            _id=_R_TRAIN,
            category=RoomTypeEnum.TRAINING,
            ability=SPECIALEnum.STRENGTH,
            size=3,
        )
        strong_dweller = _make_dweller(_id=_DSTRONG, strength=8)
        weak_dweller = _make_dweller(_id=_DWEAK, strength=2)

        with (
            patch(
                "app.services.dweller_assignment_service.crud.room.get_by_category",
                new_callable=AsyncMock,
                return_value=[room],
            ),
            patch(
                "app.services.dweller_assignment_service.crud.dweller.get_unassigned_adults",
                new_callable=AsyncMock,
                return_value=[strong_dweller, weak_dweller],
            ),
            patch(
                "app.services.dweller_assignment_service.crud.dweller.count_in_room",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "app.services.dweller_assignment_service.training_service.start_training", new_callable=AsyncMock
            ) as mock_start_training,
        ):
            result = await svc.auto_assign_training_rooms(mock_db, "v1")

        assert result["assigned_count"] == 2
        assert [call.args[1] for call in mock_start_training.await_args_list] == [_DWEAK, _DSTRONG]


# ===================================================================
# auto_assign_all_rooms
# ===================================================================


class TestAutoAssignAllRooms:
    """Tests for auto_assign_all_rooms."""

    @pytest.mark.asyncio
    async def test_unassigned_dwellers_cascade_across_tiers(self, svc, mock_db):
        """Dwellers not assigned in earlier tiers flow to later tiers."""
        r_prod = _make_room(_id=_R1, category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, size=3)
        r_train = _make_room(_id=_R2, category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH, size=3)
        d1 = _make_dweller(_id=_D1, strength=5)

        with patch.object(svc, "_assign_to_rooms_proportional") as mock_assign:
            # Call 1 (production) → returns d1 (not assigned)
            # Call 2 (medsci, no rooms) → returns d1
            # Call 3 (radio, no rooms) → returns d1
            # Call 4 (training) → returns [] (assigned)
            mock_assign.side_effect = [[d1], [d1], [d1], []]

            rooms_resp = _make_exec_result([r_prod, r_train])
            dwellers_resp = _make_exec_result([d1])
            mock_db.execute = AsyncMock(side_effect=[rooms_resp, dwellers_resp])

            await svc.auto_assign_all_rooms(mock_db, "v1")

        assert mock_assign.call_count == 4
        assert mock_assign.call_args_list[1][0][3] == [d1]  # medsci receives d1
        assert mock_assign.call_args_list[3][0][3] == [d1]  # training receives d1


# ===================================================================
# Module-level constants
# ===================================================================


class TestModuleConstants:
    """Verify the module-level constants are correct."""

    def test_ability_to_stat_map_coverage(self):
        for stat in SPECIALEnum:
            assert stat in ABILITY_TO_STAT_MAP
            assert ABILITY_TO_STAT_MAP[stat] == stat.value

    def test_production_abilities_order(self):
        assert PRODUCTION_ABILITIES == [
            SPECIALEnum.STRENGTH,
            SPECIALEnum.AGILITY,
            SPECIALEnum.PERCEPTION,
        ]

    def test_medsci_abilities(self):
        assert MEDSCI_ABILITIES == [SPECIALEnum.INTELLIGENCE]

    def test_radio_abilities(self):
        assert RADIO_ABILITIES == [SPECIALEnum.CHARISMA]

    def test_training_abilities_includes_all(self):
        assert set(TRAINING_ABILITIES) == set(SPECIALEnum)


# ===================================================================
# Singleton
# ===================================================================


class TestServiceSingleton:
    """Verify the singleton instance at module level."""

    def test_singleton_exists(self):
        from app.services.dweller_assignment_service import dweller_assignment_service

        assert isinstance(dweller_assignment_service, DwellerAssignmentService)
