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


class TestCalculateRoomCapacity:
    """Tests for _calculate_room_capacity."""

    def test_size_3_returns_2(self, svc):
        room = _make_room(size=3)
        assert svc._calculate_room_capacity(room) == 2

    def test_size_6_returns_4(self, svc):
        room = _make_room(size=6)
        assert svc._calculate_room_capacity(room) == 4

    def test_size_4_returns_2(self, svc):
        room = _make_room(size=4)
        assert svc._calculate_room_capacity(room) == 2

    def test_size_1_returns_0(self, svc):
        room = _make_room(size=1)
        assert svc._calculate_room_capacity(room) == 0

    def test_size_none_falls_back_to_size_min(self, svc):
        room = _make_room(size=None, size_min=6)
        assert svc._calculate_room_capacity(room) == 4

    def test_size_none_and_size_min_none_returns_0(self, svc):
        room = _make_room(size=None, size_min=None)
        assert svc._calculate_room_capacity(room) == 0

    def test_size_zero_returns_0(self, svc):
        room = _make_room(size=0, size_min=0)
        assert svc._calculate_room_capacity(room) == 0

    def test_size_9_returns_6(self, svc):
        room = _make_room(size=9)
        assert svc._calculate_room_capacity(room) == 6


# ===================================================================
# _filter_rooms_by_abilities
# ===================================================================


class TestFilterRoomsByAbilities:
    """Tests for _filter_rooms_by_abilities."""

    def test_empty_rooms_returns_empty(self, svc):
        result = svc._filter_rooms_by_abilities([], [SPECIALEnum.STRENGTH])
        assert result == []

    def test_empty_abilities_returns_empty(self, svc):
        rooms = [_make_room(ability=SPECIALEnum.STRENGTH)]
        result = svc._filter_rooms_by_abilities(rooms, [])
        assert result == []

    def test_single_ability_match(self, svc):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH)
        r2 = _make_room(_id=_R2, ability=SPECIALEnum.AGILITY)
        result = svc._filter_rooms_by_abilities([r1, r2], [SPECIALEnum.STRENGTH])
        assert len(result) == 1
        assert result[0].id == _R1

    def test_multiple_abilities(self, svc):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH)
        r2 = _make_room(_id=_R2, ability=SPECIALEnum.AGILITY)
        r3 = _make_room(_id=_R3, ability=SPECIALEnum.PERCEPTION)
        result = svc._filter_rooms_by_abilities([r1, r2, r3], [SPECIALEnum.STRENGTH, SPECIALEnum.PERCEPTION])
        assert len(result) == 2
        ids = {r.id for r in result}
        assert ids == {_R1, _R3}

    def test_ability_not_in_list(self, svc):
        r1 = _make_room(ability=SPECIALEnum.STRENGTH)
        result = svc._filter_rooms_by_abilities([r1], [SPECIALEnum.CHARISMA])
        assert result == []

    def test_duplicate_abilities_duplicates_rooms(self, svc):
        """When same ability appears twice, rooms are duplicated."""
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH)
        result = svc._filter_rooms_by_abilities([r1], [SPECIALEnum.STRENGTH, SPECIALEnum.STRENGTH])
        assert len(result) == 2


# ===================================================================
# _get_available_slots
# ===================================================================


class TestGetAvailableSlots:
    """Tests for _get_available_slots."""

    @pytest.mark.asyncio
    async def test_empty_room_returns_full_capacity(self, svc, mock_db):
        room = _make_room(size=6)  # capacity 4
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        slots = await svc._get_available_slots(room, mock_db)
        assert slots == 4

    @pytest.mark.asyncio
    async def test_full_room_returns_zero(self, svc, mock_db):
        room = _make_room(size=3)  # capacity 2
        mock_db.execute = AsyncMock(return_value=_make_exec_result([MagicMock(), MagicMock()]))

        slots = await svc._get_available_slots(room, mock_db)
        assert slots == 0

    @pytest.mark.asyncio
    async def test_partially_filled_room(self, svc, mock_db):
        room = _make_room(size=6)  # capacity 4
        mock_db.execute = AsyncMock(return_value=_make_exec_result([MagicMock(), MagicMock()]))

        slots = await svc._get_available_slots(room, mock_db)
        assert slots == 2

    @pytest.mark.asyncio
    async def test_overfilled_room_returns_zero_not_negative(self, svc, mock_db):
        room = _make_room(size=3)  # capacity 2
        mock_db.execute = AsyncMock(return_value=_make_exec_result([MagicMock()] * 5))

        slots = await svc._get_available_slots(room, mock_db)
        assert slots == 0

    @pytest.mark.asyncio
    async def test_zero_capacity_room(self, svc, mock_db):
        room = _make_room(size=1)  # capacity 0
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        slots = await svc._get_available_slots(room, mock_db)
        assert slots == 0


