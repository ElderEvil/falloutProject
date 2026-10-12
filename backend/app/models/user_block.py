"""User-to-user block list model (A2 identity, bilateral blocking)."""

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class UserBlockBase(SQLModel):
    blocker_id: UUID4 = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    blocked_id: UUID4 = Field(foreign_key="user.id", ondelete="CASCADE", index=True)


class UserBlock(BaseUUIDModel, UserBlockBase, TimeStampMixin, table=True):
    """A unilateral block that is enforced bilaterally by the services.

    Unique on the *ordered* pair: the same user may block many users and be
    blocked by many users, but only one row per (blocker, blocked) pair.
    """

    __tablename__ = "userblock"

    __table_args__ = (sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_userblock_blocker_blocked"),)

    def __str__(self):
        return f"UserBlock {self.blocker_id} -> {self.blocked_id}"
