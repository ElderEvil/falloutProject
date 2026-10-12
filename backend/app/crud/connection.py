"""CRUD operations for player connections (A1)."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from pydantic import UUID4
from sqlmodel import col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ConnectionStatus
from app.crud.base import CRUDBase
from app.models.connection import Connection


def _ordered_pair(user_a: UUID4 | UUID, user_b: UUID4 | UUID) -> tuple[UUID, UUID]:
    """Return the canonical (sorted) pair used by the ``user_a``/``user_b`` columns."""
    first = UUID(str(user_a))
    second = UUID(str(user_b))
    return (first, second) if first < second else (second, first)


class CRUDConnection(CRUDBase[Connection, None, None]):
    async def create_connection(
        self,
        db_session: AsyncSession,
        *,
        requester_id: UUID4,
        addressee_id: UUID4,
        status: ConnectionStatus = ConnectionStatus.PENDING,
    ) -> Connection:
        """Stage a connection row; the caller owns the transaction commit.

        ``user_a``/``user_b`` are derived here as the sorted pair so the unique
        constraint on the unordered pair is always satisfied by construction.
        """
        first, second = _ordered_pair(requester_id, addressee_id)
        connection = Connection(
            requester_id=requester_id,
            addressee_id=addressee_id,
            user_a=first,
            user_b=second,
            status=status,
            responded_at=datetime.utcnow() if status == ConnectionStatus.ACCEPTED else None,
        )
        db_session.add(connection)
        await db_session.flush()
        await db_session.refresh(connection)
        return connection

    async def get_by_pair(self, db_session: AsyncSession, user_a: UUID4, user_b: UUID4) -> Connection | None:
        """Return the connection row for the (unordered) pair, if any."""
        first, second = _ordered_pair(user_a, user_b)
        query = select(Connection).where(col(Connection.user_a) == first, col(Connection.user_b) == second)
        result = await db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, db_session: AsyncSession, connection_id: UUID4) -> Connection | None:
        """Return the connection row by id, or None when absent (no 404 raise)."""
        query = select(Connection).where(Connection.id == connection_id)
        result = await db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_user(self, db_session: AsyncSession, user_id: UUID4) -> Sequence[Connection]:
        """All rows the user participates in, as requester or addressee."""
        query = (
            select(Connection)
            .where(or_(Connection.requester_id == user_id, Connection.addressee_id == user_id))
            .order_by(col(Connection.created_at).desc())
        )
        result = await db_session.execute(query)
        return result.scalars().all()

    async def set_status(
        self,
        db_session: AsyncSession,
        connection: Connection,
        status: ConnectionStatus,
        *,
        responded_at: datetime | None = None,
    ) -> Connection:
        """Update the status (and response timestamp) of an existing row."""
        connection.status = status
        connection.responded_at = responded_at
        db_session.add(connection)
        await db_session.flush()
        await db_session.refresh(connection)
        return connection

    async def delete_row(self, db_session: AsyncSession, connection: Connection) -> None:
        """Remove a connection row (revoke / decline) hard, without soft-delete."""
        await db_session.delete(connection)
        await db_session.flush()

    async def delete_between(self, db_session: AsyncSession, user_a: UUID4, user_b: UUID4) -> int:
        """Delete every connection row between a pair; returns the count removed.

        Used by blocking so a block makes any existing thread inert and the
        ability to connect must be re-earned after unblocking.
        """
        first, second = _ordered_pair(user_a, user_b)
        query = select(Connection).where(col(Connection.user_a) == first, col(Connection.user_b) == second)
        result = await db_session.execute(query)
        rows = result.scalars().all()
        for row in rows:
            await db_session.delete(row)
        await db_session.flush()
        return len(rows)


connection = CRUDConnection(Connection)