# ===================================================================
# _assign_dweller_to_room
# ===================================================================


class TestAssignDwellerToRoom:
    """Tests for _assign_dweller_to_room."""

    @pytest.mark.asyncio
    async def test_assigns_dweller_and_records_assignment(self, svc, mock_db):
        dweller = _make_dweller(_id=_D1)
        room = _make_room(_id=_R1, name="Power Plant", category=RoomTypeEnum.PRODUCTION)
        assignments: list[dict[str, str]] = []
        assigned_ids: set = set()

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            await svc._assign_dweller_to_room(dweller, room, mock_db, assignments, assigned_ids)

        assert len(assignments) == 1
        assert assignments[0]["dweller_id"] == str(_D1)
        assert assignments[0]["room_id"] == str(_R1)
        assert assignments[0]["room_name"] == "Power Plant"
        assert _D1 in assigned_ids

    @pytest.mark.asyncio
    async def test_multiple_assignments_accumulate(self, svc, mock_db):
        d1 = _make_dweller(_id=_D1)
        d2 = _make_dweller(_id=_D2)
        room = _make_room(_id=_R1, name="Diner", category=RoomTypeEnum.PRODUCTION)
        assignments: list[dict[str, str]] = []
        assigned_ids: set = set()

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            await svc._assign_dweller_to_room(d1, room, mock_db, assignments, assigned_ids)
            await svc._assign_dweller_to_room(d2, room, mock_db, assignments, assigned_ids)

        assert len(assignments) == 2
        assert len(assigned_ids) == 2


# ===================================================================
# _calculate_total_slots
# ===================================================================


class TestCalculateTotalSlots:
    """Tests for _calculate_total_slots."""

    @pytest.mark.asyncio
    async def test_empty_rooms_returns_zero(self, svc, mock_db):
        room_slots, total = await svc._calculate_total_slots([], mock_db)
        assert room_slots == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_rooms_with_available_slots(self, svc, mock_db):
        r1 = _make_room(_id=_R1, size=3)  # cap 2
        r2 = _make_room(_id=_R2, size=6)  # cap 4

        responses = [_make_exec_result([]), _make_exec_result([])]
        mock_db.execute = AsyncMock(side_effect=responses)

        room_slots, total = await svc._calculate_total_slots([r1, r2], mock_db)
        assert total == 6
        assert len(room_slots) == 2

    @pytest.mark.asyncio
    async def test_full_rooms_contribute_zero(self, svc, mock_db):
        r1 = _make_room(_id=_R1, size=3)  # cap 2
        responses = [_make_exec_result([MagicMock(), MagicMock()])]
        mock_db.execute = AsyncMock(side_effect=responses)

        room_slots, total = await svc._calculate_total_slots([r1], mock_db)
        assert total == 0
        assert len(room_slots) == 0


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
        mock_db.execute = AsyncMock(return_value=_make_exec_result([MagicMock(), MagicMock()]))
        dwellers = [_make_dweller(_id=_D1, strength=7)]
        result = await svc._assign_ability_dwellers(SPECIALEnum.STRENGTH, [r1], mock_db, dwellers, [], set(), 1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_assigns_highest_stat_dwellers_first(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        d_strong = _make_dweller(_id=_DSTRONG, strength=9)
        d_weak = _make_dweller(_id=_DWEAK, strength=3)
        dwellers = [d_weak, d_strong]

        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            result = await svc._assign_ability_dwellers(SPECIALEnum.STRENGTH, [r1], mock_db, dwellers, [], set(), 2)

        assert len(result) == 0  # both assigned

    @pytest.mark.asyncio
    async def test_respects_dwellers_for_tier_proportion(self, svc, mock_db):
        """When dwellers_for_tier < slots, only assign that many."""
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        d1 = _make_dweller(_id=_D1, strength=8)
        d2 = _make_dweller(_id=_D2, strength=7)
        dwellers = [d1, d2]

        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))
        assignments: list[dict[str, str]] = []
        assigned: set = set()

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            result = await svc._assign_ability_dwellers(
                SPECIALEnum.STRENGTH, [r1], mock_db, dwellers, assignments, assigned, 1
            )
        # Only 1 should be assigned (dwellers_for_tier=1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_all_dwellers_already_assigned(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH, size=3)
        d1 = _make_dweller(_id=_D1, strength=5)
        dwellers = [d1]

        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            result = await svc._assign_ability_dwellers(SPECIALEnum.STRENGTH, [r1], mock_db, dwellers, [], {_D1}, 5)
        # d1 already in assigned set → filtered out from result
        assert len(result) == 0


