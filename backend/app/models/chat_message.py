from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.llm_interaction import LLMInteraction
    from app.models.user import User
    from app.models.vault import Vault


class ChatMessageBase(SQLModel):
    vault_id: UUID = Field(foreign_key="vault.id", index=True)

    # Source (one must be set)
    from_user_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)
    from_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", index=True)

    # Destination (one must be set)
    to_user_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)
    to_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", index=True)

    message_text: str = Field(max_length=2000)

    # Optional: Link to LLMInteraction for AI-generated messages
    llm_interaction_id: UUID | None = Field(default=None, foreign_key="llminteraction.id")


class ChatMessage(BaseUUIDModel, ChatMessageBase, table=True):
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Relationships
    vault: "Vault" = Relationship()
    from_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[ChatMessage.from_user_id]",
            "lazy": "joined",
        }
    )
    from_dweller: Optional["Dweller"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[ChatMessage.from_dweller_id]",
            "lazy": "joined",
        }
    )
    to_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[ChatMessage.to_user_id]",
            "lazy": "joined",
        }
    )
    to_dweller: Optional["Dweller"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[ChatMessage.to_dweller_id]",
            "lazy": "joined",
        }
    )
    llm_interaction: Optional["LLMInteraction"] = Relationship()


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessageRead(ChatMessageBase):
    id: UUID
    created_at: datetime
