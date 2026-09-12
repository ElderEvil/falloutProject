"""Tests for chat service error handling, especially AI provider failures."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from pydantic_ai.usage import RunUsage
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.chat_message import chat_message as chat_message_crud
from app.models.dweller import Dweller
from app.models.user import User
from app.models.vault import Vault
from app.schemas.chat import ChatStreamDone, ChatStreamError, ChatStreamToken, NoAction, UnlockedPlace
from app.schemas.common import GenderEnum
from app.schemas.dweller import DwellerCreate, DwellerReadFull
from app.services.chat.agent_runner import extract_usage, run_chat_agent
from app.services.chat.models import AgentChatResult, StreamBundle
from app.services.chat.notifications import maybe_unlock_places
from app.services.chat_service import chat_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.exceptions import ResourceNotFoundException

pytestmark = pytest.mark.asyncio(scope="module")


@pytest_asyncio.fixture(name="chat_dweller")
async def chat_dweller_fixture(async_session: AsyncSession, vault: Vault) -> DwellerReadFull:
    """Create a test dweller for chat tests."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Test",
            "last_name": "Dweller",
            "gender": GenderEnum.MALE,
            "is_adult": True,
            "level": 5,
            "happiness": 80,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    return await crud.dweller.get_full_info(async_session, dweller.id)


@pytest_asyncio.fixture(name="test_user")
async def test_user_fixture(async_session: AsyncSession, vault: Vault) -> User:
    """Get the user who owns the vault."""
    await async_session.refresh(vault, ["user"])
    return vault.user


