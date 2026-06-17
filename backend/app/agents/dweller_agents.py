"""PydanticAI agents for dweller content generation."""

from pydantic_ai import Agent, RunContext

from app.agents.deps import BackstoryDeps, ExtendBioDeps, VisualAttributesDeps
from app.schemas.common import GenderEnum
from app.schemas.dweller import DwellerVisualAttributes
from app.schemas.dweller_ai import DwellerBackstory, ExtendedBio
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
    ),
)


@visual_attributes_agent.system_prompt
def visual_attributes_system_prompt(ctx: RunContext[VisualAttributesDeps]) -> str:
    """Dynamic system prompt based on dweller information."""
    pronoun = GENDER_PRONOUNS_MAP.get(ctx.deps.gender, "their")
    bio_context = f"\n\nBackstory: {ctx.deps.bio}" if ctx.deps.bio else ""

    race_context = ""
    if ctx.deps.race:
        race_context = f"\nThe dweller's race is {ctx.deps.race}. "
        match ctx.deps.race:
            case "ghoul":
                race_context += (
                    "Ghouls have leathery, radiation-scarred, slightly decayed skin, sunken eyes, "
                    "and aged facial features. Choose skin_tones like pale_grey, ashen, "
                    "mottled, necrotic, or glowing. Builds include skeletal, withered, or twisted."
                )
            case "super_mutant":
                race_context += (
                    "Super Mutants are large, muscular humanoids with green or dark green skin, "
                    "rough battle-scarred texture, and powerful bulky frames. "
                    "Choose skin_tones like light_green, green, dark_green, or olive_green. "
                    "Builds include muscular, brutish, or towering."
                )
            case "synth":
                race_context += (
                    "Synths have artificial skin that can appear human-like or visibly synthetic. "
                    "Choose skin_tones like synthetic_fair, synthetic_dark, metallic_silver, "
                    "or exposed_component. Builds include slender, muscular, or armored."
                )
            case _:  # human
                race_context += (
                    "Humans have natural skin tones. Choose from pale, light, tan, brown, "
                    "dark_brown, or ebony. Builds include slim, athletic, muscular, "
                    "stocky, average, or overweight."
                )

    faction_context = ""
    if ctx.deps.faction and ctx.deps.faction != "none":
        faction_context = (
            f"\nThe dweller's faction is {ctx.deps.faction}. "
            "Consider how their faction affiliation affects their clothing style, "
            "equipment, and overall appearance."
        )

    return (
        f"Create visual attributes for {ctx.deps.first_name} {ctx.deps.last_name}. "
        f"Consider {pronoun} background and personality when selecting visual traits."
        f"{race_context}{faction_context}{bio_context}\n\n"
        "Generate a cohesive visual description that matches their character. "
        "Use the available options to create a believable Fallout character appearance. "
        "IMPORTANT: For the 'build' field, use lore-appropriate options based on the dweller's race. "
        "For the 'skin_tone' field, use options appropriate to the dweller's race."
    )
