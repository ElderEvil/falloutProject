"""CRUD for the persisted generated-world snapshot.

Reads never regenerate: the snapshot row is written explicitly once per
(world_id, generator_version) and fetched thereafter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import update as sa_update
from sqlmodel import select

from app.models.world_snapshot import WorldSnapshot

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlmodel.ext.asyncio.session import AsyncSession


class CRUDWorldSnapshot:
    async def get_version(
        self, db_session: AsyncSession, *, world_id: str, generator_version: int
    ) -> WorldSnapshot | None:
        """The persisted snapshot for an explicitly selected world version, or None.

        Selection is by exact ``(world_id, generator_version)`` — never "the newest" —
        so generating a later version cannot silently change what an existing reader sees.
        """
        result = await db_session.execute(
            select(WorldSnapshot).where(
                WorldSnapshot.world_id == world_id,
                WorldSnapshot.generator_version == generator_version,
            )
        )
        return result.scalar_one_or_none()

    async def get_active(self, db_session: AsyncSession, *, world_id: str) -> WorldSnapshot | None:
        """The explicitly activated snapshot for a world, or None.

        A partial unique index keeps this to at most one row per world; reads never
        infer the active world from the newest version.
        """
        result = await db_session.execute(
            select(WorldSnapshot).where(
                WorldSnapshot.world_id == world_id,
                WorldSnapshot.is_active == True,  # ruff: ignore[true-false-comparison]
            )
        )
        return result.scalar_one_or_none()

    async def list_for_world(self, db_session: AsyncSession, *, world_id: str) -> Sequence[WorldSnapshot]:
        """Every stored snapshot for a world, newest generator version first."""
        result = await db_session.execute(
            select(WorldSnapshot)
            .where(WorldSnapshot.world_id == world_id)
            .order_by(WorldSnapshot.generator_version.desc())
        )
        return result.scalars().all()

    async def list_candidates(self, db_session: AsyncSession, *, world_id: str) -> Sequence[WorldSnapshot]:
        """Stored snapshots for a world that are not active, newest version first."""
        result = await db_session.execute(
            select(WorldSnapshot)
            .where(
                WorldSnapshot.world_id == world_id,
                WorldSnapshot.is_active == False,  # ruff: ignore[true-false-comparison]
            )
            .order_by(WorldSnapshot.generator_version.desc())
        )
        return result.scalars().all()

    async def deactivate_active(self, db_session: AsyncSession, *, world_id: str) -> int:
        """Clear the active pointer for a world (caller owns the transaction)."""
        result = await db_session.execute(
            sa_update(WorldSnapshot)
            .where(
                WorldSnapshot.world_id == world_id,
                WorldSnapshot.is_active == True,  # ruff: ignore[true-false-comparison]
            )
            .values(is_active=False, activated_at=None)
        )
        return result.rowcount or 0

    async def create(self, db_session: AsyncSession, *, snapshot: WorldSnapshot) -> WorldSnapshot:
        """Persist a freshly generated snapshot (caller commits)."""
        db_session.add(snapshot)
        await db_session.flush()
        return snapshot


world_snapshot = CRUDWorldSnapshot()
