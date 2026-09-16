"""Tests for death service logic."""

import logging
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import DeathCauseEnum, DwellerStatusEnum
from app.schemas.dweller import DwellerCreate
from app.services.family.death_service import death_service
from app.tests.factory.dwellers import create_fake_dweller


@pytest_asyncio.fixture(name="alive_dweller")
async def alive_dweller_fixture(
    async_session: AsyncSession,
    vault: Vault,
) -> Dweller:
    """Create a living dweller."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Alive",
            "last_name": "Dweller",
            "status": DwellerStatusEnum.IDLE.value,
            "is_dead": False,
            "is_permanently_dead": False,
            "health": 100,
            "max_health": 100,
            "level": 5,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="dead_dweller")
async def dead_dweller_fixture(
    async_session: AsyncSession,
    vault: Vault,
) -> Dweller:
    """Create a dead but revivable dweller."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Dead",
            "last_name": "Dweller",
            "status": DwellerStatusEnum.DEAD.value,
            "is_dead": True,
            "is_permanently_dead": False,
            "death_timestamp": datetime.utcnow() - timedelta(days=2),
            "death_cause": DeathCauseEnum.HEALTH.value,
            "epitaph": "Test epitaph",
            "health": 0,
            "max_health": 100,
            "level": 5,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="permanently_dead_dweller")
