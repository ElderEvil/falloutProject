from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.agents.dweller_chat_agent import (
    DwellerChatDeps,
    RoomInfo,
    dweller_chat_agent,
    list_all_rooms,
)
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.tests.factory.dwellers import create_fake_dweller

pytestmark = pytest.mark.asyncio(scope="module")


ROOM_CONFIGS: list[dict] = [
    {
        "name": "Living Quarters",
        "category": RoomTypeEnum.CAPACITY,
        "ability": SPECIALEnum.ENDURANCE,
        "size": 6,
        "size_min": 3,
        "size_max": 9,
    },
    {
        "name": "Weapon Workshop",
        "category": RoomTypeEnum.CRAFTING,
        "ability": None,
        "size": 6,
        "size_min": 3,
        "size_max": 9,
    },
    {
        "name": "Radio Studio",
        "category": RoomTypeEnum.MISC,
        "ability": SPECIALEnum.CHARISMA,
        "size": 3,
        "size_min": 3,
        "size_max": 3,
    },
    {
        "name": "Power Generator",
        "category": RoomTypeEnum.PRODUCTION,
        "ability": SPECIALEnum.STRENGTH,
        "size": 6,
        "size_min": 3,
        "size_max": 9,
    },
    {
        "name": "Overseer Office",
        "category": RoomTypeEnum.QUESTS,
        "ability": None,
        "size": 3,
        "size_min": 3,
        "size_max": 3,
    },
    {
        "name": "Theme Workshop",
        "category": RoomTypeEnum.THEME,
        "ability": None,
        "size": 3,
        "size_min": 3,
        "size_max": 3,
    },
    {
        "name": "Weight Room",
        "category": RoomTypeEnum.TRAINING,
        "ability": SPECIALEnum.STRENGTH,
        "size": 6,
        "size_min": 3,
        "size_max": 9,
    },
]

ROOM_DEFAULTS = {
    "base_cost": 100,
    "incremental_cost": 50,
    "t2_upgrade_cost": 500,
    "t3_upgrade_cost": 1500,
    "capacity": 4,
    "output": None,
    "tier": 1,
    "coordinate_x": 0,
    "coordinate_y": 0,
    "image_url": None,
}


async def _create_room(session: AsyncSession, vault_id, config: dict):
    data = {**ROOM_DEFAULTS, **config, "vault_id": vault_id}
    room_in = RoomCreate(**data)
    return await crud.room.create(db_session=session, obj_in=room_in)


@pytest_asyncio.fixture(name="all_type_rooms")
async def all_type_rooms_fixture(async_session: AsyncSession, vault: Vault):
    rooms = {}
    for i, config in enumerate(ROOM_CONFIGS):
        cfg = {**config, "coordinate_y": i}
        room = await _create_room(async_session, vault.id, cfg)
        rooms[config["category"].value] = room
    return rooms


def _make_ctx(db_session: AsyncSession, vault: Vault) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = DwellerChatDeps(db_session=db_session, dweller=MagicMock(), vault_id=vault.id)
    return ctx


