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
async def test_dweller_not_found(async_session: AsyncSession):
    with pytest.raises(ResourceNotFoundException):
        await apply_chat_happiness(async_session, UUID("00000000-0000-0000-0000-000000000000"), delta=5)


def test_neutral_delta_is_zero():
    assert compute_neutral_delta() == 0


def test_dweller_bounds():
    assert DWELLER_HAPPINESS_MIN == 10
    assert DWELLER_HAPPINESS_MAX == 100


def test_vault_bounds():
    assert VAULT_HAPPINESS_MIN == 0
    assert VAULT_HAPPINESS_MAX == 100
