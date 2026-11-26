from datetime import timedelta
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExpeditionRunStatus
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException
from app.utils.time import utcnow

SITE = "red_rocket"
RECENT = timedelta(days=7)


async def _make_exploration(async_session: AsyncSession):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    dweller = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id))
    )
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    return vault, dweller, exploration


async def _run(async_session, vault, exploration, *, site_id: str = SITE):
    return await crud.expedition_run.create_run(
        async_session, exploration_id=exploration.id, vault_id=vault.id, site_id=site_id
    )


async def _open_run(async_session, *, status=None):
    vault, dweller, exploration = await _make_exploration(async_session)
    run = await _run(async_session, vault, exploration)
    if status is not None:
        run.status = status
        run.finished_at = utcnow()
        async_session.add(run)
        await async_session.commit()
    return vault, exploration, run


@pytest.mark.parametrize("state", ["open", "none", "closed"])
async def test_get_open_for_exploration(async_session: AsyncSession, state: str) -> None:
    if state == "none":
        _, _, exploration = await _make_exploration(async_session)
        assert await crud.expedition_run.get_open_for_exploration(async_session, exploration.id) is None
        return

    status = ExpeditionRunStatus.CLEARED if state == "closed" else None
    vault, exploration, run = await _open_run(async_session, status=status)
    fetched = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    if state == "closed":
        assert fetched is None
        return
    assert run.status == ExpeditionRunStatus.IN_ROOM
    assert run.room_cursor == 0
    assert fetched is not None
    assert fetched.id == run.id


@pytest.mark.parametrize(
    "status", [ExpeditionRunStatus.CLEARED, ExpeditionRunStatus.RETREATED, ExpeditionRunStatus.DIED]
)
async def test_recent_terminal_matches_every_terminal_status(
    async_session: AsyncSession, status: ExpeditionRunStatus
) -> None:
    vault, _, run = await _open_run(async_session, status=status)

    found = await crud.expedition_run.get_recent_terminal(
        async_session, vault_id=vault.id, site_id=SITE, since=utcnow() - RECENT
    )
    assert found is not None
    assert found.id == run.id
    old = await crud.expedition_run.get_recent_terminal(
        async_session, vault_id=vault.id, site_id=SITE, since=utcnow() + timedelta(days=1)
    )
    assert old is None


@pytest.mark.parametrize("state", ["open", "other-site", "closed"])
async def test_get_open_for_vault_site(async_session: AsyncSession, state: str) -> None:
    status = ExpeditionRunStatus.RETREATED if state == "closed" else None
    vault, _, run = await _open_run(async_session, status=status)
    site_id = "super_duper_mart" if state == "other-site" else SITE
    found = await crud.expedition_run.get_open_for_vault_site(async_session, vault_id=vault.id, site_id=site_id)
    if state == "open":
        assert found is not None
        assert found.id == run.id
        other_site = await crud.expedition_run.get_open_for_vault_site(
            async_session, vault_id=vault.id, site_id="super_duper_mart"
        )
        assert other_site is None
    else:
        assert found is None


async def test_second_open_run_conflicts(async_session: AsyncSession) -> None:
    vault, exploration, _ = await _open_run(async_session)
    with pytest.raises(ResourceConflictException, match="already has an open expedition run"):
        await _run(async_session, vault, exploration)


async def test_second_exploration_same_site_conflicts(async_session: AsyncSession) -> None:
    vault, exploration, _ = await _open_run(async_session)
    dweller2 = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id))
    )
    exploration2 = await exploration_service.send_dweller(async_session, vault.id, dweller2.id, duration=4)
    with pytest.raises(ResourceConflictException, match="red_rocket already has an open expedition run"):
        await _run(async_session, vault, exploration2)


async def test_get_missing_run_raises(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException):
        await crud.expedition_run.get(async_session, uuid4())
