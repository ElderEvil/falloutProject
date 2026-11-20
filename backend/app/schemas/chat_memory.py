"""Contracts for automatic dweller-memory extraction.

These live in ``app/schemas`` because a service carries behaviour, not data contracts.
"""

from typing import Literal

from pydantic import BaseModel, Field

MemoryKind = Literal["habit", "fear", "keepsake", "promise", "event", "relationship"]


class MemoryCandidate(BaseModel):
    """One fact proposed by the extraction model, before any validation."""

    fact: str = Field(description="First-person sentence, at most 240 characters.")
    kind: MemoryKind


class MemoryExtractionOutput(BaseModel):
    """The extraction model's whole answer."""

    facts: list[MemoryCandidate] = Field(default_factory=list)
