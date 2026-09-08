"""Tests for conversation service (audio chat)."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest

from app.schemas.common import GenderEnum
from app.services.conversation_service import MessagePayload, conversation_service

# ============================================================================
# Unit Tests for Helper Methods
# ============================================================================


@pytest.mark.asyncio
class TestVoiceSelection:
    """Tests for gender-based voice selection."""

    def test_select_voice_for_male(self):
        """Test voice selection for male dwellers."""
        voice = conversation_service._select_voice_for_gender(GenderEnum.MALE)
        assert voice in ["echo", "fable", "onyx"]

    def test_select_voice_for_none_gender(self):
        """Test voice selection defaults to alloy for None gender."""
        voice = conversation_service._select_voice_for_gender(None)
        assert voice == "alloy"


class TestAudioChatProvenance:
    """Regression tests for voice-chat LLM audit records."""

    async def test_save_messages_persists_prompt_and_model_snapshot(self) -> None:
        """Voice chat must retain the same call-time provenance as text chat."""
        prompt_id = uuid4()
        payload = MessagePayload(
            transcribed_text="Status report?",
            user_audio_url=None,
            audio_duration=None,
            dweller_response_text="All clear.",
            dweller_audio_url=None,
            provider="openai",
            model="gpt-4o-mini",
            prompt_id=prompt_id,
            instructions_hash="a" * 64,
            instructions_snapshot="Respond in character.",
        )
        user = MagicMock(id=uuid4())
        dweller = MagicMock(id=uuid4(), vault=MagicMock(id=uuid4()))
        interaction = MagicMock(id=uuid4())
        message = MagicMock(id=uuid4())

        with (
            patch(
                "app.services.conversation_service.llm_interaction_crud.create",
                new=AsyncMock(return_value=interaction),
            ) as create_interaction,
            patch(
                "app.services.conversation_service.chat_message_crud.create_message",
                new=AsyncMock(return_value=message),
            ),
        ):
            await conversation_service._save_messages_to_db(MagicMock(), user, dweller, payload)

        saved_interaction = create_interaction.await_args.kwargs["obj_in"]
        assert saved_interaction.provider == "openai"
        assert saved_interaction.model == "gpt-4o-mini"
        assert saved_interaction.prompt_id == prompt_id
        assert saved_interaction.instructions_hash == "a" * 64
        assert saved_interaction.instructions_snapshot == "Respond in character."


# Note: Integration tests for audio processing are omitted as they require complex mocking
# of external services (OpenAI API, storage). The unit tests above (voice selection and
# prompt building) cover the core logic of the conversation service.


@pytest.mark.parametrize("usage_kind", ["valid", "missing", "broken"])
async def test_voice_response_survives_malformed_usage(usage_kind: str) -> None:
    from pydantic_ai.usage import RunUsage

    from app.agents.dweller_chat_agent import DwellerChatOutput

    usage = RunUsage(input_tokens=12, output_tokens=8) if usage_kind == "valid" else None
    if usage_kind == "broken":
        usage = MagicMock(spec=RunUsage)
        type(usage).input_tokens = PropertyMock(side_effect=ValueError("Invalid usage"))
    output = DwellerChatOutput(
        response_text="All clear.", sentiment_score=0, reason_text="Neutral", action_type="no_action"
    )
    with (
        patch(
            "app.services.conversation_service.dweller_chat_agent.run",
            new=AsyncMock(return_value=MagicMock(output=output, usage=usage)),
        ),
        patch("app.services.conversation_service.apply_chat_happiness", new=AsyncMock(return_value=(80, None))),
        patch("app.services.conversation_service.parse_action_suggestion", new=AsyncMock(return_value=None)),
    ):
        result = await conversation_service._generate_response_with_agent(MagicMock(), MagicMock(), "Status?", "Chat")
    assert result.text == "All clear."
    expected = (12, 8, 20) if usage_kind == "valid" else (None, None, None)
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == expected


async def test_empty_audio_is_rejected_before_loading_dweller() -> None:
    from app.utils.exceptions import ValidationException

    with (
        patch("app.services.conversation_service.get_accessible_dweller", new_callable=AsyncMock) as load,
        patch.object(
            conversation_service,
            "_transcribe_audio",
            new=AsyncMock(side_effect=AssertionError("Unexpected transcription")),
        ),
        pytest.raises(ValidationException, match="Empty audio file"),
    ):
        await conversation_service.process_audio_message(MagicMock(), MagicMock(), uuid4(), b"")
    load.assert_not_awaited()
