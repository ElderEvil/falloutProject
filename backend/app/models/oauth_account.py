from pydantic import UUID4
from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.models.base import BaseUUIDModel, TimeStampMixin


class OAuthAccount(BaseUUIDModel, TimeStampMixin, table=True):
    """Link between a local user and a provider identity.

    ``provider`` is a plain varchar: no PG enum, so adding a provider needs no
    enum migration.
    """

    __tablename__ = "oauth_account"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_account_provider_provider_user_id"),
        UniqueConstraint("user_id", "provider", name="uq_oauth_account_user_provider"),
    )

    provider: str = Field(max_length=16, index=True)
    provider_user_id: str = Field(max_length=64, index=True)
    user_id: UUID4 = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
