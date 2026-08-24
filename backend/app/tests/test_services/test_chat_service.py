"""Tests for chat service error handling, especially AI provider failures."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.user import User
from app.models.vault import Vault
from app.schemas.common import GenderEnum
from app.schemas.dweller import DwellerCreate
from app.services.chat_service import chat_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.exceptions import ResourceNotFoundException

pytestmark = pytest.mark.asyncio(scope="module")


@pytest_asyncio.fixture(name="chat_dweller")
async def chat_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
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

    async def test_process_text_message_raises_not_found_for_missing_dweller(self) -> None:
        """A missing chat dweller is reported as the project's 404 exception."""
        dweller_id = uuid4()

        with (
            patch("app.services.chat_service.dweller_crud.get_full_info", new_callable=AsyncMock, return_value=None),
            pytest.raises(ResourceNotFoundException) as exc_info,
        ):
            await chat_service.process_text_message(
                db_session=MagicMock(),
                user=MagicMock(id=uuid4()),
                dweller_id=dweller_id,
                message_text="Hello",
            )

        assert exc_info.value.status_code == 404

    async def test_run_chat_agent_handles_usage_attribute_error(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
    ) -> None:
        """Test that _run_chat_agent handles AttributeError from usage() gracefully.

        Regression test for: AttributeError: 'coroutine' object has no attribute 'input_tokens'
        When the AI provider fails, result.usage() may return an unexpected type
        or raise an AttributeError when accessing token attributes.
        """
        from pydantic_ai.agent import AgentRunResult

        from app.agents.dweller_chat_agent import DwellerChatOutput

        # Create a mock result where usage() returns something that causes
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
        mock_result.usage.return_value = BrokenUsage()

        with patch("app.services.chat_service.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            # This should NOT raise an exception - it should handle the error gracefully
            result = await chat_service._run_chat_agent(
                db_session=async_session,
                dweller=chat_dweller,
                message_text="Hello",
            )

            (
                response_message,
                _happiness_impact,
                _action_suggestion,
                prompt_tokens,
                completion_tokens,
                total_tokens,
            ) = result

            # Verify we got a response
            assert response_message == "Test response"
            # Token counts should be None when usage extraction fails
            assert prompt_tokens is None
            assert completion_tokens is None
            assert total_tokens is None

    async def test_run_chat_agent_handles_usage_returns_none(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
    ) -> None:
        """Test that _run_chat_agent handles usage() returning None gracefully."""
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
        mock_result.usage.return_value = None

        with patch("app.services.chat_service.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            result = await chat_service._run_chat_agent(
                db_session=async_session,
                dweller=chat_dweller,
                message_text="Hello",
            )

            (
                response_message,
                _happiness_impact,
                _action_suggestion,
                prompt_tokens,
                completion_tokens,
                total_tokens,
            ) = result

            assert response_message == "Test response"
            assert prompt_tokens is None
            assert completion_tokens is None
            assert total_tokens is None

    async def test_run_chat_agent_handles_usage_raises_exception(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
    ) -> None:
        """Test that _run_chat_agent handles usage() raising any exception gracefully."""
        from pydantic_ai.agent import AgentRunResult

        from app.agents.dweller_chat_agent import DwellerChatOutput

        mock_output = DwellerChatOutput(
            response_text="Test response",
            sentiment_score=1,
            reason_text="Test",
            action_type="no_action",
            action_room_id=None,
            action_room_name=None,
            action_stat=None,
            action_reason="No action needed",
        )

        mock_result = MagicMock(spec=AgentRunResult)
        mock_result.output = mock_output
        mock_result.usage.side_effect = RuntimeError("Usage data unavailable")

        with patch("app.services.chat_service.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=mock_result)

            # Should not raise - should handle gracefully
            result = await chat_service._run_chat_agent(
                db_session=async_session,
                dweller=chat_dweller,
                message_text="Hello",
            )

            (
                response_message,
                _happiness_impact,
                _action_suggestion,
                prompt_tokens,
                completion_tokens,
                total_tokens,
            ) = result

            assert response_message == "Test response"
            assert prompt_tokens is None
            assert completion_tokens is None
            assert total_tokens is None

    async def test_run_chat_agent_fallback_when_agent_completely_fails(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
    ) -> None:
        """Test that _run_chat_agent falls back when the agent raises an exception."""
        from app.services.ai_service import ChatCompletionResult

        with patch("app.services.chat_service.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock(side_effect=Exception("AI provider unavailable"))

            # Mock the fallback AI service
            with patch("app.services.chat_service.get_ai_service") as mock_get_ai:
                mock_ai_service = MagicMock()
                mock_ai_service.chat_completion_with_usage = AsyncMock(
                    return_value=ChatCompletionResult(
                        text="Fallback response",
                        prompt_tokens=10,
                        completion_tokens=20,
                        total_tokens=30,
                    )
                )
                mock_get_ai.return_value = mock_ai_service

                result = await chat_service._run_chat_agent(
                    db_session=async_session,
                    dweller=chat_dweller,
                    message_text="Hello",
                )

                (
                    response_message,
                    happiness_impact,
                    _action_suggestion,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                ) = result

                assert response_message == "Fallback response"
                assert prompt_tokens == 10
                assert completion_tokens == 20
                assert total_tokens == 30
                # Fallback should have neutral happiness
                assert happiness_impact.delta == 0
                assert happiness_impact.reason_code.value == "chat_neutral"

    async def test_stream_response_ownership_denied(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
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

        events = [
            event
            async for event in chat_service.stream_response(
                db_session=async_session,
                user=other_user,
                dweller_id=chat_dweller.id,
                message_text="Hello",
            )
        ]

        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["detail"] == "Dweller does not belong to the current user"

    async def test_stream_response_streams_structured_output_deltas(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
        test_user: User,
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

            def usage(self):
                return MagicMock(input_tokens=5, output_tokens=6, total_tokens=11)

            async def get_output(self):
                return output

        class FakeRunStreamCM:
            async def __aenter__(self):
                return FakeStreamResult()

            async def __aexit__(self, *exc):
                return False

        with (
            patch(
                "app.services.chat_service.dweller_chat_agent.run_stream",
                return_value=FakeRunStreamCM(),
            ),
            patch(
                "app.services.chat_service.quota_service.check_quota",
                new=AsyncMock(return_value=MagicMock(remaining=10, warning=False)),
            ),
            patch(
                "app.services.chat_service.chat_message_crud.create_message",
                new=AsyncMock(return_value=MagicMock(id=uuid4())),
            ),
            patch(
                "app.services.chat_service.llm_interaction_crud.create",
                new=AsyncMock(return_value=MagicMock(id=uuid4())),
            ),
            patch("app.services.chat_service.apply_chat_happiness", new=AsyncMock(return_value=(80, None))),
            patch(
                "app.services.chat_service.parse_action_suggestion",
                new=AsyncMock(return_value=MagicMock(model_dump=dict)),
            ),
            patch.object(chat_service, "_maybe_unlock_places", new=AsyncMock()),
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

        tokens = [event for event in events if event["type"] == "token"]
        assert tokens == [
            {"type": "token", "text": "Helo vault"},
            {"type": "token", "text": "Hello vault dweller!", "replace": True},
        ]
        assert events[-1]["type"] == "done"
        assert events[-1]["response_text"] == "Hello vault dweller!"
        assert events[-1]["happiness_impact"]["delta"] == 4

    async def test_stream_response_yields_provider_reason_on_model_http_error(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
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
                "app.services.chat_service.dweller_chat_agent.run_stream",
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
        assert events[0]["type"] == "error"
        assert events[0]["detail"] == "You have no credits remaining."


@pytest.mark.asyncio
class TestMaybeUnlockPlaces:
    """Tests for the _maybe_unlock_places side-effect."""

    async def test_unlocks_after_three_messages(
        self,
        async_session: AsyncSession,
        vault: Vault,
        chat_dweller: Dweller,
    ) -> None:
        """After 3 user messages to a dweller, their linked places get unlocked."""
        from app.crud.chat_message import chat_message as chat_crud
        from app.crud.wasteland_location import wasteland_location as wl_crud
        from app.models.chat_message import ChatMessageCreate
        from app.models.wasteland_location import (
            DwellerLocation,
            DwellerLocationRelationEnum,
            LocationTypeEnum,
            WastelandLocation,
        )

        # Create a location and link it to the chat_dweller
        loc = WastelandLocation(
            name="Megaton",
            normalized_name="megaton",
            type=LocationTypeEnum.ORIGIN,
            coord_x=30.0,
            coord_y=40.0,
            description="Test",
            vault_id=vault.id,
        )
        async_session.add(loc)
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

        await chat_service._maybe_unlock_places(async_session, chat_dweller)

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

        await chat_service._maybe_unlock_places(async_session, chat_dweller)

        await async_session.refresh(link)
        assert link.is_unlocked is True, "Should unlock after 3 messages"

    async def test_no_unlock_when_no_places(
        self,
        async_session: AsyncSession,
        vault: Vault,
        chat_dweller: Dweller,
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
        await chat_service._maybe_unlock_places(async_session, chat_dweller)

    async def test_already_unlocked_is_idempotent(
        self,
        async_session: AsyncSession,
        vault: Vault,
        chat_dweller: Dweller,
    ) -> None:
        """Calling _maybe_unlock_places when places are already unlocked is safe."""
        from app.crud.chat_message import chat_message as chat_crud
        from app.crud.wasteland_location import wasteland_location as wl_crud
        from app.models.chat_message import ChatMessageCreate
        from app.models.wasteland_location import (
            DwellerLocation,
            DwellerLocationRelationEnum,
            LocationTypeEnum,
            WastelandLocation,
        )

        loc = WastelandLocation(
            name="Megaton",
            normalized_name="megaton2",
            type=LocationTypeEnum.ORIGIN,
            coord_x=35.0,
            coord_y=45.0,
            description="Test",
            vault_id=vault.id,
        )
        async_session.add(loc)
        await async_session.flush()

        link = DwellerLocation(
            dweller_id=chat_dweller.id,
            location_id=loc.id,
            relation=DwellerLocationRelationEnum.ORIGIN,
        )
        async_session.add(link)
        await async_session.commit()

        # Pre-unlock
        await wl_crud.unlock_places_for_dweller(async_session, dweller_id=chat_dweller.id)

        for i in range(5):
            await chat_crud.create_message(
                async_session,
                obj_in=ChatMessageCreate(
                    vault_id=vault.id,
                    from_user_id=vault.user_id,
                    to_dweller_id=chat_dweller.id,
                    message_text=f"Hello {i}",
                ),
            )

        # Must not raise; places stay unlocked
        await chat_service._maybe_unlock_places(async_session, chat_dweller)

        await async_session.refresh(link)
        assert link.is_unlocked is True
