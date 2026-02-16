from datetime import datetime
from typing import Self

from pydantic import UUID4, BaseModel, Field, model_validator
from sqlmodel import SQLModel

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
    resource_warnings: list[dict[str, str]] = Field(default_factory=list)


class MedicalTransferRequest(BaseModel):
    """Request schema for medical supply transfer."""

    dweller_id: UUID4
    stimpaks: int = Field(default=0, ge=0, le=15)
    radaways: int = Field(default=0, ge=0, le=15)

    model_config = {"strict": True}

    @model_validator(mode="after")
    def check_at_least_one_item(self) -> Self:
        if self.stimpaks == 0 and self.radaways == 0:
            raise ValueError("At least one item (stimpaks or radaways) must be provided")
        return self


class MedicalTransferResponse(BaseModel):
    """Response schema for medical supply transfer."""

    vault_stimpaks: int
    vault_radaways: int
    dweller_stimpaks: int
    dweller_radaways: int


class VaultReadWithUser(VaultRead):
    user_id: UUID4


class VaultReadWithNumbers(VaultRead):
    room_count: int
    dweller_count: int


@optional()
class VaultUpdate(VaultBase):
    pass
