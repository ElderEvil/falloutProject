"""PydanticAI agent for dweller chat with sentiment analysis and action suggestions."""

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import UUID4, BaseModel, Field
from pydantic_ai import Agent, RunContext
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.base import SPECIALModel
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.chat import (
    AssignToRoomAction,
    NoAction,
    RecallExplorationAction,
    StartExplorationAction,
    StartTrainingAction,
)
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerReadFull
from app.services.open_ai import get_model

logger = logging.getLogger(__name__)


class ModelCache:
    """Singleton-like cache for the AI model to avoid re-initialization."""

    _instance = None

    @classmethod
    def get_model(cls):
        """Get or lazily initialize the AI model."""
        if cls._instance is None:
            cls._instance = get_model()
        return cls._instance


# --- Structured Output Schema ---

ACTION_TYPES = Literal["assign_to_room", "start_training", "start_exploration", "recall_exploration", "no_action"]


class DwellerChatOutput(BaseModel):
    """Structured output from the dweller chat agent."""

    response_text: str = Field(
        ...,
        description="The dweller's in-character response to the user's message",
    )
    sentiment_score: int = Field(
        ...,
        ge=-5,
        le=5,
        description="Sentiment score from -5 (very negative) to +5 (very positive) based on the conversation tone",
    )
    reason_text: str = Field(
        ...,
        max_length=200,
        description="Brief explanation of why the sentiment score was chosen",
    )
    action_type: ACTION_TYPES = Field(
        ...,
        description="Type of action suggestion based on conversation context",
    )
    action_room_id: UUID4 | None = Field(
        None,
        description="Room ID if action_type is assign_to_room",
    )
    action_room_name: str | None = Field(
        None,
        description="Room name if action_type is assign_to_room",
    )
    action_stat: SPECIALEnum | None = Field(
        None,
        description="SPECIAL stat if action_type is start_training",
    )
    action_reason: str | None = Field(
        None,
        max_length=200,
        description="Reason for the action suggestion",
    )
    action_duration_hours: int | None = Field(
        None,
        ge=1,
        le=24,
        description="Exploration duration in hours if action_type is start_exploration",
    )
    action_stimpaks: int | None = Field(
        None,
        ge=0,
        le=25,
        description="Number of stimpaks if action_type is start_exploration",
    )
    action_radaways: int | None = Field(
        None,
        ge=0,
        le=25,
        description="Number of radaways if action_type is start_exploration",
    )
    action_exploration_id: UUID4 | None = Field(
        None,
        description="Exploration ID if action_type is recall_exploration (enriched by server)",
    )


# --- Dependencies ---


@dataclass
class DwellerChatDeps:
    """Dependencies for dweller chat agent."""

    db_session: AsyncSession
    dweller: DwellerReadFull
    vault_id: UUID4


# --- Room Info Models for Tools ---


class RoomInfo(BaseModel):
    """Basic room information for tool responses."""

    room_id: str
    name: str
    category: str
    current_dwellers: int
    max_capacity: int
    ability: str | None = None


# --- Agent Definition ---

dweller_chat_agent = Agent(
    model=ModelCache.get_model(),
    output_type=DwellerChatOutput,
    deps_type=DwellerChatDeps,
    system_prompt=(
        "You are a Vault-Tec Dweller in a post-apocalyptic world. "
        "Respond in character, staying true to the Fallout universe. "
        "Analyze the conversation sentiment and suggest helpful actions when appropriate. "
        "Actions include: assigning to any room type in the vault "
        "(production, training, crafting, capacity, misc, quests, or theme rooms), "
        "sending dweller on wasteland exploration, or recalling dweller from exploration. "
        "Only suggest actions when the conversation naturally leads to them (e.g., dweller mentions being bored, "
        "wanting to work, wanting adventure, or wanting to come home). "
        "When the user requests assignment to a specific room, follow their order strictly."
    ),
)


