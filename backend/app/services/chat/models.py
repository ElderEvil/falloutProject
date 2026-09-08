"""Internal data records shared by chat collaborators."""

from dataclasses import dataclass

from pydantic import UUID4

from app.schemas.chat import ActionSuggestion
from app.schemas.happiness import HappinessImpact


@dataclass
class AgentChatResult:
    """Outcome of one structured or fallback agent run."""

    response_text: str
    happiness_impact: HappinessImpact
    action_suggestion: ActionSuggestion
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass
class StreamBundle:
    """Streaming outcome collected before chat persistence."""

    response_text: str = ""
    happiness_impact: HappinessImpact | None = None
    action_suggestion: ActionSuggestion | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    provider: str | None = None
    model: str | None = None
    prompt_id: UUID4 | None = None
    instructions_hash: str | None = None
    instructions_snapshot: str | None = None


@dataclass
class VoiceMessagePayload:
    """Voice-chat data awaiting persistence."""

    transcribed_text: str
    user_audio_url: str | None
    audio_duration: float | None
    dweller_response_text: str
    dweller_audio_url: str | None
    happiness_impact: HappinessImpact | None = None
    action_suggestion: ActionSuggestion | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    provider: str | None = None
    model: str | None = None
    prompt_id: UUID4 | None = None
    instructions_hash: str | None = None
    instructions_snapshot: str | None = None
