"""Pydantic models for AI-generated dweller content."""

from pydantic import BaseModel, Field


class DwellerBackstory(BaseModel):
    """Structured output for dweller backstory generation."""

    bio: str = Field(
        ...,
        description="A Fallout-style biography for the dweller, approximately 800-1000 characters",
    )


class ExtendedBio(BaseModel):
    """Structured output for bio extension."""

    extended_bio: str = Field(
        ...,
        description="Additional biographical information to extend the existing bio",
    )


class DwellerVisualAttributes(BaseModel):
    """Structured output for dweller visual attributes."""

    # Note: age is excluded - use existing DwellerVisualAttributesInput.age (int field) instead
    height: str | None = Field(None, description="Height: tall, average, short")
    eye_color: str | None = Field(None, description="Eye color: blue, green, brown, hazel, gray")
    appearance: str | None = Field(None, description="Appearance: attractive, cute, average, unattractive")
    skin_tone: str | None = Field(None, description="Skin tone: fair, medium, olive, tan, dark, black")
    build: str | None = Field(None, description="Build: slim, athletic, muscular, stocky, average, overweight")
    hair_style: str | None = Field(None, description="Hair style: short, long, curly, straight, wavy, bald")
    hair_color: str | None = Field(None, description="Hair color: blonde, brunette, redhead, black, gray, colored")
    distinguishing_features: list[str] | None = Field(
        None,
        description=(
            "Distinguishing features: scar, tattoo, mole, freckles, birthmark, piercing, eyepatch, prosthetic limb"
        ),
    )
    clothing_style: str | None = Field(None, description="Clothing style: casual, military, formal, rugged, eclectic")
    facial_hair: str | None = Field(
        None, description="Facial hair (male only): clean-shaven, mustache, beard, goatee, stubble"
    )
    makeup: str | None = Field(None, description="Makeup (female only): natural, glamorous, goth, no makeup")
