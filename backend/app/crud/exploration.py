"""CRUD operations for explorations."""

from datetime import datetime

from pydantic import UUID4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.exploration import Exploration, ExplorationStatus
from app.schemas.exploration import ExplorationCreate, ExplorationUpdate


class CRUDExploration(CRUDBase[Exploration, ExplorationCreate, ExplorationUpdate]):
    """CRUD operations for Exploration model."""

    async def create_with_dweller_stats(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4,
        dweller_id: UUID4,
        duration: int,
    ) -> Exploration:
        """
        Create an exploration with dweller's SPECIAL stats.
        Captures the dweller's stats at the moment of departure.
        """
        # Fetch the dweller to get their current stats
        result = await db_session.execute(select(Dweller).where(Dweller.id == dweller_id))
        dweller = result.scalar_one()

        obj_in = ExplorationCreate(
            vault_id=vault_id,
            dweller_id=dweller_id,
            duration=duration,
        )

        # Create exploration with dweller's stats
        db_obj = Exploration(
            **obj_in.model_dump(),
            dweller_strength=dweller.strength,
            dweller_perception=dweller.perception,
            dweller_endurance=dweller.endurance,
            dweller_charisma=dweller.charisma,
            dweller_intelligence=dweller.intelligence,
            dweller_agility=dweller.agility,
            dweller_luck=dweller.luck,
            start_time=datetime.utcnow(),
            status=ExplorationStatus.ACTIVE,
        )
        db_session.add(db_obj)
        await db_session.commit()
        await db_session.refresh(db_obj)
        return db_obj

    async def get_active_by_vault(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4,
    ) -> list[Exploration]:
        """Get all active explorations for a vault."""
        result = await db_session.execute(
            select(Exploration)
            .where(Exploration.vault_id == vault_id)
            .where(Exploration.status == ExplorationStatus.ACTIVE)
        )
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
