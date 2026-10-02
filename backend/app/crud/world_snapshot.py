"""CRUD for the persisted generated-world snapshot.

Reads never regenerate: the snapshot row is written explicitly once per
(world_id, generator_version) and fetched thereafter.
"""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.world_snapshot import WorldSnapshot


class CRUDWorldSnapshot:
    async def get_active(
        self, db_session: AsyncSession, *, world_id: str, generator_version: int
    ) -> WorldSnapshot | None:
        """The persisted snapshot for a world version, or None when not generated yet."""
        result = await db_session.execute(
            select(WorldSnapshot).where(
                WorldSnapshot.world_id == world_id,
                WorldSnapshot.generator_version == generator_version,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, db_session: AsyncSession, *, snapshot: WorldSnapshot) -> WorldSnapshot:
        """Persist a freshly generated snapshot (caller commits)."""
        db_session.add(snapshot)
        await db_session.flush()
        return snapshot


world_snapshot = CRUDWorldSnapshot()
