from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import unquote
from uuid import uuid4

import pytest
import pytest_asyncio
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.usage import RunUsage
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.agents.dweller_chat_agent import DwellerChatOutput, parse_action_suggestion
from app.api.v1.endpoints.chat import chat_with_dweller, voice_chat_with_dweller
from app.core.config import settings
from app.core.enums import ExplorationStatus, GenderEnum
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.schemas.chat import (
    AssignToRoomAction,
    ChatMessage,
    NoAction,
    RecallExplorationAction,
    StartExplorationAction,
    UnlockedPlace,
)
from app.schemas.dweller import DwellerCreate
from app.services.ai_service import ChatCompletionResult
from app.services.conversation_service import conversation_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.exceptions import ResourceNotFoundException, ValidationException

pytestmark = pytest.mark.asyncio(scope="module")

SPECIAL = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")
AUDIO = {"audio_file": ("test.webm", b"audio", "audio/webm")}


@pytest_asyncio.fixture(name="chat_dweller")
async def chat_dweller_fixture(async_session, vault, normal_user_token_headers):
    user = await crud.user.get_by_email(async_session, settings.EMAIL_TEST_USER)
    assert user is not None
    vault.user_id = user.id
    await async_session.flush()
    data = create_fake_dweller() | {"first_name": "John", "last_name": "Doe", "gender": GenderEnum.MALE}
    data |= {"level": 5, "happiness": 80, "max_health": 100, "health": 100, "radiation": 0}
    data |= {"stimpack": 0, "radaway": 0}
    dweller = await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))
    return await crud.dweller.get(db_session=async_session, id=dweller.id)


def _output(
    response_text="Hello! How can I help you today?", sentiment_score=2, reason_text="Friendly greeting", **overrides
):
    base = {"action_type": "no_action", "action_room_id": None, "action_room_name": None, "action_stat": None}
    base |= {"action_reason": "No action needed", **overrides}
    return DwellerChatOutput(
        **base, response_text=response_text, sentiment_score=sentiment_score, reason_text=reason_text
    )


