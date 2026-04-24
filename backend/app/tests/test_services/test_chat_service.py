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

    async def test_run_chat_agent_handles_usage_attribute_error(
        self,
        async_session: AsyncSession,
        chat_dweller: Dweller,
    ):
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
    ):
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
    ):
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
    ):
        """Test that _run_chat_agent falls back when the agent raises an exception."""
        from app.services.open_ai import ChatCompletionResult

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
