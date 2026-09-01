from datetime import datetime
from typing import Any, Literal

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
    previous_quest_id: UUID4 | None = None
    next_quest_id: UUID4 | None = None
    is_visible: bool = True
    is_completed: bool = False
    is_reward_ready: bool = False
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


class QuestPartyMemberRead(SQLModel):
    """Quest party member read schema."""

    id: UUID4
    quest_id: UUID4
    vault_id: UUID4
    dweller_id: UUID4
    slot_number: int
    status: str
    created_at: str | None = None
    updated_at: str | None = None


class EligibleDwellerRead(SQLModel):
    """Eligible dweller for a quest."""

    id: UUID4
    first_name: str
    last_name: str | None = None
    level: int
    rarity: str


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


class QuestItemData(SQLModel):
    """Typed authored data for an inventory reward, serialized into JSONB on persistence."""

    name: str | None = None
    item_type: Literal["weapon", "outfit", "junk", "consumable", "lunchbox", "pet", "dweller"] | None = None
    rarity: str = "common"
    value: int | None = None
    image_url: str | None = None
    weapon_type: str | None = None
    weapon_subtype: str | None = None
    stat: str | None = None
    damage_min: int | None = None
    damage_max: int | None = None
    outfit_type: str | None = None
    gender: str | None = None
    junk_type: str | None = None
    description: str | None = None


def infer_item_type(name: str, item_data: QuestItemData | dict[str, Any] | None = None) -> str:
    """Infer the inventory category for an authored item reward."""
    explicit_type = item_data.item_type if isinstance(item_data, QuestItemData) else (item_data or {}).get("item_type")
    if explicit_type:
        return str(explicit_type).lower()
    normalized_name = name.lower()
    if "junk" in normalized_name:
        return "junk"
    if "lunchbox" in normalized_name:
        return "lunchbox"
    if normalized_name.strip() == "legendary dweller":
        return "dweller"
    if any(token in normalized_name for token in ("nuka", "quantum", "stimpak", "stim", "radaway", "cola")):
        return "consumable"
    if any(token in normalized_name for token in ("armor", "armour", "suit", "outfit", "robe", "coat")):
        return "outfit"
    if any(
        token in normalized_name
        for token in ("pool cue", "shotgun", "rifle", "pistol", "plasma", "weapon", "laser", "gun")
    ):
        return "weapon"
    return "junk"


def normalize_item_reward(
    reward_data: dict[str, Any], item_data: QuestItemData | None
) -> tuple[dict[str, Any], QuestItemData]:
    """Return the canonical storage-ready representation of an item reward."""
    normalized_reward_data = dict(reward_data)
    normalized_item_data = item_data or QuestItemData()
    item_name = normalized_reward_data.get("item_name") or normalized_item_data.name or ""
    if normalized_item_data.name is None:
        normalized_item_data.name = item_name
    if normalized_item_data.item_type is None:
        normalized_item_data.item_type = infer_item_type(item_name, normalized_item_data)
    if "quantity" not in normalized_reward_data and "amount" in normalized_reward_data:
        normalized_reward_data["quantity"] = normalized_reward_data["amount"]
    if "quantity" in normalized_reward_data:
        try:
            quantity = int(normalized_reward_data["quantity"])
        except (TypeError, ValueError) as error:
            raise ValueError("Item reward quantity must be an integer") from error
        if (
            isinstance(normalized_reward_data["quantity"], float)
            and not normalized_reward_data["quantity"].is_integer()
        ):
            raise ValueError("Item reward quantity must be an integer")
        if quantity < 1:
            raise ValueError("Item reward quantity must be positive")
        normalized_reward_data["quantity"] = quantity
    return normalized_reward_data, normalized_item_data


class QuestRewardJSON(SQLModel):
    """Schema for quest rewards in JSON files."""

    reward_type: str
    reward_data: dict[str, Any]
    reward_chance: float = 1.0
    item_data: QuestItemData | None = Field(default=None, validation_alias="item_data")

    @property
    def item_data_json(self) -> dict[str, Any] | None:
        """Serialize typed item data for the JSONB persistence boundary."""
        return self.item_data.model_dump(exclude_none=True) if self.item_data else None

    @model_validator(mode="after")
    def _normalize_item_contract(self) -> "QuestRewardJSON":
        if self.reward_type.lower() == "item":
            self.reward_data, self.item_data = normalize_item_reward(self.reward_data, self.item_data)
        return self


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
    duration_minutes: int | None = Field(default=None, ge=15, le=240, validation_alias="duration_minutes")

    @model_validator(mode="after")
    def set_duration_minutes(self) -> "QuestJSON":
        if self.duration_minutes is None:
            if self.quest_type == "main":
                self.duration_minutes = min(240, 60 + max(self.chain_order, 1) * 60)
            elif self.quest_category == "exploration":
                self.duration_minutes = min(240, max(self.chain_order, 1) * 60)
            else:
                self.duration_minutes = min(120, 15 * max(self.chain_order, 1))
        return self

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