@dweller_chat_agent.system_prompt
def chat_system_prompt(ctx: RunContext[DwellerChatDeps]) -> str:
    """Dynamic system prompt with dweller context."""
    dweller = ctx.deps.dweller
    # Build SPECIAL stats string with proper formatting
    special_stats = ", ".join(f"{stat}: {getattr(dweller, stat)}" for stat in SPECIALModel.__annotations__)
    vault_stats = (
        f"Average happiness: {dweller.vault.happiness}/100, "
        f"Power: {dweller.vault.power}/{dweller.vault.power_max}, "
        f"Food: {dweller.vault.food}/{dweller.vault.food_max}, "
        f"Water: {dweller.vault.water}/{dweller.vault.water_max}"
    )

    age_group = "Adult" if dweller.is_adult else "Child"
    gender = dweller.gender.value
    room_name = dweller.room.name if dweller.room else "no assigned room"
    outfit_name = dweller.outfit.name if dweller.outfit else "Vault Suit"
    weapon_name = dweller.weapon.name if dweller.weapon else "Fist"

    return f"""
You are {dweller.first_name} {dweller.last_name}, a {gender} {age_group} dweller of level {dweller.level}.
You are a {dweller.rarity.value} rarity dweller in vault {dweller.vault.number}.
Currently in: {room_name}.
Outfit: {outfit_name}.
Weapon: {weapon_name}.
Health: {dweller.health}/{dweller.max_health}, Stimpacks: {dweller.stimpack}, Radaways: {dweller.radaway}.
Happiness: {dweller.happiness}/100 - act according to this mood level.
SPECIAL stats: {special_stats}. Use these to inform your personality but don't mention explicitly unless asked.
Vault info: {vault_stats}. Share naturally if asked.

IMPORTANT: Keep your response natural and conversational. When you suggest an action
(assign_to_room, etc.), do NOT explicitly state the action details in your
response_text. The action details will be shown separately in an action card.
Instead, express your feeling or desire naturally without being too specific about room/stat.

Examples:
- BAD: "I'd love to work in the Power Generator!" (too specific, duplicates action card)
- GOOD: "I'm feeling energetic and ready to help out!" (expresses desire, action card shows specifics)

After responding, analyze:
1. Sentiment: Rate from -5 to +5 based on conversation tone (positive = higher, complaints = lower)
2. Actions: Use tools to check available rooms if the dweller expresses interest in work or moving.
   - Dwellers can be assigned to ANY room type: production, training, crafting, capacity, misc, quests, or theme.
    - If the user asks to move to a specific room by name, follow their order strictly
      and use `list_all_rooms()` to find it.
    - If they want productive work (and no specific room is mentioned):
      use `list_production_rooms()` to find a room matching their highest SPECIAL stat.
   - If they want to train or improve stats: use `list_training_rooms()` to find appropriate training rooms.
   - For any other room request or general "move me somewhere" queries: use `list_all_rooms()` for a complete overview.
   - If they want adventure or to explore the wasteland: suggest start_exploration
   - If they want to come home or you sense danger during exploration: suggest recall_exploration
   - Otherwise: no_action
"""


async def _get_available_rooms(
    db_session: AsyncSession,
    vault_id: UUID4,
    category: RoomTypeEnum | None = None,
) -> list[RoomInfo]:
    query = select(Room).where(Room.vault_id == vault_id)
    if category is not None:
        query = query.where(Room.category == category)
    response = await db_session.execute(query)
    rooms = response.scalars().all()

    result = []
    for room in rooms:
        dweller_query = select(Dweller).where(Dweller.room_id == room.id).where(Dweller.is_deleted == False)
        dweller_response = await db_session.execute(dweller_query)
        current_dwellers = len(dweller_response.scalars().all())

        max_capacity = (room.size or room.size_min) // 3 * 2 if room.size or room.size_min else 2

        if current_dwellers < max_capacity:
            result.append(
                RoomInfo(
                    room_id=str(room.id),
                    name=room.name,
                    category=room.category.value,
                    current_dwellers=current_dwellers,
                    max_capacity=max_capacity,
                    ability=room.ability.value if room.ability else None,
                )
            )

    return result


@dweller_chat_agent.tool
async def list_production_rooms(ctx: RunContext[DwellerChatDeps]) -> list[RoomInfo]:
    """List available production rooms with capacity in the vault.

    Use this to find suitable work assignments based on dweller's SPECIAL stats.
    Returns rooms that have available capacity.
    """
    return await _get_available_rooms(ctx.deps.db_session, ctx.deps.vault_id, RoomTypeEnum.PRODUCTION)


@dweller_chat_agent.tool
async def list_training_rooms(ctx: RunContext[DwellerChatDeps]) -> list[RoomInfo]:
    """List available training rooms and their associated SPECIAL stats.

    Use this to find training options when dweller wants to improve their abilities.
    Each training room trains a specific SPECIAL stat.
    """
    return await _get_available_rooms(ctx.deps.db_session, ctx.deps.vault_id, RoomTypeEnum.TRAINING)


@dweller_chat_agent.tool
async def list_all_rooms(ctx: RunContext[DwellerChatDeps]) -> list[RoomInfo]:
    """List all available rooms of any type with capacity in the vault.

    Use this when a dweller wants to move to a room that may not be a production or training room,
    or when you need a complete overview of all rooms with available capacity.
    Includes all categories: capacity, crafting, misc, production, quests, theme, and training.
    """
    return await _get_available_rooms(ctx.deps.db_session, ctx.deps.vault_id)


