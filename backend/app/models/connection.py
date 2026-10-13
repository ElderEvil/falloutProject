"""Player-to-player connection model (A1 of the multiplayer slice)."""

from datetime import datetime

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.core.enums import ConnectionStatus
from app.models.base import BaseUUIDModel, TimeStampMixin


class ConnectionBase(SQLModel):
    requester_id: UUID4 = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    addressee_id: UUID4 = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    status: ConnectionStatus = Field(default=ConnectionStatus.PENDING, index=True)
    responded_at: datetime | None = Field(default=None)


class Connection(BaseUUIDModel, ConnectionBase, TimeStampMixin, table=True):
    """A bidirectional player relationship that requires explicit consent.

    ``user_a``/``user_b`` hold the canonical (sorted) pair of participants so the
    unique constraint covers the *unordered* pair: a PENDING/ACCEPTED row can
    never exist twice for the same two users, no matter which side asked first.
    They are derived from ``requester_id``/``addressee_id`` by the CRUD layer,
    which is the only code that writes these rows.
    """

    __tablename__ = "connection"

    __table_args__ = (sa.UniqueConstraint("user_a", "user_b", name="uq_connection_user_pair"),)

    user_a: UUID4 = Field(index=True)
    user_b: UUID4 = Field(index=True)

    def __str__(self):
        return f"Connection {self.requester_id} <-> {self.addressee_id} ({self.status.value})"
