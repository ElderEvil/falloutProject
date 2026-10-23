"""Tick performance probe: wall-time and query-count regression signal.

Seeds real vaults via `vault_service.initiate_vault` (parametrized normal vs
boosted) and times full `process_vault_tick` runs. Marked slow: it exercises
real phase work instead of mocks. The printed per-tick timings and SQL statement
counts are the actual signal (compare before/after runs): wall time is noisy and
SQLite latency is not PostgreSQL latency, but the statement count is the stable
N+1 signal for the tick phases. Objective event handlers are not registered
here, so their round-trips are covered by test_objective_evaluators instead.
Assertion bounds are deliberately generous so CI never flakes.
"""

import math
import statistics
import time

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.schemas.user import UserCreate
from app.schemas.vault import VaultNumber
from app.services.game_loop import game_loop_service
from app.services.vault_service import vault_service
from app.tests.utils.query_counter import count_sql_statements

WARMUP_RUNS = 1
MEASURED_RUNS = 6
P95_UPPER_BOUND_SECONDS = 10.0
# Structural guard: roughly 2x today's phase counts (101 normal, 178 boosted).
# A large N+1 moves this; ordinary feature work does not.
STATEMENTS_PER_TICK_UPPER_BOUND = 250


@pytest.mark.slow
@pytest.mark.parametrize("is_boosted", [False, True], ids=["normal", "boosted"])
async def test_vault_tick_wall_time(async_session: AsyncSession, is_boosted: bool) -> None:
    """Time full vault ticks over a really seeded vault; fail only on extreme blowup."""
    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(
            username=f"tickperf_{'boosted' if is_boosted else 'normal'}",
            email=f"tickperf_{'boosted' if is_boosted else 'normal'}@example.com",
            password="TickPerf123!",
        ),
    )
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=902 if is_boosted else 901),
        user_id=user.id,
        is_boosted=is_boosted,
    )

    for _ in range(WARMUP_RUNS):
        await game_loop_service.process_vault_tick(async_session, vault.id)

    samples_ms: list[float] = []
    samples_statements: list[int] = []
    for _ in range(MEASURED_RUNS):
        with count_sql_statements(async_session) as statements:
            started = time.perf_counter()
            result = await game_loop_service.process_vault_tick(async_session, vault.id)
            samples_ms.append((time.perf_counter() - started) * 1000.0)
        samples_statements.append(statements.value)
        assert "updates" in result

    label = "boosted" if is_boosted else "normal"
    mean_ms = statistics.fmean(samples_ms)
    ordered = sorted(samples_ms)
    p95_ms = ordered[math.ceil(0.95 * len(ordered)) - 1]
    print(
        f"\n[tick-perf:{label}] runs={MEASURED_RUNS} mean={mean_ms:.0f}ms p95={p95_ms:.0f}ms "
        f"max={max(samples_ms):.0f}ms statements/tick={sorted(samples_statements)}"
    )
    assert min(samples_statements) > 0, "statement counter observed no SQL; the probe is broken"
    assert max(samples_statements) <= STATEMENTS_PER_TICK_UPPER_BOUND
    assert p95_ms / 1000.0 < P95_UPPER_BOUND_SECONDS
