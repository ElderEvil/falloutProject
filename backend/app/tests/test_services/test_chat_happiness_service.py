from uuid import UUID

import pytest
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
    async def test_dweller_not_found(
        self,
        async_session: AsyncSession,
    ):
        fake_dweller_id = UUID("00000000-0000-0000-0000-000000000000")

        with pytest.raises(ResourceNotFoundException):
            await apply_chat_happiness(
                async_session,
                fake_dweller_id,
                delta=5,
            )


@pytest.mark.asyncio
class TestComputeNeutralDelta:
    async def test_returns_zero(self):
        result = compute_neutral_delta()
        assert result == 0


@pytest.mark.asyncio
class TestHappinessBoundsConstants:
    async def test_dweller_bounds(self):
        assert DWELLER_HAPPINESS_MIN == 10
        assert DWELLER_HAPPINESS_MAX == 100

    async def test_vault_bounds(self):
        assert VAULT_HAPPINESS_MIN == 0
        assert VAULT_HAPPINESS_MAX == 100
