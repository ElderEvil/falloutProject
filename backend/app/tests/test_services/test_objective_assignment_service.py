import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.crud.objective import objective_crud
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.assignment import ObjectiveAssignmentService

_VAULT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")

_O1 = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_O2 = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_O3 = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
_O4 = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
_O5 = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
_O6 = uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")

_SEQ_PREFIX = "11111111-1111-4111-8111-0000000000"
_SEQUENTIAL_O_IDS = [_O1, _O2, _O3, _O4, _O5, _O6, *(uuid.UUID(f"{_SEQ_PREFIX}{n:02d}") for n in range(1, 6))]


def _make_exec_result(items: list) -> MagicMock:
    scalars = MagicMock()
    scalars.all.return_value = list(items)
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


def _make_exec_all(items: list) -> MagicMock:
    result = MagicMock()
    result.all.return_value = [(item,) for item in items]
    return result


def _make_objective(
    _id=_O1,
    *,
    challenge="Test Objective",
    reward="Test Reward",
    category=ObjectiveCategoryEnum.DAILY,
    objective_type="collect",
    target_amount=5,
):
    obj = MagicMock(spec=Objective)
    obj.id, obj.challenge, obj.reward = _id, challenge, reward
    obj.category, obj.objective_type, obj.target_amount = category, objective_type, target_amount
    return obj


@contextmanager
def _catalog(objectives, links):
    delete = AsyncMock()
    with (
        patch.object(objective_crud, "get_by_category", new_callable=AsyncMock, return_value=objectives),
        patch.object(objective_crud, "get_links_for_vault", new_callable=AsyncMock, return_value=links),
        patch.object(objective_crud, "delete_links", new=delete),
    ):
        yield delete


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def service(mock_db: AsyncMock) -> ObjectiveAssignmentService:
    return ObjectiveAssignmentService(mock_db)


@pytest.mark.asyncio
async def test_aggregates_all_three_categories(async_session, vault) -> None:
    objectives = [
        Objective(
            challenge=f"{category} task", reward="10 caps", category=category, objective_type="collect", target_amount=5
        )
        for category in ("daily", "weekly", "achievement")
    ]
    async_session.add_all(objectives)
    await async_session.commit()
    result = await ObjectiveAssignmentService(async_session).assign_all_objectives(vault.id)
    assert set(result) == {"daily", "weekly", "achievements"}
    assert all(len(rows) == 1 for rows in result.values())
    assert {link.objective_id for link in await objective_crud.get_links_for_vault(async_session, vault.id)} == {
        o.id for o in objectives
    }


@pytest.mark.asyncio
async def test_no_links_returns_zero(service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

    result = await service.clear_daily_objectives(_VAULT_ID)

    assert result == 0
    assert mock_db.delete.await_count == 0
    assert mock_db.commit.await_count == 0


@pytest.mark.asyncio
async def test_clears_existing_links(service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
    link = MagicMock(spec=VaultObjectiveProgressLink)
    link.objective_id = _O1
    with _catalog([_make_objective()], [link]) as mock_delete:
        result = await service.clear_weekly_objectives(_VAULT_ID)

    assert result == 1
    mock_delete.assert_awaited_once()
    assert mock_db.commit.await_count == 1


@pytest.mark.asyncio
async def test_no_objectives_available_returns_empty(service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
    old_link = MagicMock(spec=VaultObjectiveProgressLink)
    with _catalog([], [old_link]) as mock_delete:
        result = await service.refresh_daily_objectives(_VAULT_ID)

    assert result == []
    mock_delete.assert_awaited_once()
    assert mock_db.commit.await_count == 1


@pytest.mark.asyncio
async def test_no_weekly_still_commits(service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
    with (
        patch.object(objective_crud, "get_by_category", new_callable=AsyncMock, return_value=[]),
        patch.object(objective_crud, "get_links_for_vault", new_callable=AsyncMock, return_value=[]),
    ):
        result = await service.refresh_weekly_objectives(_VAULT_ID)

    assert result == []
    assert mock_db.commit.await_count == 1


@pytest.mark.asyncio
async def test_skips_already_assigned(service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
    objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(5)]
    mock_db.execute = AsyncMock(side_effect=[_make_exec_all([_O1]), _make_exec_result(objs)])  # O1 already assigned

    result = await service.assign_random_objectives(_VAULT_ID, count=4)

    # O1 is excluded, so max 4 remain, we want 4
    assert len(result) == 4
    assert _O1 not in {r.id for r in result}


@pytest.mark.parametrize(("constant", "expected"), [("DAILY_COUNT", 3), ("WEEKLY_COUNT", 7)])
def test_counts(constant: str, expected: int) -> None:
    assert getattr(ObjectiveAssignmentService, constant) == expected


async def test_daily_reset_preserves_earned_unclaimed_rewards() -> None:
    session = AsyncMock()
    earned = VaultObjectiveProgressLink(vault_id=_VAULT_ID, objective_id=_O1, progress=5, total=5)
    unfinished = VaultObjectiveProgressLink(vault_id=_VAULT_ID, objective_id=_O2, progress=1, total=5)
    service = ObjectiveAssignmentService(session)
    with _catalog([_make_objective(_O1), _make_objective(_O2)], [earned, unfinished]) as delete:
        assert await service.clear_daily_objectives(_VAULT_ID) == 1
        assert delete.call_args.args[1] == [unfinished]
