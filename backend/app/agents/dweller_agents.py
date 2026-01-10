"""PydanticAI agents for dweller content generation."""

from pydantic_ai import Agent, RunContext

from app.agents.deps import BackstoryDeps, ExtendBioDeps, VisualAttributesDeps
from app.schemas.common import GenderEnum
from app.schemas.dweller_ai import DwellerBackstory, DwellerVisualAttributes, ExtendedBio
from app.services.open_ai import AIService

# Initialize the model (will be shared across agents)
model = AIService.get_model()

GENDER_PRONOUNS_MAP = {
    GenderEnum.MALE: "his",
    GenderEnum.FEMALE: "her",
    None: "their",
}

BIO_MAX_LENGTH = 1_000

# Backstory Generation Agent
backstory_agent = Agent(
    model=model,
    output_type=DwellerBackstory,
    deps_type=BackstoryDeps,
    system_prompt=(
        "You are a creative writer specialized in creating Fallout game series style character biographies. "
        "Generate immersive, lore-accurate backstories for vault dwellers in the post-apocalyptic world. "
        "Use the dweller's SPECIAL attributes to inform their skills and personality traits. "
        "IMPORTANT: Keep biographies between 600-900 characters (not words). Be concise and focused. "
        "Focus on their background, survival skills, and how they relate to their environment."
    ),
)


@backstory_agent.system_prompt
def backstory_system_prompt(ctx: RunContext[BackstoryDeps]) -> str:
    """Dynamic system prompt based on dweller information."""
    pronoun = GENDER_PRONOUNS_MAP.get(ctx.deps.gender, "their")
    return (
        f"Generate a biography for {ctx.deps.first_name}, a dweller from {ctx.deps.location}. "
        f"Include details about {pronoun} background, skills, and personality traits "
        f"as they relate to surviving in the post-apocalyptic world. "
        f"Their SPECIAL stats are: {ctx.deps.special_stats}. "
        f"Use these stats to create a unique backstory that reflects their strengths and weaknesses. "
        f"CRITICAL: The biography must be between 600-900 characters. Count carefully and stay within this limit."
    )


# Bio Extension Agent
bio_extension_agent = Agent(
    model=model,
    output_type=ExtendedBio,
    deps_type=ExtendBioDeps,
    system_prompt=(
        "You are a creative writer helping to extend character biographies in the Fallout universe. "
        "Given an existing bio, add meaningful details that expand on the character's backstory, "
        "experiences, relationships, or personality. Maintain consistency with the original bio "
        "and keep the tone consistent with the Fallout game series."
    ),
)


@bio_extension_agent.system_prompt
def bio_extension_system_prompt(ctx: RunContext[ExtendBioDeps]) -> str:
    """Dynamic system prompt with current bio context."""
    return (
        f"Here is the current biography:\n\n{ctx.deps.current_bio}\n\n"
        "Extend this biography with additional meaningful details. "
        "Add new information about their experiences, relationships, or character development. "
        "Maintain the same writing style and tone."
    )


# Visual Attributes Generation Agent
visual_attributes_agent = Agent(
    model=model,
    output_type=DwellerVisualAttributes,
    deps_type=VisualAttributesDeps,
    system_prompt=(
        "You are a character design specialist for the Fallout universe. "
        "Generate visual attributes for vault dwellers based on their biography and characteristics. "
        "Create realistic, lore-appropriate visual descriptions that match the post-apocalyptic setting. "
        "Available options:\n"
        "- height: tall, average, short\n"
        "- eye_color: blue, green, brown, hazel, gray\n"
        "- appearance: attractive, cute, average, unattractive\n"
        "- skin_tone: fair, medium, olive, tan, dark, black\n"
        "- build: slim, athletic, muscular, stocky, average, overweight\n"
        "- hair_style: short, long, curly, straight, wavy, bald\n"
        "- hair_color: blonde, brunette, redhead, black, gray, colored\n"
        "- distinguishing_features: scar, tattoo, mole, freckles, birthmark, piercing, eyepatch, prosthetic limb\n"
        "- clothing_style: casual, military, formal, rugged, eclectic\n"
        "- facial_hair (male only): clean-shaven, mustache, beard, goatee, stubble\n"
        "- makeup (female only): natural, glamorous, goth, no makeup"
    ),
)


@visual_attributes_agent.system_prompt
def visual_attributes_system_prompt(ctx: RunContext[VisualAttributesDeps]) -> str:
    """Dynamic system prompt based on dweller information."""
    pronoun = GENDER_PRONOUNS_MAP.get(ctx.deps.gender, "their")
    bio_context = f"\n\nBackstory: {ctx.deps.bio}" if ctx.deps.bio else ""

    return (
        f"Create visual attributes for {ctx.deps.first_name} {ctx.deps.last_name}. "
        f"Consider {pronoun} background and personality when selecting visual traits.{bio_context}\n\n"
        "Generate a cohesive visual description that matches their character. "
        "Use the available options to create a believable Fallout character appearance."
    )