@pytest.mark.asyncio
class TestChatServiceErrorHandling:
    """Tests for chat service resilience when AI provider fails."""

    @pytest.mark.parametrize("usage_kind", ["valid", "missing", "broken"])
    def test_extract_usage_handles_malformed_provider_metadata(self, usage_kind: str) -> None:
        usage = RunUsage(input_tokens=12, output_tokens=8) if usage_kind == "valid" else None
        if usage_kind == "broken":
            usage = MagicMock(spec=RunUsage)
            type(usage).input_tokens = PropertyMock(side_effect=ValueError("Invalid usage"))

        assert extract_usage(usage) == ((12, 8, 20) if usage_kind == "valid" else (None, None, None))

    async def test_run_chat_agent_passes_active_registry_prompt(
        self,
        async_session: AsyncSession,
        chat_dweller: DwellerReadFull,
    ) -> None:
        """The active chat prompt is passed to the PydanticAI run."""
        from app.agents.dweller_chat_agent import DwellerChatOutput

        active_instructions = "Use this active chat prompt."
        output = DwellerChatOutput(
            response_text="Test response",
            sentiment_score=0,
            reason_text="Neutral",
            action_type="no_action",
        )
        mock_result = MagicMock()
        mock_result.output = output
        mock_result.usage = RunUsage(input_tokens=1, output_tokens=1)

        with (
            patch("app.services.chat.agent_runner.dweller_chat_agent") as mock_agent,
            patch("app.services.chat.agent_runner.apply_chat_happiness", new=AsyncMock(return_value=(80, None))),
        ):
            mock_agent.run = AsyncMock(return_value=mock_result)

            result = await run_chat_agent(
                db_session=async_session,
                dweller=chat_dweller,
                message_text="Hello",
                instructions=active_instructions,
            )

        assert mock_agent.run.call_args.kwargs["instructions"] == active_instructions
        assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (1, 1, 2)

    async def test_process_text_message_raises_not_found_for_missing_dweller(self, async_session: AsyncSession) -> None:
        """A missing chat dweller is reported as the project's 404 exception."""
        dweller_id = uuid4()

        with pytest.raises(ResourceNotFoundException) as exc_info:
            await chat_service.process_text_message(
                db_session=async_session,
                user=MagicMock(id=uuid4()),
                dweller_id=dweller_id,
                message_text="Hello",
            )

        assert exc_info.value.status_code == 404

    async def test_run_chat_agent_handles_usage_attribute_error(
        self,
        async_session: AsyncSession,
        chat_dweller: DwellerReadFull,
    ) -> None:
        """Test that _run_chat_agent handles AttributeError from usage gracefully.

        Regression test for: AttributeError: 'coroutine' object has no attribute 'input_tokens'
        When the AI provider fails, result.usage may return an unexpected type
        or raise an AttributeError when accessing token attributes.
        """
        from pydantic_ai.agent import AgentRunResult

        from app.agents.dweller_chat_agent import DwellerChatOutput

        # Create a mock result where usage returns something that causes
        # AttributeError when accessing input_tokens
        mock_output = DwellerChatOutput(
            response_text="Test response",
            sentiment_score=1,
            reason_text="Test reason",
            action_type="no_action",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="No action needed",
        )

        # Create a mock usage object that raises AttributeError on attribute access
        class BrokenUsage:
            def __getattr__(self, name):
                raise AttributeError(f"'coroutine' object has no attribute '{name}'")

        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_result.usage = BrokenUsage()

        with patch("app.services.chat.agent_runner.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            # This should NOT raise an exception - it should handle the error gracefully
            result = await run_chat_agent(
                db_session=async_session,
                dweller=chat_dweller,
                message_text="Hello",
            )

            # Verify we got a response; token counts are None when usage extraction fails
            assert result.response_text == "Test response"
            assert result.prompt_tokens is None
            assert result.completion_tokens is None
            assert result.total_tokens is None

    async def test_run_chat_agent_handles_usage_returns_none(
        self,
        async_session: AsyncSession,
        chat_dweller: DwellerReadFull,
    ) -> None:
        """Test that _run_chat_agent handles usage returning None gracefully."""
        from pydantic_ai.agent import AgentRunResult

        from app.agents.dweller_chat_agent import DwellerChatOutput

        mock_output = DwellerChatOutput(
            response_text="Test response",
            sentiment_score=0,
            reason_text="Neutral",
            action_type="no_action",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="No action needed",
        )

        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_result.usage = None

        with patch("app.services.chat.agent_runner.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            result = await run_chat_agent(
                db_session=async_session,
                dweller=chat_dweller,
                message_text="Hello",
            )

            assert result.response_text == "Test response"
            assert result.prompt_tokens is None
            assert result.completion_tokens is None
            assert result.total_tokens is None

    async def test_run_chat_agent_rolls_back_savepoint_before_fallback_on_model_http_error(
        self,
        chat_dweller: DwellerReadFull,
    ) -> None:
        """Fallback after a provider error rolls back only the agent savepoint before delegation."""
        from pydantic_ai.exceptions import ModelHTTPError

        provider_error = ModelHTTPError(status_code=500, model_name="gpt-4o-mini", body={"message": "provider down"})
        savepoint = MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=False))
        db_session = MagicMock(begin_nested=MagicMock(return_value=savepoint))
        fallback = AsyncMock(return_value=MagicMock(spec=AgentChatResult))
        order = MagicMock()
        order.attach_mock(savepoint.__aexit__, "rollback")
        order.attach_mock(fallback, "fallback")

        with (
            patch("app.services.chat.agent_runner.dweller_chat_agent") as mock_agent,
            patch("app.services.chat.agent_runner.run_fallback_chat_agent", fallback),
        ):
            mock_agent.run = AsyncMock(side_effect=provider_error)

            result = await run_chat_agent(db_session=db_session, dweller=chat_dweller, message_text="Hello")

        assert [c[0] for c in order.mock_calls] == ["rollback", "fallback"]
        fallback.assert_awaited_once_with(chat_dweller, "Hello", None, for_audio=False)
        assert result is fallback.return_value

    async def test_run_chat_agent_rolls_back_savepoint_before_fallback_on_unexpected_error(
        self,
        chat_dweller: DwellerReadFull,
    ) -> None:
        """Fallback after an unexpected error rolls back only the agent savepoint before delegation."""
        savepoint = MagicMock(__aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=False))
        db_session = MagicMock(begin_nested=MagicMock(return_value=savepoint))
        fallback = AsyncMock(return_value=MagicMock(spec=AgentChatResult))
        order = MagicMock()
        order.attach_mock(savepoint.__aexit__, "rollback")
        order.attach_mock(fallback, "fallback")

        with (
            patch("app.services.chat.agent_runner.dweller_chat_agent") as mock_agent,
            patch("app.services.chat.agent_runner.run_fallback_chat_agent", fallback),
        ):
            mock_agent.run = AsyncMock(side_effect=RuntimeError("boom"))

            result = await run_chat_agent(db_session=db_session, dweller=chat_dweller, message_text="Hello")

        assert [c[0] for c in order.mock_calls] == ["rollback", "fallback"]
        fallback.assert_awaited_once_with(chat_dweller, "Hello", None, for_audio=False)
        assert result is fallback.return_value

    @pytest.mark.parametrize("missing", [False, True])
    async def test_stream_response_ownership_denied(
        self,
        async_session: AsyncSession,
        chat_dweller: DwellerReadFull,
        missing: bool,
    ) -> None:
        """Test that stream_response yields error when dweller's vault belongs to a different user."""
        from app.schemas.user import UserCreate

        other_user = await crud.user.create(
            db_session=async_session,
            obj_in=UserCreate(
                username="other-chat-user",
                email="other-chat@example.com",
                password="secretpass123",
            ),
        )

        dweller_id = uuid4() if missing else chat_dweller.id
        events = [
            event
            async for event in chat_service.stream_response(
                db_session=async_session,
                user=other_user,
                dweller_id=dweller_id,
                message_text="Hello",
            )
        ]

        assert len(events) == 1
        assert events[0] == ChatStreamError(
            detail=(
                str(ResourceNotFoundException(Dweller, dweller_id))
                if missing
                else "The user doesn't have enough privileges"
            )
        )

    @pytest.mark.parametrize("as_admin", [False, True])
    async def test_stream_response_streams_structured_output_deltas(
        self,
        async_session: AsyncSession,
        chat_dweller: DwellerReadFull,
        test_user: User,
        superuser: User,
        as_admin: bool,
    ) -> None:
        """stream_response streams response_text deltas from a structured-output agent."""
        from app.agents.dweller_chat_agent import DwellerChatOutput

        output = DwellerChatOutput(
            response_text="Hello vault dweller!",
            sentiment_score=2,
            reason_text="Friendly greeting",
            action_type="no_action",
        )

        async def fake_stream_output():
            yield output.model_copy(update={"response_text": "Helo vault"})
            yield output

        class FakeStreamResult:
            def __init__(self) -> None:
                self.output = output

            def stream_output(self):
                return fake_stream_output()

            @property
            def usage(self):
                return RunUsage(input_tokens=5, output_tokens=6)

            async def get_output(self):
                return output

        class FakeRunStreamCM:
            async def __aenter__(self):
                return FakeStreamResult()

            async def __aexit__(self, *exc):
                return False

        with (
            patch(
                "app.services.chat.streaming.dweller_chat_agent.run_stream",
                return_value=FakeRunStreamCM(),
            ),
            patch(
                "app.services.chat_service.quota_service.check_quota",
                new=AsyncMock(return_value=MagicMock(remaining=10, warning=False)),
            ),
            patch(
                "app.services.chat.persistence.chat_message_crud.create_message",
                new=AsyncMock(return_value=MagicMock(id=uuid4())),
            ),
            patch(
                "app.services.chat.persistence.llm_interaction_crud.create",
                new=AsyncMock(return_value=MagicMock(id=uuid4())),
            ) as record_usage,
            patch("app.services.chat.streaming.apply_chat_happiness", new=AsyncMock(return_value=(80, None))),
            patch(
                "app.services.chat.streaming.parse_action_suggestion",
                new=AsyncMock(return_value=NoAction()),
            ),
            patch(
                "app.services.chat.notifications.maybe_unlock_places",
                new=AsyncMock(return_value=[UnlockedPlace(location_id=uuid4(), name="Megaton")]),
            ),
        ):
            events = [
                event
                async for event in chat_service.stream_response(
                    db_session=async_session,
                    user=superuser if as_admin else test_user,
                    dweller_id=chat_dweller.id,
                    message_text="Hello",
                )
            ]

        tokens = [event for event in events if event.type == "token"]
        assert tokens == [
            ChatStreamToken(text="Helo vault"),
            ChatStreamToken(text="Hello vault dweller!", replace=True),
        ]
        assert isinstance(events[-1], ChatStreamDone)
        assert events[-1].response_text == "Hello vault dweller!"
        assert events[-1].happiness_impact is not None
        assert events[-1].happiness_impact.delta == 4
        assert events[-1].unlocked_places[0].name == "Megaton"
        usage = record_usage.call_args.kwargs["obj_in"]
        assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (5, 6, 11)

    async def test_stream_response_yields_provider_reason_on_model_http_error(
        self,
        async_session: AsyncSession,
        chat_dweller: DwellerReadFull,
        test_user: User,
    ) -> None:
        """stream_response yields the exact provider reason when run_stream raises ModelHTTPError."""
        from pydantic_ai.exceptions import ModelHTTPError

        provider_error = ModelHTTPError(
            status_code=429,
            model_name="gpt-4o-mini",
            body={"code": "credit_balance_exhausted", "message": "You have no credits remaining."},
        )

        with (
            patch(
                "app.services.chat.streaming.dweller_chat_agent.run_stream",
                side_effect=provider_error,
            ),
            patch(
                "app.services.chat_service.quota_service.check_quota",
                new=AsyncMock(return_value=MagicMock(remaining=10, warning=False)),
            ),
        ):
            events = [
                event
                async for event in chat_service.stream_response(
                    db_session=async_session,
                    user=test_user,
                    dweller_id=chat_dweller.id,
                    message_text="Hello",
                )
            ]

        assert len(events) == 1
        assert events[0] == ChatStreamError(detail="You have no credits remaining.")

    async def test_stream_response_falls_back_on_invalid_structured_output(
        self,
        async_session: AsyncSession,
        chat_dweller: DwellerReadFull,
        test_user: User,
    ) -> None:
        """stream_response re-runs via run() (retry-capable) when structured streaming output fails validation."""
        from pydantic_ai.exceptions import UnexpectedModelBehavior

        from app.schemas.chat import NoAction
        from app.schemas.happiness import HappinessImpact, HappinessReasonCode

        class FakeFailStreamResult:
            def stream_output(self):
                raise UnexpectedModelBehavior("Output validation failed during streaming")

        class FakeFailRunStreamCM:
            async def __aenter__(self):
                return FakeFailStreamResult()

            async def __aexit__(self, *exc):
                return False

        fallback_result = AgentChatResult(
            response_text="Sure, let's head to the wasteland!",
            happiness_impact=HappinessImpact(
                delta=0,
                reason_code=HappinessReasonCode.CHAT_NEUTRAL,
                reason_text="Chat processed without sentiment analysis",
                happiness_after=chat_dweller.happiness,
            ),
            action_suggestion=NoAction(reason="Unable to analyze conversation for suggestions"),
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )

        with (
            patch(
                "app.services.chat.streaming.dweller_chat_agent.run_stream",
                return_value=FakeFailRunStreamCM(),
            ),
            patch(
                "app.services.chat_service.quota_service.check_quota",
                new=AsyncMock(return_value=MagicMock(remaining=10, warning=False)),
            ),
            patch(
                "app.services.chat.persistence.chat_message_crud.create_message",
                new=AsyncMock(return_value=MagicMock(id=uuid4())),
            ),
            patch(
                "app.services.chat.persistence.llm_interaction_crud.create",
                new=AsyncMock(return_value=MagicMock(id=uuid4())),
            ),
            patch(
                "app.services.chat.agent_runner.run_chat_agent",
                new=AsyncMock(return_value=fallback_result),
            ),
            patch("app.services.chat.notifications.maybe_unlock_places", new=AsyncMock()),
        ):
            events = [
                event
                async for event in chat_service.stream_response(
                    db_session=async_session,
                    user=test_user,
                    dweller_id=chat_dweller.id,
                    message_text="Hello",
                )
            ]

        assert events[0] == ChatStreamToken(text="Sure, let's head to the wasteland!", replace=True)
        assert isinstance(events[-1], ChatStreamDone)
        assert events[-1].response_text == "Sure, let's head to the wasteland!"
        assert events[-1].happiness_impact is not None
        assert events[-1].happiness_impact.delta == 0


