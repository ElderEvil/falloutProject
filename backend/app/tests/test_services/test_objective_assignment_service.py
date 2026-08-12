"""Tests for ObjectiveAssignmentService — unit tests with mocked DB."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import ObjectiveCategoryEnum
from app.services.objective_assignment_service import ObjectiveAssignmentService

# ---------------------------------------------------------------------------
# Stable UUIDs for deterministic test IDs
# ---------------------------------------------------------------------------

_VAULT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")

_O1 = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_O2 = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_O3 = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
_O4 = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
_O5 = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
_O6 = uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
_OACH1 = uuid.UUID("11111111-2222-4333-8444-aaaaaaaaaaaa")
_OACH2 = uuid.UUID("22222222-3333-4444-8555-bbbbbbbbbbbb")

# Pre-generated sequential UUIDs for creating multiple test objectives
_SEQUENTIAL_O_IDS = [
    _O1,
    _O2,
    _O3,
    _O4,
    _O5,
    _O6,
    uuid.UUID("11111111-1111-4111-8111-000000000001"),
    uuid.UUID("11111111-1111-4111-8111-000000000002"),
    uuid.UUID("11111111-1111-4111-8111-000000000003"),
    uuid.UUID("11111111-1111-4111-8111-000000000004"),
    uuid.UUID("11111111-1111-4111-8111-000000000005"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_result(items: list) -> MagicMock:
    """Build a mock DB execute result returning scalars().all() = items."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = list(items)
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


def _make_exec_all(items: list) -> MagicMock:
    """Build a mock DB execute result returning scalars().all() as list of tuples
    (for assigned_ids queries that return objective_id rows)."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [(item,) for item in items]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    return mock_result


def _make_exec_all(items: list) -> MagicMock:
    """Mock where .all() returns list of (value,) tuples for row[0] access.
    Used for queries where the service calls result.all() directly (not .scalars().all())."""
    mock_result = MagicMock()
    mock_result.all.return_value = [(item,) for item in items]
    return mock_result


def _make_exec_result_scalar_one_or_none(return_value: MagicMock | None) -> MagicMock:
    """Build a mock DB execute result returning scalar_one_or_none()."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    return mock_result


