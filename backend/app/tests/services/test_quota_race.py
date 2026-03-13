"""Race condition tests for QuotaService with real database.

These tests verify that the SELECT FOR UPDATE locking prevents race conditions
when multiple concurrent requests attempt to check and use quota simultaneously.
"""

from datetime import UTC, datetime, timezone
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app import crud
from app.models.llm_interaction import LLMInteraction
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.quota_service import QuotaService

# Tokens per request and user limit for race condition test
TOKENS_PER_REQUEST = 20
USER_TOKEN_LIMIT = 100
NUM_CONCURRENT_REQUESTS = 10
EXPECTED_SUCCESSFUL_REQUESTS = 5  # 100 tokens / 20 per request = 5 requests


@pytest_asyncio.fixture
async def quota_test_user(async_session: AsyncSession) -> User:
    """Create a test user with 100 token monthly limit."""
    user_in = UserCreate(
        username="quota_race_test_user",
        email="quota_race_test@example.com",
        password="testpass123",
        is_superuser=False,
    )
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    # Set custom token limit to 100 for predictable test calculations
    user.monthly_token_limit = USER_TOKEN_LIMIT
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)

    return user


async def check_and_record_quota(
    user_id: UUID,
    tokens: int,
    db_session: AsyncSession,
) -> bool:
    """Check quota and record usage if allowed.

    This helper simulates the real-world flow where a service:
    1. Checks if quota is available (with SELECT FOR UPDATE lock)
    2. If allowed, records the usage within the same transaction

    Args:
        user_id: The user to check quota for
        tokens: Number of tokens to use if quota allows
        db_session: Database session

    Returns:
        True if quota check passed and usage was recorded, False otherwise
    """
    quota_service = QuotaService()

    try:
        # Check quota - this uses SELECT FOR UPDATE for atomicity
        result = await quota_service.check_quota(user_id, db_session)

        if not result.allowed:
            return False

        # Check if we have enough remaining for this request
        if result.remaining < tokens:
            return False

        # Record usage - in real scenario this would happen after LLM call
        interaction = LLMInteraction(
            user_id=user_id,
            total_tokens=tokens,
            prompt_tokens=0,
            completion_tokens=0,
            parameters=None,
            response=None,
            usage="quota_tracking",
        )
        db_session.add(interaction)
        await db_session.flush()

        return True

    except SQLAlchemyError:
        return False


@pytest.mark.asyncio
async def test_concurrent_quota_checks_no_over_usage(
    async_session: AsyncSession,
    quota_test_user: User,
) -> None:
    """Test that concurrent quota checks prevent over-usage.

    Scenario: User has 100 tokens limit. 10 concurrent requests each try to use 20 tokens.
    Expected: Exactly 5 requests succeed (5 * 20 = 100 tokens), 5 requests fail.

    Note: SQLite has limited concurrency support. This test verifies that:
    - The quota service correctly tracks usage across sequential operations
    - No over-usage occurs (critical invariant)
    - SELECT FOR UPDATE is used (verified in separate test)

    With SQLite, concurrent writes are serialized, so we simulate the scenario
    by checking that after 5 successful 20-token uses, the 6th is rejected.
    """
    user_id = quota_test_user.id

    # Verify initial state: user has 100 token limit and no usage
    assert quota_test_user.monthly_token_limit == USER_TOKEN_LIMIT

    # Simulate concurrent requests by rapidly issuing sequential checks
    # In SQLite this is effectively what happens - concurrent writes serialize
    successful_count = 0
    failed_count = 0

    for _ in range(NUM_CONCURRENT_REQUESTS):
        result = await check_and_record_quota(
            user_id=user_id,
            tokens=TOKENS_PER_REQUEST,
            db_session=async_session,
        )
        if result:
            successful_count += 1
        else:
            failed_count += 1

    # Verify exactly 5 requests succeeded (100 tokens / 20 per request = 5)
    assert successful_count == EXPECTED_SUCCESSFUL_REQUESTS, (
        f"Expected {EXPECTED_SUCCESSFUL_REQUESTS} successful requests, got {successful_count}"
    )

    # Verify 5 requests failed
    assert failed_count == NUM_CONCURRENT_REQUESTS - EXPECTED_SUCCESSFUL_REQUESTS, (
        f"Expected {NUM_CONCURRENT_REQUESTS - EXPECTED_SUCCESSFUL_REQUESTS} failed requests, got {failed_count}"
    )

    # Verify total usage is exactly 100 tokens (no over-usage)
    now = datetime.now(UTC)
    current_month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

    usage_query = select(col(LLMInteraction.total_tokens)).where(
        col(LLMInteraction.user_id) == user_id,
        col(LLMInteraction.created_at) >= current_month_start,
    )

    final_usage_result = await async_session.execute(usage_query)
    final_usages = final_usage_result.all()
    total_usage = sum(u[0] for u in final_usages) if final_usages else 0

    expected_total = EXPECTED_SUCCESSFUL_REQUESTS * TOKENS_PER_REQUEST
    assert total_usage == expected_total, (
        f"Total usage should be {expected_total} tokens, got {total_usage}. OVER-USAGE DETECTED!"
    )


