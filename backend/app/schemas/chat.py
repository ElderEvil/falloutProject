"""Pydantic schemas for dweller chat requests and responses."""

from typing import Annotated, Literal

from pydantic import UUID4, BaseModel, Field

from app.core.enums import SPECIALEnum
from app.schemas.happiness import HappinessImpact


class ChatMessage(BaseModel):
    """Request schema for sending a text message to a dweller."""

    message: str = Field(..., min_length=1, description="The chat message text")


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


class StartExplorationAction(BaseModel):
    """Suggestion to send dweller on wasteland exploration."""

    action_type: Literal["start_exploration"] = "start_exploration"
    duration_hours: int = Field(..., ge=1, le=24, description="Exploration duration in hours")
    stimpaks: int = Field(..., ge=0, le=25, description="Number of stimpaks to take")
    radaways: int = Field(..., ge=0, le=25, description="Number of radaways to take")
    reason: str = Field(..., max_length=200, description="Why exploration is suggested")


class RecallExplorationAction(BaseModel):
    """Suggestion to recall dweller from wasteland exploration."""

    action_type: Literal["recall_exploration"] = "recall_exploration"
    exploration_id: UUID4 = Field(..., description="ID of the active exploration to recall from")
    reason: str = Field(..., max_length=200, description="Why recall is suggested")


class RequestStimpakAction(BaseModel):
    """Suggestion to give the dweller a Stimpak."""

    action_type: Literal["request_stimpak"] = "request_stimpak"
    reason: str = Field(..., max_length=200, description="Why the dweller needs a Stimpak")


class RequestRadawayAction(BaseModel):
    """Suggestion to give the dweller a RadAway."""

    action_type: Literal["request_radaway"] = "request_radaway"
    reason: str = Field(..., max_length=200, description="Why the dweller needs RadAway")


class RequestExitAction(BaseModel):
    """Suggestion to let the dweller leave the vault. Granting is permanent."""

    action_type: Literal["request_exit"] = "request_exit"
    reason: str = Field(..., max_length=200, description="Why the dweller wants to leave")


MedicalRecommendation = Literal["request_stimpak", "request_radaway", "none"]


class MedicalAidStatus(BaseModel):
    """Live health, radiation, and medical supply state for chat decisions."""

    health_percent: float
    radiation_percent: float
    available_stimpaks: int
    available_radaways: int
    recommended_action: MedicalRecommendation


class NoAction(BaseModel):
    """Indicates no action is suggested."""

    action_type: Literal["no_action"] = "no_action"
    reason: str | None = Field(None, max_length=200, description="Optional explanation")


class BioAddendumAction(BaseModel):
    """Suggestion to record a durable detail from the conversation into the biography."""

    action_type: Literal["bio_addendum"] = "bio_addendum"
    bio_text: str = Field(
        ...,
        min_length=8,
        max_length=240,
        description="First-person detail to append to the dweller's biography",
    )
    reason: str = Field(..., max_length=200, description="Why this detail is worth keeping")


ActionSuggestion = Annotated[
    AssignToRoomAction
    | StartTrainingAction
    | StartExplorationAction
    | RecallExplorationAction
    | RequestStimpakAction
    | RequestRadawayAction
    | RequestExitAction
    | BioAddendumAction
    | NoAction,
    Field(discriminator="action_type"),
]


# --- Chat Response Schema ---


class UnlockedPlace(BaseModel):
    """A map location newly revealed by a conversation."""

    location_id: UUID4 = Field(..., description="ID used to open the location on the vault map")
    name: str = Field(..., description="Display name of the revealed location")


class ChatGuardrailDebug(BaseModel):
    """Whether the input screen ran and what it decided."""

    ran: bool = Field(..., description="Whether the guardrail judged this message")
    blocked: bool = Field(..., description="Whether the message was blocked")
    reason: str | None = Field(None, description="Human-readable block reason, if any")


class ChatJevField(BaseModel):
    """One judged Jev field, answer and confidence together.

    ``confidence`` is the probability of ``answer``; a ``False`` at 0.96 means
    "96% sure it is not this", so the pair must be read together.
    """

    answer: bool = Field(..., description="The field's answer")
    confidence: float = Field(..., description="Probability of that answer, 0-1")


