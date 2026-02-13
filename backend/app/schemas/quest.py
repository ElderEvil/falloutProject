from datetime import datetime
from typing import Any

from pydantic import UUID4, Field, model_validator
from sqlmodel import SQLModel

from app.models.quest import QuestBase
from app.utils.partial import optional


class QuestCreate(QuestBase):
    pass


class QuestRequirementRead(SQLModel):
    id: UUID4
    requirement_type: str
    requirement_data: dict[str, Any]
    is_mandatory: bool


class QuestRewardRead(SQLModel):
    id: UUID4
    reward_type: str
    reward_data: dict[str, Any]
    reward_chance: float
    item_data: dict[str, Any] | None = None


class QuestRead(QuestBase):
    id: UUID4
    is_visible: bool = True
    is_completed: bool = False
    started_at: datetime | None = None
    duration_minutes: int | None = None
    quest_requirements: list[QuestRequirementRead] | None = None
    quest_rewards: list[QuestRewardRead] | None = None


class QuestCompleteResponse(SQLModel):
    """Response schema for quest completion with granted rewards."""

    quest_id: UUID4
    quest_title: str
    is_completed: bool = True
    granted_rewards: list[dict[str, Any]] = []


class QuestReadShort(SQLModel):
    id: UUID4
    title: str
    short_description: str


class QuestPartyAssign(SQLModel):
    dweller_ids: list[UUID4]


@optional()
class QuestUpdate(QuestBase):
    pass


class QuestObjectiveJSON(SQLModel):
    """Schema for quest objectives in JSON files."""

    title: str


class QuestRequirementJSON(SQLModel):
    """Schema for quest requirements in JSON files."""

    requirement_type: str
    requirement_data: dict[str, Any]
    is_mandatory: bool = True


class QuestRewardJSON(SQLModel):
    """Schema for quest rewards in JSON files."""

    reward_type: str
    reward_data: dict[str, Any]
    reward_chance: float = 1.0
    # Optional item definition for ITEM type rewards
    # When reward_type is "item", this defines the item to be created
    item_data: dict[str, Any] | None = Field(default=None, validation_alias="item_data")


class QuestJSON(SQLModel):
    """Schema for individual quests in JSON files with field aliases for JSON compatibility."""

    # Support both "Quest name" (space) and "quest_name" (snake_case) formats
    quest_name: str = Field(default="", alias="Quest name", validation_alias="quest_name")
    long_description: str = Field(default="", alias="Long description", validation_alias="long_description")
    short_description: str = Field(default="", alias="Short description", validation_alias="short_description")
    requirements: str | list[str] = Field(default="", alias="Requirements", validation_alias="requirements")
    rewards: str = Field(default="", alias="Rewards", validation_alias="rewards")
    # Quest objective can be a string or list of objects in the JSON
    quest_objective: str | list[QuestObjectiveJSON] | None = Field(
        default=None, alias="Quest objective", validation_alias="quest_objective"
    )
    # Structured requirements and rewards
    quest_requirements: list[QuestRequirementJSON] = Field(default_factory=list, validation_alias="quest_requirements")
    quest_rewards: list[QuestRewardJSON] = Field(default_factory=list, validation_alias="quest_rewards")
    # Quest chain metadata
    quest_type: str | None = Field(default=None, validation_alias="quest_type")
    quest_category: str | None = Field(default=None, validation_alias="quest_category")
    chain_order: int = Field(default=0, validation_alias="chain_order")

    @model_validator(mode="before")
    @classmethod
    def normalize_field_names(cls, data):
        """Support both space-separated and snake_case field names from JSON."""
        if isinstance(data, dict):
            # Map space-separated keys to snake_case for fields that need it
            field_mapping = {
                "Quest name": "quest_name",
                "Long description": "long_description",
                "Short description": "short_description",
                "Quest objective": "quest_objective",
                "Rewards": "rewards",
                "Requirements": "requirements",
            }
            for space_key, snake_key in field_mapping.items():
                if space_key in data and snake_key not in data:
                    data[snake_key] = data[space_key]
            # If 'title' is present but 'quest_name' is not, use title as quest_name
            if data.get("title") and not data.get("quest_name"):
                data["quest_name"] = data["title"]
        return data


class QuestChainJSON(SQLModel):
    """Schema for quest chains (collection of related quests)."""

    title: str
    chain_id: str | None = None
    chain_name: str | None = None
    chain_description: str | None = None
    quests: list[QuestJSON]
