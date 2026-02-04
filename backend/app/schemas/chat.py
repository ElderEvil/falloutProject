"""Pydantic schemas for dweller chat responses."""

from typing import Annotated, Literal

from pydantic import UUID4, BaseModel, Field

from app.schemas.common import SPECIALEnum
from app.schemas.happiness import HappinessImpact

# --- Action Suggestion Discriminated Union ---


class AssignToRoomAction(BaseModel):
    """Suggestion to assign dweller to a specific room."""

    action_type: Literal["assign_to_room"] = "assign_to_room"
    room_id: UUID4 = Field(..., description="ID of the room to assign the dweller to")
    room_name: str = Field(..., max_length=100, description="Name of the room for display")
    reason: str = Field(..., max_length=200, description="Why this room is suggested")


class StartTrainingAction(BaseModel):
    """Suggestion to start training a SPECIAL stat."""

    action_type: Literal["start_training"] = "start_training"
    stat: SPECIALEnum = Field(..., description="SPECIAL stat to train")
    reason: str = Field(..., max_length=200, description="Why this training is suggested")


class NoAction(BaseModel):
    """Indicates no action is suggested."""

    action_type: Literal["no_action"] = "no_action"
    reason: str | None = Field(None, max_length=200, description="Optional explanation")


ActionSuggestion = Annotated[
    AssignToRoomAction | StartTrainingAction | NoAction,
    Field(discriminator="action_type"),
]


# --- Chat Response Schema ---


class DwellerChatResponse(BaseModel):
    """Response schema for dweller chat interactions.

    Includes the AI-generated response, happiness impact analysis,
    and optional action suggestions.
    """

    response: str = Field(..., description="The dweller's chat response text")
    happiness_impact: HappinessImpact | None = Field(
        None,
        description="Happiness impact from this interaction (None if not analyzed)",
    )
    action_suggestion: ActionSuggestion | None = Field(
        None,
        description="Optional action suggestion based on conversation context",
    )


class DwellerVoiceChatResponse(BaseModel):
    """Response schema for voice chat interactions (JSON mode)."""

    transcription: str = Field(..., description="Transcribed user audio input")
    user_audio_url: str | None = Field(None, description="URL to stored user audio")
    dweller_response: str = Field(..., description="The dweller's text response")
    dweller_audio_url: str | None = Field(None, description="URL to dweller's audio response")
    happiness_impact: HappinessImpact | None = Field(
        None,
        description="Happiness impact from this interaction",
    )
    action_suggestion: ActionSuggestion | None = Field(
        None,
        description="Optional action suggestion",
    )
