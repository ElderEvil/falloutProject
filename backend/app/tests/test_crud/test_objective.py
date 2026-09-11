"""Tests for objective persistence and settlement."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.common import ObjectiveCategoryEnum
from app.schemas.objective import ObjectiveCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_update_objective_progress(async_session: AsyncSession) -> None:
    """Test updating progress for an objective."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create objective
    objective_data = ObjectiveCreate(
        challenge="Collect 10 weapons", reward="500 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    objective = await crud.objective_crud.create_for_vault(
        db_session=async_session, vault_id=vault.id, obj_in=objective_data
    )

    initial_caps = vault.bottle_caps
    # Update progress to 5 (with total=1 by default, this will auto-complete since 5 >= 1)
    link = await reward_service.settle_objective_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=5
    )

    assert link.progress == 5
    # With total=1 by default, progress=5 should auto-complete since 5 >= 1
    assert link.is_completed is True
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 500


@pytest.mark.asyncio
async def test_complete_objective(async_session: AsyncSession) -> None:
    """Test marking an objective as completed."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create objective
    objective_data = ObjectiveCreate(
        challenge="Collect 100 food", reward="50 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    objective = await crud.objective_crud.create_for_vault(
        db_session=async_session, vault_id=vault.id, obj_in=objective_data
    )
    initial_caps = vault.bottle_caps

    # Complete objective
    completed_objective = await reward_service.settle_objective_completion(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id
    )

    assert completed_objective.id == objective.id
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50

    # Verify completion via get_multi_for_vault
    objectives = await crud.objective_crud.get_multi_for_vault(
        db_session=async_session, vault_id=vault.id, skip=0, limit=100
    )

    assert len(objectives) == 1
    assert objectives[0].is_completed is True


@pytest.mark.asyncio
async def test_complete_nonexistent_objective_creates_link(async_session: AsyncSession) -> None:
    """Test that completing an objective that wasn't assigned creates a new link."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create objective WITHOUT using create_for_vault (no link created)
    objective_data = ObjectiveCreate(
        challenge="Collect 7 junk", reward="600 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    objective = await crud.objective_crud.create(async_session, obj_in=objective_data)

    # Complete objective (should create link automatically)
    completed_objective = await reward_service.settle_objective_completion(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id
    )

    assert completed_objective.id == objective.id

    # Verify the link was created
    objectives = await crud.objective_crud.get_multi_for_vault(
        db_session=async_session, vault_id=vault.id, skip=0, limit=100
    )

    assert len(objectives) == 1
    assert objectives[0].is_completed is True
    assert objectives[0].challenge == "Collect 7 junk"


@pytest.mark.asyncio
async def test_update_progress_creates_link_if_not_exists(async_session: AsyncSession) -> None:
    """Test that updating progress for an objective creates link if it doesn't exist."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create objective WITHOUT link
    objective_data = ObjectiveCreate(
        challenge="Collect 100 water", reward="50 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    objective = await crud.objective_crud.create(async_session, obj_in=objective_data)

    initial_caps = vault.bottle_caps
    # Update progress (should create and complete the link)
    link = await reward_service.settle_objective_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=3
    )

    assert link.vault_id == vault.id
    assert link.objective_id == objective.id
    assert link.progress == 3
    assert link.is_completed is True
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50


@pytest.mark.asyncio
async def test_assign_initial_objectives(async_session: AsyncSession) -> None:
    """Starter objectives are selected and linked in the CRUD layer."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    for category in (ObjectiveCategoryEnum.DAILY, ObjectiveCategoryEnum.WEEKLY, ObjectiveCategoryEnum.ACHIEVEMENT):
        await crud.objective_crud.create(
            async_session,
            obj_in=ObjectiveCreate(
                challenge=f"Starter {category.value}",
                reward="10 caps",
                category=category,
                objective_type="collect",
            ),
        )

    assigned_count = await crud.objective_crud.assign_initial(async_session, vault.id, is_boosted=True)
    assigned = await crud.objective_crud.get_multi_for_vault(async_session, vault.id)

    assert assigned_count == 3
    assert {objective.category for objective in assigned} == {
        ObjectiveCategoryEnum.DAILY,
        ObjectiveCategoryEnum.WEEKLY,
        ObjectiveCategoryEnum.ACHIEVEMENT,
    }


@pytest.mark.asyncio
async def test_assign_initial_rolls_back_on_db_error() -> None:
    """A DB failure assigns nothing but leaves the session usable."""
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from sqlalchemy.exc import SQLAlchemyError

    db_session = AsyncMock()
    db_session.execute = AsyncMock(side_effect=SQLAlchemyError("DB down"))

    assigned = await crud.objective_crud.assign_initial(db_session, uuid4(), is_boosted=False)

    assert assigned == 0
    db_session.rollback.assert_awaited_once()
