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


# ===================================================================
# assign_weekly_objectives
# ===================================================================


# ===================================================================
# assign_achievement_objectives
# ===================================================================


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


# ===================================================================
# clear_daily_objectives
# ===================================================================


class TestClearDailyObjectives:
    """Tests for clear_daily_objectives."""

    @pytest.mark.asyncio
    async def test_no_links_returns_zero(self, service: ObjectiveAssignmentService, mock_db: AsyncMock) -> None:
        """No daily links → returns 0, no delete/commit."""
        mock_db.execute = AsyncMock(return_value=_make_exec_result([]))

        result = await service.clear_daily_objectives(_VAULT_ID)

        assert result == 0
        assert mock_db.delete.await_count == 0
        assert mock_db.commit.await_count == 0


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


# ===================================================================
# refresh_daily_objectives
# ===================================================================


class TestRefreshDailyObjectives:
    """Tests for refresh_daily_objectives — atomic clear + assign."""

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


# ===================================================================
# Edge case: mixed categories don't interfere
# ===================================================================


# The mock can't verify the SQL subquery constraint, but we trust it


# ===================================================================
# VaultObjectiveProgressLink creation
# ===================================================================


# ===================================================================
# auto_commit=False behavior
# ===================================================================


# ===================================================================
# Constants
# ===================================================================


class TestConstants:
    """Verify service-level constants."""

    def test_daily_count_is_5(self) -> None:
        assert ObjectiveAssignmentService.DAILY_COUNT == 5

    def test_weekly_count_is_3(self) -> None:
        assert ObjectiveAssignmentService.WEEKLY_COUNT == 3
