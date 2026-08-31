"""Prompt registry resolution: DB-backed instructions with a 60s TTL cache and hardcoded fallbacks.

Resolution happens in the service layer before ``agent.run`` — agent deps never
carry a DB session. Any DB failure degrades to the hardcoded v1 defaults
(verbatim copies of the seed strings) so provenance lookup can never fail an
LLM call.
"""

import hashlib
import logging
import time
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.crud.ai_settings import ai_settings as ai_settings_crud
from app.models.prompt import Prompt

logger = logging.getLogger(__name__)

PROMPT_CACHE_TTL_SECONDS = 60.0  # admin edits propagate quickly without a DB hit per request

# Hardcoded fallbacks, verbatim copies of the v1 seed strings in
# app.utils.seed_prompts (deliberately not imported from the agents or the
# seeds: the fallback must stay stable even if those change).
DEFAULT_PROMPTS: dict[str, str] = {
    "backstory": (
        "You are a creative writer specialized in creating Fallout game series style character biographies. "
        "Generate immersive, lore-accurate backstories for vault dwellers in the post-apocalyptic world. "
        "Use the dweller's SPECIAL attributes to inform their skills and personality traits. "
        "IMPORTANT: Keep biographies between 600-900 characters (not words). Be concise and focused. "
        "Focus on their background, survival skills, and how they relate to their environment. "
        "You MUST also specify origin_place: a specific settlement/place the dweller comes from. "
        "Invent a proper-noun Fallout-style name (e.g. 'Megaton', 'Shady Sands', 'Goodneighbor'). "
        "NEVER use generic names like 'Wasteland', 'the wastes', 'Unknown', or 'Vault'. "
        "Also list 0-5 visited_places: other notable named places the dweller has travelled to, "
        "each a proper-noun Fallout-style location name (max 64 chars each)."
    ),
    "extend_bio": (
        "You are a creative writer helping to extend character biographies in the Fallout universe. "
        "Given an existing bio, add meaningful details that expand on the character's backstory, "
        "experiences, relationships, or personality. Maintain consistency with the original bio "
        "and keep the tone consistent with the Fallout game series. "
        "While extending, if you mention any NEW named Fallout-style locations "
        "(settlements, outposts, vaults, landmarks), list them in visited_places "
        "(0-3 proper-noun names, max 64 chars each). "
        "Only include places you introduce in the extension — do NOT repeat places from the original bio."
    ),
    "visual_attributes": (
        "You are a character design specialist for the Fallout universe. "
        "Generate visual attributes for vault dwellers based on their biography and characteristics. "
        "Create realistic, lore-appropriate visual descriptions that match the post-apocalyptic setting."
    ),
    "chat": (
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
}

# agent_name -> (instructions, prompt_id, instructions_hash, cached_at monotonic)
_cache: dict[str, tuple[str, UUID | None, str, float]] = {}


def compute_instructions_hash(instructions: str) -> str:
    """SHA256 of the instructions, truncated to 64 hex chars (matches the column)."""
    return hashlib.sha256(instructions.encode()).hexdigest()[:64]


def invalidate(agent_name: str | None = None) -> None:
    """Drop cached prompt resolutions — all agents, or a single one."""
    if agent_name is None:
        _cache.clear()
    else:
        _cache.pop(agent_name, None)


async def get_instructions(db_session: AsyncSession, agent_name: str) -> tuple[str, UUID | None, str]:
    """Resolve the active instructions for an agent name.

    Returns ``(instructions, prompt_id, instructions_hash)``. Reads the active
    registry row through the TTL cache; on DB error — or when no row is active
    yet — falls back to the hardcoded default (prompt_id ``None``). Never
    raises for DB problems; unknown agent names are caller bugs.
    """
    default = DEFAULT_PROMPTS.get(agent_name)
    if default is None:
        raise ValueError(f"Unknown prompt agent_name: {agent_name!r}")

    cached = _cache.get(agent_name)
    if cached is not None and time.monotonic() - cached[3] < PROMPT_CACHE_TTL_SECONDS:
        return cached[0], cached[1], cached[2]

    try:
        async with db_session.begin_nested():
            rows = await db_session.execute(
                select(Prompt).where(col(Prompt.prompt_name) == agent_name, col(Prompt.is_active).is_(True))
            )
            prompt = rows.scalars().first()
    except Exception:
        logger.warning("Prompt registry lookup failed for %r; using hardcoded default", agent_name)
        return default, None, compute_instructions_hash(default)

    if prompt is None:
        # Nothing active seeded yet — default, uncached so a later seed is picked up.
        return default, None, compute_instructions_hash(default)

    instructions_hash = compute_instructions_hash(prompt.prompt_template)
    _cache[agent_name] = (prompt.prompt_template, prompt.id, instructions_hash, time.monotonic())
    return prompt.prompt_template, prompt.id, instructions_hash


async def get_prompt_id(db_session: AsyncSession, agent_name: str) -> UUID | None:
    """Resolve just the active prompt row id (``None`` when on the hardcoded default)."""
    return (await get_instructions(db_session, agent_name))[1]


async def get_provider_model_snapshot(db_session: AsyncSession) -> tuple[str, str]:
    """Snapshot the effective provider/model at call time (DB profile overrides env).

    Best-effort provenance: a failed profile read degrades to env config.
    """
    try:
        async with db_session.begin_nested():
            profile = await ai_settings_crud.get_single(db_session)
    except Exception:
        logger.warning("AI settings profile read failed; snapshotting env config only")
        return settings.AI_PROVIDER, settings.AI_MODEL
    return settings.effective_ai_provider(profile), settings.effective_ai_model(profile)


def format_prompt(template: str, **kwargs: object) -> str:
    """Format a prompt template, falling back to the raw template on bad placeholders."""
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        logger.warning("Prompt template formatting failed; returning raw template")
        return template
