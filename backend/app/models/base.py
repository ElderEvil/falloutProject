from datetime import datetime, timezone
from uuid import uuid4

from pydantic import UUID4
from sqlmodel import Field, SQLModel


class TimeStampMixin(SQLModel):
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)},
    )


class BaseUUIDModel(SQLModel):
    id: UUID4 = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )


class SoftDeleteMixin(SQLModel):
    is_deleted: bool = Field(default=False, index=True)
    deleted_at: datetime | None = Field(default=None)

    def soft_delete(self):
        """Marks the object as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self):
        """Restores the object if it was soft-deleted."""
        self.is_deleted = False
        self.deleted_at = None


class SPECIALModel(SQLModel):
    strength: int = Field(default=1, ge=1, le=10, alias="S")
    perception: int = Field(default=1, ge=1, le=10, alias="P")
    endurance: int = Field(default=1, ge=1, le=10, alias="E")
    charisma: int = Field(default=1, ge=1, le=10, alias="C")
    intelligence: int = Field(default=1, ge=1, le=10, alias="I")
    agility: int = Field(default=1, ge=1, le=10, alias="A")
    luck: int = Field(default=1, ge=1, le=10, alias="L")

    model_config = {"populate_by_name": True}
