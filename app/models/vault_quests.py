from pydantic import UUID4
from sqlmodel import Field, SQLModel


class VaultQuestChainCompletionLink(SQLModel, table=True):
    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    quest_entity_id: UUID4 = Field(foreign_key="questchain.id", primary_key=True)
    is_completed: bool = Field(default=False)
    is_visible: bool = Field(default=False)


class VaultQuestCompletionLink(SQLModel, table=True):
    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    quest_entity_id: UUID4 = Field(foreign_key="quest.id", primary_key=True)
    is_completed: bool = Field(default=False)
    is_visible: bool = Field(default=False)


class VaultQuestObjectiveCompletionLink(SQLModel, table=True):
    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    quest_entity_id: UUID4 = Field(foreign_key="questobjective.id", primary_key=True)
    is_completed: bool = Field(default=False)
