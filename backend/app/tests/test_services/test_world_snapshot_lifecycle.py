"""Snapshot lifecycle contract: generating a version never activates it.

The requirement under test: a read must resolve an *explicitly selected*
``(world_id, generator_version)`` slice, and generating a later version must not
change what an existing reader sees. There is deliberately no "newest wins" path.
"""

from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.world_generation_service import WorldConfig, WorldRecipe
from app.services.world_snapshot_service import world_snapshot_service

pytestmark = pytest.mark.asyncio


async def test_read_selects_explicit_version_not_newest(async_session: AsyncSession) -> None:
    """Generating v2 leaves reads for v1 unchanged: no implicit activation."""
    v1 = WorldRecipe(seed="activation-v1", generator_version=1, config=WorldConfig())
    v2 = WorldRecipe(seed="activation-v2", generator_version=2, config=WorldConfig())

    first = await world_snapshot_service.get_or_generate(async_session, v1)
    second = await world_snapshot_service.get_or_generate(async_session, v2)

    assert (first.world_id, first.generator_version) == (v1.world_id, 1)
    assert (second.world_id, second.generator_version) == (v2.world_id, 2)

    # Re-reading v1 still returns the v1 row — the newer v2 row does not shadow it.
    reread_v1 = await world_snapshot_service.get_or_generate(async_session, v1)
    assert reread_v1.id == first.id
    assert reread_v1.generator_version == 1
    assert reread_v1.snapshot_checksum == first.snapshot_checksum


async def test_generate_is_idempotent_per_version(async_session: AsyncSession) -> None:
    """A second generate for the same version returns the same row (no duplicate write)."""
    recipe = WorldRecipe(seed="idempotent", generator_version=1, config=WorldConfig())
    first = await world_snapshot_service.get_or_generate(async_session, recipe)
    second = await world_snapshot_service.get_or_generate(async_session, recipe)
    assert second.id == first.id
    assert second.snapshot_checksum == first.snapshot_checksum