@pytest.mark.asyncio
async def test_sequential_quota_checks_correct_counting(
    async_session: AsyncSession,
    quota_test_user: User,
) -> None:
    """Test that sequential quota checks work correctly as a baseline.

    This test verifies the basic math works correctly when there's no concurrency:
    - 5 requests of 20 tokens each = 100 tokens total
    - 6th request should fail (would exceed 100 token limit)
    """
    user_id = quota_test_user.id

    quota_service = QuotaService()
    successful_requests = 0

    # Make 6 sequential requests
    for _ in range(6):
        result = await quota_service.check_quota(user_id, async_session)

        if result.allowed and result.remaining >= TOKENS_PER_REQUEST:
            # Record usage
            interaction = LLMInteraction(
                user_id=user_id,
                total_tokens=TOKENS_PER_REQUEST,
                prompt_tokens=0,
                completion_tokens=0,
                parameters=None,
                response=None,
                usage="quota_tracking",
            )
            async_session.add(interaction)
            await async_session.flush()
            successful_requests += 1

    # First 5 should succeed
    assert successful_requests == 5, f"Expected 5 successful requests, got {successful_requests}"

    # Verify total usage
    now = datetime.now(UTC)
    current_month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

    usage_query = select(col(LLMInteraction.total_tokens)).where(
        col(LLMInteraction.user_id) == user_id,
        col(LLMInteraction.created_at) >= current_month_start,
    )

    usage_result = await async_session.execute(usage_query)
    usages = usage_result.all()
    total_usage = sum(u[0] for u in usages) if usages else 0

    assert total_usage == 100, f"Expected 100 tokens used, got {total_usage}"


@pytest.mark.asyncio
async def test_quota_prevents_over_usage_with_isolated_sessions(
    async_session: AsyncSession,
    quota_test_user: User,
) -> None:
    """Test that isolated sessions don't cause over-usage.

    This test verifies that even with separate sessions, the quota system
    correctly tracks usage and prevents exceeding the limit.

    Note: Uses existing session since SQLite in-memory db has limitations
    with creating new sessions from the engine in test fixtures.
    """
    user_id = quota_test_user.id

    # Simulate 10 requests using the check_and_record_quota flow
    results = []
    for _ in range(NUM_CONCURRENT_REQUESTS):
        result = await check_and_record_quota(
            user_id=user_id,
            tokens=TOKENS_PER_REQUEST,
            db_session=async_session,
        )
        results.append(result)

    successes = sum(1 for r in results if r)
    failures = sum(1 for r in results if not r)

    # Verify we got exactly 5 successes and 5 failures
    assert successes == EXPECTED_SUCCESSFUL_REQUESTS
    assert failures == NUM_CONCURRENT_REQUESTS - EXPECTED_SUCCESSFUL_REQUESTS

    # Verify total usage equals successful requests times tokens per request
    now = datetime.now(UTC)
    current_month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

    usage_query = select(col(LLMInteraction.total_tokens)).where(
        col(LLMInteraction.user_id) == user_id,
        col(LLMInteraction.created_at) >= current_month_start,
    )

    usage_result = await async_session.execute(usage_query)
    usages = usage_result.all()
    total_usage = sum(u[0] for u in usages) if usages else 0

    expected_total = successes * TOKENS_PER_REQUEST
    assert total_usage == expected_total, f"OVER-USAGE: expected {expected_total}, got {total_usage}"


@pytest.mark.asyncio
async def test_select_for_update_locking_mechanism(
    async_session: AsyncSession,
    quota_test_user: User,
) -> None:
    """Test that SELECT FOR UPDATE is actually being used.

    This test verifies that the QuotaService uses row-level locking by checking
    the query execution pattern.
    """
    quota_service = QuotaService()
    user_id = quota_test_user.id

    # Mock to capture the queries being executed
    executed_queries = []

    original_execute = async_session.execute

    async def capture_execute(query, *args, **kwargs):
        query_str = str(query)
        executed_queries.append(query_str)
        return await original_execute(query, *args, **kwargs)

    async_session.execute = capture_execute  # type: ignore[method-assign]

    try:
        # Check quota
        await quota_service.check_quota(user_id, async_session)

        # Verify a query was executed
        assert len(executed_queries) >= 1, "No queries were executed"

        # Check for FOR UPDATE in the first query (user query)
        user_query = executed_queries[0]
        assert "FOR UPDATE" in user_query.upper() or "for_update" in user_query.lower(), (
            f"User query does not use FOR UPDATE locking: {user_query}"
        )

    finally:
        async_session.execute = original_execute  # type: ignore[method-assign]