async def test_closing_stream_releases_provider_and_savepoint(
    async_session: AsyncSession, chat_dweller: DwellerReadFull
) -> None:
    """A disconnected client immediately closes the provider stream and its savepoint."""
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from app.agents.dweller_chat_agent import DwellerChatDeps
    from app.services.chat.streaming import stream_with_fallback

    provider_closed = False

    async def stream_output():
        yield SimpleNamespace(response_text="Hello")

    @asynccontextmanager
    async def fake_provider(*args, **kwargs):
        nonlocal provider_closed
        try:
            yield SimpleNamespace(stream_output=stream_output)
        finally:
            provider_closed = True

    deps = DwellerChatDeps(
        db_session=async_session,
        dweller=chat_dweller,
        vault_id=chat_dweller.vault.id,
    )
    with patch("app.services.chat.streaming.dweller_chat_agent.run_stream", new=fake_provider):
        stream = stream_with_fallback(deps, chat_dweller, "Hi", StreamBundle(), "Chat")
        assert await anext(stream) == ChatStreamToken(text="Hello")
        await stream.aclose()

    assert provider_closed is True
    assert async_session.in_nested_transaction() is False


@pytest.mark.asyncio
class TestMaybeUnlockPlaces:
    """Tests for the _maybe_unlock_places side-effect."""

    async def test_unlocks_after_three_messages(
        self,
        async_session: AsyncSession,
        vault: Vault,
        chat_dweller: DwellerReadFull,
    ) -> None:
        """After 3 user messages to a dweller, their linked places get unlocked."""
        from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum, PlaceKindEnum
        from app.crud.chat_message import chat_message as chat_crud
        from app.crud.world_location import world_location as wl_crud
        from app.models.chat_message import ChatMessageCreate
        from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation

        # Create a location and link it to the chat_dweller
        loc = WorldLocation(
            name="Megaton",
            normalized_name="megaton",
            kind=PlaceKindEnum.PLACE,
            coord_x=30.0,
            coord_y=40.0,
            description="Test",
        )
        async_session.add(loc)
        await async_session.flush()
        state = VaultLocationState(
            vault_id=vault.id,
            location_id=loc.id,
            type=LocationTypeEnum.ORIGIN,
            description="Test",
        )
        async_session.add(state)
        await async_session.flush()

        link = DwellerLocation(
            dweller_id=chat_dweller.id,
            location_id=loc.id,
            relation=DwellerLocationRelationEnum.ORIGIN,
        )
        async_session.add(link)
        await async_session.commit()

        # Create 2 messages — should NOT unlock yet
        for i in range(2):
            await chat_crud.create_message(
                async_session,
                obj_in=ChatMessageCreate(
                    vault_id=vault.id,
                    from_user_id=vault.user_id,
                    to_dweller_id=chat_dweller.id,
                    message_text=f"Hello {i}",
                ),
            )

        assert await maybe_unlock_places(async_session, chat_dweller) == []

        await async_session.refresh(link)
        assert link.is_unlocked is False, "Should NOT unlock after only 2 messages"

        # Create 3rd message — should unlock now
        await chat_crud.create_message(
            async_session,
            obj_in=ChatMessageCreate(
                vault_id=vault.id,
                from_user_id=vault.user_id,
                to_dweller_id=chat_dweller.id,
                message_text="Hello 2",
            ),
        )

        unlocked_places = await maybe_unlock_places(async_session, chat_dweller)
        assert [place.name for place in unlocked_places] == ["Megaton"]
        assert unlocked_places[0].location_id == loc.id

        await async_session.refresh(link)
        assert link.is_unlocked is True, "Should unlock after 3 messages"

    async def test_no_unlock_when_no_places(
        self,
        async_session: AsyncSession,
        vault: Vault,
        chat_dweller: DwellerReadFull,
    ) -> None:
        """_maybe_unlock_places does not raise when the dweller has no linked places."""
        from app.crud.chat_message import chat_message as chat_crud
        from app.models.chat_message import ChatMessageCreate

        for i in range(3):
            await chat_crud.create_message(
                async_session,
                obj_in=ChatMessageCreate(
                    vault_id=vault.id,
                    from_user_id=vault.user_id,
                    to_dweller_id=chat_dweller.id,
                    message_text=f"Hello {i}",
                ),
            )

        # Must not raise even though dweller has no DwellerLocation rows
        await maybe_unlock_places(async_session, chat_dweller)


