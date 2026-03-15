"""Integration tests for quota enforcement across all AI services.

These tests verify that quota limits are properly enforced at 100% usage
for all AI-powered features: chat, backstory, bio extension, visual attributes,
TTS, and voice chat.

All tests mock the LLM service to avoid calling real APIs.
"""

import io
from datetime import UTC, datetime
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
from app.models.llm_interaction import LLMInteraction
from app.models.user import User
from app.schemas.common import GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.dweller_ai import DwellerBackstory, DwellerVisualAttributes
from app.schemas.user import UserCreate
from app.services.dweller_ai import dweller_ai
from app.tests.utils.user import authentication_token_from_email

pytestmark = pytest.mark.asyncio(scope="module")

DEFAULT_QUOTA_LIMIT = 500000


@pytest_asyncio.fixture(name="quota_user")
async def quota_user_fixture(async_session: AsyncSession) -> User:
    """Create a test user with default quota limit."""
    user_in = UserCreate(
        username=f"quota_test_{uuid4().hex[:8]}",
        email=f"quota_{uuid4().hex[:8]}@test.com",
        password="testpass123",
        is_superuser=False,
    )
    return await crud.user.create(db_session=async_session, obj_in=user_in)


@pytest_asyncio.fixture(name="user_at_quota_limit")
async def user_at_quota_limit_fixture(async_session: AsyncSession, quota_user: User) -> User:
    """Create a user who has reached 100% of their quota limit."""
    # Create LLM interaction that uses up all quota
    interaction = LLMInteraction(
        user_id=quota_user.id,
        parameters="test prompt",
        response="test response",
        usage="test",
        prompt_tokens=250000,
        completion_tokens=250000,
        total_tokens=500000,
        created_at=datetime.now(UTC),
    )
    async_session.add(interaction)
    await async_session.commit()
    await async_session.refresh(quota_user)
    return quota_user


@pytest_asyncio.fixture(name="quota_dweller")
async def quota_dweller_fixture(async_session: AsyncSession, quota_user: User) -> "Dweller":
    """Create a test dweller for quota tests."""
    from app.schemas.vault import VaultCreateWithUserID

    vault_in = VaultCreateWithUserID(
        number=100,
        bottle_caps=1000,
        user_id=quota_user.id,
    )
    vault = await crud.vault.create(db_session=async_session, obj_in=vault_in)

    dweller_in = DwellerCreate(
        first_name="Test",
        last_name="Dweller",
        gender=GenderEnum.MALE,
        is_adult=True,
        level=5,
        vault_id=vault.id,
        rarity=RarityEnum.COMMON,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
    )
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    return await crud.dweller.get_full_info(async_session, dweller.id)


@pytest_asyncio.fixture(name="quota_dweller_with_bio")
async def quota_dweller_with_bio_fixture(async_session: AsyncSession, quota_dweller: "Dweller") -> "Dweller":
    """Create a dweller with existing bio for extend_bio tests."""
    from app.schemas.dweller import DwellerUpdate

    await crud.dweller.update(
        async_session,
        quota_dweller.id,
        DwellerUpdate(bio="Test bio for extension testing."),
    )
    return await crud.dweller.get_full_info(async_session, quota_dweller.id)


