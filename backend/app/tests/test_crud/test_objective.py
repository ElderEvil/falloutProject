"""Tests for objective CRUD operations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.common import ObjectiveCategoryEnum
from app.schemas.objective import ObjectiveCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_create_objective(async_session: AsyncSession) -> None:
    """Test creating an objective."""
    objective_data = ObjectiveCreate(
        challenge="Collect 10 weapons", reward="100 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    objective = await crud.objective_crud.create(async_session, obj_in=objective_data)
    assert objective.id
    assert objective.challenge == "Collect 10 weapons"
    assert objective.reward == "100 caps"


@pytest.mark.asyncio
async def test_read_objective(async_session: AsyncSession) -> None:
    """Test reading an objective."""
    objective_data = ObjectiveCreate(
        challenge="Assign 5 dwellers", reward="50 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    objective = await crud.objective_crud.create(async_session, obj_in=objective_data)
    read_objective = await crud.objective_crud.get(async_session, id=objective.id)
    assert read_objective
    assert read_objective.id == objective.id
    assert read_objective.challenge == objective.challenge


@pytest.mark.asyncio
async def test_create_objective_for_vault(async_session: AsyncSession) -> None:
    """Test creating an objective for a specific vault."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create objective for vault
    objective_data = ObjectiveCreate(
        challenge="Collect 3 stimpaks", reward="70 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    objective = await crud.objective_crud.create_for_vault(
        db_session=async_session, vault_id=vault.id, obj_in=objective_data
    )

    assert objective.id
    assert objective.challenge == "Collect 3 stimpaks"
    assert objective.reward == "70 caps"


@pytest.mark.asyncio
async def test_get_multi_for_vault(async_session: AsyncSession) -> None:
    """Test getting multiple objectives for a vault with progress tracking."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create multiple objectives for vault
    objective1_data = ObjectiveCreate(
        challenge="Collect 5 outfits", reward="100 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
    )
    await crud.objective_crud.create_for_vault(db_session=async_session, vault_id=vault.id, obj_in=objective1_data)

    objective2_data = ObjectiveCreate(
        challenge="Assign 10 dwellers", reward="200 caps", category=ObjectiveCategoryEnum.DAILY
    )
    await crud.objective_crud.create_for_vault(db_session=async_session, vault_id=vault.id, obj_in=objective2_data)

    # Get objectives for vault
    objectives = await crud.objective_crud.get_multi_for_vault(
        db_session=async_session, vault_id=vault.id, skip=0, limit=100
    )

    assert len(objectives) == 2
    challenges = {obj.challenge for obj in objectives}
    assert "Collect 5 outfits" in challenges
    assert "Assign 10 dwellers" in challenges

    # Check that progress tracking fields are present
    for obj in objectives:
        assert hasattr(obj, "progress")
        assert hasattr(obj, "total")
        assert hasattr(obj, "is_completed")
        assert obj.progress == 0  # Default progress
        assert obj.total == 1  # Default total
        assert obj.is_completed is False  # Not completed by default


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

    # Update progress to 5 (with total=1 by default, this will auto-complete since 5 >= 1)
    link = await crud.objective_crud.update_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=5
    )

    assert link.progress == 5
    # With total=1 by default, progress=5 should auto-complete since 5 >= 1
    assert link.is_completed is True


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

    # Complete objective
    completed_objective = await crud.objective_crud.complete(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id
    )

    assert completed_objective.id == objective.id

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
    completed_objective = await crud.objective_crud.complete(
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

    # Update progress (should create link)
    link = await crud.objective_crud.update_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=3
    )

    assert link.vault_id == vault.id
    assert link.objective_id == objective.id
    assert link.progress == 3
    assert link.is_completed is False
