from datetime import datetime

from pydantic import UUID4
from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel

from app.models.vault import VaultBase
from app.utils.partial import optional


class VaultCreate(VaultBase):
    pass


class VaultCreateWithUserID(VaultBase):
    user_id: UUID4


class VaultNumber(SQLModel):
    number: int = Field(gt=0, lt=1_000)
    boosted: bool = False


class VaultRead(VaultBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    resource_warnings: list[dict[str, str]] = PydanticField(default_factory=list)


class VaultReadWithUser(VaultRead):
    user_id: UUID4


class VaultReadWithNumbers(VaultRead):
    room_count: int
    dweller_count: int


@optional()
class VaultUpdate(VaultBase):
    pass