@pytest.mark.parametrize("mode", ["text", "stream", "voice"])
@pytest.mark.parametrize("fail_write", [False, True])
async def test_chat_commits_usage_messages_and_happiness_together(
    async_session, chat_dweller, test_user, mode, fail_write
):
    from sqlalchemy import func, select

    from app.agents.dweller_chat_agent import DwellerChatOutput
    from app.models.chat_message import ChatMessage
    from app.models.llm_interaction import LLMInteraction
    from app.services.conversation_service import conversation_service

    dweller_id, happiness = chat_dweller.id, chat_dweller.happiness
    output = DwellerChatOutput(
        response_text="Hello", sentiment_score=5, reason_text="Friendly", action_type="no_action"
    )
    result = MagicMock(output=output, usage=RunUsage(input_tokens=3, output_tokens=2))
    original = chat_message_crud.create_message

    async def fail_reply(db, *, obj_in):
        if fail_write and obj_in.from_dweller_id:
            raise RuntimeError("reply write failed")
        return await original(db, obj_in=obj_in)

    async def generate_stream(deps, dweller, message_text, bundle, instructions):
        from app.services.chat_happiness_service import apply_chat_happiness

        await apply_chat_happiness(deps.db_session, dweller.id, 5)
        bundle.response_text = "Hello"
        yield ChatStreamToken(text="Hello")

    with (
        patch("app.services.chat.agent_runner.dweller_chat_agent.run", new=AsyncMock(return_value=result)),
        patch("app.services.chat_service.stream_with_fallback", new=generate_stream),
        patch.object(chat_message_crud, "create_message", new=fail_reply),
        patch.object(conversation_service, "_transcribe_audio", new=AsyncMock(return_value=("Hi", None, None))),
        patch.object(conversation_service, "_generate_tts_audio", new=AsyncMock(return_value=(b"audio", None))),
    ):
        if mode == "stream":
            events = [event async for event in chat_service.stream_response(async_session, test_user, dweller_id, "Hi")]
            assert events[-1].type == ("error" if fail_write else "done")
        else:
            operation = (
                conversation_service.process_audio_message(async_session, test_user, dweller_id, b"audio")
                if mode == "voice"
                else chat_service.process_text_message(async_session, test_user, dweller_id, "Hi")
            )
            if fail_write:
                with pytest.raises(RuntimeError, match="reply write failed"):
                    await operation
            else:
                await operation

    await async_session.rollback()
    assert (await async_session.execute(select(func.count()).select_from(LLMInteraction))).scalar_one() == (
        0 if fail_write else 1
    )
    assert (await async_session.execute(select(func.count()).select_from(ChatMessage))).scalar_one() == (
        0 if fail_write else 2
    )
    saved_happiness = (await crud.dweller.get(async_session, dweller_id)).happiness
    assert saved_happiness == happiness if fail_write else saved_happiness > happiness


async def test_discovery_failure_preserves_pending_conversation(async_session, chat_dweller, test_user):
    from app.models.chat_message import ChatMessageCreate

    message = await chat_message_crud.create_message(
        async_session,
        obj_in=ChatMessageCreate(
            vault_id=chat_dweller.vault.id,
            from_user_id=test_user.id,
            to_dweller_id=chat_dweller.id,
            message_text="Keep this message",
        ),
    )
    with patch.object(
        chat_message_crud, "count_user_messages_to_dweller", new=AsyncMock(side_effect=RuntimeError("offline"))
    ):
        assert await maybe_unlock_places(async_session, chat_dweller) == []
    await async_session.commit()
    assert (await chat_message_crud.get(async_session, message.id)).message_text == "Keep this message"
