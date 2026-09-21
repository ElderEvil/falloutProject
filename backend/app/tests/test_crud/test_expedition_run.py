"""CRUD tests for expedition runs (SQLite, no network)."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.exploration import ExpeditionRunStatus
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


async def _make_exploration(async_session: AsyncSession):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id)),
    )
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    return vault, dweller, exploration


@pytest.mark.asyncio
async def test_create_and_fetch_open_run(async_session: AsyncSession):
    vault, dweller, exploration = await _make_exploration(async_session)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
    )
    assert run.status == ExpeditionRunStatus.ENTERED
    assert run.room_cursor == 0

    fetched = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert fetched is not None
    assert fetched.id == run.id


@pytest.mark.asyncio
async def test_no_open_run_initially(async_session: AsyncSession):
    _, _, exploration = await _make_exploration(async_session)
    assert await crud.expedition_run.get_open_for_exploration(async_session, exploration.id) is None


@pytest.mark.asyncio
async def test_closed_run_is_not_open(async_session: AsyncSession):
    vault, dweller, exploration = await _make_exploration(async_session)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
    )
    run.status = ExpeditionRunStatus.CLEARED
    async_session.add(run)
    await async_session.commit()
    assert await crud.expedition_run.get_open_for_exploration(async_session, exploration.id) is None


@pytest.mark.asyncio
async def test_recent_clear_found_for_anti_farm(async_session: AsyncSession):
    from datetime import datetime, timedelta

    vault, dweller, exploration = await _make_exploration(async_session)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
    )
    run.status = ExpeditionRunStatus.CLEARED
    run.cleared_at = datetime.utcnow()
    async_session.add(run)
    await async_session.commit()

    found = await crud.expedition_run.get_recent_clear(
        async_session, vault_id=vault.id, site_id="red_rocket", since=datetime.utcnow() - timedelta(days=7)
    )
    assert found is not None
    assert found.id == run.id

    old = await crud.expedition_run.get_recent_clear(
        async_session, vault_id=vault.id, site_id="red_rocket", since=datetime.utcnow() + timedelta(days=1)
    )
    assert old is None


@pytest.mark.asyncio
async def test_second_open_run_conflicts(async_session: AsyncSession):
    vault, dweller, exploration = await _make_exploration(async_session)
    await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        dweller_id=dweller.id,
        site_id="red_rocket",
    )
    with pytest.raises(ResourceConflictException, match="already has an open expedition run"):
        await crud.expedition_run.create_run(
            async_session,
            exploration_id=exploration.id,
            vault_id=vault.id,
            dweller_id=dweller.id,
            site_id="red_rocket",
        )


@pytest.mark.asyncio
async def test_get_missing_run_raises(async_session: AsyncSession):
    from uuid import uuid4

    with pytest.raises(ResourceNotFoundException):
        await crud.expedition_run.get(async_session, uuid4())
