"""CRUD operations for explorations."""

from pydantic import UUID4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.exploration import IN_PROGRESS_STATUSES, Exploration
from app.schemas.exploration import ExplorationCreate, ExplorationUpdate


class CRUDExploration(CRUDBase[Exploration, ExplorationCreate, ExplorationUpdate]):
    """CRUD operations for Exploration model."""

    async def get_by_vault(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4,
        active_only: bool = False,
    ) -> list[Exploration]:
        """Get all explorations for a vault, optionally filtering to ongoing only.

        Args:
            db_session: Database session.
            vault_id: Vault ID to filter by.
            active_only: If True, only return explorations that are still in progress
                (exploring or on the return leg).
        """
        query = select(Exploration).where(Exploration.vault_id == vault_id)
        if active_only:
            query = query.where(Exploration.status.in_(IN_PROGRESS_STATUSES))
        result = await db_session.execute(query)
        return list(result.scalars().all())

    async def get_for_update(self, db_session: AsyncSession, exploration_id: UUID4) -> Exploration | None:
        """One exploration locked FOR UPDATE (reward claiming serialization).

        ``populate_existing`` refreshes the instance even when the row is already in
        the session's identity map, so a tick that loaded the run earlier revalidates
        against the current committed state instead of a stale one.
        """
        result = await db_session.execute(
            select(Exploration)
            .where(Exploration.id == exploration_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_dweller(
        self,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4,
    ) -> Exploration | None:
        """Get the in-progress exploration for a dweller (exploring or returning)."""
        result = await db_session.execute(
            select(Exploration)
            .where(Exploration.dweller_id == dweller_id)
            .where(Exploration.status.in_(IN_PROGRESS_STATUSES))
        )
        return result.scalar_one_or_none()

    async def get_in_progress_for_dwellers(
        self,
        db_session: AsyncSession,
        dweller_ids: list[UUID4],
    ) -> list[Exploration]:
        """Any open (exploring or returning) run for any of the given dwellers."""
        if not dweller_ids:
            return []
        result = await db_session.execute(
            select(Exploration)
            .where(Exploration.dweller_id.in_(dweller_ids))
            .where(Exploration.status.in_(IN_PROGRESS_STATUSES))
        )
        return list(result.scalars().all())

    async def get_all_active(
        self,
        db_session: AsyncSession,
    ) -> list[Exploration]:
        """Get all in-progress explorations across all vaults."""
        result = await db_session.execute(select(Exploration).where(Exploration.status.in_(IN_PROGRESS_STATUSES)))
        return list(result.scalars().all())

    async def start_return(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
        recalled: bool = False,
    ) -> Exploration:
        """Move an exploration onto its return leg; the caller owns the commit."""
        exploration = await self.get(db_session, exploration_id)
        exploration.start_return(recalled=recalled)
        db_session.add(exploration)
        await db_session.flush()
        await db_session.refresh(exploration)
        return exploration

    async def finalize_return(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
    ) -> Exploration:
        """Stage an arrived exploration's terminal outcome for the caller's transaction."""
        exploration = await self.get(db_session, exploration_id)
        exploration.finalize_return()
        db_session.add(exploration)
        await db_session.flush()
        return exploration

    async def add_event(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
        event_type: str,
        description: str,
        loot: dict | None = None,
    ) -> Exploration:
        """Add an event to an exploration's journey log."""
        exploration = await self.get(db_session, exploration_id)
        exploration.add_event(event_type, description, loot)
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration

    async def add_loot(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
        item_name: str,
        quantity: int = 1,
        rarity: str = "common",
    ) -> Exploration:
        """Add loot to an exploration."""
        exploration = await self.get(db_session, exploration_id)
        exploration.add_loot(item_name, quantity, rarity)
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration

    async def update_stats(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
        distance: int | None = None,
        caps: int | None = None,
        enemies: int | None = None,
    ) -> Exploration:
        """Update exploration statistics."""
        exploration = await self.get(db_session, exploration_id)
        if distance is not None:
            exploration.total_distance += distance
        if caps is not None:
            exploration.total_caps_found += caps
        if enemies is not None:
            exploration.enemies_encountered += enemies

        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration


exploration = CRUDExploration(Exploration)
