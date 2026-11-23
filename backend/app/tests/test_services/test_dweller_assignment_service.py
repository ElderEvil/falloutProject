import uuid
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.room import Room
from app.services.dweller_assignment_service import (
    ABILITY_TO_STAT_MAP,
    MEDSCI_ABILITIES,
    PRODUCTION_ABILITIES,
    RADIO_ABILITIES,
    TRAINING_ABILITIES,
    DwellerAssignmentService,
    dweller_assignment_service,
)

SVC = "app.services.dweller_assignment_service"

# Stable UUIDs keep assignment ordering deterministic across runs.
_D1, _D2, _D3, _D4, _D5, _DSTRONG, _DWEAK = (
    uuid.UUID(n)
    for n in (
        "15a0766e-8c61-4e42-a7bb-fed34ed0a7ee",
        "e5cf820c-e7e6-4e4a-95f0-c12a9f96984a",
        "77ba2369-f980-4523-84b8-5e7d7f48d9cf",
        "4c3436ea-1daa-4689-858c-a5c7292bf1ae",
        "85286379-3647-4e62-b926-1a0d21a7f550",
        "50a1f0ba-b512-44b9-8e40-91762d652baf",
        "49d03e23-72e1-485f-aa62-7959ed2dd63a",
    )
)
_R1, _R2, _R3, _R4, _R_STR, _R_AGI, _R_PROD, _R_TRAIN, _R_MED, _R_RADIO, _R_CRAFT = (
    uuid.UUID(n)
    for n in (
        "b378c18e-3e8f-4203-9537-46c13d0ec7bc",
        "c0a89001-25a9-4787-a406-e86b162bc942",
        "9792b400-42ee-4110-98fb-365901d1788f",
        "d912e26c-4665-4258-9771-dc802d89f6b4",
        "ca4d8588-ce0a-487b-bbc3-c2e0cc4db770",
        "e8add549-6c49-4ba5-b64a-7029698d6745",
        "7b847537-b55b-4b6e-940c-b468f7d4e02f",
        "39856d32-88de-4138-b2e1-1355cb753cba",
        "0a00b469-9e82-427b-944b-b8c0c04b5e03",
        "d78c2ead-faef-4c77-b4d5-37094526be31",
        "5f2a1c3e-9b4d-4e6f-8a1b-2c3d4e5f6a7b",
    )
)


def _make_dweller(
    _id: UUID = _D1,
    *,
    strength: int = 5,
    perception: int = 5,
    endurance: int = 5,
    charisma: int = 5,
    intelligence: int = 5,
    agility: int = 5,
    luck: int = 5,
    room_id: UUID | None = None,
    vault_id: UUID | None = None,
    is_deleted: bool = False,
    is_dead: bool = False,
) -> MagicMock:
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
    _id: UUID = _R1,
    *,
    name: str = "Test Room",
    category: RoomTypeEnum = RoomTypeEnum.PRODUCTION,
    ability: SPECIALEnum = SPECIALEnum.STRENGTH,
    size: int | None = 3,
    size_min: int = 3,
    size_max: int = 6,
    vault_id: UUID | None = None,
) -> MagicMock:
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
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = list(items)
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


@contextmanager
def _assignment_env(
    *, rooms, adults=(), youth=None, occupants: int | Callable = 0, room_getter="get_by_category", with_update=True
):
    """Patch the CRUD surface an assignment pass touches; yields the mocks tests assert on."""
    mocks: dict[str, MagicMock] = {}
    with ExitStack() as stack:

        def p(path: str, **kwargs):
            return stack.enter_context(patch(f"{SVC}.crud.{path}", **kwargs))

        p(f"room.{room_getter}", new_callable=AsyncMock, return_value=list(rooms))
        mocks["adults"] = p("dweller.get_unassigned_adults", new_callable=AsyncMock, return_value=list(adults))
        if youth is None:
            mocks["youth"] = p("dweller.get_unassigned_youth")
        else:
            mocks["youth"] = p("dweller.get_unassigned_youth", new_callable=AsyncMock, return_value=list(youth))
        count = p("dweller.count_in_room", new_callable=AsyncMock)
        if callable(occupants):
            count.side_effect = occupants
        else:
            count.return_value = occupants
        mocks["count"] = count
        mocks["lock"] = p("dweller.lock_vault", new_callable=AsyncMock)
        if with_update:
            mocks["update"] = p("dweller.update")
        yield mocks


