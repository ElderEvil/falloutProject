from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.vault import VaultBase

if TYPE_CHECKING:
    from app.schemas.user import UserRead


class VaultCreate(VaultBase):
    name: int = Field(..., gt=0, lt=1_000)


class VaultCreateWithUserID(VaultBase):
    user_id: UUID4


class VaultRead(VaultBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class VaultReadWithUser(VaultRead):
    user: Optional["UserRead"] = None


class VaultUpdate(SQLModel):
    name: int | None = Field(default=None, gt=0, lt=1_000)
    bottle_caps: int | None = Field(default=None, ge=0, lt=1_000_000)
    happiness: int | None = Field(default=50, ge=0, le=100)
