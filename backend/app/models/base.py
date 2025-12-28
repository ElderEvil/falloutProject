from datetime import datetime
from uuid import uuid4

from pydantic import UUID4
from sqlmodel import Field, SQLModel


class TimeStampMixin(SQLModel):
    created_at: datetime | None = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )


class BaseUUIDModel(SQLModel):
    id: UUID4 = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )


class SoftDeleteMixin:
    is_deleted: bool = Field(default=False, index=True)
    deleted_at: datetime | None = None

    def soft_delete(self):
        """Marks the object as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()  # noqa: DTZ003

    def restore(self):
        """Restores the object if it was soft-deleted."""
        self.is_deleted = False
        self.deleted_at = None


class SPECIALModel(SQLModel):
    strength: int = Field(ge=1, le=10, alias="S")
    perception: int = Field(ge=1, le=10, alias="P")
    endurance: int = Field(ge=1, le=10, alias="E")
    charisma: int = Field(ge=1, le=10, alias="C")
    intelligence: int = Field(ge=1, le=10, alias="I")
    agility: int = Field(ge=1, le=10, alias="A")
    luck: int = Field(ge=1, le=10, alias="L")

    model_config = {"populate_by_name": True}