@pytest.fixture
def svc() -> DwellerAssignmentService:
    return DwellerAssignmentService()


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


class TestAssignAbilityDwellers:
    @pytest.mark.asyncio
    async def test_no_ability_specific_rooms_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(ability=SPECIALEnum.AGILITY)
        result = await svc._assign_ability_dwellers(
            SPECIALEnum.STRENGTH, [r1], mock_db, [_make_dweller(strength=7)], [], set(), 1
        )
        assert len(result) == 1
        assert result[0].id == _D1

    @pytest.mark.asyncio
    async def test_no_available_slots_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(size=3)
        with _assignment_env(rooms=[r1], occupants=2):
            result = await svc._assign_ability_dwellers(
                SPECIALEnum.STRENGTH, [r1], mock_db, [_make_dweller(strength=7)], [], set(), 1
            )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_skips_dwellers_at_training_stat_maximum(self, svc, mock_db):
        room = _make_room(_id=_R_TRAIN, category=RoomTypeEnum.TRAINING, ability=SPECIALEnum.PERCEPTION, size=3)
        capped_dweller = _make_dweller(perception=10)
        assignments: list[dict[str, str]] = []
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))
        with patch(f"{SVC}.training_service.start_training", new_callable=AsyncMock) as mock_start_training:
            result = await svc._assign_ability_dwellers(
                SPECIALEnum.PERCEPTION, [room], mock_db, [capped_dweller], assignments, set(), 1
            )
        assert result == [capped_dweller]
        assert assignments == []
        mock_start_training.assert_not_awaited()


