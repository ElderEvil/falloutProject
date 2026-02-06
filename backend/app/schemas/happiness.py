"""Pydantic schemas for happiness-related chat responses."""

from enum import StrEnum

from pydantic import BaseModel, Field


class HappinessReasonCode(StrEnum):
    """Reason codes for happiness changes from chat interactions."""

    CHAT_POSITIVE = "chat_positive"
    CHAT_NEUTRAL = "chat_neutral"
    CHAT_NEGATIVE = "chat_negative"


class HappinessImpact(BaseModel):
    """Schema describing the happiness impact of a chat interaction.

    Provides both numerical impact (delta) and human-readable context
    for understanding why happiness changed.
    """

    delta: int = Field(
        ...,
        ge=-10,
        le=10,
        description="Happiness change applied to dweller (-10 to +10)",
    )
    reason_code: HappinessReasonCode = Field(
        ...,
        description="Machine-readable reason code for the happiness change",
    )
    reason_text: str = Field(
        ...,
        max_length=200,
        description="Human-readable explanation of why happiness changed",
    )
    happiness_after: int = Field(
        ...,
        ge=0,
        le=100,
        description="Dweller's happiness value after applying the delta (clamped 0-100)",
    )
