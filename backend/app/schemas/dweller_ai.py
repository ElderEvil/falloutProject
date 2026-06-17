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