class TestAssignToRoomsProportional:
    @pytest.mark.asyncio
    async def test_no_matching_ability_rooms_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(ability=SPECIALEnum.CHARISMA)
        result = await svc._assign_to_rooms_proportional(
            [r1], MEDSCI_ABILITIES, mock_db, [_make_dweller(strength=5)], [], set()
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_zero_total_slots_returns_unchanged(self, svc, mock_db):
        r1 = _make_room(size=3)
        with _assignment_env(rooms=[r1], occupants=2):
            result = await svc._assign_to_rooms_proportional(
                [r1], PRODUCTION_ABILITIES, mock_db, [_make_dweller(strength=5)], [], set()
            )
        assert len(result) == 1


class TestUnassignAllDwellers:
    @pytest.mark.asyncio
    async def test_updates_to_idle_status(self, svc, mock_db):
        d = _make_dweller(room_id=_R1)
        with (
            patch(f"{SVC}.crud.dweller.get_multi_by_vault") as mock_get,
            patch(f"{SVC}.crud.dweller.update") as mock_update,
            patch(f"{SVC}.crud.room.get_by_category", new_callable=AsyncMock, return_value=[]),
        ):
            mock_get.return_value = [d]
            await svc.unassign_all_dwellers(mock_db, "v1")
        call_args = mock_update.call_args
        assert call_args[0][0] is mock_db
        assert call_args[0][1] == _D1
        update_schema = call_args[0][2]
        assert update_schema.room_id is None
        assert update_schema.status == DwellerStatusEnum.IDLE


class TestAutoAssignProductionRooms:
    @pytest.mark.asyncio
    async def test_apprentice_does_not_consume_production_worker_capacity(self, svc, mock_db):
        room = _make_room(_id=_R_STR, size=3)  # 2 worker slots
        dweller = _make_dweller(strength=5)
        # One worker and one apprentice occupy the room.

        def count_room_occupants(_db, _room_id, *, include_apprentices=True):
            return 2 if include_apprentices else 1

        with _assignment_env(rooms=[room], adults=[dweller], occupants=count_room_occupants) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 1
        env["update"].assert_called_once()

    @pytest.mark.asyncio
    async def test_apprentice_fills_vacant_slot_without_taking_worker_slot(self, svc, mock_db):
        room = _make_room(_id=_R_STR, size=3)  # 2 worker slots
        youth = _make_dweller(strength=4)
        youth.is_mature = False
        # Two workers, no apprentice.
        with _assignment_env(rooms=[room], youth=[youth], occupants=2) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 1
        env["update"].assert_called_once()
        youth_update = env["update"].call_args[0][2]
        assert youth_update["room_id"] == _R_STR
        assert youth_update["apprentice_stat"] == SPECIALEnum.STRENGTH
        assert youth_update["apprentice_started_at"] is not None

    @pytest.mark.asyncio
    async def test_room_with_apprentice_gets_no_third_dweller(self, svc, mock_db):
        room = _make_room(_id=_R_STR, size=3)  # 2 worker slots
        adult = _make_dweller(strength=5)
        youth = _make_dweller(_id=_D2, strength=4)
        youth.is_mature = False
        # Two workers and one apprentice.

        def count_room_occupants(_db, _room_id, *, include_apprentices=True):
            return 3 if include_apprentices else 2

        with _assignment_env(rooms=[room], adults=[adult], youth=[youth], occupants=count_room_occupants) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 0
        env["update"].assert_not_called()

    @pytest.mark.asyncio
    async def test_no_youth_available_assigns_nothing_extra(self, svc, mock_db):
        room = _make_room(_id=_R_STR, size=3)  # 2 worker slots, two workers, no apprentice
        with _assignment_env(rooms=[room], occupants=2) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 0
        env["update"].assert_not_called()

    @pytest.mark.asyncio
    async def test_adult_age_group_filter_assigns_no_apprentices(self, svc, mock_db):
        room = _make_room(_id=_R_STR, size=3)
        with _assignment_env(rooms=[room], youth=None, occupants=0) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1", age_group=AgeGroupEnum.ADULT)
        assert result["assigned_count"] == 0
        env["youth"].assert_not_awaited()
        env["update"].assert_not_called()

    @pytest.mark.asyncio
    async def test_teen_age_group_filter_only_fills_teen_apprentices(self, svc, mock_db):
        room = _make_room(_id=_R_STR, size=3)
        teen = _make_dweller(strength=4)
        teen.is_mature = False
        teen.age_group = AgeGroupEnum.TEEN
        with _assignment_env(rooms=[room], youth=[teen], occupants=0) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1", age_group=AgeGroupEnum.TEEN)
        assert result["assigned_count"] == 1
        env["update"].assert_called_once()

    @pytest.mark.asyncio
    async def test_apprentice_pass_locks_vault_and_commits_once(self, svc, mock_db):
        # The vault row is locked for the pass, so two runs cannot both see the same vacant slot.
        room = _make_room(_id=_R_STR, size=3)
        youth = _make_dweller(strength=4)
        youth.is_mature = False
        with _assignment_env(rooms=[room], youth=[youth], occupants=0) as env:
            await svc.auto_assign_production_rooms(mock_db, "v1")
        env["lock"].assert_awaited_once_with(mock_db, "v1")
        assert env["update"].call_args.kwargs["commit"] is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_full_rooms_skipped(self, svc, mock_db):
        r_str = _make_room(_id=_R_STR, size=3)  # cap 2
        with _assignment_env(rooms=[r_str], adults=[_make_dweller(strength=5)], occupants=2) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 0
        env["update"].assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_ability_priority_order(self, svc, mock_db):
        r_str = _make_room(_id=_R_STR, size=3)
        r_agi = _make_room(_id=_R_AGI, ability=SPECIALEnum.AGILITY, size=3)
        d_weak = _make_dweller(_id=_DWEAK, strength=2, agility=9)
        with _assignment_env(rooms=[r_str, r_agi], adults=[d_weak], occupants=0) as env:
            result = await svc.auto_assign_production_rooms(mock_db, "v1")
        assert result["assigned_count"] == 1
        last_call_args = env["update"].call_args
        assert last_call_args[0][1] == _DWEAK
        assert last_call_args[0][2].room_id == _R_STR  # assigned to first-priority room


class TestAutoAssignTrainingRooms:
    @pytest.mark.asyncio
    async def test_assigns_lowest_eligible_stat_first(self, svc, mock_db):
        room = _make_room(_id=_R_TRAIN, category=RoomTypeEnum.TRAINING, size=3)
        strong = _make_dweller(_id=_DSTRONG, strength=8)
        weak = _make_dweller(_id=_DWEAK, strength=2)
        with (
            _assignment_env(rooms=[room], adults=[strong, weak], occupants=0, with_update=False),
            patch(f"{SVC}.training_service.start_training", new_callable=AsyncMock) as mock_start_training,
        ):
            result = await svc.auto_assign_training_rooms(mock_db, "v1")
        assert result["assigned_count"] == 2
        assert [call.args[1] for call in mock_start_training.await_args_list] == [_DWEAK, _DSTRONG]

    @pytest.mark.asyncio
    async def test_skips_dwellers_ineligible_for_work(self, svc, mock_db):
        # Feral dwellers never reach the training service.
        room = _make_room(_id=_R_TRAIN, category=RoomTypeEnum.TRAINING, size=3)
        feral = _make_dweller(strength=8)
        feral.visual_attributes = {"race": "ghoul", "state_of_being": "feral"}
        adult = _make_dweller(_id=_D2, strength=2)
        with (
            _assignment_env(rooms=[room], adults=[feral, adult], occupants=0, with_update=False),
            patch(f"{SVC}.training_service.start_training", new_callable=AsyncMock) as mock_start_training,
        ):
            result = await svc.auto_assign_training_rooms(mock_db, "v1")
        assert result["assigned_count"] == 1
        assert [call.args[1] for call in mock_start_training.await_args_list] == [_D2]


class TestTotalSpecial:
    def test_sums_all_seven_stats(self):
        d = _make_dweller(strength=1, perception=2, endurance=3, charisma=4, intelligence=5, agility=6, luck=7)
        assert DwellerAssignmentService._total_special(d) == 28

    def test_guards_none_stats(self):
        d = _make_dweller(strength=5)
        d.perception = None
        assert DwellerAssignmentService._total_special(d) == 30  # 5 * 6 remaining stats


class TestAutoAssignCraftingRooms:
    @pytest.mark.asyncio
    async def test_fills_crafting_rooms_by_descending_total_special(self, svc, mock_db):
        room = _make_room(_id=_R_CRAFT, category=RoomTypeEnum.CRAFTING, ability=None, size=9)
        high = _make_dweller(strength=7, perception=7, endurance=7, charisma=7, intelligence=7, agility=7, luck=7)
        low = _make_dweller(
            _id=_D2, strength=1, perception=1, endurance=1, charisma=1, intelligence=1, agility=1, luck=1
        )
        with _assignment_env(rooms=[room], adults=[low, high], occupants=0) as env:
            result = await svc.auto_assign_crafting_rooms(mock_db, "v1")
        assert result["assigned_count"] == 2
        assert [call.args[1] for call in env["update"].call_args_list] == [_D1, _D2]
        assert result["assignments"][0]["room_id"] == str(_R_CRAFT)

    @pytest.mark.asyncio
    async def test_skips_dwellers_ineligible_for_work(self, svc, mock_db):
        room = _make_room(_id=_R_CRAFT, category=RoomTypeEnum.CRAFTING, ability=None, size=9)
        feral = _make_dweller()
        feral.visual_attributes = {"race": "ghoul", "state_of_being": "feral"}
        adult = _make_dweller(_id=_D2)
        with _assignment_env(rooms=[room], adults=[feral, adult], occupants=0) as env:
            result = await svc.auto_assign_crafting_rooms(mock_db, "v1")
        assert result["assigned_count"] == 1
        assert [call.args[1] for call in env["update"].call_args_list] == [_D2]

    @pytest.mark.asyncio
    async def test_crafting_room_capacity_respected(self, svc, mock_db):
        room = _make_room(_id=_R_CRAFT, category=RoomTypeEnum.CRAFTING, ability=None, size=9)
        dwellers = [
            _make_dweller(
                _id=uuid.UUID(f"00000000-0000-4000-8000-{i:012d}"),
                strength=5,
                perception=5,
                endurance=5,
                charisma=5,
                intelligence=5,
                agility=5,
                luck=5,
            )
            for i in range(8)
        ]
        with _assignment_env(rooms=[room], adults=dwellers, occupants=0) as env:
            result = await svc.auto_assign_crafting_rooms(mock_db, "v1")
        assert result["assigned_count"] == 6
        assert env["update"].call_count == 6

    @pytest.mark.asyncio
    async def test_age_group_filter_passed_to_crud(self, svc, mock_db):
        room = _make_room(_id=_R_CRAFT, category=RoomTypeEnum.CRAFTING, ability=None, size=9)
        with _assignment_env(rooms=[room], adults=[], occupants=0) as env:
            result = await svc.auto_assign_crafting_rooms(mock_db, "v1", age_group=AgeGroupEnum.ADULT)
        assert result["assigned_count"] == 0
        env["adults"].assert_awaited_once_with(mock_db, "v1", AgeGroupEnum.ADULT)
        env["update"].assert_not_called()

    @pytest.mark.asyncio
    async def test_no_apprentice_pass_for_crafting(self, svc, mock_db):
        room = _make_room(_id=_R_CRAFT, category=RoomTypeEnum.CRAFTING, ability=None, size=9)
        adult = _make_dweller(strength=5, perception=5, endurance=5, charisma=5, intelligence=5, agility=5, luck=5)
        with _assignment_env(rooms=[room], adults=[adult], youth=None, occupants=0) as env:
            result = await svc.auto_assign_crafting_rooms(mock_db, "v1")
        assert result["assigned_count"] == 1
        env["youth"].assert_not_awaited()


class TestAutoAssignAllRooms:
    @pytest.mark.asyncio
    async def test_unassigned_dwellers_cascade_across_tiers(self, svc, mock_db):
        r_prod = _make_room(_id=_R1, size=3)
        r_train = _make_room(_id=_R2, category=RoomTypeEnum.TRAINING, size=3)
        d1 = _make_dweller(strength=5)
        with (
            patch.object(svc, "_assign_to_rooms_proportional") as mock_assign,
            patch(f"{SVC}.crud.dweller.get_unassigned_youth", new_callable=AsyncMock, return_value=[]),
            patch(f"{SVC}.crud.dweller.lock_vault", new_callable=AsyncMock),
        ):
            # production → d1 unassigned, medsci and radio have no rooms, training takes d1.
            mock_assign.side_effect = [[d1], [d1], [d1], []]
            mock_db.execute = AsyncMock(side_effect=[_make_exec_result([r_prod, r_train]), _make_exec_result([d1])])
            await svc.auto_assign_all_rooms(mock_db, "v1")
        assert mock_assign.call_count == 4
        assert mock_assign.call_args_list[1][0][3] == [d1]  # medsci receives d1
        assert mock_assign.call_args_list[3][0][3] == [d1]  # training receives d1

    @pytest.mark.asyncio
    async def test_crafting_rooms_filled_after_training_tier(self, svc, mock_db):
        r_craft = _make_room(_id=_R_CRAFT, category=RoomTypeEnum.CRAFTING, ability=None, size=9)
        d1 = _make_dweller(strength=5, perception=5, endurance=5, charisma=5, intelligence=5, agility=5, luck=5)
        with (
            patch.object(svc, "_assign_to_rooms_proportional", return_value=[d1]),
            _assignment_env(rooms=[r_craft], adults=[d1], occupants=0, room_getter="get_by_categories") as env,
        ):
            result = await svc.auto_assign_all_rooms(mock_db, "v1")
        assert result["assigned_count"] == 1
        assert result["assignments"][0]["room_id"] == str(_R_CRAFT)
        env["update"].assert_called_once()


class TestModuleConstants:
    def test_ability_to_stat_map_coverage(self):
        for stat in SPECIALEnum:
            assert stat in ABILITY_TO_STAT_MAP
            assert ABILITY_TO_STAT_MAP[stat] == stat.value

    def test_production_abilities_order(self):
        assert PRODUCTION_ABILITIES == [SPECIALEnum.STRENGTH, SPECIALEnum.AGILITY, SPECIALEnum.PERCEPTION]

    def test_medsci_abilities(self):
        assert MEDSCI_ABILITIES == [SPECIALEnum.INTELLIGENCE]

    def test_radio_abilities(self):
        assert RADIO_ABILITIES == [SPECIALEnum.CHARISMA]

    def test_training_abilities_includes_all(self):
        assert set(TRAINING_ABILITIES) == set(SPECIALEnum)


class TestServiceSingleton:
    def test_singleton_exists(self):
        assert isinstance(dweller_assignment_service, DwellerAssignmentService)
