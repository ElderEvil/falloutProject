"""Timing instrumentation helpers for the opt-in tick profiler."""

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.tick_profiling import (
    TickProfile,
    reset_current_profile,
    set_current_profile,
    tick_sql_phase,
)


@pytest.mark.asyncio
async def test_tick_sql_phase_records_cursor_execution(async_session: AsyncSession) -> None:
    """Cursor events record SQL execution, not ORM result consumption."""
    profile = TickProfile(vault_key="vault-key", dispatch_key="dispatch-key")
    token = set_current_profile(profile)
    try:
        with tick_sql_phase(async_session, "resource"):
            await async_session.execute(text("SELECT 1"))
    finally:
        reset_current_profile(token)

    assert profile.phases["resource.sql"] > 0
