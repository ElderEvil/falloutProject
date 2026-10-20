"""CRUD operations for workshop crafting orders."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.crafting_order import CraftingOrder, CraftingOrderStatus
from app.schemas.crafting import CraftingOrderCreate, CraftingOrderUpdate


class CRUDCraftingOrder(CRUDBase[CraftingOrder, CraftingOrderCreate, CraftingOrderUpdate]):
    """Queries for the workshop queue."""

    async def get_active_by_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[CraftingOrder]:
        """Orders still being worked on, oldest first."""
        result = await db_session.execute(
            select(CraftingOrder)
            .where(CraftingOrder.vault_id == vault_id, CraftingOrder.status == CraftingOrderStatus.ACTIVE)
            .order_by(CraftingOrder.started_at)
        )
        return list(result.scalars().all())

    async def has_uncollected(self, db_session: AsyncSession, vault_id: UUID4, item_type: str, item_name: str) -> bool:
        """True while an order for this exact item is active or awaiting collection."""
        result = await db_session.execute(
            select(CraftingOrder.id)
            .where(
                CraftingOrder.vault_id == vault_id,
                CraftingOrder.item_type == item_type,
                CraftingOrder.item_name == item_name,
                CraftingOrder.status != CraftingOrderStatus.COLLECTED,
            )
            .limit(1)
        )
        return result.first() is not None

    async def get_by_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[CraftingOrder]:
        """Every order for a vault, newest first."""
        result = await db_session.execute(
            select(CraftingOrder).where(CraftingOrder.vault_id == vault_id).order_by(CraftingOrder.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_vault(self, db_session: AsyncSession, order_id: UUID4, vault_id: UUID4) -> CraftingOrder | None:
        """One order scoped to its vault, so foreign ids cannot resolve."""
        result = await db_session.execute(
            select(CraftingOrder).where(CraftingOrder.id == order_id, CraftingOrder.vault_id == vault_id)
        )
        return result.scalars().first()

    async def get_for_vault_for_update(
        self, db_session: AsyncSession, order_id: UUID4, vault_id: UUID4
    ) -> CraftingOrder | None:
        """Lock one order while it is collected, so two requests cannot both grant it."""
        result = await db_session.execute(
            select(CraftingOrder)
            .where(CraftingOrder.id == order_id, CraftingOrder.vault_id == vault_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()


crafting_order = CRUDCraftingOrder(CraftingOrder)