@pytest.mark.asyncio
@pytest.mark.usefixtures("all_type_rooms")
class TestListAllRoomsReturnsAllTypes:
    async def test_returns_all_seven_categories(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """All 7 room types should appear in the result when they have capacity."""
        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        returned_categories = {r.category for r in result}
        expected_categories = {e.value for e in RoomTypeEnum}
        assert returned_categories == expected_categories, (
            f"Missing categories: {expected_categories - returned_categories}"
        )

    async def test_result_count_matches_rooms_created(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Should return exactly as many rooms as we created (all have capacity)."""
        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        assert len(result) == len(ROOM_CONFIGS)


@pytest.mark.asyncio
class TestListAllRoomsCapacityFiltering:
    async def test_excludes_full_capacity_room(
        self,
        async_session: AsyncSession,
        vault: Vault,
        all_type_rooms: dict,
    ):
        """A room at max capacity (size=3 → max=2) filled with 2 dwellers should be excluded."""
        radio = all_type_rooms[RoomTypeEnum.MISC.value]

        for _ in range(2):
            dweller_data = create_fake_dweller()
            dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
            d = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
            d.room_id = radio.id
            async_session.add(d)
        await async_session.flush()

        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        returned_ids = {r.room_id for r in result}
        assert str(radio.id) not in returned_ids, "Full-capacity room should be excluded"

    async def test_includes_room_with_available_capacity(
        self,
        async_session: AsyncSession,
        vault: Vault,
        all_type_rooms: dict,
    ):
        """Room with size=6 (max=4) and 1 dweller should be included."""
        power = all_type_rooms[RoomTypeEnum.PRODUCTION.value]

        dweller_data = create_fake_dweller()
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        d = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
        d.room_id = power.id
        async_session.add(d)
        await async_session.flush()

        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        returned_ids = {r.room_id for r in result}
        assert str(power.id) in returned_ids, "Room with available capacity should be included"

    async def test_includes_empty_room(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """An empty room should always be returned (0 < max_capacity)."""
        room = await _create_room(
            async_session,
            vault.id,
            {
                "name": "Empty Training",
                "category": RoomTypeEnum.TRAINING,
                "ability": SPECIALEnum.AGILITY,
                "size": 6,
                "size_min": 3,
                "size_max": 9,
                "coordinate_y": 20,
            },
        )

        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        returned_ids = {r.room_id for r in result}
        assert str(room.id) in returned_ids, "Empty room should be included"

    async def test_deleted_dwellers_not_counted(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Soft-deleted dwellers should NOT count toward capacity."""
        room = await _create_room(
            async_session,
            vault.id,
            {
                "name": "Haunted Quarters",
                "category": RoomTypeEnum.CAPACITY,
                "ability": SPECIALEnum.ENDURANCE,
                "size": 3,
                "size_min": 3,
                "size_max": 3,
                "coordinate_y": 21,
            },
        )
        for _ in range(2):
            dweller_data = create_fake_dweller()
            dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
            d = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
            d.room_id = room.id
            d.is_deleted = True
            async_session.add(d)
        await async_session.flush()

        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        returned_ids = {r.room_id for r in result}
        assert str(room.id) in returned_ids, "Room with only deleted dwellers should have capacity"


@pytest.mark.asyncio
class TestListAllRoomsRoomInfoStructure:
    async def test_room_info_fields_correct(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        room = await _create_room(
            async_session,
            vault.id,
            {
                "name": "Test Diner",
                "category": RoomTypeEnum.PRODUCTION,
                "ability": SPECIALEnum.AGILITY,
                "size": 6,
                "size_min": 3,
                "size_max": 9,
                "coordinate_y": 22,
            },
        )

        dweller_data = create_fake_dweller()
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        d = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
        d.room_id = room.id
        async_session.add(d)
        await async_session.flush()

        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        info = next(r for r in result if r.room_id == str(room.id))

        assert isinstance(info, RoomInfo)
        assert info.room_id == str(room.id)
        assert info.name == "Test Diner"
        assert info.category == RoomTypeEnum.PRODUCTION.value
        assert info.current_dwellers == 1
        assert info.max_capacity == 4
        assert info.ability == SPECIALEnum.AGILITY.value

    async def test_room_info_ability_none_when_room_has_no_ability(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        room = await _create_room(
            async_session,
            vault.id,
            {
                "name": "Craft Bench",
                "category": RoomTypeEnum.CRAFTING,
                "ability": None,
                "size": 3,
                "size_min": 3,
                "size_max": 3,
                "coordinate_y": 23,
            },
        )

        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        info = next(r for r in result if r.room_id == str(room.id))
        assert info.ability is None

    async def test_all_returned_items_are_room_info_instances(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        for item in result:
            assert isinstance(item, RoomInfo), f"Expected RoomInfo, got {type(item)}"


@pytest.mark.asyncio
class TestListAllRoomsToolRegistration:
    async def test_tool_is_registered(self):
        toolsets = dweller_chat_agent.toolsets

        from pydantic_ai import RunContext
        from pydantic_ai.models.test import TestModel
        from pydantic_ai.usage import RunUsage

        ctx = RunContext(
            deps=MagicMock(spec=DwellerChatDeps),
            model=TestModel(),
            usage=RunUsage(),
            prompt="",
            messages=[],
            run_step=0,
        )

        all_tools = {}
        for toolset in toolsets:
            tools = await toolset.get_tools(ctx)
            all_tools.update(tools)

        tool_names = list(all_tools.keys())
        assert "list_all_rooms" in tool_names, f"list_all_rooms not found in agent tools. Registered: {tool_names}"

    async def test_tool_count_is_at_least_four(self):
        toolsets = dweller_chat_agent.toolsets

        from pydantic_ai import RunContext
        from pydantic_ai.models.test import TestModel
        from pydantic_ai.usage import RunUsage

        ctx = RunContext(
            deps=MagicMock(spec=DwellerChatDeps),
            model=TestModel(),
            usage=RunUsage(),
            prompt="",
            messages=[],
            run_step=0,
        )

        all_tools = {}
        for toolset in toolsets:
            tools = await toolset.get_tools(ctx)
            all_tools.update(tools)

        assert len(all_tools) >= 4, f"Expected at least 4 tools, found {len(all_tools)}"


@pytest.mark.asyncio
class TestListAllRoomsIsolation:
    async def test_only_returns_rooms_from_target_vault(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        import random

        from faker import Faker

        from app.schemas.user import UserCreate
        from app.schemas.vault import VaultCreateWithUserID

        fake = Faker()
        user_in = UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password())
        other_user = await crud.user.create(db_session=async_session, obj_in=user_in)
        other_vault_in = VaultCreateWithUserID(
            number=random.randint(1, 999),
            bottle_caps=500,
            user_id=other_user.id,
        )
        other_vault = await crud.vault.create(db_session=async_session, obj_in=other_vault_in)

        other_room = await _create_room(
            async_session,
            other_vault.id,
            {
                "name": "Other Vault Room",
                "category": RoomTypeEnum.PRODUCTION,
                "ability": SPECIALEnum.STRENGTH,
                "size": 6,
                "size_min": 3,
                "size_max": 9,
                "coordinate_y": 0,
            },
        )

        our_room = await _create_room(
            async_session,
            vault.id,
            {
                "name": "Our Room",
                "category": RoomTypeEnum.PRODUCTION,
                "ability": SPECIALEnum.STRENGTH,
                "size": 6,
                "size_min": 3,
                "size_max": 9,
                "coordinate_y": 24,
            },
        )

        ctx = _make_ctx(async_session, vault)
        result = await list_all_rooms(ctx)

        returned_ids = {r.room_id for r in result}
        assert str(other_room.id) not in returned_ids, "Room from other vault should not appear"
        assert str(our_room.id) in returned_ids, "Room from our vault should appear"