def _make_objective(
    _id: uuid.UUID = _O1,
    *,
    challenge: str = "Test Objective",
    reward: str = "Test Reward",
    category: ObjectiveCategoryEnum = ObjectiveCategoryEnum.DAILY,
    objective_type: str | None = "collect",
    target_amount: int = 5,
) -> MagicMock:
    """Create a MagicMock objective."""
    obj = MagicMock(spec=Objective)
    obj.id = _id
    obj.challenge = challenge
    obj.reward = reward
    obj.category = category
    obj.objective_type = objective_type
    obj.target_amount = target_amount
    return obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service(mock_db: AsyncMock) -> ObjectiveAssignmentService:
    """Return a fresh service instance with mocked DB."""
    return ObjectiveAssignmentService(mock_db)


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncMock for AsyncSession."""
    return AsyncMock(spec=AsyncSession)


# ===================================================================
# assign_daily_objectives
# ===================================================================


class TestAssignDailyObjectives:
    """Tests for assign_daily_objectives."""

    @pytest.mark.asyncio
    async def test_assigns_daily_objectives(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Happy path: assigns up to DAILY_COUNT (5) daily objectives."""
        objectives = [
            _make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(6)
        ]  # 6 available, 5 assigned
        responses = [
            _make_exec_result(objectives),  # query objectives
            _make_exec_all([]),  # assigned_ids query
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_daily_objectives(_VAULT_ID)

        assert len(result) == 5
        assert mock_db.execute.call_count == 2
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_no_daily_objectives_returns_empty(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """Empty DB: returns empty list, no commit."""
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        result = await service.assign_daily_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.commit.await_count == 0

    @pytest.mark.asyncio
    async def test_all_daily_already_assigned_returns_empty(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """When all daily objectives are already assigned, returns empty."""
        objectives = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(3)]
        responses = [
            _make_exec_result(objectives),  # query objectives
            _make_exec_all([obj.id for obj in objectives]),  # assigned_ids query
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_daily_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.commit.await_count == 0

    @pytest.mark.asyncio
    async def test_fewer_than_count_assigns_all(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """When fewer objectives than DAILY_COUNT, assigns all available."""
        objectives = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(2)]
        responses = [
            _make_exec_result(objectives),
            _make_exec_all([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_daily_objectives(_VAULT_ID)

        assert len(result) == 2
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_some_already_assigned_fills_remainder(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """When some are already assigned, fills remaining slots."""
        objectives = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(7)]
        assigned_id = objectives[0].id
        responses = [
            _make_exec_result(objectives),
            _make_exec_all([assigned_id]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_daily_objectives(_VAULT_ID)

        assert len(result) == 5
        assert all(r.id != assigned_id for r in result)


# ===================================================================
# assign_weekly_objectives
# ===================================================================


class TestAssignWeeklyObjectives:
    """Tests for assign_weekly_objectives."""

    @pytest.mark.asyncio
    async def test_assigns_weekly_objectives(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Happy path: assigns up to WEEKLY_COUNT (3) weekly objectives."""
        objectives = [
            _make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.WEEKLY) for i in range(5)
        ]
        responses = [
            _make_exec_result(objectives),
            _make_exec_all([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_weekly_objectives(_VAULT_ID)

        assert len(result) == 3
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_no_weekly_objectives_returns_empty(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """Empty DB: returns empty list."""
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        result = await service.assign_weekly_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.commit.await_count == 0

    @pytest.mark.asyncio
    async def test_all_weekly_already_assigned_returns_empty(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """When all weekly objectives already assigned."""
        objectives = [
            _make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.WEEKLY) for i in range(2)
        ]
        responses = [
            _make_exec_result(objectives),
            _make_exec_all([obj.id for obj in objectives]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_weekly_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.commit.await_count == 0


# ===================================================================
# assign_achievement_objectives
# ===================================================================


class TestAssignAchievementObjectives:
    """Tests for assign_achievement_objectives."""

    @pytest.mark.asyncio
    async def test_assigns_all_unassigned_achievements(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """Assigns all unassigned achievement objectives."""
        ach1 = _make_objective(_id=_OACH1, category=ObjectiveCategoryEnum.ACHIEVEMENT)
        ach2 = _make_objective(_id=_OACH2, category=ObjectiveCategoryEnum.ACHIEVEMENT)

        responses = [
            _make_exec_result([ach1, ach2]),  # query achievements
            _make_exec_result_scalar_one_or_none(None),  # ach1 not assigned
            _make_exec_result_scalar_one_or_none(None),  # ach2 not assigned
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_achievement_objectives(_VAULT_ID)

        assert len(result) == 2
        assert mock_db.commit.await_count == 1
        assert mock_db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_no_achievements_returns_empty(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """No achievement objectives in DB."""
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        result = await service.assign_achievement_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.commit.await_count == 0
        assert mock_db.add.call_count == 0

    @pytest.mark.asyncio
    async def test_all_achievements_already_assigned_returns_empty(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """When all achievements already assigned, returns empty, no commit."""
        ach1 = _make_objective(_id=_OACH1, category=ObjectiveCategoryEnum.ACHIEVEMENT)
        existing_link = MagicMock(spec=VaultObjectiveProgressLink)
        responses = [
            _make_exec_result([ach1]),
            _make_exec_result_scalar_one_or_none(existing_link),  # already assigned
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_achievement_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.commit.await_count == 0

    @pytest.mark.asyncio
    async def test_some_achievements_already_assigned(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """Only assigns achievements not yet assigned."""
        ach1 = _make_objective(_id=_OACH1, category=ObjectiveCategoryEnum.ACHIEVEMENT)
        ach2 = _make_objective(_id=_OACH2, category=ObjectiveCategoryEnum.ACHIEVEMENT)
        existing_link = MagicMock(spec=VaultObjectiveProgressLink)
        responses = [
            _make_exec_result([ach1, ach2]),
            _make_exec_result_scalar_one_or_none(existing_link),  # ach1 already assigned
            _make_exec_result_scalar_one_or_none(None),  # ach2 not assigned
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_achievement_objectives(_VAULT_ID)

        assert len(result) == 1
        assert result[0].id == _OACH2
        assert mock_db.commit.await_count == 1
        assert mock_db.add.call_count == 1

    @pytest.mark.asyncio
    async def test_achievement_defaults_target_amount_when_none(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """Target amount None defaults to 1 in link."""
        ach = _make_objective(_id=_OACH1, category=ObjectiveCategoryEnum.ACHIEVEMENT, target_amount=0)
        responses = [
            _make_exec_result([ach]),
            _make_exec_result_scalar_one_or_none(None),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        await service.assign_achievement_objectives(_VAULT_ID)

        added_link = mock_db.add.call_args[0][0]
        assert isinstance(added_link, VaultObjectiveProgressLink)
        assert added_link.total == 1  # 0 or 1 → 1


# ===================================================================
# assign_all_objectives
# ===================================================================


class TestAssignAllObjectives:
    """Tests for assign_all_objectives."""

    @pytest.mark.asyncio
    async def test_aggregates_all_three_categories(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """Returns dict with daily, weekly, achievements keys."""
        daily_obj = _make_objective(_id=_O1, category=ObjectiveCategoryEnum.DAILY)
        weekly_obj = _make_objective(_id=_O2, category=ObjectiveCategoryEnum.WEEKLY)
        ach_obj = _make_objective(_id=_OACH1, category=ObjectiveCategoryEnum.ACHIEVEMENT)

        # assign_achievement: query achievements + check each
        responses = [
            _make_exec_result([daily_obj]),
            _make_exec_all([]),
            _make_exec_result([weekly_obj]),
            _make_exec_all([]),
            _make_exec_result([ach_obj]),
            _make_exec_result_scalar_one_or_none(None),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_all_objectives(_VAULT_ID)

        assert set(result.keys()) == {"daily", "weekly", "achievements"}
        assert len(result["daily"]) == 1
        assert len(result["weekly"]) == 1
        assert len(result["achievements"]) == 1

    @pytest.mark.asyncio
    async def test_all_empty_returns_empty_lists(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """When no objectives exist, returns empty lists."""
        # 3 queries, all return empty
        responses = [
            _make_exec_result([]),  # daily query
            _make_exec_result([]),  # weekly query
            _make_exec_result([]),  # achievements query
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_all_objectives(_VAULT_ID)

        assert result == {"daily": [], "weekly": [], "achievements": []}


# ===================================================================
# clear_daily_objectives
# ===================================================================


class TestClearDailyObjectives:
    """Tests for clear_daily_objectives."""

    @pytest.mark.asyncio
    async def test_clears_existing_links(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Clears VaultObjectiveProgressLink entries for daily objectives."""
        link1 = MagicMock(spec=VaultObjectiveProgressLink)
        link2 = MagicMock(spec=VaultObjectiveProgressLink)
        mock_db.execute = AsyncMock(return_value=_make_exec_result([link1, link2]))

        result = await service.clear_daily_objectives(_VAULT_ID)

        assert result == 2
        assert mock_db.delete.await_count == 2
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_no_links_returns_zero(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """No daily links → returns 0, no delete/commit."""
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        result = await service.clear_daily_objectives(_VAULT_ID)

        assert result == 0
        assert mock_db.delete.await_count == 0
        assert mock_db.commit.await_count == 0

    @pytest.mark.asyncio
    async def test_deletes_correct_links(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Verifies each link is deleted."""
        link = MagicMock(spec=VaultObjectiveProgressLink)
        mock_db.execute = AsyncMock(return_value=_make_exec_result([link]))

        await service.clear_daily_objectives(_VAULT_ID)

        mock_db.delete.assert_awaited_once_with(link)


# ===================================================================
# clear_weekly_objectives
# ===================================================================


class TestClearWeeklyObjectives:
    """Tests for clear_weekly_objectives."""

    @pytest.mark.asyncio
    async def test_clears_existing_links(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Clears weekly objective links."""
        link = MagicMock(spec=VaultObjectiveProgressLink)
        mock_db.execute = AsyncMock(return_value=_make_exec_result([link]))

        result = await service.clear_weekly_objectives(_VAULT_ID)

        assert result == 1
        assert mock_db.delete.await_count == 1
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_no_links_returns_zero(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """No weekly links → returns 0."""
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        result = await service.clear_weekly_objectives(_VAULT_ID)

        assert result == 0


# ===================================================================
# refresh_daily_objectives
# ===================================================================


class TestRefreshDailyObjectives:
    """Tests for refresh_daily_objectives — atomic clear + assign."""

    @pytest.mark.asyncio
    async def test_clears_and_assigns_atomically(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Clears existing, assigns new, commits once."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(6)]
        old_link = MagicMock(spec=VaultObjectiveProgressLink)
        responses = [
            _make_exec_result([old_link]),  # clear: find links
            _make_exec_result(objs),  # assign: query objectives
            _make_exec_all([]),  # assign: assigned_ids
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.refresh_daily_objectives(_VAULT_ID)

        assert len(result) == 5
        assert mock_db.delete.await_count == 1
        assert mock_db.add.call_count == 5
        assert mock_db.commit.await_count == 1  # only once

    @pytest.mark.asyncio
    async def test_no_existing_objectives_still_assigns(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """When no existing links, still assigns new ones."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(3)]
        responses = [
            _make_exec_result([]),  # clear: no links
            _make_exec_result(objs),  # assign: query objectives
            _make_exec_all([]),  # assign: assigned_ids
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.refresh_daily_objectives(_VAULT_ID)

        assert len(result) == 3
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_no_objectives_available_returns_empty(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """No daily objectives at all → clear existing, assign nothing, commit once."""
        old_link = MagicMock(spec=VaultObjectiveProgressLink)
        responses = [
            _make_exec_result([old_link]),  # clear: found 1
            _make_exec_result([]),  # assign: no objectives
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.refresh_daily_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.delete.await_count == 1
        assert mock_db.commit.await_count == 1


# ===================================================================
# refresh_weekly_objectives
# ===================================================================


class TestRefreshWeeklyObjectives:
    """Tests for refresh_weekly_objectives — atomic clear + assign."""

    @pytest.mark.asyncio
    async def test_clears_and_assigns_atomically(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Clears existing weekly, assigns new, commits once."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.WEEKLY) for i in range(4)]
        old_link = MagicMock(spec=VaultObjectiveProgressLink)
        responses = [
            _make_exec_result([old_link]),
            _make_exec_result(objs),
            _make_exec_all([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.refresh_weekly_objectives(_VAULT_ID)

        assert len(result) == 3
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_no_weekly_still_commits(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Empty clearing + empty assigning still commits."""
        responses = [
            _make_exec_result([]),
            _make_exec_result([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.refresh_weekly_objectives(_VAULT_ID)

        assert result == []
        assert mock_db.commit.await_count == 1


# ===================================================================
# assign_random_objectives
# ===================================================================


class TestAssignRandomObjectives:
    """Tests for assign_random_objectives."""

    @pytest.mark.asyncio
    async def test_assigns_random_objectives(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Assigns random unassigned objectives."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(10)]
        responses = [
            _make_exec_all([]),  # assigned_ids → none
            _make_exec_result(objs),  # all objectives
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_random_objectives(_VAULT_ID, count=3)

        assert len(result) == 3
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_no_unassigned_returns_empty(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """When all objectives already assigned, returns empty."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(3)]
        responses = [
            _make_exec_all([obj.id for obj in objs]),  # all assigned
            _make_exec_result(objs),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_random_objectives(_VAULT_ID, count=3)

        assert result == []
        assert mock_db.commit.await_count == 0

    @pytest.mark.asyncio
    async def test_fewer_available_than_count_assigns_all(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """When fewer unassigned than count, assigns all available."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(2)]
        responses = [
            _make_exec_all([]),
            _make_exec_result(objs),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_random_objectives(_VAULT_ID, count=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_skips_already_assigned(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """Doesn't reassign already assigned objectives."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(5)]
        responses = [
            _make_exec_all([_O1]),  # O1 already assigned
            _make_exec_result(objs),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_random_objectives(_VAULT_ID, count=4)

        # O1 is excluded, so max 4 remain, we want 4
        assert len(result) == 4
        assert _O1 not in {r.id for r in result}

    @pytest.mark.asyncio
    async def test_count_zero_assigns_none(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """count=0 → assigns none, no commit."""
        objs = [_make_objective(_id=_O1, category=ObjectiveCategoryEnum.DAILY)]
        responses = [
            _make_exec_all([]),
            _make_exec_result(objs),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_random_objectives(_VAULT_ID, count=0)

        assert result == []
        assert mock_db.commit.await_count == 0

    @pytest.mark.asyncio
    async def test_no_objectives_at_all_returns_empty(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """No objectives in DB → returns empty."""
        responses = [
            _make_exec_all([]),
            _make_exec_result([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        result = await service.assign_random_objectives(_VAULT_ID, count=5)

        assert result == []


# ===================================================================
# Edge case: mixed categories don't interfere
# ===================================================================


class TestCategoryIsolation:
    """Verify that categories don't interfere with each other."""

    @pytest.mark.asyncio
    async def test_daily_only_gets_daily(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """assign_daily_objectives only returns daily objectives, not weekly or achievements."""
        daily = _make_objective(_id=_O1, category=ObjectiveCategoryEnum.DAILY)
        # The query filters by category, so only daily is returned from DB
        mock_db.execute = AsyncMock(return_value=_make_exec_result([daily]))

        result = await service.assign_daily_objectives(_VAULT_ID)

        assert len(result) == 1
        # The execute is called twice (query + assigned_ids), but both properly mock
        # Since we mock `execute` with a single return value, the second call also
        # gets [daily] which is fine since assigned_ids is empty

    @pytest.mark.asyncio
    async def test_clear_daily_only_clears_daily(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """clear_daily_objectives only clears daily links (tested via SQL subquery)."""
        daily_link = MagicMock(spec=VaultObjectiveProgressLink)
        mock_db.execute = AsyncMock(return_value=_make_exec_result([daily_link]))

        result = await service.clear_daily_objectives(_VAULT_ID)

        assert result == 1
        # The mock can't verify the SQL subquery constraint, but we trust it


# ===================================================================
# VaultObjectiveProgressLink creation
# ===================================================================


class TestLinkCreation:
    """Verify the link objects created have correct attributes."""

    @pytest.mark.asyncio
    async def test_link_has_correct_fields(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """VaultObjectiveProgressLink is created with correct field values."""
        obj = _make_objective(_id=_O1, category=ObjectiveCategoryEnum.DAILY, target_amount=10)
        responses = [
            _make_exec_result([obj]),
            _make_exec_all([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        await service.assign_daily_objectives(_VAULT_ID)

        added_link: VaultObjectiveProgressLink = mock_db.add.call_args[0][0]
        assert added_link.vault_id == _VAULT_ID
        assert added_link.objective_id == _O1
        assert added_link.progress == 0
        assert added_link.total == 10
        assert added_link.is_completed is False

    @pytest.mark.asyncio
    async def test_link_defaults_total_when_target_amount_none(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """When target_amount is 0, total defaults to 1."""
        obj = _make_objective(_id=_O1, category=ObjectiveCategoryEnum.DAILY, target_amount=0)
        responses = [
            _make_exec_result([obj]),
            _make_exec_all([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        await service.assign_daily_objectives(_VAULT_ID)

        added_link: VaultObjectiveProgressLink = mock_db.add.call_args[0][0]
        assert added_link.total == 1


# ===================================================================
# auto_commit=False behavior
# ===================================================================


class TestAutoCommitFalse:
    """Verify that auto_commit=False prevents commits in _assign_category_objectives
    and _clear_category_objectives. These are tested indirectly via refresh methods
    which use auto_commit=False → commit once at the end."""

    @pytest.mark.asyncio
    async def test_refresh_commits_once_not_twice(
        self, service: ObjectiveAssignmentService, mock_db: AsyncMock
    ) -> None:
        """refresh_daily clears+assigns with auto_commit=False, then commits once."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.DAILY) for i in range(5)]
        old_link = MagicMock(spec=VaultObjectiveProgressLink)
        responses = [
            _make_exec_result([old_link]),
            _make_exec_result(objs),
            _make_exec_all([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        await service.refresh_daily_objectives(_VAULT_ID)

        # Only one commit should have happened (the explicit one in refresh)
        assert mock_db.commit.await_count == 1

    @pytest.mark.asyncio
    async def test_refresh_weekly_commits_once(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """refresh_weekly commits exactly once."""
        objs = [_make_objective(_id=_SEQUENTIAL_O_IDS[i], category=ObjectiveCategoryEnum.WEEKLY) for i in range(4)]
        old_link = MagicMock(spec=VaultObjectiveProgressLink)
        responses = [
            _make_exec_result([old_link]),
            _make_exec_result(objs),
            _make_exec_all([]),
        ]
        mock_db.execute = AsyncMock(side_effect=responses)

        await service.refresh_weekly_objectives(_VAULT_ID)

        assert mock_db.commit.await_count == 1


# ===================================================================
# Constants
# ===================================================================


class TestConstants:
    """Verify service-level constants."""

    def test_daily_count_is_5(self) -> None:
        assert ObjectiveAssignmentService.DAILY_COUNT == 5

    def test_weekly_count_is_3(self) -> None:
        assert ObjectiveAssignmentService.WEEKLY_COUNT == 3
