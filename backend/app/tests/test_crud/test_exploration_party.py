"""Tests for exploration party-team CRUD (issue 772, phase 3)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import Exploration, ExplorationStatus
from app.models.team import Team, TeamMember
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


async def _vault_with_dwellers(async_session: AsyncSession, count: int) -> tuple[object, list[Dweller]]:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dwellers = [Dweller(**create_fake_dweller(), vault_id=vault.id) for _ in range(count)]
    async_session.add_all(dwellers)
    await async_session.commit()
    return vault, dwellers


async def _create_exploration(async_session: AsyncSession, vault, dweller: Dweller) -> Exploration:
    exploration = Exploration(
        dweller_id=dweller.id,
        vault_id=vault.id,
        duration=4,
        dweller_strength=5,
        dweller_perception=5,
        dweller_endurance=5,
        dweller_charisma=5,
        dweller_intelligence=5,
        dweller_agility=5,
        dweller_luck=5,
    )
    async_session.add(exploration)
    await async_session.commit()
    return exploration


async def _dispatch_team(async_session: AsyncSession, vault, exploration: Exploration, dwellers: list[Dweller]) -> Team:
    team = Team(vault_id=vault.id, exploration_id=exploration.id)
    async_session.add(team)
    await async_session.flush()
    async_session.add_all(
        [
            TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=slot, status="assigned")
            for slot, dweller in enumerate(dwellers, start=1)
        ]
    )
    await async_session.commit()
    return team


@pytest.mark.asyncio
async def test_get_exploration_team_returns_team_with_members(async_session: AsyncSession) -> None:
    """The dispatch team is found by exploration id with its roster eager-loaded."""
    vault, dwellers = await _vault_with_dwellers(async_session, 2)
    exploration = await _create_exploration(async_session, vault, dwellers[0])
    team = await _dispatch_team(async_session, vault, exploration, dwellers)

    found = await crud.team_crud.get_exploration_team(async_session, exploration.id)

    assert found is not None
    assert found.id == team.id
    assert found.exploration_id == exploration.id
    assert {member.dweller_id for member in found.members} == {dweller.id for dweller in dwellers}


@pytest.mark.asyncio
async def test_get_exploration_team_returns_none_for_unknown_run(async_session: AsyncSession) -> None:
    from uuid import uuid4

    assert await crud.team_crud.get_exploration_team(async_session, uuid4()) is None


@pytest.mark.asyncio
async def test_get_exploration_team_dwellers_returns_slot_ordered_dwellers(async_session: AsyncSession) -> None:
    """The party's Dweller rows come back in slot order with equipment eager-loaded."""
    vault, dwellers = await _vault_with_dwellers(async_session, 3)
    exploration = await _create_exploration(async_session, vault, dwellers[0])
    await _dispatch_team(async_session, vault, exploration, dwellers)

    party = await crud.team_crud.get_exploration_team_dwellers(async_session, exploration.id)

    assert [dweller.id for dweller in party] == [dweller.id for dweller in dwellers]


@pytest.mark.asyncio
async def test_get_exploration_team_dwellers_empty_without_team(async_session: AsyncSession) -> None:
    from uuid import uuid4

    assert await crud.team_crud.get_exploration_team_dwellers(async_session, uuid4()) == []


@pytest.mark.asyncio
async def test_get_in_progress_for_dwellers_returns_only_open_runs(async_session: AsyncSession) -> None:
    """Any exploring/returning run for any of the ids is returned; finished runs are not."""
    vault, dwellers = await _vault_with_dwellers(async_session, 2)
    active = await _create_exploration(async_session, vault, dwellers[0])
    finished = await _create_exploration(async_session, vault, dwellers[1])
    finished.status = ExplorationStatus.COMPLETED
    async_session.add(finished)
    await async_session.commit()

    runs = await crud.exploration.get_in_progress_for_dwellers(async_session, [dwellers[0].id, dwellers[1].id])

    assert [run.id for run in runs] == [active.id]


@pytest.mark.asyncio
async def test_get_in_progress_for_dwellers_empty_for_unknown_ids(async_session: AsyncSession) -> None:
    from uuid import uuid4

    assert await crud.exploration.get_in_progress_for_dwellers(async_session, [uuid4()]) == []
    assert await crud.exploration.get_in_progress_for_dwellers(async_session, []) == []
