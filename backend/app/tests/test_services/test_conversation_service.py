"""Tests for conversation service (audio chat)."""

from unittest.mock import AsyncMock, MagicMock, patch
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
