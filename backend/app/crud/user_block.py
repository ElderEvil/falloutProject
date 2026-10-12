"""CRUD operations for user blocking (A2 identity)."""

from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.user_block import UserBlock


class CRUDUserBlock(CRUDBase[UserBlock, None, None]):
    async def create_block(self, db_session: AsyncSession, *, blocker_id: UUID4, blocked_id: UUID4) -> UserBlock:
        """Stage a block row; the caller owns the transaction commit."""
        block = UserBlock(blocker_id=blocker_id, blocked_id=blocked_id)
        db_session.add(block)
        await db_session.flush()
        await db_session.refresh(block)
        return block

    async def get_block(self, db_session: AsyncSession, *, blocker_id: UUID4, blocked_id: UUID4) -> UserBlock | None:
        """Return the ordered-pair block row, or None when absent."""
        query = select(UserBlock).where(
            col(UserBlock.blocker_id) == blocker_id,
            col(UserBlock.blocked_id) == blocked_id,
        )
        result = await db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_between(self, db_session: AsyncSession, user_a: UUID4, user_b: UUID4) -> UserBlock | None:
        """Return any block row between a pair (either direction), or None."""
        query = select(UserBlock).where(
            (col(UserBlock.blocker_id) == user_a) & (col(UserBlock.blocked_id) == user_b)
            | (col(UserBlock.blocker_id) == user_b) & (col(UserBlock.blocked_id) == user_a)
        )
        result = await db_session.execute(query)
        return result.scalar_one_or_none()

    async def list_for_blocker(self, db_session: AsyncSession, blocker_id: UUID4) -> Sequence[UserBlock]:
        """All blocks issued by a user."""
        query = (
            select(UserBlock).where(col(UserBlock.blocker_id) == blocker_id).order_by(col(UserBlock.created_at).desc())
        )
        result = await db_session.execute(query)
        return result.scalars().all()

    async def delete_row(self, db_session: AsyncSession, block: UserBlock) -> None:
        """Remove a block row (unblock), hard delete."""
        await db_session.delete(block)
        await db_session.flush()


user_block = CRUDUserBlock(UserBlock)
