"""Test vault objective assignment on creation.

This validates that _assign_initial_objectives correctly filters
objectives by their `category` field (not the `challenge` field).
"""
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.user import User
from app.services.vault_service import VaultService
from app.tests.factory.vaults import create_fake_vault
from app import crud
from app.schemas.vault import VaultCreateWithUserID


pytestmark = pytest.mark.asyncio(scope="function")


async def _seed_objective(async_session: AsyncSession, challenge: str, category: str, objective_type: str) -> Objective:
    """Helper to seed a test objective."""
    obj = Objective(
        challenge=challenge,
        reward="Test Reward",
        category=category,
        objective_type=objective_type,
        target_entity={"entity": "test"},
        target_amount=5,
    )
    async_session.add(obj)
    await async_session.flush()
    return obj


async def _create_vault(async_session: AsyncSession, user: User):
    """Helper to create a simple vault for a user."""
    from app.models.vault import Vault
    vault_data = VaultCreateWithUserID(**create_fake_vault(), user_id=user.id)
    return await crud.vault.create(async_session, vault_data)


class TestVaultObjectiveAssignment:
    """Tests for vault objective assignment logic."""

    async def test_assigns_daily_and_weekly_to_standard_vault(self, async_session: AsyncSession, superuser: User):
        """Standard vault gets 1 daily + 1 weekly objective when matching objectives exist."""
        daily = await _seed_objective(async_session, "Collect 250 Food", "daily", "collect")
        weekly = await _seed_objective(async_session, "Build 5 Rooms", "weekly", "build")
        await async_session.commit()

        vault = await _create_vault(async_session, superuser)

        service = VaultService()
        await service._assign_initial_objectives(async_session, vault.id, is_boosted=False)

        links = (
            await async_session.execute(
                select(VaultObjectiveProgressLink).where(VaultObjectiveProgressLink.vault_id == vault.id)
            )
        ).scalars().all()

        assert len(links) == 2
        linked_ids = {l.objective_id for l in links}
        assert daily.id in linked_ids
        assert weekly.id in linked_ids

    async def test_assigns_achievements_for_boosted_vault(self, async_session: AsyncSession, superuser: User):
        """Boosted vault gets extra achievement objectives."""
        await _seed_objective(async_session, "Collect 250 Food", "daily", "collect")
        await _seed_objective(async_session, "Build 5 Rooms", "weekly", "build")
        for i in range(5):
            await _seed_objective(async_session, f"Achievement {i}", "achievement", "build")
        await async_session.commit()

        vault = await _create_vault(async_session, superuser)

        service = VaultService()
        await service._assign_initial_objectives(async_session, vault.id, is_boosted=True)

        links = (
            await async_session.execute(
                select(VaultObjectiveProgressLink).where(VaultObjectiveProgressLink.vault_id == vault.id)
            )
        ).scalars().all()

        assert len(links) == 7  # 1 daily + 1 weekly + 5 achievement

    async def test_skips_when_no_objectives(self, async_session: AsyncSession, superuser: User):
        """No crash when no objectives exist — assigns nothing."""
        vault = await _create_vault(async_session, superuser)

        service = VaultService()
        await service._assign_initial_objectives(async_session, vault.id, is_boosted=False)

        links = (
            await async_session.execute(
                select(VaultObjectiveProgressLink).where(VaultObjectiveProgressLink.vault_id == vault.id)
            )
        ).scalars().all()

        assert len(links) == 0

    async def test_filters_by_category_not_challenge(self, async_session: AsyncSession, superuser: User):
        """Regression: uses category= filter, so objectives whose challenge lacks
        'daily'/'weekly' substring are still found if category is correct."""
        obj = await _seed_objective(async_session, "Collect caps", "daily", "collect")
        await async_session.commit()

        vault = await _create_vault(async_session, superuser)

        service = VaultService()
        await service._assign_initial_objectives(async_session, vault.id, is_boosted=False)

        links = (
            await async_session.execute(
                select(VaultObjectiveProgressLink).where(VaultObjectiveProgressLink.vault_id == vault.id)
            )
        ).scalars().all()

        assert len(links) == 1
        assert links[0].objective_id == obj.id
