"""Quota enforcement at 100% usage across AI-backed endpoints; LLM calls are mocked."""

import io
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.llm_interaction import LLMInteraction
from app.models.user import User
from app.schemas.dweller import DwellerCreate, DwellerReadFull
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.services.conversation_service import conversation_service
from app.services.dweller_ai_service import dweller_ai
from app.tests.utils.user import authentication_token_from_email

pytestmark = pytest.mark.asyncio(scope="module")


@pytest_asyncio.fixture(name="quota_user")
async def quota_user_fixture(async_session: AsyncSession) -> User:
    suffix = uuid4().hex[:8]
    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(
            username=f"quota_test_{suffix}",
            email=f"quota_{suffix}@test.com",
            password="testpass123",
            is_superuser=False,
        ),
    )
    user.email_verified = True
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture(name="user_at_quota_limit")
async def user_at_quota_limit_fixture(async_session: AsyncSession, quota_user: User) -> User:
    async_session.add(
        LLMInteraction(
            user_id=quota_user.id,
            parameters="test prompt",
            response="test response",
            usage="test",
            prompt_tokens=250000,
            completion_tokens=250000,
            total_tokens=500000,
            created_at=datetime.now(UTC),
        )
    )
    await async_session.commit()
    await async_session.refresh(quota_user)
    return quota_user


@pytest_asyncio.fixture(name="quota_dweller")
async def quota_dweller_fixture(async_session: AsyncSession, quota_user: User) -> DwellerReadFull:
    vault = await crud.vault.create_with_user_id(
        db_session=async_session, obj_in=VaultCreate(number=100, bottle_caps=1000), user_id=quota_user.id
    )
    dweller = await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Test",
            last_name="Dweller",
            gender=GenderEnum.MALE,
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
        ),
    )
    barbershop = await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(
            name="Barbershop",
            category=RoomTypeEnum.MISC,
            ability=SPECIALEnum.CHARISMA,
            population_required=50,
            base_cost=10000,
            incremental_cost=None,
            t2_upgrade_cost=50000,
            t3_upgrade_cost=None,
            size_min=6,
            size_max=6,
            size=6,
            tier=1,
            vault_id=vault.id,
        ),
    )
    dweller.room_id = barbershop.id
    async_session.add(dweller)
    await async_session.commit()
    return await crud.dweller.get_full_info(async_session, dweller.id)


@pytest_asyncio.fixture(name="quota_headers")
async def quota_headers_fixture(async_client: AsyncClient, async_session: AsyncSession, user_at_quota_limit: User):
    return await authentication_token_from_email(
        client=async_client, email=user_at_quota_limit.email, db_session=async_session
    )


def _assert_quota_block(response) -> None:
    assert response.status_code == 429, f"Expected 429, got {response.status_code}: {response.text}"
    data = response.json()
    assert "detail" in data
    assert "quota" in data["detail"].lower()


class TestDwellerAIQuotaEnforcement:
    @pytest.mark.parametrize(
        ("agent", "action"),
        [("backstory_agent", "generate_backstory"), ("visual_attributes_agent", "generate_visual_attributes")],
    )
    async def test_agent_quota_block(self, async_client, quota_headers, quota_dweller, agent, action):
        with patch(f"app.services.dweller_ai_service.{agent}") as mock_agent:
            mock_agent.run = AsyncMock()
            response = await async_client.post(f"dwellers/{quota_dweller.id}/{action}/", headers=quota_headers)
            _assert_quota_block(response)
            mock_agent.run.assert_not_called()

    async def test_tts_quota_block(self, async_client, quota_headers, quota_dweller):
        # Cache miss: the cache-first pipeline must reach the provider path for the quota check to fire.
        with patch.object(dweller_ai, "storage_service", create=True) as mock_storage:
            mock_storage.enabled = True
            mock_storage.upload_file = MagicMock(return_value="https://example.com/audio.mp3")
            mock_storage.file_exists = MagicMock(return_value=False)
            mock_storage.public_url = MagicMock(return_value="https://example.com/audio.mp3")
            with patch("app.services.dweller_ai_service.get_ai_service") as mock_ai:
                mock_ai_service = MagicMock()
                mock_ai_service.generate_audio = AsyncMock(return_value=b"fake audio bytes")
                mock_ai.return_value = mock_ai_service
                response = await async_client.post(
                    f"dwellers/{quota_dweller.id}/generate_audio/",
                    headers=quota_headers,
                    params={"text": "Hello, I am a test dweller!"},
                )
                _assert_quota_block(response)
                mock_ai_service.generate_audio.assert_not_called()


class TestVoiceChatQuotaEnforcement:
    async def test_voice_chat_quota_block(self, async_client, quota_headers, quota_dweller):
        mock_ai_service = MagicMock()
        mock_ai_service.transcribe_audio = AsyncMock(return_value="Hello there")
        files = {"audio_file": ("test.webm", io.BytesIO(b"RIFF" + b"\x00" * 100), "audio/webm")}
        with (
            patch("app.services.chat.agent_runner.dweller_chat_agent") as mock_agent,
            patch.object(conversation_service, "ai_service", mock_ai_service),
            patch("app.services.quota_service.settings") as mock_settings,
        ):
            mock_agent.run = AsyncMock()
            mock_settings.QUOTA_DISABLED = False
            response = await async_client.post(
                f"chat/{quota_dweller.id}/voice", headers=quota_headers, files=files, params={"return_audio": False}
            )
            _assert_quota_block(response)
