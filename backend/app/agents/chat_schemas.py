"""Schemas and payload contracts for the dweller chat agent."""

from dataclasses import dataclass
from typing import Literal

from pydantic import UUID4, BaseModel, Field
from pydantic_ai.exceptions import ModelRetry
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import SPECIALEnum
from app.schemas.dweller import DwellerReadFull

ACTION_TYPES = Literal[
    "assign_to_room",
    "start_training",
    "start_exploration",
    "recall_exploration",
    "request_stimpak",
    "request_radaway",
    "no_action",
]

ACTION_PAYLOAD_FIELDS = (
    "action_room_id",
    "action_room_name",
    "action_stat",
    "action_duration_hours",
    "action_stimpaks",
    "action_radaways",
    "action_exploration_id",
)

REQUIRED_ACTION_FIELDS: dict[ACTION_TYPES, tuple[str, ...]] = {
    "assign_to_room": ("action_room_id", "action_room_name"),
    "start_training": ("action_stat",),
    "start_exploration": (),
    "recall_exploration": (),
    "request_stimpak": (),
    "request_radaway": (),
    "no_action": (),
}

ALLOWED_ACTION_FIELDS: dict[ACTION_TYPES, tuple[str, ...]] = {
    "assign_to_room": ("action_room_id", "action_room_name"),
    "start_training": ("action_stat",),
    "start_exploration": ("action_duration_hours", "action_stimpaks", "action_radaways"),
    "recall_exploration": (),
    "request_stimpak": (),
    "request_radaway": (),
    "no_action": (),
}


class DwellerChatOutput(BaseModel):
    response_text: str = Field(description="In-character response to the user")
    sentiment_score: int = Field(ge=-5, le=5, description="Conversation sentiment from -5 to 5")
    reason_text: str = Field(max_length=200, description="Brief sentiment explanation")
    action_type: ACTION_TYPES = Field(description="Suggested action type")
    action_room_id: UUID4 | None = Field(None, description="Room ID for an assignment")
    action_room_name: str | None = Field(None, description="Room name for an assignment")
    action_stat: SPECIALEnum | None = Field(None, description="Stat for training")
    action_reason: str | None = Field(None, max_length=200, description="Suggested action rationale")
    action_duration_hours: int | None = Field(None, ge=1, le=24, description="Exploration duration")
    action_stimpaks: int | None = Field(None, ge=0, le=25, description="Exploration stimpaks")
    action_radaways: int | None = Field(None, ge=0, le=25, description="Exploration radaways")
    action_exploration_id: UUID4 | None = Field(None, description="Exploration ID for recall")


@dataclass
class DwellerChatDeps:
    db_session: AsyncSession
    dweller: DwellerReadFull
    vault_id: UUID4


class RoomInfo(BaseModel):
    room_id: str
    name: str
    category: str
    current_dwellers: int
    max_capacity: int
    ability: str | None = None


class TrainingOption(BaseModel):
    room_name: str
    stat: SPECIALEnum
    current_stat: int
    capacity_remaining: int
    estimated_duration_hours: float


class DwellerActivityBriefing(BaseModel):
    active_training_stat: SPECIALEnum | None = None
    active_training_progress_percent: float | None = None
    training_options: list[TrainingOption] = []
    training_blocker: str | None = None
    exploration_active: bool
    exploration_progress_percent: float | None = None
    exploration_duration_hours: int | None = None
    available_stimpaks: int
    available_radaways: int
    recommended_exploration_duration_hours: int | None = None
    recommended_stimpaks: int | None = None
    recommended_radaways: int | None = None
    exploration_blocker: str | None = None


def validate_dweller_chat_output(output: DwellerChatOutput) -> DwellerChatOutput:
    """Reject action payloads whose fields do not match their action type."""
    required_fields = REQUIRED_ACTION_FIELDS[output.action_type]
    missing_fields = [field for field in required_fields if getattr(output, field) is None]
    if missing_fields:
        fields = ", ".join(missing_fields)
        raise ModelRetry(f"{output.action_type} requires: {fields}.")

    allowed_fields = ALLOWED_ACTION_FIELDS[output.action_type]
    unexpected_fields = [
        field for field in ACTION_PAYLOAD_FIELDS if field not in allowed_fields and getattr(output, field) is not None
    ]
    if unexpected_fields:
        fields = ", ".join(unexpected_fields)
        raise ModelRetry(f"{output.action_type} must not include: {fields}.")

    return output
