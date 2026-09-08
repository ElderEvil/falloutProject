"""PydanticAI agent for dweller chat — composition only.

Schemas live in :mod:`app.agents.chat_schemas`, the prompt in
:mod:`app.agents.chat_prompts`, and tool/policy implementations in
:mod:`app.agents.chat_tools`. This module wires them onto the agent instance
and re-exports the public names for existing importers.
"""

import logging

from pydantic_ai import Agent, RunContext

from app.agents.chat_prompts import build_chat_instructions
from app.agents.chat_schemas import (
    DwellerActivityBriefing,
    DwellerChatDeps,
    DwellerChatOutput,
    RoomInfo,
    validate_dweller_chat_output,
)
from app.agents.chat_tools import (
    best_room_recommendation_text,
    build_dweller_activity_briefing,
    build_dweller_social_context,
    compute_happiness_delta,
    derive_reason_code,
    get_available_rooms,
    parse_action_suggestion,
)
from app.core.enums import RoomTypeEnum
from app.services.ai_service import get_model
from app.services.medical_service import (
    get_dweller_medical_status as fetch_dweller_medical_status,
)

logger = logging.getLogger(__name__)

__all__ = [
    "DwellerActivityBriefing",
    "DwellerChatDeps",
    "DwellerChatOutput",
    "ModelCache",
    "RoomInfo",
    "build_dweller_activity_briefing",
    "build_dweller_social_context",
    "compute_happiness_delta",
    "derive_reason_code",
    "dweller_chat_agent",
    "parse_action_suggestion",
]


class ModelCache:
    """Singleton-like cache for the AI model to avoid re-initialization."""

    _instance = None

    @classmethod
    def get_model(cls):
        """Get or lazily initialize the AI model."""
        if cls._instance is None:
            cls._instance = get_model()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the cached model so the next get_model() re-initializes."""
        cls._instance = None


dweller_chat_agent = Agent(
    model=ModelCache.get_model(),
    output_type=DwellerChatOutput,
    deps_type=DwellerChatDeps,
    retries=2,
)


@dweller_chat_agent.instructions
def chat_instructions(ctx: RunContext[DwellerChatDeps]) -> str:
    """Build dynamic instructions with dweller context for this stateless chat run."""
    return build_chat_instructions(ctx.deps.dweller)


@dweller_chat_agent.output_validator
def validate_output(output: DwellerChatOutput) -> DwellerChatOutput:
    """Reject action payloads whose fields do not match their action type."""
    return validate_dweller_chat_output(output)


@dweller_chat_agent.tool
async def list_production_rooms(ctx: RunContext[DwellerChatDeps]) -> list[RoomInfo]:
    """List available production rooms with capacity in the vault.

    Use this to find suitable work assignments based on dweller's SPECIAL stats.
    Returns rooms that have available capacity.
    """
    return await get_available_rooms(ctx.deps.db_session, ctx.deps.vault_id, RoomTypeEnum.PRODUCTION)


@dweller_chat_agent.tool
async def list_training_rooms(ctx: RunContext[DwellerChatDeps]) -> list[RoomInfo]:
    """List available training rooms and their associated SPECIAL stats.

    Use this to find training options when dweller wants to improve their abilities.
    Each training room trains a specific SPECIAL stat.
    """
    return await get_available_rooms(ctx.deps.db_session, ctx.deps.vault_id, RoomTypeEnum.TRAINING)


@dweller_chat_agent.tool
async def list_all_rooms(ctx: RunContext[DwellerChatDeps]) -> list[RoomInfo]:
    """List all available rooms of any type with capacity in the vault.

    Use this when a dweller wants to move to a room that may not be a production or training room,
    or when you need a complete overview of all rooms with available capacity.
    Includes all categories: capacity, crafting, misc, production, quests, theme, and training.
    """
    return await get_available_rooms(ctx.deps.db_session, ctx.deps.vault_id)


@dweller_chat_agent.tool
async def get_dweller_social_context(ctx: RunContext[DwellerChatDeps], topic: str = "general") -> dict:
    """Get live status, room, family, and relationship affinity for a social topic."""
    return {"requested_topic": topic, **await build_dweller_social_context(ctx.deps)}


@dweller_chat_agent.tool
async def get_dweller_activity_briefing(ctx: RunContext[DwellerChatDeps]) -> DwellerActivityBriefing:
    """Inspect current training and exploration readiness before suggesting either activity."""
    return await build_dweller_activity_briefing(ctx.deps)


@dweller_chat_agent.tool
async def get_dweller_medical_status(ctx: RunContext[DwellerChatDeps]):
    """Check whether this dweller should request a Stimpak or RadAway."""
    return await fetch_dweller_medical_status(ctx.deps.db_session, ctx.deps.dweller, ctx.deps.vault_id)


@dweller_chat_agent.tool
def get_best_room_recommendation(ctx: RunContext[DwellerChatDeps]) -> str:
    """Recommend a room based on the dweller's highest SPECIAL stat."""
    return best_room_recommendation_text(ctx.deps.dweller)
