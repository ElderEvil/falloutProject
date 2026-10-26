from datetime import datetime

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field

from app.models.base import BaseUUIDModel


class AccountMerge(BaseUUIDModel, table=True):
    """One-time audit record for moving an account's data into a surviving account.

    ``source_user_id`` is unique, so a source can be merged only once. Identity
    snapshots keep the audit readable after the source row is tombstoned, and the
    ``RESTRICT`` foreign keys keep an audit row from being orphaned by a hard delete.
    """

    __tablename__ = "account_merge"

    source_user_id: UUID4 = Field(foreign_key="user.id", unique=True, ondelete="RESTRICT")
    target_user_id: UUID4 = Field(foreign_key="user.id", index=True, ondelete="RESTRICT")
    actor_user_id: UUID4 = Field(foreign_key="user.id", index=True, ondelete="RESTRICT")

    source_username: str = Field(max_length=32)
    target_username: str = Field(max_length=32)
    source_email: str | None = Field(default=None, max_length=320)
    target_email: str | None = Field(default=None, max_length=320)
    reason: str = Field(max_length=500)

    # Portable JSON (not JSONB): the audit payload must work on SQLite tests too.
    moved_counts: dict[str, int] = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
