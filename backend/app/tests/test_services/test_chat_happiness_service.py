"""Tests for chat happiness service."""

import pytest
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.chat_happiness_service import (
    DWELLER_HAPPINESS_MAX,
    DWELLER_HAPPINESS_MIN,
    VAULT_HAPPINESS_MAX,
    VAULT_HAPPINESS_MIN,
    apply_chat_happiness,
    compute_neutral_delta,
)
from app.utils.exceptions import ResourceNotFoundException


@pytest.mark.asyncio
class TestApplyChatHappiness:
    """Test apply_chat_happiness function."""

    async def test_dweller_not_found(
        self,
        async_session: AsyncSession,
    ):
        """Test that ResourceNotFoundException is raised for invalid dweller."""
        fake_dweller_id = UUID4("00000000-0000-0000-0000-000000000000")

        with pytest.raises(ResourceNotFoundException):
            await apply_chat_happiness(
                async_session,
                fake_dweller_id,
                delta=5,
            )


@pytest.mark.asyncio
class TestComputeNeutralDelta:
    """Test compute_neutral_delta function."""

    async def test_returns_zero(self):
        """Test that neutral fallback returns 0."""
        result = compute_neutral_delta()
        assert result == 0


@pytest.mark.asyncio
class TestHappinessBoundsConstants:
    """Test that constants are correct."""

    async def test_dweller_bounds(self):
        """Test dweller happiness bounds."""
        assert DWELLER_HAPPINESS_MIN == 10
        assert DWELLER_HAPPINESS_MAX == 100

    async def test_vault_bounds(self):
        """Test vault happiness bounds."""
        assert VAULT_HAPPINESS_MIN == 0
        assert VAULT_HAPPINESS_MAX == 100
