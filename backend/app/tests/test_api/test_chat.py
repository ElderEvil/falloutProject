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
from app.agents.dweller_chat_agent import DwellerChatOutput, parse_action_suggestion
from app.models.dweller import Dweller
from app.models.exploration import Exploration, ExplorationStatus
from app.models.vault import Vault
from app.schemas.chat import AssignToRoomAction, NoAction, RecallExplorationAction, StartExplorationAction
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

    @patch("app.services.chat_service.dweller_chat_agent")
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

    @patch("app.services.chat_service.dweller_chat_agent")
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

    @patch("app.services.chat_service.dweller_chat_agent")
    @patch("app.services.chat_service.get_ai_service")
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

    @patch("app.services.chat_service.dweller_chat_agent")
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


# ============================================================================
# Exploration Action Tests
# ============================================================================


@pytest.mark.asyncio
class TestExplorationActions:
    """Tests for exploration action suggestions (start_exploration, recall_exploration)."""

    @pytest_asyncio.fixture(name="exploring_dweller")
    async def exploring_dweller_fixture(self, async_session: AsyncSession, vault: Vault) -> Dweller:
        """Create a test dweller with supplies for exploration."""
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Explorer",
                "last_name": "Test",
                "gender": GenderEnum.MALE,
                "is_adult": True,
                "level": 10,
                "happiness": 75,
                "stimpack": 5,
                "radaway": 3,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
        return await crud.dweller.get(db_session=async_session, id=dweller.id)

    async def test_parse_start_exploration_action(
        self,
        async_session: AsyncSession,
        exploring_dweller: Dweller,
    ):
        """Test parse_action_suggestion for start_exploration with deterministic enrichment."""
        dweller_full = await crud.dweller.get_full_info(async_session, exploring_dweller.id)

        output = DwellerChatOutput(
            response_text="I want to explore the wasteland!",
            sentiment_score=3,
            reason_text="Excited about adventure",
            action_type="start_exploration",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="Dweller wants adventure",
        )

        result = await parse_action_suggestion(output, async_session, dweller_full)

        assert isinstance(result, StartExplorationAction)
        assert result.action_type == "start_exploration"
        assert result.duration_hours == 4
        # Caps: min(5, 2) = 2 stimpaks, min(3, 1) = 1 radaway
        assert result.stimpaks == 2
        assert result.radaways == 1
        assert result.reason == "Dweller wants adventure"

    async def test_parse_start_exploration_with_low_supplies(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test start_exploration enrichment with dweller having low supplies."""
        # Create dweller with minimal supplies
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "LowSupply",
                "last_name": "Test",
                "gender": GenderEnum.FEMALE,
                "is_adult": True,
                "stimpack": 1,
                "radaway": 0,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
        dweller_full = await crud.dweller.get_full_info(async_session, dweller.id)

        output = DwellerChatOutput(
            response_text="Let me explore!",
            sentiment_score=2,
            reason_text="Wants to leave",
            action_type="start_exploration",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="Ready for adventure",
        )

        result = await parse_action_suggestion(output, async_session, dweller_full)

        assert isinstance(result, StartExplorationAction)
        # Caps: min(1, 2) = 1 stimpak, min(0, 1) = 0 radaway
        assert result.stimpaks == 1
        assert result.radaways == 0

    async def test_parse_recall_exploration_with_active_exploration(
        self,
        async_session: AsyncSession,
        exploring_dweller: Dweller,
        vault: Vault,
    ):
        """Test parse_action_suggestion for recall_exploration with active exploration."""
        dweller_full = await crud.dweller.get_full_info(async_session, exploring_dweller.id)

        # Create an active exploration for the dweller
        active_exploration = Exploration(
            vault_id=vault.id,
            dweller_id=exploring_dweller.id,
            status=ExplorationStatus.ACTIVE,
            duration=4,
            stimpaks=2,
            radaways=1,
            dweller_strength=5,
            dweller_perception=5,
            dweller_endurance=5,
            dweller_charisma=5,
            dweller_intelligence=5,
            dweller_agility=5,
            dweller_luck=5,
        )
        async_session.add(active_exploration)
        await async_session.commit()
        await async_session.refresh(active_exploration)

        output = DwellerChatOutput(
            response_text="I want to come home!",
            sentiment_score=-1,
            reason_text="Dweller is tired",
            action_type="recall_exploration",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="Dweller wants to return",
        )

        result = await parse_action_suggestion(output, async_session, dweller_full)

        assert isinstance(result, RecallExplorationAction)
        assert result.action_type == "recall_exploration"
        assert result.exploration_id == active_exploration.id
        assert result.reason == "Dweller wants to return"

    async def test_parse_recall_exploration_without_active_exploration(
        self,
        async_session: AsyncSession,
        exploring_dweller: Dweller,
    ):
        """Test parse_action_suggestion for recall_exploration returns NoAction when no active exploration."""
        dweller_full = await crud.dweller.get_full_info(async_session, exploring_dweller.id)

        output = DwellerChatOutput(
            response_text="Recall me!",
            sentiment_score=0,
            reason_text="Wants to come back",
            action_type="recall_exploration",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="Wants to return home",
        )

        result = await parse_action_suggestion(output, async_session, dweller_full)

        # Should return NoAction since dweller is not exploring
        assert isinstance(result, NoAction)
        assert result.action_type == "no_action"
        assert result.reason == "Dweller is not currently exploring the wasteland"

    @patch("app.services.chat_service.dweller_chat_agent")
    @patch("app.api.v1.endpoints.chat.manager")
    async def test_start_exploration_action_api_response(
        self,
        mock_manager: MagicMock,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        exploring_dweller: Dweller,
    ):
        """Test that start_exploration action is correctly returned in API response."""
        mock_output = DwellerChatOutput(
            response_text="Time for an adventure!",
            sentiment_score=3,
            reason_text="Excited dweller",
            action_type="start_exploration",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="Dweller eager to explore",
        )
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_manager.send_chat_message = AsyncMock()

        response = await async_client.post(
            f"chat/{exploring_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "I want to go explore the wasteland!"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "action_suggestion" in data
        assert data["action_suggestion"]["action_type"] == "start_exploration"
        assert data["action_suggestion"]["duration_hours"] == 4
        assert data["action_suggestion"]["stimpaks"] == 2  # min(5, 2)
        assert data["action_suggestion"]["radaways"] == 1  # min(3, 1)

    # ============================================================================
    # Action Suggestion Policy Tests
    # ============================================================================

    @patch("app.services.chat_service.dweller_chat_agent")
    async def test_neutral_message_does_not_suggest_training(
        self,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that neutral messages do not suggest training actions even if agent suggests it."""
        # Mock agent output with neutral sentiment but agent tries to suggest training
        # (This should be filtered out by the policy)
        mock_output = DwellerChatOutput(
            response_text="Hello! How can I help you today?",
            sentiment_score=0,
            reason_text="Neutral greeting",
            action_type="start_training",
            action_room_id=None,
            action_room_name=None,
            action_stat="strength",
            action_reason="Neutral message should not suggest training",
        )
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

        # Verify action suggestion is not training (policy enforces this)
        assert "action_suggestion" in data
        assert data["action_suggestion"]["action_type"] != "start_training", (
            "Neutral messages should not suggest training"
        )

    @patch("app.services.chat_service.dweller_chat_agent")
    async def test_explicit_training_request_suggests_training(
        self,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that explicit training requests suggest start_training action."""
        # Mock agent output with user explicitly asking about training
        mock_output = DwellerChatOutput(
            response_text="You should train your strength! It's currently low.",
            sentiment_score=1,
            reason_text="User asked about training",
            action_type="start_training",
            action_room_id=None,
            action_room_name=None,
            action_stat="strength",
            action_reason="Strength is low and needs improvement",
        )
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Should I train my strength?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify action suggestion is training
        assert "action_suggestion" in data
        assert data["action_suggestion"]["action_type"] == "start_training", (
            "Explicit training requests should suggest training"
        )

    @patch("app.services.chat_service.dweller_chat_agent")
    async def test_assign_to_room_can_target_any_room(
        self,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that assign_to_room suggestions can target any room type."""
        # Mock agent output suggesting assignment to a non-production room
        room_id = uuid4()
        mock_output = DwellerChatOutput(
            response_text="You should work in the Science Lab!",
            sentiment_score=2,
            reason_text="Good intelligence stat",
            action_type="assign_to_room",
            action_room_id=room_id,
            action_room_name="Science Lab",
            action_stat=None,
            action_reason="Intelligence makes this ideal",
        )
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Where should I work?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify action suggestion is assignment to any room
        assert "action_suggestion" in data
        assert data["action_suggestion"]["action_type"] == "assign_to_room", (
            "Assignment suggestions should be allowed for any room"
        )
        assert data["action_suggestion"]["room_id"] == str(room_id)
        assert data["action_suggestion"]["room_name"] == "Science Lab"


# ============================================================================
# Message ID Tests (for WS action_suggestion correlation)
# ============================================================================


@pytest.mark.asyncio
class TestMessageIdCorrelation:
    """Tests for dweller_message_id in HTTP responses and message_id in WS payloads.

    These tests verify that:
    1. HTTP responses include dweller_message_id (UUID) for correlation
    2. WS action_suggestion payloads include message_id matching the HTTP response
    """

    @patch("app.services.chat_service.dweller_chat_agent")
    @patch("app.api.v1.endpoints.chat.manager")
    async def test_text_chat_response_includes_dweller_message_id(
        self,
        mock_manager: MagicMock,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that POST /chat/{dweller_id} response includes dweller_message_id (UUID)."""
        mock_output = create_mock_agent_output()
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_manager.send_chat_message = AsyncMock()

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Hello!"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify dweller_message_id is present and is a valid UUID
        assert "dweller_message_id" in data, "Response should include dweller_message_id"
        dweller_message_id = data["dweller_message_id"]
        assert dweller_message_id is not None, "dweller_message_id should not be None"

        # Verify it's a valid UUID string
        import uuid

        try:
            uuid.UUID(dweller_message_id)
        except ValueError:
            pytest.fail(f"dweller_message_id '{dweller_message_id}' is not a valid UUID")

    @patch("app.services.chat_service.dweller_chat_agent")
    @patch("app.api.v1.endpoints.chat.manager")
    async def test_ws_action_suggestion_includes_message_id(
        self,
        mock_manager: MagicMock,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that WS action_suggestion payload includes message_id matching dweller_message_id."""
        room_id = uuid4()

        # Create agent output with an actionable suggestion
        mock_output = DwellerChatOutput(
            response_text="You should work in the power plant!",
            sentiment_score=2,
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

        # Capture WS messages
        captured_messages = []

        async def capture_message(message, **_kwargs):
            captured_messages.append(message)

        mock_manager.send_chat_message = AsyncMock(side_effect=capture_message)

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "What should I do?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Get the dweller_message_id from HTTP response
        assert "dweller_message_id" in data, "Response should include dweller_message_id"
        dweller_message_id = data["dweller_message_id"]

        # Find the action_suggestion WS message
        action_msg = next(
            (msg for msg in captured_messages if msg.get("type") == "action_suggestion"),
            None,
        )
        assert action_msg is not None, "WS action_suggestion message should be sent"

        # Verify message_id in WS payload matches dweller_message_id
        assert "message_id" in action_msg, "WS action_suggestion should include message_id"
        assert action_msg["message_id"] == dweller_message_id, (
            f"WS message_id '{action_msg['message_id']}' should match HTTP dweller_message_id '{dweller_message_id}'"
        )

    @patch("app.services.chat_service.dweller_chat_agent")
    @patch("app.api.v1.endpoints.chat.manager")
    async def test_ws_message_id_is_valid_uuid(
        self,
        mock_manager: MagicMock,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that WS action_suggestion message_id is a valid UUID string."""
        room_id = uuid4()

        mock_output = DwellerChatOutput(
            response_text="Let me help you!",
            sentiment_score=1,
            reason_text="Helpful dweller",
            action_type="assign_to_room",
            action_room_id=room_id,
            action_room_name="Science Lab",
            action_stat=None,
            action_reason="Good intelligence stat",
        )
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_agent.run = AsyncMock(return_value=mock_result)

        captured_messages = []

        async def capture_message(message, **_kwargs):
            captured_messages.append(message)

        mock_manager.send_chat_message = AsyncMock(side_effect=capture_message)

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Where should I work?"},
        )

        assert response.status_code == 200

        action_msg = next(
            (msg for msg in captured_messages if msg.get("type") == "action_suggestion"),
            None,
        )
        assert action_msg is not None

        # Verify message_id is a valid UUID
        import uuid

        message_id = action_msg.get("message_id")
        assert message_id is not None, "message_id should not be None"

        try:
            uuid.UUID(message_id)
        except ValueError:
            pytest.fail(f"message_id '{message_id}' is not a valid UUID")

    @patch("app.api.v1.endpoints.chat.conversation_service")
    @patch("app.api.v1.endpoints.chat.manager")
    async def test_voice_chat_response_includes_dweller_message_id(
        self,
        mock_manager: MagicMock,
        mock_conversation_service: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that POST /chat/{dweller_id}/voice response includes dweller_message_id (UUID)."""
        import io

        from app.schemas.happiness import HappinessImpact, HappinessReasonCode

        # Mock conversation_service.process_audio_message result
        mock_message_id = uuid4()
        mock_conversation_service.process_audio_message = AsyncMock(
            return_value={
                "transcription": "Hello there!",
                "user_audio_url": "https://example.com/user.webm",
                "dweller_response": "Hi! How can I help?",
                "dweller_audio_url": "https://example.com/dweller.mp3",
                "dweller_audio_bytes": b"fake audio bytes",
                "dweller_message_id": mock_message_id,
                "happiness_impact": HappinessImpact(
                    delta=4,
                    reason_code=HappinessReasonCode.CHAT_POSITIVE,
                    reason_text="Friendly greeting",
                    happiness_after=84,
                ),
                "action_suggestion": NoAction(reason="No action needed"),
            }
        )
        mock_manager.send_chat_message = AsyncMock()

        # Create fake audio file
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.webm", io.BytesIO(audio_data), "audio/webm")}

        response = await async_client.post(
            f"chat/{chat_dweller.id}/voice",
            headers=normal_user_token_headers,
            files=files,
            params={"return_audio": False},  # Request JSON response
        )

        assert response.status_code == 200
        data = response.json()

        # Verify dweller_message_id is present and is a valid UUID
        assert "dweller_message_id" in data, "Voice chat response should include dweller_message_id"
        dweller_message_id = data["dweller_message_id"]
        assert dweller_message_id is not None, "dweller_message_id should not be None"

        # Verify it's a valid UUID string
        import uuid

        try:
            uuid.UUID(dweller_message_id)
        except ValueError:
            pytest.fail(f"dweller_message_id '{dweller_message_id}' is not a valid UUID")

    @patch("app.api.v1.endpoints.chat.conversation_service")
    @patch("app.api.v1.endpoints.chat.manager")
    async def test_voice_chat_ws_action_suggestion_includes_message_id(
        self,
        mock_manager: MagicMock,
        mock_conversation_service: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that voice chat WS action_suggestion includes message_id matching dweller_message_id."""
        import io

        from app.schemas.happiness import HappinessImpact, HappinessReasonCode

        room_id = uuid4()
        mock_message_id = uuid4()

        # Mock conversation_service with an actionable suggestion
        mock_conversation_service.process_audio_message = AsyncMock(
            return_value={
                "transcription": "Where should I work?",
                "user_audio_url": "https://example.com/user.webm",
                "dweller_response": "You should work in the power plant!",
                "dweller_audio_url": "https://example.com/dweller.mp3",
                "dweller_audio_bytes": b"fake audio bytes",
                "dweller_message_id": mock_message_id,
                "happiness_impact": HappinessImpact(
                    delta=2,
                    reason_code=HappinessReasonCode.CHAT_POSITIVE,
                    reason_text="Helpful suggestion",
                    happiness_after=82,
                ),
                "action_suggestion": AssignToRoomAction(
                    room_id=room_id,
                    room_name="Power Plant",
                    reason="High strength stat",
                ),
            }
        )

        # Capture WS messages
        captured_messages = []

        async def capture_message(message, **_kwargs):
            captured_messages.append(message)

        mock_manager.send_chat_message = AsyncMock(side_effect=capture_message)

        # Create fake audio file
        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.webm", io.BytesIO(audio_data), "audio/webm")}

        response = await async_client.post(
            f"chat/{chat_dweller.id}/voice",
            headers=normal_user_token_headers,
            files=files,
            params={"return_audio": False},  # Request JSON response
        )

        assert response.status_code == 200
        data = response.json()

        # Get the dweller_message_id from HTTP response
        assert "dweller_message_id" in data, "Voice chat response should include dweller_message_id"
        dweller_message_id = data["dweller_message_id"]

        # Find the action_suggestion WS message
        action_msg = next(
            (msg for msg in captured_messages if msg.get("type") == "action_suggestion"),
            None,
        )
        assert action_msg is not None, "WS action_suggestion message should be sent for voice chat"

        # Verify message_id in WS payload matches dweller_message_id
        assert "message_id" in action_msg, "WS action_suggestion should include message_id"
        assert action_msg["message_id"] == dweller_message_id, (
            f"WS message_id '{action_msg['message_id']}' should match HTTP dweller_message_id '{dweller_message_id}'"
        )
