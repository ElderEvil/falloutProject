"""Tick performance probe: wall-time regression signal for the game-loop refactor.

Seeds real vaults via `vault_service.initiate_vault` (parametrized normal vs
boosted) and times full `process_vault_tick` runs. Marked slow: it exercises
real phase work instead of mocks. The printed per-tick timings are the actual
signal (compare before/after runs); the assertion bound is deliberately
generous so CI never flakes on timing.
"""

import statistics
import time

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.schemas.user import UserCreate
from app.schemas.vault import VaultNumber
from app.services.game_loop import game_loop_service
from app.services.vault_service import vault_service

WARMUP_RUNS = 1
MEASURED_RUNS = 6
P95_UPPER_BOUND_SECONDS = 10.0


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
    for _ in range(MEASURED_RUNS):
        started = time.perf_counter()
        result = await game_loop_service.process_vault_tick(async_session, vault.id)
        samples_ms.append((time.perf_counter() - started) * 1000.0)
        assert "updates" in result

    label = "boosted" if is_boosted else "normal"
    mean_ms = statistics.fmean(samples_ms)
    p95_ms = sorted(samples_ms)[max(0, int(len(samples_ms) * 0.95) - 1)]
    print(
        f"\n[tick-perf:{label}] runs={MEASURED_RUNS} mean={mean_ms:.0f}ms p95={p95_ms:.0f}ms max={max(samples_ms):.0f}ms"
    )
    assert p95_ms / 1000.0 < P95_UPPER_BOUND_SECONDS