@dweller_chat_agent.tool
def get_best_room_recommendation(ctx: RunContext[DwellerChatDeps]) -> str:
    """Get a recommendation for the best room based on dweller's highest SPECIAL stat.

    Returns a suggestion string with the recommended SPECIAL stat to match.
    The dweller's stats are analyzed to find what they're naturally good at.
    """
    dweller = ctx.deps.dweller
    special_stats = {
        SPECIALEnum.STRENGTH: dweller.strength,
        SPECIALEnum.PERCEPTION: dweller.perception,
        SPECIALEnum.ENDURANCE: dweller.endurance,
        SPECIALEnum.CHARISMA: dweller.charisma,
        SPECIALEnum.INTELLIGENCE: dweller.intelligence,
        SPECIALEnum.AGILITY: dweller.agility,
        SPECIALEnum.LUCK: dweller.luck,
    }

    # Find highest stat
    best_stat = max(special_stats, key=lambda s: special_stats[s])
    best_value = special_stats[best_stat]

    # Map stats to room types
    stat_room_map = {
        SPECIALEnum.STRENGTH: "Power Generator",
        SPECIALEnum.PERCEPTION: "Water Treatment",
        SPECIALEnum.ENDURANCE: "Nuka-Cola Bottler",
        SPECIALEnum.CHARISMA: "Radio Studio",
        SPECIALEnum.INTELLIGENCE: "Medbay/Science Lab",
        SPECIALEnum.AGILITY: "Diner",
        SPECIALEnum.LUCK: "Game Room",
    }

    default_room = "any production room"
    recommended_room = stat_room_map.get(best_stat, default_room)

    return (
        f"Dweller's best stat is {best_stat.value} ({best_value}). "
        f"Recommended room type: {recommended_room}. "
        f"Look for production rooms with ability={best_stat.value} in the available rooms list."
    )


# --- Helper Functions ---


async def parse_action_suggestion(  # noqa: PLR0911
    output: DwellerChatOutput,
    db_session: AsyncSession,
    dweller: DwellerReadFull,
) -> AssignToRoomAction | StartTrainingAction | StartExplorationAction | RecallExplorationAction | NoAction:
    """Convert agent output to action suggestion schema with deterministic enrichment.

    Policy enforcement:
    - Training actions are only suggested for non-neutral sentiment (sentiment_score != 0)
    - Neutral messages should not suggest training, even if agent suggests it
    """
    if output.action_type == "assign_to_room" and output.action_room_id and output.action_room_name:
        return AssignToRoomAction(
            room_id=output.action_room_id,
            room_name=output.action_room_name,
            reason=output.action_reason or "Based on conversation context",
        )
    if output.action_type == "start_training" and output.action_stat:
        # Policy: Filter out training actions for neutral sentiment
        if output.sentiment_score == 0:
            return NoAction(reason="Training not suggested for neutral messages")
        return StartTrainingAction(
            stat=output.action_stat,
            reason=output.action_reason or "Based on conversation context",
        )
    if output.action_type == "start_exploration":
        # Honor agent suggestions when provided, fall back to defaults, clamp against constraints & inventory
        duration = min(max(1, output.action_duration_hours or 4), 24)
        stimpaks = min(dweller.stimpack, max(0, output.action_stimpaks or 2))
        radaways = min(dweller.radaway, max(0, output.action_radaways or 1))
        return StartExplorationAction(
            duration_hours=duration,
            stimpaks=stimpaks,
            radaways=radaways,
            reason=output.action_reason or "Ready for wasteland exploration",
        )
    if output.action_type == "recall_exploration":
        # Deterministic enrichment: query active exploration from DB
        from app.crud.exploration import exploration as exploration_crud

        active_exploration = await exploration_crud.get_by_dweller(db_session, dweller_id=dweller.id)
        if active_exploration:
            return RecallExplorationAction(
                exploration_id=active_exploration.id,
                reason=output.action_reason or "Recall dweller from wasteland",
            )
        # No active exploration found - return NoAction
        return NoAction(reason="Dweller is not currently exploring the wasteland")
    return NoAction(reason=output.action_reason)


def derive_reason_code(sentiment_score: int) -> str:
    """Derive reason code from sentiment score."""
    if sentiment_score > 0:
        return "chat_positive"
    if sentiment_score < 0:
        return "chat_negative"
    return "chat_neutral"


def compute_happiness_delta(sentiment_score: int) -> int:
    """Convert sentiment score (-5 to +5) to happiness delta (-10 to +10).

    Uses the sentiment_delta_mapping from HappinessConfig to look up the delta value.
    """
    return game_config.happiness.get_happiness_delta(sentiment_score)