class ChatJevDecision(BaseModel):
    """One Jev decision that fired: its named fields, each answered with confidence."""

    name: str = Field(..., description="Decision identifier, e.g. 'guardrail'")
    fields: dict[str, ChatJevField] = Field(
        default_factory=dict,
        description="Field name -> {answer, confidence}",
    )


class ChatDebug(BaseModel):
    """Dev-only diagnostics for one chat turn. Populated only when opt-in requested.

    Never persisted: this rides the live response (and the streamed done event) so
    stored history stays bounded, and any message-shaped schema may embed it as an
    optional field.
    """

    provider: str | None = Field(None, description="Provider id used for this turn")
    model: str | None = Field(None, description="Model id used for this turn")
    prompt_tokens: int | None = Field(None, description="Input tokens billed")
    completion_tokens: int | None = Field(None, description="Output tokens billed")
    total_tokens: int | None = Field(None, description="Total tokens billed")
    guardrail: ChatGuardrailDebug | None = Field(None, description="Input screen outcome")
    jev_decisions: list[ChatJevDecision] = Field(
        default_factory=list,
        description="Jev decisions that fired this turn, in the order they ran",
    )


class DwellerChatResponse(BaseModel):
    """Response schema for dweller chat interactions.

    Includes the AI-generated response, happiness impact analysis,
    and optional action suggestions.
    """

    response: str = Field(..., description="The dweller's chat response text")
    dweller_message_id: UUID4 = Field(..., description="ID of the dweller's chat message in database")
    happiness_impact: HappinessImpact | None = Field(
        None,
        description="Happiness impact from this interaction (None if not analyzed)",
    )
    action_suggestion: ActionSuggestion | None = Field(
        None,
        description="Optional action suggestion based on conversation context",
    )
    unlocked_places: list[UnlockedPlace] = Field(
        default_factory=list,
        description="Map locations newly unlocked by this conversation",
    )
    debug: ChatDebug | None = Field(
        None,
        description="Dev diagnostics (tokens, model, guardrail/Jev decisions); only when debug is requested",
    )


class ChatStreamToken(BaseModel):
    """An incremental or replacement fragment of a streamed dweller response."""

    type: Literal["token"] = "token"
    text: str
    replace: bool | None = None


class ChatStreamDone(BaseModel):
    """The persisted result of a completed streamed dweller response."""

    type: Literal["done"] = "done"
    dweller_message_id: UUID4
    response_text: str
    happiness_impact: HappinessImpact | None = None
    action_suggestion: ActionSuggestion | None = None
    unlocked_places: list[UnlockedPlace] = Field(default_factory=list)
    debug: ChatDebug | None = Field(
        None,
        description="Dev diagnostics; present only when the turn opted into debug",
    )


class ChatStreamError(BaseModel):
    """A recoverable failure reported through the chat streaming protocol."""

    type: Literal["error"] = "error"
    detail: str


ChatStreamEvent = Annotated[
    ChatStreamToken | ChatStreamDone | ChatStreamError,
    Field(discriminator="type"),
]


class DwellerVoiceChatResponse(BaseModel):
    """Response schema for voice chat interactions (JSON mode)."""

    transcription: str = Field(..., description="Transcribed user audio input")
    user_audio_url: str | None = Field(None, description="URL to stored user audio")
    dweller_response: str = Field(..., description="The dweller's text response")
    dweller_audio_url: str | None = Field(None, description="URL to dweller's audio response")
    dweller_message_id: UUID4 = Field(..., description="ID of the dweller's chat message in database")
    happiness_impact: HappinessImpact | None = Field(
        None,
        description="Happiness impact from this interaction",
    )
    action_suggestion: ActionSuggestion | None = Field(
        None,
        description="Optional action suggestion",
    )
    unlocked_places: list[UnlockedPlace] = Field(
        default_factory=list,
        description="Map locations newly unlocked by this conversation",
    )


class VoiceChatResult(DwellerVoiceChatResponse):
    """Completed voice conversation, including audio for binary playback."""

    dweller_audio_bytes: bytes = Field(exclude=True)
