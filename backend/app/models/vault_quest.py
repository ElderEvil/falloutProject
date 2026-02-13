from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel


class VaultQuestCompletionLink(SQLModel, table=True):
    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    quest_id: UUID4 = Field(foreign_key="quest.id", primary_key=True)
    is_completed: bool = Field(default=False)
    is_visible: bool = Field(default=False)
    started_at: datetime | None = Field(default=None)
    duration_minutes: int | None = Field(default=None)
