from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.vault import VaultBase
from app.utils.partial import optional


class VaultCreate(VaultBase):
    name: int = Field(gt=0, lt=1_000)


class VaultCreateWithUserID(VaultBase):
    user_id: UUID4


class VaultNumber(SQLModel):
    name: int = Field(gt=0, lt=1_000)


class VaultRead(VaultBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class VaultReadWithUser(VaultRead):
    user_id: UUID4


class VaultReadWithNumbers(VaultRead):
    room_count: int
    dweller_count: int


@optional()
class VaultUpdate(VaultBase):
    pass
