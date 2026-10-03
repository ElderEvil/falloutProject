"""CRUD for the persisted generated-world snapshot.

Reads never regenerate: the snapshot row is written explicitly once per
(world_id, generator_version) and fetched thereafter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from app.models.world_snapshot import WorldSnapshot

if TYPE_CHECKING:
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

    async def create(self, db_session: AsyncSession, *, snapshot: WorldSnapshot) -> WorldSnapshot:
        """Persist a freshly generated snapshot (caller commits)."""
        db_session.add(snapshot)
        await db_session.flush()
        return snapshot


world_snapshot = CRUDWorldSnapshot()
