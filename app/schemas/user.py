from datetime import datetime

from pydantic import UUID4, EmailStr
from sqlmodel import Field, SQLModel

from app.models.user import UserBase
from app.schemas.vault import VaultRead  # noqa: TCH001


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class UserReadWithVaults(UserRead):
    vaults: list["VaultRead"] = []


UserReadWithVaults.update_forward_refs()


class UserUpdate(SQLModel):
    username: str | None = Field(index=True, min_length=3, max_length=32, default=None)
    email: EmailStr | None = None
    password: str | None
    is_active: bool | None = None
    is_superuser: bool | None = None
