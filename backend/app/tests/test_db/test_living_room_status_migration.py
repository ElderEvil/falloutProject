"""Regression coverage for the Living Quarters status backfill."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import room as room_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic/versions/2026_08_21_0001-d4e5f6a7b8c9_backfill_living_quarters_socializing_status.py"
)
MIGRATION_SPEC = importlib.util.spec_from_file_location("living_room_status_migration", MIGRATION_PATH)
assert MIGRATION_SPEC
assert MIGRATION_SPEC.loader
MIGRATION = importlib.util.module_from_spec(MIGRATION_SPEC)
MIGRATION_SPEC.loader.exec_module(MIGRATION)


@pytest.mark.asyncio
async def test_backfill_skips_non_capacity_living_room(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    room = await room_crud.create(
        async_session,
        RoomCreate(
            vault_id=vault.id,
            name="Living Room",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.CHARISMA,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            capacity=2,
            size_min=1,
            size_max=3,
        ),
    )
    dweller.room_id = room.id
    dweller.status = DwellerStatusEnum.WORKING
    async_session.add(dweller)
    await async_session.commit()

    sqlite_sql = MIGRATION.BACKFILL_SOCIALIZING_DWELLERS_SQL.replace("::dwellerstatusenum", "").replace(
        "::roomtypeenum", ""
    )
    await async_session.execute(text(sqlite_sql))
    await async_session.commit()
    await async_session.refresh(dweller)

    assert dweller.status == DwellerStatusEnum.WORKING
