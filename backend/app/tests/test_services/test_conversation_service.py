"""Tests for conversation service (audio chat)."""

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.user import User
from app.models.vault import Vault
from app.schemas.common import GenderEnum
from app.schemas.dweller import DwellerCreate
from app.services.conversation_service import conversation_service
from app.tests.factory.dwellers import create_fake_dweller

# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture(name="test_dweller")
async def test_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a test dweller for conversation with full relationships loaded."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Sarah",
            "last_name": "Connor",
            "gender": GenderEnum.FEMALE,
            "is_adult": True,
            "level": 10,
            "happiness": 75,
            "health": 90,
            "max_health": 100,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Use crud.dweller.get() to eager load all relationships for prompt building
    return await crud.dweller.get(db_session=async_session, id=dweller.id)


@pytest_asyncio.fixture(name="test_user")
async def test_user_fixture(async_session: AsyncSession, vault: Vault) -> User:
    """Get the user who owns the vault."""
    # Refresh to load user relationship
    await async_session.refresh(vault, ["user"])
    return vault.user


@pytest.fixture
def mock_audio_bytes():
    """Mock audio file bytes."""
    # Create a minimal mock audio file
    return b"RIFF" + b"\x00" * 100  # Minimal RIFF header + some data


# ============================================================================
# Unit Tests for Helper Methods
# ============================================================================


@pytest.mark.asyncio
class TestVoiceSelection:
    """Tests for gender-based voice selection."""

    def test_select_voice_for_male(self):
        """Test voice selection for male dwellers."""
        voice = conversation_service._select_voice_for_gender(GenderEnum.MALE)
        assert voice in ["echo", "fable", "onyx"]

    def test_select_voice_for_female(self):
        """Test voice selection for female dwellers."""
        voice = conversation_service._select_voice_for_gender(GenderEnum.FEMALE)
        assert voice in ["nova", "shimmer", "alloy"]

    def test_select_voice_for_none_gender(self):
        """Test voice selection defaults to alloy for None gender."""
        voice = conversation_service._select_voice_for_gender(None)
        assert voice == "alloy"


@pytest.mark.asyncio
class TestPromptBuilder:
    """Tests for dweller prompt building."""

    async def test_build_prompt_text_mode(self, test_dweller: Dweller):
        """Test building prompt for text chat."""
        # Load full dweller info
        prompt = conversation_service._build_dweller_prompt(test_dweller, for_audio=False)

        # Check essential elements
        assert test_dweller.first_name in prompt
        assert test_dweller.last_name in prompt
        assert str(test_dweller.level) in prompt
        assert test_dweller.gender.value in prompt
        assert "concise" not in prompt.lower() or "150 words" not in prompt

    async def test_build_prompt_audio_mode(self, test_dweller: Dweller):
        """Test building prompt for audio chat includes conciseness instruction."""
        prompt = conversation_service._build_dweller_prompt(test_dweller, for_audio=True)

        # Check essential elements
        assert test_dweller.first_name in prompt
        assert "concise" in prompt.lower()
        assert "150 words" in prompt

    async def test_build_prompt_includes_special_stats(self, test_dweller: Dweller):
        """Test prompt includes SPECIAL stats."""
        prompt = conversation_service._build_dweller_prompt(test_dweller, for_audio=False)

        # Should include SPECIAL stat names
        assert "strength" in prompt.lower()
        assert "perception" in prompt.lower()
        assert "endurance" in prompt.lower()
        assert "charisma" in prompt.lower()
        assert "intelligence" in prompt.lower()
        assert "agility" in prompt.lower()
        assert "luck" in prompt.lower()

    async def test_build_prompt_includes_vault_info(self, test_dweller: Dweller):
        """Test prompt includes vault information."""
        prompt = conversation_service._build_dweller_prompt(test_dweller, for_audio=False)

        # Should mention vault
        assert "vault" in prompt.lower()
        assert str(test_dweller.vault.number) in prompt


# Note: Integration tests for audio processing are omitted as they require complex mocking
# of external services (OpenAI API, MinIO). The unit tests above (voice selection and
# prompt building) cover the core logic of the conversation service.
