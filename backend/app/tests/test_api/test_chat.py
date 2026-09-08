"""Tests for chat API endpoints (text and audio chat).

Note: These are simplified tests focusing on API contract validation and basic functionality.
Integration tests with external services (OpenAI API, storage) are omitted due to complexity.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import unquote
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.usage import RunUsage
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.agents.dweller_chat_agent import DwellerChatOutput, parse_action_suggestion
from app.api.v1.endpoints.chat import chat_with_dweller, voice_chat_with_dweller
from app.core.config import settings
from app.models.dweller import Dweller
from app.models.exploration import Exploration, ExplorationStatus
from app.models.room import RoomTypeEnum
from app.models.vault import Vault
from app.schemas.chat import (
    AssignToRoomAction,
    ChatMessage,
    NoAction,
    RecallExplorationAction,
    StartExplorationAction,
    UnlockedPlace,
)
from app.schemas.common import GenderEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.ai_service import ChatCompletionResult
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.exceptions import ResourceNotFoundException, ValidationException

pytestmark = pytest.mark.asyncio(scope="module")


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture(name="chat_dweller")
async def chat_dweller_fixture(
    async_session: AsyncSession,
    vault: Vault,
    normal_user_token_headers: dict[str, str],
) -> Dweller:
    """Create a dweller owned by the authenticated normal user."""
    user = await crud.user.get_by_email(async_session, settings.EMAIL_TEST_USER)
    assert user is not None
    vault.user_id = user.id
    await async_session.flush()
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "John",
            "last_name": "Doe",
            "gender": GenderEnum.MALE,
            "is_adult": True,
            "level": 5,
            "happiness": 80,
            "max_health": 100,
            "health": 100,
            "radiation": 0,
            "stimpack": 0,
            "radaway": 0,
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

    @pytest.mark.parametrize("mode", ["text", "voice", "history"])
    @pytest.mark.parametrize("missing", [False, True])
    async def test_chat_rejects_inaccessible_dweller_before_work(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        normal_user_token_headers: dict[str, str],
        vault: Vault,
        mode: str,
        missing: bool,
    ) -> None:
        foreign_dweller = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(**create_fake_dweller(), vault_id=vault.id),
        )
        dweller_id = uuid4() if missing else foreign_dweller.id
        with (
            patch(
                "app.services.chat_service.run_chat_agent",
                new=AsyncMock(side_effect=AssertionError("Unexpected generation")),
            ),
            patch(
                "app.services.conversation_service.conversation_service._transcribe_audio",
                new=AsyncMock(side_effect=AssertionError("Unexpected transcription")),
            ),
        ):
            if mode == "history":
                response = await async_client.get(f"chat/history/{dweller_id}", headers=normal_user_token_headers)
            else:
                path = f"chat/{dweller_id}" + ("/voice" if mode == "voice" else "")
                if mode == "voice":
                    response = await async_client.post(
                        path,
                        headers=normal_user_token_headers,
                        files={"audio_file": ("test.webm", b"audio", "audio/webm")},
                    )
                else:
                    response = await async_client.post(path, headers=normal_user_token_headers, json={"message": "Hi"})
        assert response.status_code == (404 if missing else 403)

    async def test_missing_dweller_exception_propagates_to_api_boundary(self) -> None:
        """The shared API handler receives the original not-found domain error."""
        dweller_id = uuid4()
        user = MagicMock(id=uuid4())

        with (
            patch(
                "app.api.v1.endpoints.chat.chat_service.process_text_message",
                new_callable=AsyncMock,
                side_effect=ResourceNotFoundException(Dweller, dweller_id),
            ),
            pytest.raises(ResourceNotFoundException) as exc_info,
        ):
            await chat_with_dweller(
                dweller_id=dweller_id,
                user=user,
                message=ChatMessage(message="Hello"),
                db_session=MagicMock(),
            )

        assert exc_info.value.status_code == 404

    async def test_text_chat_value_error_is_not_mapped_to_404(self) -> None:
        """Unexpected validation failures keep their original error semantics."""
        with (
            patch(
                "app.api.v1.endpoints.chat.chat_service.process_text_message",
                new_callable=AsyncMock,
                side_effect=ValueError("Invalid chat message"),
            ),
            pytest.raises(ValueError, match="Invalid chat message"),
        ):
            await chat_with_dweller(
                dweller_id=uuid4(),
                user=MagicMock(id=uuid4()),
                message=ChatMessage(message="Hello"),
                db_session=MagicMock(),
            )

    @pytest.mark.parametrize("as_admin", [False, True])
    @patch("app.services.chat.agent_runner.dweller_chat_agent")
    async def test_chat_returns_structured_response(
        self,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
        superuser_token_headers: dict[str, str],
        as_admin: bool,
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
        mock_result.usage = RunUsage(input_tokens=12, output_tokens=8)
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.chat.persistence.llm_interaction_crud.create",
            wraps=crud.llm_interaction.create,
        ) as record_usage:
            response = await async_client.post(
                f"chat/{chat_dweller.id}",
                headers=superuser_token_headers if as_admin else normal_user_token_headers,
                json={"message": "How are you feeling?"},
            )
        usage = record_usage.call_args.kwargs["obj_in"]
        assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (12, 8, 20)

        assert response.status_code == 200
        data = response.json()

        # Verify negative sentiment handling
        assert data["happiness_impact"]["delta"] == -4  # -2 * 2
        assert data["happiness_impact"]["reason_code"] == "chat_negative"
        assert data["happiness_impact"]["reason_text"] == "Dweller expressed discomfort"
        history = await async_client.get(
            f"chat/history/{chat_dweller.id}",
            headers=superuser_token_headers if as_admin else normal_user_token_headers,
        )
        assert history.status_code == 200
        assert data["dweller_message_id"] in [message["id"] for message in history.json()]

    @patch("app.services.chat.agent_runner.dweller_chat_agent")
    @patch("app.services.chat.agent_runner.get_ai_service")
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
        mock_ai.chat_completion_with_usage.return_value = ChatCompletionResult(
            text="Fallback response",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        mock_ai_service_func.return_value = mock_ai

        # The shared harness session (join_transaction_mode="create_savepoint", one
        # connection across tasks) cannot roll back from the request task, so stub
        # the endpoint-side rollback; ordering is unit-tested in test_chat_service.
        with patch.object(AsyncSession, "rollback", new_callable=AsyncMock):
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

    @patch("app.services.chat.agent_runner.dweller_chat_agent")
    @patch("app.services.chat.agent_runner.get_ai_service")
    async def test_chat_reports_exhausted_provider_credits(
        self,
        mock_ai_service_func: MagicMock,
        mock_agent: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ) -> None:
        """Return an actionable response when OpenAI reports exhausted credits."""
        provider_error = ModelHTTPError(
            status_code=429,
            model_name="gpt-4o-mini",
            body={"code": "credit_balance_exhausted", "message": "You have no credits remaining."},
        )
        mock_agent.run = AsyncMock(side_effect=provider_error)
        mock_ai = MagicMock()
        mock_ai.chat_completion_with_usage = AsyncMock(side_effect=provider_error)
        mock_ai_service_func.return_value = mock_ai

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Can you help me?"},
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "You have no credits remaining."
        mock_ai.chat_completion_with_usage.assert_not_awaited()


# ============================================================================
# Audio Chat Tests
# ============================================================================


@pytest.mark.asyncio
class TestAudioChat:
    """Tests for audio-based chat endpoint."""

    async def test_audio_chat_empty_file_returns_validation_error(self) -> None:
        """Empty audio is a client validation error, not an internal server error."""
        audio_file = MagicMock()
        audio_file.read = AsyncMock(return_value=b"")

        with pytest.raises(ValidationException) as exc_info:
            await voice_chat_with_dweller(
                dweller_id=uuid4(),
                user=MagicMock(id=uuid4()),
                db_session=MagicMock(),
                audio_file=audio_file,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.parametrize("failure_kind", ["missing", "provider"])
    async def test_voice_chat_preserves_domain_error_status(
        self,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        failure_kind: str,
    ) -> None:
        from app.utils.exceptions import AIProviderCreditsExhaustedException, DwellerNotFoundError

        error = (
            DwellerNotFoundError("Dweller not found")
            if failure_kind == "missing"
            else AIProviderCreditsExhaustedException()
        )
        with patch(
            "app.api.v1.endpoints.chat.conversation_service.process_audio_message", new=AsyncMock(side_effect=error)
        ):
            response = await async_client.post(
                f"chat/{uuid4()}/voice",
                headers=normal_user_token_headers,
                files={"audio_file": ("test.webm", b"audio", "audio/webm")},
            )
        assert response.status_code == error.status_code
        assert response.json() == {"detail": error.detail}


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
                "max_health": 100,
                "health": 100,
                "radiation": 0,
                "stimpack": 5,
                "radaway": 3,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
        return await crud.dweller.get(db_session=async_session, id=dweller.id)

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
                "max_health": 100,
                "health": 100,
                "radiation": 0,
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

    # ============================================================================
    # Action Suggestion Policy Tests
    # ============================================================================


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

    @pytest.mark.parametrize(
        ("transcription", "reply", "encoded_transcription", "encoded_reply"),
        [
            (
                "Where should I work?",
                "You should work in the power plant!",
                "Where%20should%20I%20work%3F",
                "You%20should%20work%20in%20the%20power%20plant%21",
            ),
            (
                "Де / 100% +?",
                "你好 👋\r\n",
                "%D0%94%D0%B5%20%2F%20100%25%20%2B%3F",
                "%E4%BD%A0%E5%A5%BD%20%F0%9F%91%8B%0D%0A",
            ),
        ],
    )
    @pytest.mark.parametrize("return_audio", [False, True])
    @pytest.mark.parametrize("as_admin", [False, True])
    async def test_voice_chat_ws_action_suggestion_includes_message_id(
        self,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
        return_audio: bool,
        superuser_token_headers: dict[str, str],
        as_admin: bool,
        transcription: str,
        reply: str,
        encoded_transcription: str,
        encoded_reply: str,
    ) -> None:
        """Both response modes retain message correlation and progression metadata."""
        from app.schemas.happiness import HappinessImpact, HappinessReasonCode
        from app.services.chat.models import AgentChatResult
        from app.services.conversation_service import conversation_service

        message_id, place_id = uuid4(), uuid4()
        generated = AgentChatResult(
            response_text=reply,
            happiness_impact=HappinessImpact(
                delta=2,
                reason_code=HappinessReasonCode.CHAT_POSITIVE,
                reason_text="Helpful suggestion",
                happiness_after=82,
            ),
            action_suggestion=AssignToRoomAction(room_id=uuid4(), room_name="Power Plant", reason="High strength"),
            prompt_tokens=12,
            completion_tokens=8,
            total_tokens=20,
        )
        with (
            patch.object(
                conversation_service,
                "_transcribe_audio",
                new=AsyncMock(return_value=(transcription, None, None)),
            ),
            patch.object(conversation_service, "_generate_response_with_agent", new=AsyncMock(return_value=generated)),
            patch.object(
                conversation_service, "_generate_tts_audio", new=AsyncMock(return_value=(b"fake audio bytes", None))
            ),
            patch.object(conversation_service, "_save_messages_to_db", new=AsyncMock(return_value=message_id)),
            patch(
                "app.services.chat.notifications.maybe_unlock_places",
                new=AsyncMock(return_value=[UnlockedPlace(location_id=place_id, name="Megaton")]),
            ),
            patch("app.services.chat.notifications.manager.send_chat_message", new_callable=AsyncMock) as notify,
        ):
            response = await async_client.post(
                f"chat/{chat_dweller.id}/voice",
                headers=superuser_token_headers if as_admin else normal_user_token_headers,
                files={"audio_file": ("test.webm", b"audio", "audio/webm")},
                params={"return_audio": return_audio},
            )
        assert response.status_code == 200
        if return_audio:
            assert response.content == b"fake audio bytes"
            assert response.headers["content-type"] == "audio/mpeg"
            assert response.headers["x-message-id"] == str(message_id)
            assert response.headers["x-transcription"] == encoded_transcription
            assert unquote(response.headers["x-transcription"]) == transcription
            assert response.headers["x-response-text"] == encoded_reply
            assert unquote(response.headers["x-response-text"]) == reply
        else:
            data = response.json()
            assert data["transcription"] == transcription
            assert data["dweller_message_id"] == str(message_id)
            assert data["dweller_response"] == generated.response_text
            assert "dweller_audio_bytes" not in data
            assert data["unlocked_places"] == [{"location_id": str(place_id), "name": "Megaton"}]
        assert [call.args[0]["type"] for call in notify.await_args_list] == ["happiness_update", "action_suggestion"]
        assert all(call.args[0]["message_id"] == str(message_id) for call in notify.await_args_list)
