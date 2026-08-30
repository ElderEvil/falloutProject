"""CRUD operations for explorations."""

from pydantic import UUID4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.exploration import Exploration, ExplorationStatus
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
        """Get all explorations for a vault, optionally filtering to active only.

        Args:
            db_session: Database session.
            vault_id: Vault ID to filter by.
            active_only: If True, only return explorations with ACTIVE status.
        """
        query = select(Exploration).where(Exploration.vault_id == vault_id)
        if active_only:
            query = query.where(Exploration.status == ExplorationStatus.ACTIVE)
        result = await db_session.execute(query)
        return list(result.scalars().all())

    async def get_by_dweller(
        self,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4,
    ) -> Exploration | None:
        """Get active exploration for a dweller."""
        result = await db_session.execute(
            select(Exploration)
            .where(Exploration.dweller_id == dweller_id)
            .where(Exploration.status == ExplorationStatus.ACTIVE)
        )
        return result.scalar_one_or_none()

    async def get_all_active(
        self,
        db_session: AsyncSession,
    ) -> list[Exploration]:
        """Get all active explorations across all vaults."""
        result = await db_session.execute(select(Exploration).where(Exploration.status == ExplorationStatus.ACTIVE))
        return list(result.scalars().all())

    async def complete_exploration(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
    ) -> Exploration:
        """Mark an exploration as completed."""
        exploration = await self.get(db_session, exploration_id)
        exploration.complete()
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration

    async def recall_exploration(
        self,
        db_session: AsyncSession,
        *,
        exploration_id: UUID4,
    ) -> Exploration:
        """Mark an exploration as recalled (early return)."""
        exploration = await self.get(db_session, exploration_id)
        exploration.recall()
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
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
