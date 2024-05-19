from datetime import datetime

from pydantic import UUID4

from app.models.user import UserBase
from app.schemas.vault import VaultRead  # noqa: TCH001
from app.utils.partial import optional


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class UserReadWithVaults(UserRead):
    vaults: list["VaultRead"] = []


UserReadWithVaults.update_forward_refs()


@optional()
class UserUpdate(UserBase):
    password: str | None
