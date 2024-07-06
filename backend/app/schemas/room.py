from datetime import datetime

from pydantic import UUID4

from app.models.room import RoomBase
from app.utils.partial import optional


class RoomCreateWithoutVaultID(RoomBase):
    capacity_formula: str | None = None


class RoomCreate(RoomCreateWithoutVaultID):
    vault_id: UUID4


class RoomRead(RoomBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


@optional()
class RoomUpdate(RoomBase):
    pass