class TestTextChat:
    @pytest.mark.parametrize(("mode", "missing"), [(m, x) for m in ("text", "voice", "history") for x in (False, True)])
    async def test_chat_rejects_inaccessible_dweller_before_work(
        self, async_client, async_session, normal_user_token_headers, vault, mode, missing
    ) -> None:
        foreign = await crud.dweller.create(
            async_session, obj_in=DwellerCreate(**create_fake_dweller(), vault_id=vault.id)
        )
        dweller_id = uuid4() if missing else foreign.id
        with (
            patch("app.services.chat_service.run_chat_agent", new=AsyncMock(side_effect=AssertionError("Unexpected"))),
            patch(
                "app.services.conversation_service.conversation_service._transcribe_audio",
                new=AsyncMock(side_effect=AssertionError("Unexpected")),
            ),
        ):
            if mode == "history":
                response = await async_client.get(f"chat/history/{dweller_id}", headers=normal_user_token_headers)
            elif mode == "voice":
                response = await async_client.post(
                    f"chat/{dweller_id}/voice", headers=normal_user_token_headers, files=AUDIO
                )
            else:
                response = await async_client.post(
                    f"chat/{dweller_id}", headers=normal_user_token_headers, json={"message": "Hi"}
                )
        assert response.status_code == (404 if missing else 403)

    @pytest.mark.parametrize("kind", ["missing", "value"])
    async def test_chat_endpoint_surfaces_domain_errors(self, kind) -> None:
        dweller_id = uuid4()
        error = (
            ResourceNotFoundException(Dweller, dweller_id) if kind == "missing" else ValueError("Invalid chat message")
        )
        with (
            patch(
                "app.api.v1.endpoints.chat.chat_service.process_text_message",
                new_callable=AsyncMock,
                side_effect=error,
            ),
            pytest.raises(type(error), match=None if kind == "missing" else "Invalid chat message") as exc_info,
        ):
            await chat_with_dweller(
                dweller_id=dweller_id,
                user=MagicMock(id=uuid4()),
                message=ChatMessage(message="Hello"),
                db_session=MagicMock(),
            )
        if kind == "missing":
            assert exc_info.value.status_code == 404

    @pytest.mark.parametrize("as_admin", [False, True])
    @patch("app.services.chat.agent_runner.dweller_chat_agent")
    async def test_chat_returns_structured_response(
        self, mock_agent, async_client, normal_user_token_headers, chat_dweller, superuser_token_headers, as_admin
    ) -> None:
        mock_output = _output("I'm not feeling great today.", -2, "Dweller expressed discomfort")
        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_result.usage = RunUsage(input_tokens=12, output_tokens=8)
        mock_agent.run = AsyncMock(return_value=mock_result)
        headers = superuser_token_headers if as_admin else normal_user_token_headers

        with patch(
            "app.services.chat.persistence.llm_interaction_crud.create", wraps=crud.llm_interaction.create
        ) as record_usage:
            response = await async_client.post(
                f"chat/{chat_dweller.id}", headers=headers, json={"message": "How are you feeling?"}
            )
        usage = record_usage.call_args.kwargs["obj_in"]
        assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (12, 8, 20)

        assert response.status_code == 200
        data = response.json()
        assert data["happiness_impact"]["delta"] == -4
        assert data["happiness_impact"]["reason_code"] == "chat_negative"
        assert data["happiness_impact"]["reason_text"] == "Dweller expressed discomfort"
        history = await async_client.get(f"chat/history/{chat_dweller.id}", headers=headers)
        assert history.status_code == 200
        assert data["dweller_message_id"] in [message["id"] for message in history.json()]

        # ?debug=true must be ignored for non-superusers, honored for admins.
        mock_result.output = _output(response_text="Hi", sentiment_score=0)
        mock_result.usage = RunUsage(input_tokens=5, output_tokens=5)
        normal = await async_client.post(
            f"chat/{chat_dweller.id}?debug=true", headers=normal_user_token_headers, json={"message": "Hello"}
        )
        admin = await async_client.post(
            f"chat/{chat_dweller.id}?debug=true", headers=superuser_token_headers, json={"message": "Hello"}
        )
        assert normal.status_code == 200
        assert normal.json()["debug"] is None
        assert admin.json()["debug"] is not None
        assert admin.json()["debug"]["total_tokens"] == 10

    @pytest.mark.parametrize(("failure", "message"), [("agent", "Hi there!"), ("credits", "Can you help me?")])
    @patch("app.services.chat.agent_runner.dweller_chat_agent")
    @patch("app.services.chat.agent_runner.get_ai_service")
    async def test_chat_failure_handling(
        self, mock_ai_service_func, mock_agent, async_client, normal_user_token_headers, chat_dweller, failure, message
    ) -> None:
        provider_error = ModelHTTPError(
            429, "gpt-4o-mini", {"code": "credit_balance_exhausted", "message": "You have no credits remaining."}
        )
        mock_agent.run = AsyncMock(side_effect=Exception("Agent failed") if failure == "agent" else provider_error)
        if failure == "agent":
            mock_ai = AsyncMock()
            mock_ai.chat_completion_with_usage.return_value = ChatCompletionResult(
                text="Fallback response", prompt_tokens=10, completion_tokens=20, total_tokens=30
            )
        else:
            mock_ai = MagicMock()
            mock_ai.chat_completion_with_usage = AsyncMock(side_effect=provider_error)
        mock_ai_service_func.return_value = mock_ai

        # The shared harness session cannot roll back from the request task; stub the
        # endpoint-side rollback (ordering is unit-tested in test_chat_service).
        with patch.object(AsyncSession, "rollback", new_callable=AsyncMock):
            response = await async_client.post(
                f"chat/{chat_dweller.id}", headers=normal_user_token_headers, json={"message": message}
            )
        if failure == "credits":
            assert response.status_code == 503
            assert response.json()["detail"] == "You have no credits remaining."
            mock_ai.chat_completion_with_usage.assert_not_awaited()
            return
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "Fallback response"
        assert data["happiness_impact"]["delta"] == 0
        assert data["happiness_impact"]["reason_code"] == "chat_neutral"
        assert data["action_suggestion"]["action_type"] == "no_action"


class TestAudioChat:
    @pytest.mark.parametrize("kind", ["empty", "missing", "provider"])
    async def test_audio_chat_preserves_error_status(self, async_client, normal_user_token_headers, kind) -> None:
        from app.utils.exceptions import AIProviderCreditsExhaustedException, DwellerNotFoundError

        if kind == "empty":
            audio_file = MagicMock()
            audio_file.read = AsyncMock(return_value=b"")
            with pytest.raises(ValidationException) as exc_info:
                await voice_chat_with_dweller(
                    dweller_id=uuid4(), user=MagicMock(id=uuid4()), db_session=MagicMock(), audio_file=audio_file
                )
            assert exc_info.value.status_code == 400
            return
        exc = AIProviderCreditsExhaustedException if kind == "provider" else DwellerNotFoundError
        error = exc() if kind == "provider" else exc("Dweller not found")
        with patch(
            "app.api.v1.endpoints.chat.conversation_service.process_audio_message", new=AsyncMock(side_effect=error)
        ):
            response = await async_client.post(f"chat/{uuid4()}/voice", headers=normal_user_token_headers, files=AUDIO)
        assert response.status_code == error.status_code
        assert response.json() == {"detail": error.detail}