# ===================================================================
# _assign_to_rooms_proportional
# ===================================================================


class TestAssignToRoomsProportional:
    """Tests for _assign_to_rooms_proportional."""

    @pytest.mark.asyncio
    async def test_empty_dwellers_returns_empty(self, svc, mock_db):
        rooms = [_make_room()]
        result = await svc._assign_to_rooms_proportional(rooms, PRODUCTION_ABILITIES, mock_db, [], [], set())
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_rooms_returns_unchanged(self, svc, mock_db):
        dwellers = [_make_dweller(_id=_D1)]
        result = await svc._assign_to_rooms_proportional([], PRODUCTION_ABILITIES, mock_db, dwellers, [], set())
        assert len(result) == 1

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
        mock_db.execute = AsyncMock(return_value=_make_exec_result([MagicMock(), MagicMock()]))
        result = await svc._assign_to_rooms_proportional([r1], PRODUCTION_ABILITIES, mock_db, dwellers, [], set())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_assigns_to_multiple_abilities(self, svc, mock_db):
        """Test proportional assignment across multiple abilities."""
        r_str = _make_room(_id=_R_STR, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        r_agi = _make_room(_id=_R_AGI, ability=SPECIALEnum.AGILITY, size=3)  # cap 2

        d1 = _make_dweller(_id=_D1, strength=8, agility=3)
        d2 = _make_dweller(_id=_D2, strength=5, agility=9)
        dwellers = [d1, d2]

        # Both rooms empty → 4 execute calls (2 for _calculate_total_slots, 2 for _assign_ability_dwellers)
        responses = [
            _make_exec_result([]),  # _calculate_total_slots: r_str
            _make_exec_result([]),  # _calculate_total_slots: r_agi
            _make_exec_result([]),  # _assign_ability_dwellers: r_str
            _make_exec_result([]),  # _assign_ability_dwellers: r_agi
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            result = await svc._assign_to_rooms_proportional(
                [r_str, r_agi], PRODUCTION_ABILITIES, mock_db, dwellers, [], set()
            )

        assert len(result) == 0  # both assigned


# ===================================================================
# unassign_all_dwellers
# ===================================================================


class TestUnassignAllDwellers:
    """Tests for unassign_all_dwellers."""

    @pytest.mark.asyncio
    async def test_no_dwellers_returns_zero(self, svc, mock_db):
        with patch("app.services.dweller_assignment_service.crud.dweller.get_multi_by_vault") as mock_get:
            mock_get.return_value = []
            result = await svc.unassign_all_dwellers(mock_db, "v1")

        assert result == {"unassigned_count": 0}

    @pytest.mark.asyncio
    async def test_unassigned_dwellers_not_counted(self, svc, mock_db):
        """Dwellers with room_id=None are skipped."""
        d = _make_dweller(_id=_D1, room_id=None)
        with (
            patch("app.services.dweller_assignment_service.crud.dweller.get_multi_by_vault") as mock_get,
            patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update,
        ):
            mock_get.return_value = [d]
            result = await svc.unassign_all_dwellers(mock_db, "v1")

        assert result == {"unassigned_count": 0}
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_assigned_dwellers_unassigned(self, svc, mock_db):
        d1 = _make_dweller(_id=_D1, room_id=_R1)
        d2 = _make_dweller(_id=_D2, room_id=_R2)
        with (
            patch("app.services.dweller_assignment_service.crud.dweller.get_multi_by_vault") as mock_get,
            patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update,
        ):
            mock_get.return_value = [d1, d2]
            result = await svc.unassign_all_dwellers(mock_db, "v1")

        assert result == {"unassigned_count": 2}
        assert mock_update.call_count == 2

    @pytest.mark.asyncio
    async def test_updates_to_idle_status(self, svc, mock_db):
        d = _make_dweller(_id=_D1, room_id=_R1)
        with (
            patch("app.services.dweller_assignment_service.crud.dweller.get_multi_by_vault") as mock_get,
            patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update,
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
    async def test_no_unassigned_dwellers_returns_empty(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH, size=3)
        responses = [_make_exec_result([r1]), _make_exec_result([])]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 0
        assert result["assignments"] == []

    @pytest.mark.asyncio
    async def test_no_rooms_returns_empty(self, svc, mock_db):
        d1 = _make_dweller(_id=_D1, strength=5)
        responses = [_make_exec_result([]), _make_exec_result([d1])]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 0

    @pytest.mark.asyncio
    async def test_assigns_dwellers_to_best_matching_rooms(self, svc, mock_db):
        r_str = _make_room(_id=_R_STR, name="Power Plant", ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        d_strong = _make_dweller(_id=_DSTRONG, strength=8)
        d_weak = _make_dweller(_id=_DWEAK, strength=3)

        responses = [
            _make_exec_result([r_str]),
            _make_exec_result([d_strong, d_weak]),
            _make_exec_result([]),  # room count
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            result = await svc.auto_assign_production_rooms(mock_db, "v1")

        assert result["assigned_count"] == 2

    @pytest.mark.asyncio
    async def test_full_rooms_skipped(self, svc, mock_db):
        r_str = _make_room(_id=_R_STR, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        d1 = _make_dweller(_id=_D1, strength=5)

        responses = [
            _make_exec_result([r_str]),
            _make_exec_result([d1]),
            _make_exec_result([MagicMock(), MagicMock()]),  # 2 already in room
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        with patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")

        assert result["assigned_count"] == 0
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_ability_priority_order(self, svc, mock_db):
        """Strength rooms filled first, even if dweller has higher agility."""
        r_str = _make_room(_id=_R_STR, ability=SPECIALEnum.STRENGTH, size=3)
        r_agi = _make_room(_id=_R_AGI, ability=SPECIALEnum.AGILITY, size=3)

        d_weak = _make_dweller(_id=_DWEAK, strength=2, agility=9)

        responses = [
            _make_exec_result([r_str, r_agi]),
            _make_exec_result([d_weak]),
            _make_exec_result([]),  # r_str count
            _make_exec_result([]),  # r_agi count
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        with patch("app.services.dweller_assignment_service.crud.dweller.update") as mock_update:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")

        assert result["assigned_count"] == 1
        last_call_args = mock_update.call_args
        assert last_call_args[0][1] == _DWEAK
        update_schema = last_call_args[0][2]
        assert update_schema.room_id == _R_STR  # assigned to first-priority room

    @pytest.mark.asyncio
    async def test_partially_filled_room_gets_remainder(self, svc, mock_db):
        r_str = _make_room(_id=_R_STR, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        dwellers = [
            _make_dweller(_id=_D1, strength=9),
            _make_dweller(_id=_D2, strength=7),
            _make_dweller(_id=_D3, strength=5),
        ]

        responses = [
            _make_exec_result([r_str]),
            _make_exec_result(dwellers),
            _make_exec_result([MagicMock()]),  # 1 existing → 1 slot
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            result = await svc.auto_assign_production_rooms(mock_db, "v1")

        assert result["assigned_count"] == 1  # only 1 slot

    @pytest.mark.asyncio
    async def test_multiple_rooms_under_same_ability(self, svc, mock_db):
        r1 = _make_room(_id=_R1, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        r2 = _make_room(_id=_R2, ability=SPECIALEnum.STRENGTH, size=3)  # cap 2
        dwellers = [
            _make_dweller(_id=_D1, strength=9),
            _make_dweller(_id=_D2, strength=8),
            _make_dweller(_id=_D3, strength=7),
            _make_dweller(_id=_D4, strength=6),
        ]

        responses = [
            _make_exec_result([r1, r2]),
            _make_exec_result(dwellers),
            _make_exec_result([]),  # r1 count
            _make_exec_result([]),  # r2 count
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        with patch("app.services.dweller_assignment_service.crud.dweller.update"):
            result = await svc.auto_assign_production_rooms(mock_db, "v1")

        assert result["assigned_count"] == 4


# ===================================================================
# auto_assign_all_rooms
# ===================================================================


class TestAutoAssignAllRooms:
    """Tests for auto_assign_all_rooms."""

    @pytest.mark.asyncio
    async def test_no_unassigned_dwellers_returns_empty(self, svc, mock_db):
        responses = [_make_exec_result([]), _make_exec_result([])]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await svc.auto_assign_all_rooms(mock_db, "v1")
        assert result["assigned_count"] == 0

    @pytest.mark.asyncio
    async def test_assigns_to_production_first(self, svc, mock_db):
        r_prod = _make_room(_id=_R_PROD, category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, size=3)
        d1 = _make_dweller(_id=_D1, strength=8)

        with patch.object(svc, "_assign_to_rooms_proportional") as mock_assign:
            mock_assign.return_value = []

            rooms_resp = _make_exec_result([r_prod])
            dwellers_resp = _make_exec_result([d1])
            mock_db.execute = AsyncMock(side_effect=[rooms_resp, dwellers_resp])

            result = await svc.auto_assign_all_rooms(mock_db, "v1")

        assert mock_assign.call_count == 4  # prod, medsci, radio, training
        assert result["assigned_count"] == 0

    @pytest.mark.asyncio
    async def test_categorizes_rooms_correctly(self, svc, mock_db):
        """Verify rooms categorized: production, medsci (MISC+INT), radio (MISC+CHA), training."""
        r_prod = _make_room(_id=_R1, category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, size=3)
        r_med = _make_room(_id=_R_MED, category=RoomTypeEnum.MISC, ability=SPECIALEnum.INTELLIGENCE, size=3)
        r_radio = _make_room(_id=_R_RADIO, category=RoomTypeEnum.MISC, ability=SPECIALEnum.CHARISMA, size=3)
        r_train = _make_room(_id=_R4, category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.STRENGTH, size=3)
        d1 = _make_dweller(_id=_D1, strength=5, intelligence=5, charisma=5)

        with patch.object(svc, "_assign_to_rooms_proportional") as mock_assign:
            mock_assign.return_value = []

            rooms_resp = _make_exec_result([r_prod, r_med, r_radio, r_train])
            dwellers_resp = _make_exec_result([d1])
            mock_db.execute = AsyncMock(side_effect=[rooms_resp, dwellers_resp])

            await svc.auto_assign_all_rooms(mock_db, "v1")

        assert mock_assign.call_count == 4
        assert mock_assign.call_args_list[0][0][0] == [r_prod]  # production
        assert mock_assign.call_args_list[1][0][0] == [r_med]  # medsci
        assert mock_assign.call_args_list[2][0][0] == [r_radio]  # radio
        assert mock_assign.call_args_list[3][0][0] == [r_train]  # training

    @pytest.mark.asyncio
    async def test_medsci_only_includes_intelligence_misc_rooms(self, svc, mock_db):
        """MISC rooms without INTELLIGENCE are not in medsci category."""
        r_misc_int = _make_room(_id=_R1, category=RoomTypeEnum.MISC, ability=SPECIALEnum.INTELLIGENCE, size=3)
        r_misc_other = _make_room(_id=_R2, category=RoomTypeEnum.MISC, ability=SPECIALEnum.LUCK, size=3)

        d1 = _make_dweller(_id=_D1, intelligence=5)

        with patch.object(svc, "_assign_to_rooms_proportional") as mock_assign:
            mock_assign.return_value = []

            rooms_resp = _make_exec_result([r_misc_int, r_misc_other])
            dwellers_resp = _make_exec_result([d1])
            mock_db.execute = AsyncMock(side_effect=[rooms_resp, dwellers_resp])

            await svc.auto_assign_all_rooms(mock_db, "v1")

        # Check medsci call (2nd call) — only r_misc_int
        medsci_rooms = mock_assign.call_args_list[1][0][0]
        assert len(medsci_rooms) == 1
        assert medsci_rooms[0].id == _R1

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
