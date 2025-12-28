"""Dependency types for PydanticAI agents."""

from dataclasses import dataclass

from app.schemas.common import GenderEnum


@dataclass
class BackstoryDeps:
    """Dependencies for backstory generation agent."""

    first_name: str
    gender: GenderEnum | None
    special_stats: str  # Formatted SPECIAL stats string
    location: str  # Origin location (Wasteland, Vault, etc.)


@dataclass
class ExtendBioDeps:
    """Dependencies for bio extension agent."""

    current_bio: str


@dataclass
class VisualAttributesDeps:
    """Dependencies for visual attributes generation agent."""

    first_name: str
    last_name: str
    gender: GenderEnum | None
    bio: str | None