async def permanently_dead_dweller_fixture(
    async_session: AsyncSession,
    vault: Vault,
) -> Dweller:
    """Create a permanently dead dweller."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Permanent",
            "last_name": "Dead",
            "status": DwellerStatusEnum.DEAD.value,
            "is_dead": True,
            "is_permanently_dead": True,
            "death_timestamp": datetime.utcnow() - timedelta(days=10),
            "death_cause": DeathCauseEnum.COMBAT.value,
            "epitaph": "Gone forever",
            "health": 0,
            "max_health": 100,
            "level": 10,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
class TestDeathService:
    """Test death service functionality."""

    async def test_mark_as_dead_already_dead_raises(
        self,
        async_session: AsyncSession,
        dead_dweller: Dweller,
    ):
        """Test that marking already dead dweller raises exception."""
        from app.utils.exceptions import ContentNoChangeException

        with pytest.raises(ContentNoChangeException):
            await death_service.mark_as_dead(
                async_session,
                dead_dweller,
                DeathCauseEnum.HEALTH,
            )

    async def test_revive_dweller_success(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
    ):
        """Test successful dweller revival."""
        # Give vault enough caps
        vault.bottle_caps = 10000
        async_session.add(vault)
        await async_session.commit()
        owner = await crud.user.get(async_session, vault.user_id)

        result = await death_service.revive_dweller(
            async_session,
            dead_dweller.id,
            owner,
        )

        assert result.dweller.is_dead is False
        assert result.dweller.status == DwellerStatusEnum.IDLE
        assert result.dweller.death_timestamp is None
        assert result.dweller.death_cause is None
        assert result.dweller.health > 0
        assert result.caps_spent == death_service.get_revival_cost(dead_dweller.level)
        assert result.remaining_caps == 10000 - result.caps_spent

    async def test_revive_rejects_foreign_vault_owner(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
    ):
        """A user who does not own the vault cannot revive, and nothing changes."""
        from app.schemas.user import UserCreate
        from app.utils.exceptions import AccessDeniedException

        vault.bottle_caps = 10000
        async_session.add(vault)
        await async_session.commit()
        intruder = await crud.user.create(
            db_session=async_session,
            obj_in=UserCreate(username="intruder", email="intruder@example.com", password="testpass123"),
        )

        with pytest.raises(AccessDeniedException):
            await death_service.revive_dweller(async_session, dead_dweller.id, intruder)

        await async_session.refresh(dead_dweller)
        await async_session.refresh(vault)
        assert dead_dweller.is_dead is True
        assert vault.bottle_caps == 10000

    async def test_build_revival_quote_matches_cost_and_affordability(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
    ):
        """The quote reuses the single cost path and reports affordability."""
        vault.bottle_caps = dead_dweller.level * 10
        async_session.add(vault)
        await async_session.commit()
        owner = await crud.user.get(async_session, vault.user_id)

        quote = await death_service.build_revival_quote(async_session, dead_dweller.id, owner)

        assert quote.revival_cost == death_service.get_revival_cost(dead_dweller.level)
        assert quote.vault_caps == vault.bottle_caps
        assert quote.can_afford == (vault.bottle_caps >= quote.revival_cost)

    async def test_build_revival_quote_rejects_living_dweller(
        self,
        async_session: AsyncSession,
        vault: Vault,
        alive_dweller: Dweller,
    ):
        """A living dweller has no revival quote."""
        from app.utils.exceptions import ContentNoChangeException

        owner = await crud.user.get(async_session, vault.user_id)

        with pytest.raises(ContentNoChangeException):
            await death_service.build_revival_quote(async_session, alive_dweller.id, owner)

    async def test_build_revival_quote_rejects_foreign_vault_owner(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
    ):
        """The quote is not readable by a user who does not own the vault."""
        from app.schemas.user import UserCreate
        from app.utils.exceptions import AccessDeniedException

        intruder = await crud.user.create(
            db_session=async_session,
            obj_in=UserCreate(username="intruder2", email="intruder2@example.com", password="testpass123"),
        )

        with pytest.raises(AccessDeniedException):
            await death_service.build_revival_quote(async_session, dead_dweller.id, intruder)

    async def test_revive_dweller_insufficient_caps(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
    ):
        """Test revival fails with insufficient caps."""
        from app.utils.exceptions import InsufficientResourcesException

        # Set low caps
        vault.bottle_caps = 10
        async_session.add(vault)
        await async_session.commit()
        owner = await crud.user.get(async_session, vault.user_id)

        with pytest.raises(InsufficientResourcesException):
            await death_service.revive_dweller(
                async_session,
                dead_dweller.id,
                owner,
            )

    async def test_revive_permanently_dead_raises(
        self,
        async_session: AsyncSession,
        vault: Vault,
        permanently_dead_dweller: Dweller,
    ):
        """Test revival of permanently dead dweller raises exception."""
        from app.utils.exceptions import ContentNoChangeException

        vault.bottle_caps = 10000
        async_session.add(vault)
        await async_session.commit()
        owner = await crud.user.get(async_session, vault.user_id)

        with pytest.raises(ContentNoChangeException) as exc_info:
            await death_service.revive_dweller(
                async_session,
                permanently_dead_dweller.id,
                owner,
            )

        assert "permanently dead" in str(exc_info.value.detail).lower()

    async def test_revive_living_dweller_raises(
        self,
        async_session: AsyncSession,
        vault: Vault,
        alive_dweller: Dweller,
    ):
        """Test revival of living dweller raises exception."""
        from app.utils.exceptions import ContentNoChangeException

        vault.bottle_caps = 10000
        async_session.add(vault)
        await async_session.commit()
        owner = await crud.user.get(async_session, vault.user_id)

        with pytest.raises(ContentNoChangeException) as exc_info:
            await death_service.revive_dweller(
                async_session,
                alive_dweller.id,
                owner,
            )

        assert "not dead" in str(exc_info.value.detail).lower()

    async def test_get_revival_cost_tier_2(self):
        """Test revival cost for level 6-10 dwellers."""
        # Level 6: 450 caps
        assert death_service.get_revival_cost(6) == 450
        # Level 10: 750 caps
        assert death_service.get_revival_cost(10) == 750

    async def test_get_revival_cost_tier_3(self):
        """Test revival cost for level 11+ dwellers."""
        # Level 11: 1100 caps
        assert death_service.get_revival_cost(11) == 1100
        # Level 20: 2000 caps (capped)
        assert death_service.get_revival_cost(20) == 2000
        # Level 50: still 2000 caps (max)
        assert death_service.get_revival_cost(50) == 2000

    async def test_get_days_until_permanent_alive_dweller(
        self,
        alive_dweller: Dweller,
    ):
        """Test days calculation for alive dweller returns None."""
        result = death_service.get_days_until_permanent(alive_dweller)
        assert result is None

    async def test_get_days_until_permanent_recently_dead(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test days calculation for recently dead dweller."""
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Recent",
                "last_name": "Death",
                "is_dead": True,
                "is_permanently_dead": False,
                "death_timestamp": datetime.utcnow() - timedelta(days=2),
                "death_cause": DeathCauseEnum.HEALTH.value,
                "health": 0,
                "max_health": 100,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        days_left = death_service.get_days_until_permanent(dweller)
        assert days_left is not None
        assert 4 <= days_left <= 5

    async def test_check_and_mark_permanent_deaths(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test batch processing of expired deaths."""
        # Create dweller that died 10 days ago (past threshold)
        expired_data = create_fake_dweller()
        expired_data.update(
            {
                "first_name": "Expired",
                "last_name": "Death",
                "is_dead": True,
                "is_permanently_dead": False,
                "death_timestamp": datetime.utcnow() - timedelta(days=10),
                "death_cause": DeathCauseEnum.EXPLORATION.value,
                "health": 0,
                "max_health": 100,
            }
        )
        expired_in = DwellerCreate(**expired_data, vault_id=vault.id)
        expired_dweller = await crud.dweller.create(db_session=async_session, obj_in=expired_in)

        # Create dweller that died 2 days ago (not yet expired)
        recent_data = create_fake_dweller()
        recent_data.update(
            {
                "first_name": "Recent",
                "last_name": "Death",
                "is_dead": True,
                "is_permanently_dead": False,
                "death_timestamp": datetime.utcnow() - timedelta(days=2),
                "death_cause": DeathCauseEnum.INCIDENT.value,
                "health": 0,
                "max_health": 100,
            }
        )
        recent_in = DwellerCreate(**recent_data, vault_id=vault.id)
        recent_dweller = await crud.dweller.create(db_session=async_session, obj_in=recent_in)

        await async_session.commit()

        # Run the check
        count = await death_service.check_and_mark_permanent_deaths(async_session)
        await async_session.commit()

        # Should have marked 1 dweller as permanently dead
        assert count == 1

        # Refresh and verify
        await async_session.refresh(expired_dweller)
        await async_session.refresh(recent_dweller)

        assert expired_dweller.is_permanently_dead is True
        assert recent_dweller.is_permanently_dead is False

    async def test_get_death_statistics(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
        permanently_dead_dweller: Dweller,
    ):
        """Test getting death statistics for a user."""
        # First create profile for user if not exists
        from app.crud.user_profile import profile_crud

        existing_profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
        if not existing_profile:
            from app.schemas.user_profile import ProfileCreate

            profile_in = ProfileCreate(user_id=vault.user_id)
            await profile_crud.create(async_session, obj_in=profile_in)
            await async_session.commit()

        stats = await death_service.get_death_statistics(async_session, vault.user_id)

        assert "total_dwellers_born" in stats
        assert "total_dwellers_died" in stats
        assert "deaths_by_cause" in stats
        assert "revivable_count" in stats
        assert "permanently_dead_count" in stats

        # Should have 1 revivable and 1 permanent
        assert stats["revivable_count"] == 1
        assert stats["permanently_dead_count"] == 1


@pytest.mark.asyncio
class TestDeathCRUD:
    """Test death-related CRUD operations."""

    async def test_get_dead_dwellers(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
        permanently_dead_dweller: Dweller,
        alive_dweller: Dweller,
    ):
        """Test fetching dead (revivable) dwellers."""
        result = await crud.dweller.get_dead_dwellers(async_session, vault.id)

        # Should only include dead but not permanently dead
        assert len(result) == 1
        assert result[0].id == dead_dweller.id

    async def test_get_graveyard(
        self,
        async_session: AsyncSession,
        vault: Vault,
        dead_dweller: Dweller,
        permanently_dead_dweller: Dweller,
    ):
        """Test fetching graveyard (permanently dead) dwellers."""
        result = await crud.dweller.get_graveyard(async_session, vault.id)

        # Should only include permanently dead
        assert len(result) == 1
        assert result[0].id == permanently_dead_dweller.id
        assert result[0].is_permanently_dead is True
