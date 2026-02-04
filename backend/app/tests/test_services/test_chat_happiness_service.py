"""Tests for chat happiness service."""

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.chat_happiness_service import (
    DWELLER_HAPPINESS_MAX,
    DWELLER_HAPPINESS_MIN,
    VAULT_HAPPINESS_MAX,
    VAULT_HAPPINESS_MIN,
    apply_chat_happiness,
    compute_neutral_delta,
)
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.exceptions import ResourceNotFoundException


@pytest_asyncio.fixture(name="test_dweller")
async def test_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a test dweller with neutral happiness."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Chat",
            "last_name": "Tester",
            "happiness": 50,
            "health": 100,
            "max_health": 100,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="second_dweller")
async def second_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a second dweller for vault average tests."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Second",
            "last_name": "Dweller",
            "happiness": 70,
            "health": 100,
            "max_health": 100,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
class TestApplyChatHappiness:
    """Test apply_chat_happiness function."""

    async def test_positive_delta(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_dweller: Dweller,
    ):
        """Test applying a positive happiness delta."""
        initial_happiness = test_dweller.happiness

        new_dweller_happiness, _new_vault_happiness = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=5,
        )

        # Dweller happiness should increase
        assert new_dweller_happiness == initial_happiness + 5

        # Refresh from DB to verify persistence
        await async_session.refresh(test_dweller)
        assert test_dweller.happiness == new_dweller_happiness

        # Vault happiness should be updated (single dweller = same as dweller happiness)
        await async_session.refresh(vault)
        assert vault.happiness == new_dweller_happiness

    async def test_negative_delta(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed to create dweller
        test_dweller: Dweller,
    ):
        """Test applying a negative happiness delta."""
        initial_happiness = test_dweller.happiness

        new_dweller_happiness, _new_vault_happiness = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=-5,
        )

        # Dweller happiness should decrease
        assert new_dweller_happiness == initial_happiness - 5

        await async_session.refresh(test_dweller)
        assert test_dweller.happiness == new_dweller_happiness

    async def test_zero_delta(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed to create dweller
        test_dweller: Dweller,
    ):
        """Test applying a zero (neutral) delta."""
        initial_happiness = test_dweller.happiness

        new_dweller_happiness, _new_vault_happiness = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=0,
        )

        # Happiness should remain unchanged
        assert new_dweller_happiness == initial_happiness

    async def test_clamp_upper_bound(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed to create dweller
        test_dweller: Dweller,
    ):
        """Test that happiness is clamped to 100."""
        # Set dweller to high happiness
        test_dweller.happiness = 95
        async_session.add(test_dweller)
        await async_session.commit()

        new_dweller_happiness, _ = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=10,
        )

        # Should be clamped to 100
        assert new_dweller_happiness == DWELLER_HAPPINESS_MAX
        assert new_dweller_happiness == 100

    async def test_clamp_lower_bound(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed to create dweller
        test_dweller: Dweller,
    ):
        """Test that happiness is clamped to 10 (not 0)."""
        # Set dweller to low happiness
        test_dweller.happiness = 15
        async_session.add(test_dweller)
        await async_session.commit()

        new_dweller_happiness, _ = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=-10,
        )

        # Should be clamped to 10 (dweller minimum)
        assert new_dweller_happiness == DWELLER_HAPPINESS_MIN
        assert new_dweller_happiness == 10

    async def test_vault_happiness_average(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_dweller: Dweller,
        second_dweller: Dweller,  # noqa: ARG002 - fixture needed for vault average calc
    ):
        """Test that vault happiness is calculated as average of all dwellers."""
        # test_dweller: 50, second_dweller: 70
        # Apply +10 to test_dweller -> 60
        # Expected vault average: (60 + 70) / 2 = 65

        new_dweller_happiness, new_vault_happiness = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=10,
        )

        assert new_dweller_happiness == 60
        assert new_vault_happiness == 65  # int((60 + 70) / 2)

        await async_session.refresh(vault)
        assert vault.happiness == 65

    async def test_vault_happiness_truncation(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed for vault context
        test_dweller: Dweller,
        second_dweller: Dweller,  # noqa: ARG002 - fixture needed for vault average calc
    ):
        """Test that vault happiness uses truncation (int), not rounding."""
        # test_dweller: 50, second_dweller: 70
        # Apply +1 to test_dweller -> 51
        # Expected vault average: (51 + 70) / 2 = 60.5 -> truncated to 60

        new_dweller_happiness, new_vault_happiness = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=1,
        )

        assert new_dweller_happiness == 51
        assert new_vault_happiness == 60  # int((51 + 70) / 2) = int(60.5) = 60

    async def test_dweller_not_found(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed for session context
    ):
        """Test that ResourceNotFoundException is raised for invalid dweller."""
        fake_dweller_id = UUID4("00000000-0000-0000-0000-000000000000")

        with pytest.raises(ResourceNotFoundException):
            await apply_chat_happiness(
                async_session,
                fake_dweller_id,
                delta=5,
            )

    async def test_large_positive_delta(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed to create dweller
        test_dweller: Dweller,
    ):
        """Test applying a delta larger than typical range."""
        new_dweller_happiness, _ = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=100,  # Way beyond typical -10 to +10
        )

        # Should still clamp to max
        assert new_dweller_happiness == DWELLER_HAPPINESS_MAX

    async def test_large_negative_delta(
        self,
        async_session: AsyncSession,
        vault: Vault,  # noqa: ARG002 - fixture needed to create dweller
        test_dweller: Dweller,
    ):
        """Test applying a large negative delta."""
        new_dweller_happiness, _ = await apply_chat_happiness(
            async_session,
            test_dweller.id,
            delta=-100,  # Way beyond typical range
        )

        # Should clamp to min
        assert new_dweller_happiness == DWELLER_HAPPINESS_MIN


@pytest.mark.asyncio
class TestComputeNeutralDelta:
    """Test compute_neutral_delta function."""

    async def test_returns_zero(self):
        """Test that neutral fallback returns 0."""
        result = compute_neutral_delta()
        assert result == 0

    async def test_is_integer(self):
        """Test that result is an integer."""
        result = compute_neutral_delta()
        assert isinstance(result, int)


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
