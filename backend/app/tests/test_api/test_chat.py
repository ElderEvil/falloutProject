"""Tests for chat API endpoints (text and audio chat).

Note: These are simplified tests focusing on API contract validation and basic functionality.
Integration tests with external services (OpenAI API, MinIO) are omitted due to complexity.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from pydantic_ai.agent import AgentRunResult
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.agents.dweller_chat_agent import DwellerChatOutput
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import GenderEnum
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller

pytestmark = pytest.mark.asyncio(scope="module")


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture(name="chat_dweller")
async def chat_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a test dweller for chat."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "John",
            "last_name": "Doe",
            "gender": GenderEnum.MALE,
            "is_adult": True,
            "level": 5,
            "happiness": 80,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    # Load full relationships
    return await crud.dweller.get(db_session=async_session, id=dweller.id)


# ============================================================================
# Text Chat Tests
# ============================================================================


def create_mock_agent_output(
    response_text: str = "Hello! How can I help you today?",
    sentiment_score: int = 2,
    reason_text: str = "Friendly greeting",
) -> DwellerChatOutput:
    """Create a mock DwellerChatOutput for testing."""
    return DwellerChatOutput(
        response_text=response_text,
        sentiment_score=sentiment_score,
        reason_text=reason_text,
        action_type="no_action",
        action_room_id=None,
        action_room_name=None,
        action_stat=None,
        action_reason="No action needed",
    )


@pytest.mark.asyncio
class TestTextChat:
    """Tests for text-based chat endpoint."""

    @patch("app.api.v1.endpoints.chat.dweller_chat_agent")
    async def test_send_text_message_success(
        self,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test sending a text message to a dweller."""
        # Mock agent output
        mock_output = create_mock_agent_output()
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Hi there!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] == "Hello! How can I help you today?"

        # Verify happiness impact is populated
        assert "happiness_impact" in data
        assert data["happiness_impact"] is not None
        assert data["happiness_impact"]["delta"] == 4  # 2 * 2 (sentiment_score * 2)
        assert data["happiness_impact"]["reason_code"] == "chat_positive"

        # Verify action suggestion is populated
        assert "action_suggestion" in data
        assert data["action_suggestion"] is not None
        assert data["action_suggestion"]["action_type"] == "no_action"

    async def test_text_chat_requires_authentication(
        self,
        async_client: AsyncClient,
        chat_dweller: Dweller,
    ):
        """Test that text chat requires authentication."""
        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            json={"message": "Hello"},
        )

        assert response.status_code == 401

    @patch("app.api.v1.endpoints.chat.dweller_chat_agent")
    async def test_chat_returns_structured_response(
        self,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that chat returns properly structured response with happiness and suggestions."""
        # Mock agent with negative sentiment
        mock_output = create_mock_agent_output(
            response_text="I'm not feeling great today.",
            sentiment_score=-2,
            reason_text="Dweller expressed discomfort",
        )
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "How are you feeling?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify negative sentiment handling
        assert data["happiness_impact"]["delta"] == -4  # -2 * 2
        assert data["happiness_impact"]["reason_code"] == "chat_negative"
        assert data["happiness_impact"]["reason_text"] == "Dweller expressed discomfort"

    @patch("app.api.v1.endpoints.chat.dweller_chat_agent")
    @patch("app.api.v1.endpoints.chat.get_ai_service")
    async def test_chat_fallback_on_agent_failure(
        self,
        mock_ai_service_func: MagicMock,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that chat falls back to basic AI service when agent fails."""
        # Mock agent to raise an exception
        mock_agent.run = AsyncMock(side_effect=Exception("Agent failed"))

        # Mock fallback AI service
        mock_ai = AsyncMock()
        mock_ai.chat_completion.return_value = "Fallback response"
        mock_ai_service_func.return_value = mock_ai

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Hi there!"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify fallback response
        assert data["response"] == "Fallback response"

        # Verify neutral happiness impact on fallback
        assert data["happiness_impact"]["delta"] == 0
        assert data["happiness_impact"]["reason_code"] == "chat_neutral"

        # Verify no_action suggestion on fallback
        assert data["action_suggestion"]["action_type"] == "no_action"

    @patch("app.api.v1.endpoints.chat.dweller_chat_agent")
    @patch("app.api.v1.endpoints.chat.manager")
    async def test_chat_action_suggestion_websocket_serialization(
        self,
        mock_manager: MagicMock,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that action suggestions with UUIDs serialize correctly for WebSocket.

        Regression test for Bug #4: UUID JSON serialization error.
        Verifies that room_id (UUID) is converted to string in WebSocket message.
        """
        room_id = uuid4()

        mock_output = DwellerChatOutput(
            response_text="You should work in the power plant!",
            sentiment_score=1,
            reason_text="Dweller has high strength",
            action_type="assign_to_room",
            action_room_id=room_id,
            action_room_name="Power Plant",
            action_stat=None,
            action_reason="High strength stat makes this ideal",
        )
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)

        captured_messages = []

        async def capture_message(message, **_kwargs):
            json.dumps(message)
            captured_messages.append(message)

        mock_manager.send_chat_message = AsyncMock(side_effect=capture_message)

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "What should I do?"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "action_suggestion" in data
        assert data["action_suggestion"]["action_type"] == "assign_to_room"
        assert data["action_suggestion"]["room_id"] == str(room_id)
        assert data["action_suggestion"]["room_name"] == "Power Plant"

        assert len(captured_messages) > 0

        action_msg = next(
            (msg for msg in captured_messages if msg.get("type") == "action_suggestion"),
            None,
        )
        assert action_msg is not None

        action_suggestion = action_msg["action_suggestion"]
        assert isinstance(action_suggestion["room_id"], str)
        assert action_suggestion["room_id"] == str(room_id)
        assert action_suggestion["room_name"] == "Power Plant"
        assert action_suggestion["action_type"] == "assign_to_room"


# ============================================================================
# Audio Chat Tests
# ============================================================================


@pytest.mark.asyncio
class TestAudioChat:
    """Tests for audio-based chat endpoint."""

    async def test_audio_chat_requires_authentication(
        self,
        async_client: AsyncClient,
        chat_dweller: Dweller,
    ):
        """Test that audio chat requires authentication."""
        import io

        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.webm", io.BytesIO(audio_data), "audio/webm")}

        response = await async_client.post(
            f"chat/{chat_dweller.id}/voice",
            files=files,
        )

        assert response.status_code == 401

    async def test_audio_chat_missing_file(
        self,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test audio chat without file returns validation error."""
        response = await async_client.post(
            f"chat/{chat_dweller.id}/voice",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 422  # Validation error

    async def test_audio_chat_nonexistent_dweller(
        self,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
    ):
        """Test sending audio to non-existent dweller returns 404."""
        import io
        from uuid import uuid4

        fake_dweller_id = uuid4()
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.webm", io.BytesIO(audio_data), "audio/webm")}

        response = await async_client.post(
            f"chat/{fake_dweller_id}/voice",
            headers=normal_user_token_headers,
            files=files,
        )

        assert response.status_code == 404
