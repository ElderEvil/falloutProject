"""Deleting a dweller must not leave an orphaned in-progress journey."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, ExpeditionRunStatus, ExplorationStatus
from app.crud.team import team_crud
from app.models.dweller import Dweller
from app.models.team import Team, TeamMember
from app.models.vault import Vault
from app.services.dweller_service import dweller_service
from app.services.exploration.event_service import event_service
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
async def test_delete_dweller_rolls_back_journey_state_and_delivery_when_persist_fails(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed soft-delete must leave the journey, run, roster and delivery untouched."""
    partner = await dweller_service.create_random_dweller(async_session, vault.id, register_bio_places=False)
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
        site_id="collapsed_subway",
    )
    team = Team(vault_id=vault.id, exploration_id=exploration.id)
    async_session.add(team)
    await async_session.flush()
    async_session.add_all(
        [
            TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"),
            TeamMember(team_id=team.id, dweller_id=partner.id, slot_number=2, status="assigned"),
        ]
    )
    exploration.team_id = team.id
    async_session.add(exploration)
    await crud.dweller.update(async_session, partner.id, {"status": DwellerStatusEnum.EXPLORING}, commit=False)
    await async_session.commit()
    exploration_id, run_id, partner_id = exploration.id, run.id, partner.id

    published = AsyncMock()
    monkeypatch.setattr(event_service, "publish_sse", published)

    def fail_on_dweller_soft_delete(session, _flush_context, _instances) -> None:
        if any(isinstance(obj, Dweller) and obj.is_deleted for obj in session.dirty):
            raise RuntimeError("persist failed")

    event.listen(async_session.sync_session, "before_flush", fail_on_dweller_soft_delete)
    try:
        with pytest.raises(RuntimeError, match="persist failed"):
            await dweller_service.delete_dweller(async_session, partner_id, soft=True)
    finally:
        event.remove(async_session.sync_session, "before_flush", fail_on_dweller_soft_delete)

    await async_session.rollback()

    fresh_exploration = await crud.exploration.get(async_session, exploration_id)
    assert fresh_exploration is not None
    assert fresh_exploration.status == ExplorationStatus.ACTIVE
    fresh_run = await crud.expedition_run.get(async_session, run_id)
    assert fresh_run is not None
    assert fresh_run.status == ExpeditionRunStatus.IN_ROOM
    assert await team_crud.get_exploration_team(async_session, exploration_id) is not None

    fresh_partner = await crud.dweller.get(async_session, partner_id)
    assert fresh_partner is not None
    assert fresh_partner.is_deleted is False
    assert fresh_partner.status == DwellerStatusEnum.EXPLORING
    anchor = await crud.dweller.get(async_session, dweller.id)
    assert anchor is not None
    assert anchor.status == DwellerStatusEnum.EXPLORING
    published.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_party_member_restores_survivors_and_roster(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    teammate = await dweller_service.create_random_dweller(async_session, vault.id, register_bio_places=False)
    exploration = await exploration_service.send_dweller(
        async_session,
        vault.id,
        dweller.id,
        duration=4,
        stimpaks=0,
        radaways=0,
    )
    team = Team(vault_id=vault.id, exploration_id=exploration.id)
    async_session.add(team)
    await async_session.flush()
    async_session.add_all(
        [
            TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"),
            TeamMember(team_id=team.id, dweller_id=teammate.id, slot_number=2, status="assigned"),
        ]
    )
    exploration.team_id = team.id
    async_session.add(exploration)
    await crud.dweller.update(async_session, teammate.id, {"status": DwellerStatusEnum.EXPLORING}, commit=False)
    await async_session.commit()
    teammate_id = teammate.id
    exploration_id = exploration.id

    await dweller_service.delete_dweller(async_session, teammate_id, soft=True)

    fresh_exploration = await crud.exploration.get(async_session, exploration_id)
    assert fresh_exploration is not None
    assert fresh_exploration.status == ExplorationStatus.RECALLED
    assert await team_crud.get_exploration_team(async_session, exploration_id) is None

    survivor = await crud.dweller.get(async_session, dweller.id)
    assert survivor is not None
    assert survivor.status == DwellerStatusEnum.IDLE
    deleted = await crud.dweller.get(async_session, teammate_id, include_deleted=True)
    assert deleted is not None
    assert deleted.is_deleted is True