class TestExplorationActions:
    @pytest_asyncio.fixture(name="exploring_dweller")
    async def exploring_dweller_fixture(self, async_session, vault):
        data = create_fake_dweller() | {"first_name": "Explorer", "last_name": "Test", "gender": GenderEnum.MALE}
        data |= {"level": 10, "happiness": 75, "max_health": 100, "health": 100, "radiation": 0}
        data |= {"stimpack": 5, "radaway": 3}
        dweller = await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))
        return await crud.dweller.get(db_session=async_session, id=dweller.id)

    async def test_parse_start_exploration_with_low_supplies(self, async_session, vault) -> None:
        data = create_fake_dweller() | {"first_name": "LowSupply", "last_name": "Test", "gender": GenderEnum.FEMALE}
        data |= {"max_health": 100, "health": 100, "radiation": 0, "stimpack": 1, "radaway": 0}
        dweller = await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))
        dweller_full = await crud.dweller.get_full_info(async_session, dweller.id)
        output = _output(
            "Let me explore!", 2, "Wants to leave", action_type="start_exploration", action_reason="Ready for adventure"
        )
        result = await parse_action_suggestion(output, async_session, dweller_full)
        assert isinstance(result, StartExplorationAction)
        # Caps: min(1, 2) = 1 stimpak, min(0, 1) = 0 radaway
        assert result.stimpaks == 1
        assert result.radaways == 0

    async def test_parse_recall_exploration_with_active_exploration(
        self, async_session, exploring_dweller, vault
    ) -> None:
        dweller_full = await crud.dweller.get_full_info(async_session, exploring_dweller.id)
        active = Exploration(
            vault_id=vault.id,
            dweller_id=exploring_dweller.id,
            status=ExplorationStatus.ACTIVE,
            duration=4,
            stimpaks=2,
            radaways=1,
            **{f"dweller_{stat}": 5 for stat in SPECIAL},
        )
        async_session.add(active)
        await async_session.commit()
        await async_session.refresh(active)

        output = _output(
            "I want to come home!",
            -1,
            "Dweller is tired",
            action_type="recall_exploration",
            action_reason="Dweller wants to return",
        )
        result = await parse_action_suggestion(output, async_session, dweller_full)
        assert isinstance(result, RecallExplorationAction)
        assert result.action_type == "recall_exploration"
        assert result.exploration_id == active.id
        assert result.reason == "Dweller wants to return"

    async def test_parse_recall_exploration_without_active_exploration(self, async_session, exploring_dweller) -> None:
        dweller_full = await crud.dweller.get_full_info(async_session, exploring_dweller.id)
        output = _output(
            "Recall me!",
            0,
            "Wants to come back",
            action_type="recall_exploration",
            action_reason="Wants to return home",
        )
        result = await parse_action_suggestion(output, async_session, dweller_full)
        # Should return NoAction since dweller is not exploring
        assert isinstance(result, NoAction)
        assert result.action_type == "no_action"
        assert result.reason == "Dweller is not currently exploring the wasteland"


class TestMessageIdCorrelation:
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
        async_client,
        normal_user_token_headers,
        chat_dweller,
        return_audio,
        superuser_token_headers,
        as_admin,
        transcription,
        reply,
        encoded_transcription,
        encoded_reply,
    ) -> None:
        from app.schemas.chat_models import AgentChatResult
        from app.schemas.happiness import HappinessImpact, HappinessReasonCode

        message_id, place_id = uuid4(), uuid4()
        impact = HappinessImpact(
            delta=2, reason_code=HappinessReasonCode.CHAT_POSITIVE, happiness_after=82, reason_text="Helpful suggestion"
        )
        generated = AgentChatResult(
            response_text=reply,
            happiness_impact=impact,
            action_suggestion=AssignToRoomAction(room_id=uuid4(), room_name="Power Plant", reason="High strength"),
            prompt_tokens=12,
            completion_tokens=8,
            total_tokens=20,
        )
        with (
            patch.object(
                conversation_service, "_transcribe_audio", new=AsyncMock(return_value=(transcription, None, None))
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
