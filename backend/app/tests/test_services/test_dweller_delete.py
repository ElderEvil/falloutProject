"""Deleting a dweller must not leave an orphaned in-progress journey."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExpeditionRunStatus, ExplorationStatus
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.dweller_service import dweller_service
from app.services.exploration_service import exploration_service


@pytest.mark.asyncio
async def test_delete_dweller_closes_active_exploration(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(
        async_session,
        vault.id,
        dweller.id,
        duration=4,
        stimpaks=0,
        radaways=0,
    )
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        site_id="gloomwater_bog",
    )

    await dweller_service.delete_dweller(async_session, dweller.id, soft=True)

    fresh_exploration = await crud.exploration.get(async_session, exploration.id)
    assert fresh_exploration is not None
    assert fresh_exploration.status == ExplorationStatus.RECALLED
    assert fresh_exploration.end_time is not None
    assert fresh_exploration.return_started_at is None
    assert fresh_exploration.return_completes_at is None
    assert fresh_exploration.paused_at is None
    assert fresh_exploration.unclaimed_loot == []

    fresh_run = await crud.expedition_run.get(async_session, run.id)
    assert fresh_run is not None
    assert fresh_run.status == ExpeditionRunStatus.RETREATED
    assert fresh_run.finished_at is not None

    fresh_dweller = await crud.dweller.get(async_session, dweller.id, include_deleted=True)
    assert fresh_dweller is not None
    assert fresh_dweller.is_deleted is True
    assert await crud.exploration.get_by_dweller(async_session, dweller_id=dweller.id) is None


@pytest.mark.asyncio
async def test_delete_dweller_rolls_back_journey_close_when_delete_fails(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    exploration = await exploration_service.send_dweller(
        async_session,
        vault.id,
        dweller.id,
        duration=4,
        stimpaks=0,
        radaways=0,
    )
    exploration_id = exploration.id
    dweller_id = dweller.id

    async def failing_delete(*args: object, **kwargs: object) -> None:
        raise RuntimeError("delete failed")

    monkeypatch.setattr(crud.dweller, "delete", failing_delete)

    with pytest.raises(RuntimeError, match="delete failed"):
        await dweller_service.delete_dweller(async_session, dweller_id, soft=True)

    await async_session.rollback()

    fresh_exploration = await crud.exploration.get(async_session, exploration_id)
    assert fresh_exploration is not None
    assert fresh_exploration.status == ExplorationStatus.ACTIVE
    assert (await crud.dweller.get(async_session, dweller_id)) is not None
