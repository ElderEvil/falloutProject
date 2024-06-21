from pydantic import UUID4
from sqlmodel import Field, SQLModel


class VaultObjectiveProgressLink(SQLModel, table=True):
    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    objective_id: UUID4 = Field(foreign_key="objective.id", primary_key=True)
    progress: int = Field(default=0)
    total: int = Field(default=1)
    is_completed: bool = Field(default=False)