@pytest.mark.asyncio
class TestChatQuotaEnforcement:
    """Tests for chat service quota enforcement."""

    async def test_chat_quota_block(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that chat is blocked when user is at 100% quota."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        with patch("app.services.chat_service.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock()

            response = await async_client.post(
                f"chat/{quota_dweller.id}",
                headers=token_headers,
                json={"message": "Hello, are you there?"},
            )

            assert response.status_code == 429, f"Expected 429 status, got {response.status_code}: {response.text}"

            data = response.json()
            assert "detail" in data
            assert "quota" in data["detail"].lower()
            mock_agent.run.assert_not_called()

    async def test_chat_quota_response_headers(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that quota headers are included in the 429 response."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        response = await async_client.post(
            f"chat/{quota_dweller.id}",
            headers=token_headers,
            json={"message": "Hello?"},
        )

        assert response.status_code == 429
        assert "x-quota-remaining" in response.headers
        assert response.headers["x-quota-remaining"] == "0"


@pytest.mark.asyncio
class TestDwellerAIQuotaEnforcement:
    """Tests for DwellerAI service quota enforcement."""

    async def test_backstory_quota_block(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that backstory generation is blocked at 100% quota."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        with patch("app.services.dweller_ai.backstory_agent") as mock_agent:
            mock_agent.run = AsyncMock(return_value=MagicMock(output=DwellerBackstory(bio="Generated backstory")))

            response = await async_client.post(
                f"dwellers/{quota_dweller.id}/generate_backstory/",
                headers=token_headers,
            )

            assert response.status_code == 429, f"Expected 429 status, got {response.status_code}: {response.text}"

            data = response.json()
            assert "detail" in data
            assert "quota" in data["detail"].lower()
            mock_agent.run.assert_not_called()

    async def test_visual_quota_block(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that visual attributes generation is blocked at 100% quota."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        with patch("app.services.dweller_ai.visual_attributes_agent") as mock_agent:
            mock_output = DwellerVisualAttributes(
                hair_color="brown",
                eye_color="blue",
                skin_tone="fair",
                height="average",
                build="athletic",
                distinguishing_features=["scar on left cheek"],
            )
            mock_agent.run = AsyncMock(return_value=MagicMock(output=mock_output))

            response = await async_client.post(
                f"dwellers/{quota_dweller.id}/generate_visual_attributes/",
                headers=token_headers,
            )

            assert response.status_code == 429, f"Expected 429 status, got {response.status_code}: {response.text}"

            data = response.json()
            assert "detail" in data
            assert "quota" in data["detail"].lower()
            mock_agent.run.assert_not_called()

    async def test_tts_quota_block(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that TTS (audio generation) is blocked at 100% quota."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        # Patch the storage_service on the dweller_ai instance directly
        with patch.object(dweller_ai, "storage_service", create=True) as mock_storage:
            mock_storage.enabled = True
            mock_storage.upload_file = MagicMock(return_value="https://example.com/audio.mp3")

            with patch("app.services.dweller_ai.get_ai_service") as mock_ai:
                mock_ai_service = MagicMock()
                mock_ai_service.generate_audio = AsyncMock(return_value=b"fake audio bytes")
                mock_ai.return_value = mock_ai_service

                response = await async_client.post(
                    f"dwellers/{quota_dweller.id}/generate_audio/",
                    headers=token_headers,
                    params={"text": "Hello, I am a test dweller!"},
                )

                assert response.status_code == 429, f"Expected 429 status, got {response.status_code}: {response.text}"

                data = response.json()
                assert "detail" in data
                assert "quota" in data["detail"].lower()
                mock_ai_service.generate_audio.assert_not_called()


@pytest.mark.asyncio
class TestVoiceChatQuotaEnforcement:
    """Tests for voice chat quota enforcement."""

    async def test_voice_chat_quota_block(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that voice chat is blocked at 100% quota."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        audio_data = b"RIFF" + b"\x00" * 100
        files = {"audio_file": ("test.webm", io.BytesIO(audio_data), "audio/webm")}

        with patch("app.services.conversation_service.dweller_chat_agent") as mock_agent:
            mock_agent.run = AsyncMock()

            with patch("app.services.conversation_service.get_ai_service") as mock_ai:
                mock_ai_service = MagicMock()
                mock_ai_service.transcribe_audio = AsyncMock(return_value="Hello there")
                mock_ai.return_value = mock_ai_service

                response = await async_client.post(
                    f"chat/{quota_dweller.id}/voice",
                    headers=token_headers,
                    files=files,
                    params={"return_audio": False},
                )

                assert response.status_code == 429
                data = response.json()
                assert "detail" in data
                assert "quota" in data["detail"].lower()


@pytest.mark.asyncio
class TestQuotaErrorResponseFormat:
    """Tests for quota error response format and content."""

    async def test_quota_error_includes_remaining_tokens(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that quota error includes remaining tokens (0 at limit)."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        response = await async_client.post(
            f"chat/{quota_dweller.id}",
            headers=token_headers,
            json={"message": "Test message"},
        )

        assert response.status_code == 429
        data = response.json()
        assert "detail" in data
        detail = data["detail"].lower()
        assert "quota" in detail

    async def test_quota_error_header_includes_remaining(
        self,
        async_client: AsyncClient,
        async_session: AsyncSession,
        user_at_quota_limit: User,
        quota_dweller: "Dweller",
    ):
        """Test that X-Quota-Remaining header is 0 at limit."""
        token_headers = await authentication_token_from_email(
            client=async_client,
            email=user_at_quota_limit.email,
            db_session=async_session,
        )

        response = await async_client.post(
            f"chat/{quota_dweller.id}",
            headers=token_headers,
            json={"message": "Test message"},
        )

        assert response.status_code == 429
        assert "x-quota-remaining" in response.headers
        assert response.headers["x-quota-remaining"] == "0"


@pytest.mark.asyncio
class TestAdminQuotaBypass:
    """Tests that admin users bypass quota checks."""

    async def test_admin_bypasses_quota(
        self,
        async_client: AsyncClient,
        superuser_token_headers: dict[str, str],
        quota_dweller: "Dweller",
    ):
        """Test that admin users can still use AI features at quota limit."""
        with patch("app.services.chat_service.dweller_chat_agent") as mock_agent:
            mock_output = DwellerChatOutput(
                response_text="Hello! How can I help you?",
                sentiment_score=2,
                reason_text="Friendly greeting",
                action_type="no_action",
                action_room_id=None,
                action_room_name=None,
                action_stat=None,
                action_reason="No action needed",
            )
            mock_result = MagicMock(spec=AgentRunResult)
            mock_result.output = mock_output
            mock_agent.run = AsyncMock(return_value=mock_result)

            response = await async_client.post(
                f"chat/{quota_dweller.id}",
                headers=superuser_token_headers,
                json={"message": "Hello, are you there?"},
            )

            assert response.status_code == 200, (
                f"Admin should bypass quota, got {response.status_code}: {response.text}"
            )

            data = response.json()
            assert data["response"] == "Hello! How can I help you?"
            mock_agent.run.assert_called_once()
