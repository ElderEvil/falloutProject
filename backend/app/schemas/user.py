from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import UUID4

from app.models.user import UserBase
from app.utils.partial import optional

if TYPE_CHECKING:
    from app.schemas.vault import VaultRead


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class UserWithTokens(UserRead):
    access_token: str
    refresh_token: str
    token_type: str


class UserReadWithVaults(UserRead):
    vaults: list["VaultRead"] = []


UserReadWithVaults.model_rebuild()


@optional()
class UserUpdate(UserBase):
    password: str | None
