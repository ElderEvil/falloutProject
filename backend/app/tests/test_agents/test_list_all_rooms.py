from unittest.mock import MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.agents.dweller_chat_agent import DwellerChatDeps, RoomInfo, dweller_chat_agent, list_all_rooms
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.tests.factory.dwellers import create_fake_dweller

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
    return await crud.room.create(
        db_session=session, obj_in=RoomCreate(**{**ROOM_DEFAULTS, **config, "vault_id": vault_id})
    )


def _make_ctx(db_session: AsyncSession, vault: Vault) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = DwellerChatDeps(db_session=db_session, dweller=MagicMock(), vault_id=vault.id)
    return ctx


async def test_room_info_fields_correct(async_session: AsyncSession, vault: Vault):
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
    d = await crud.dweller.create(
        db_session=async_session, obj_in=DwellerCreate(**create_fake_dweller(), vault_id=vault.id)
    )
    d.room_id = room.id
    async_session.add(d)
    await async_session.flush()
    result = await list_all_rooms(_make_ctx(async_session, vault))
    info = next(r for r in result if r.room_id == str(room.id))
    assert isinstance(info, RoomInfo)
    assert ((info.room_id, info.name), (info.category, info.current_dwellers)) == (
        (str(room.id), "Test Diner"),
        (RoomTypeEnum.PRODUCTION.value, 1),
    )
    assert (info.max_capacity, info.ability) == (4, SPECIALEnum.AGILITY.value)


async def _registered_tool_names() -> set[str]:
    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.usage import RunUsage

    ctx = RunContext(
        deps=MagicMock(spec=DwellerChatDeps), model=TestModel(), usage=RunUsage(), prompt="", messages=[], run_step=0
    )
    names: set[str] = set()
    for toolset in dweller_chat_agent.toolsets:
        names.update((await toolset.get_tools(ctx)).keys())
    return names


EXPECTED_CHAT_TOOLS = {
    "list_all_rooms",
    "list_production_rooms",
    "list_training_rooms",
    "get_best_room_recommendation",
    "get_dweller_activity_briefing",
    "get_dweller_medical_status",
    "get_dweller_social_context",
}


async def test_expected_tools_are_registered():
    names = await _registered_tool_names()
    assert "list_all_rooms" in names, f"list_all_rooms not found in agent tools. Registered: {sorted(names)}"
    missing = EXPECTED_CHAT_TOOLS - names
    assert not missing, f"Expected chat tools missing from the agent: {sorted(missing)}"
