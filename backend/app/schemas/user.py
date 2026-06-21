from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import UUID4, BaseModel, Field

from app.models.user import UserBase
from app.utils.partial import optional


class DeathCauseBreakdown(BaseModel):
    """Breakdown of deaths by cause."""

    health: int = 0
    radiation: int = 0
    incident: int = 0
    exploration: int = 0
    combat: int = 0


class DeathStatsResponse(BaseModel):
    """Life/death statistics for a user."""

    total_dwellers_born: int = 0
    total_dwellers_died: int = 0
    deaths_by_cause: DeathCauseBreakdown
    revivable_count: int = 0
    permanently_dead_count: int = 0


if TYPE_CHECKING:
    from app.schemas.vault import VaultRead


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


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


@optional()
class UserUpdate(UserBase):
    password: str | None


class UserAdminUpdate(UserBase):
    """Schema for admin-only updates including quota management."""

    monthly_token_limit: int | None = None
