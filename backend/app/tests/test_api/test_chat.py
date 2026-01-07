"""Tests for chat API endpoints (text and audio chat).

Note: These are simplified tests focusing on API contract validation and basic functionality.
Integration tests with external services (OpenAI API, MinIO) are omitted due to complexity.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
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


@pytest.mark.asyncio
class TestTextChat:
    """Tests for text-based chat endpoint."""

    @patch("app.api.v1.endpoints.chat.get_ai_service")
    async def test_send_text_message_success(
        self,
        mock_ai_service_func: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test sending a text message to a dweller."""
        # Mock AI service
        mock_ai = AsyncMock()
        mock_ai.chat_completion.return_value = "Hello! How can I help you today?"
        mock_ai_service_func.return_value = mock_ai

        response = await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "Hi there!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] == "Hello! How can I help you today?"

        # Verify AI service was called
        mock_ai.chat_completion.assert_called_once()
        call_args = mock_ai.chat_completion.call_args[0][0]
        assert isinstance(call_args, list)
        assert any("system" in msg.get("role", "") for msg in call_args)
        assert any("Hi there!" in msg.get("content", "") for msg in call_args)

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

    @patch("app.api.v1.endpoints.chat.get_ai_service")
    async def test_chat_uses_dweller_context(
        self,
        mock_ai_service_func: MagicMock,
        async_client: AsyncClient,
        normal_user_token_headers: dict[str, str],
        chat_dweller: Dweller,
    ):
        """Test that chat includes dweller context in prompts."""
        mock_ai = AsyncMock()
        mock_ai.chat_completion.return_value = "Response"
        mock_ai_service_func.return_value = mock_ai

        await async_client.post(
            f"chat/{chat_dweller.id}",
            headers=normal_user_token_headers,
            json={"message": "What's your name?"},
        )

        # Verify AI was called with dweller context
        mock_ai.chat_completion.assert_called_once()
        call_args = mock_ai.chat_completion.call_args[0][0]
        system_message = next((m for m in call_args if m["role"] == "system"), None)
        assert system_message is not None
        # Should include dweller name
        assert chat_dweller.first_name in system_message["content"]
        assert chat_dweller.last_name in system_message["content"]


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
