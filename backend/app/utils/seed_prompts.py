"""Prompt registry seed command."""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.prompt import Prompt
from app.services.prompt_service import DEFAULT_PROMPTS

PROMPT_DESCRIPTIONS = {
    "backstory": "Backstory generation for new dwellers (backstory_agent v1).",
    "extend_bio": "Bio extension for existing dweller biographies (bio_extension_agent v1).",
    "visual_attributes": "Visual attributes generation from dweller bios (visual_attributes_agent v1).",
    "chat": "In-character dweller chat with sentiment and action suggestions (dweller_chat_agent v1).",
}


async def seed_prompts(db_session: AsyncSession) -> int:
    """Insert missing v1 prompts without replacing existing versions."""
    existing = set(
        (await db_session.exec(select(Prompt.prompt_name).where(col(Prompt.prompt_name).in_(DEFAULT_PROMPTS)))).all()
    )
    db_session.add_all(
        [
            Prompt(prompt_name=name, description=PROMPT_DESCRIPTIONS[name], prompt_template=template)
            for name, template in DEFAULT_PROMPTS.items()
            if name not in existing
        ]
    )
    await db_session.commit()
    return len(DEFAULT_PROMPTS) - len(existing)
