"""Prompt registry seeding: inserts v1 agent instructions as immutable provenance rows."""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.prompt import Prompt

# Frozen v1 instruction strings, copied verbatim from the agents they document
# (dweller_agents.py, dweller_chat_agent.py). Deliberately not imported from
# the agents: a versioned registry row must record what v1 said at seed time,
# not silently track later edits to the live agents.
BACKSTORY_V1 = (
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
)

EXTEND_BIO_V1 = (
    "You are a creative writer helping to extend character biographies in the Fallout universe. "
    "Given an existing bio, add meaningful details that expand on the character's backstory, "
    "experiences, relationships, or personality. Maintain consistency with the original bio "
    "and keep the tone consistent with the Fallout game series. "
    "While extending, if you mention any NEW named Fallout-style locations "
    "(settlements, outposts, vaults, landmarks), list them in visited_places "
    "(0-3 proper-noun names, max 64 chars each). "
    "Only include places you introduce in the extension — do NOT repeat places from the original bio."
)

VISUAL_ATTRIBUTES_V1 = (
    "You are a character design specialist for the Fallout universe. "
    "Generate visual attributes for vault dwellers based on their biography and characteristics. "
    "Create realistic, lore-appropriate visual descriptions that match the post-apocalyptic setting."
)

CHAT_V1 = (
    "You are a Vault-Tec Dweller in a post-apocalyptic world. "
    "Respond in character, staying true to the Fallout universe. "
    "Analyze the conversation sentiment and suggest helpful actions when appropriate. "
    "Actions include: assigning to any room type in the vault "
    "(production, training, crafting, capacity, misc, quests, or theme rooms), "
    "sending dweller on wasteland exploration, or recalling dweller from exploration. "
    "Only suggest actions when the conversation naturally leads to them (e.g., dweller mentions being bored, "
    "wanting to work, wanting adventure, or wanting to come home). "
    "When the user requests assignment to a specific room, follow their order strictly."
)

PROMPT_SEEDS: dict[str, tuple[str, str]] = {
    "backstory": ("Backstory generation for new dwellers (backstory_agent v1).", BACKSTORY_V1),
    "extend_bio": ("Bio extension for existing dweller biographies (bio_extension_agent v1).", EXTEND_BIO_V1),
    "visual_attributes": (
        "Visual attributes generation from dweller bios (visual_attributes_agent v1).",
        VISUAL_ATTRIBUTES_V1,
    ),
    "chat": ("In-character dweller chat with sentiment and action suggestions (dweller_chat_agent v1).", CHAT_V1),
}


async def seed_prompts(db_session: AsyncSession) -> int:
    """Insert v1 prompt rows; skip names that already have any registry row."""
    rows = await db_session.execute(select(Prompt.prompt_name).where(col(Prompt.prompt_name).in_(PROMPT_SEEDS)))
    existing = set(rows.scalars().all())
    new_prompts = [
        Prompt(prompt_name=name, description=description, prompt_template=template)
        for name, (description, template) in PROMPT_SEEDS.items()
        if name not in existing
    ]
    db_session.add_all(new_prompts)
    await db_session.commit()
    return len(new_prompts)
