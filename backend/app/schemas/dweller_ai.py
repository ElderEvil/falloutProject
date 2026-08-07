"""Pydantic models for AI-generated dweller content."""

from typing import Annotated

from pydantic import BaseModel, Field


class DwellerBackstory(BaseModel):
    """Structured output for dweller backstory generation."""

    bio: str = Field(
        ...,
        description="A Fallout-style biography for the dweller, approximately 800-1000 characters",
    )
    origin_place: str = Field(
        max_length=64,
        description=(
            "Proper-noun name of the specific settlement/place the dweller comes from; "
            "invent a Fallout-style name; NEVER a generic term like 'Wasteland'"
        ),
    )
    visited_places: list[Annotated[str, Field(max_length=64)]] = Field(
        default_factory=list,
        max_length=5,
        description="0-5 notable named places the dweller has visited, each <=64 chars",
    )


class ExtendedBio(BaseModel):
    """Structured output for bio extension."""

    extended_bio: str = Field(
        ...,
        description="Additional biographical information to extend the existing bio",
    )
    visited_places: list[Annotated[str, Field(max_length=64)]] = Field(
        default_factory=list,
        max_length=3,
        description="0-3 newly mentioned named places from the extension, each <=64 chars",
    )
