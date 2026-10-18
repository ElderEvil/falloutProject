from pydantic import UUID4
from sqlalchemy import JSON, Boolean, Column, false
from sqlmodel import Field, SQLModel


class VaultObjectiveProgressLink(SQLModel, table=True):
    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    objective_id: UUID4 = Field(foreign_key="objective.id", primary_key=True)
    progress: int = Field(default=0)
    total: int = Field(default=1)
    is_completed: bool = Field(default=False)
    is_locked: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default=false()))

    credited_dweller_ids: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]")
    )
    reward_snapshot: str | None = Field(default=None, max_length=32)
