"""Tests for objective persistence and settlement."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import ObjectiveCategoryEnum
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
    # Update progress beyond the target; a claim is still required.
    link = await reward_service.settle_objective_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=5
    )

    assert link.progress == 5
    # Progress reaching the target makes the reward claimable, without paying it.
    assert link.is_completed is False
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps


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
    # Update progress (should create a claimable link).
    link = await reward_service.settle_objective_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=3
    )

    assert link.vault_id == vault.id
    assert link.objective_id == objective.id
    assert link.progress == 3
    assert link.is_completed is False
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps


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
async def test_vault_read_exposes_template_key(async_session: AsyncSession) -> None:
    """The vault read carries template_key, the identity onboarding keys on."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    await crud.objective_crud.create(
        async_session,
        obj_in=ObjectiveCreate(
            challenge="Match a dweller to their room",
            reward="50 caps",
            category=ObjectiveCategoryEnum.STARTER,
            objective_type="assign_correct",
            target_entity={},
            target_amount=1,
            sequence=0,
            description="Match a dweller's best SPECIAL to the room.",
            template_key="starter:assign a dweller correctly",
        ),
    )

    await crud.objective_crud.assign_initial(async_session, vault.id, is_boosted=False)
    read = await crud.objective_crud.get_multi_for_vault(async_session, vault.id)

    assert {objective.template_key for objective in read} == {"starter:assign a dweller correctly"}


@pytest.mark.asyncio
async def test_assign_initial_seeds_starter_arc_for_standard_vault(async_session: AsyncSession) -> None:
    """A standard vault gets the full starter arc, ordered by sequence."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    for sequence in range(8):
        await crud.objective_crud.create(
            async_session,
            obj_in=ObjectiveCreate(
                challenge=f"Starter step {sequence}",
                reward="10 caps",
                category=ObjectiveCategoryEnum.STARTER,
                objective_type="collect",
                target_entity={"resource_type": "caps"},
                target_amount=1,
                sequence=sequence,
                description=f"Step {sequence}",
            ),
        )

    assigned_count = await crud.objective_crud.assign_initial(async_session, vault.id, is_boosted=False)
    assigned = await crud.objective_crud.get_multi_for_vault(async_session, vault.id)

    starter = [o for o in assigned if o.category == ObjectiveCategoryEnum.STARTER]
    assert assigned_count == 8
    assert len(starter) == 8
    assert sorted(o.sequence for o in starter) == list(range(8))
    assert all(o.description is not None for o in starter)


@pytest.mark.asyncio
async def test_assign_initial_skips_starter_arc_for_boosted_vault(async_session: AsyncSession) -> None:
    """A boosted vault skips the starter arc (the Office is already seeded)."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    for sequence in range(8):
        await crud.objective_crud.create(
            async_session,
            obj_in=ObjectiveCreate(
                challenge=f"Starter step {sequence}",
                reward="10 caps",
                category=ObjectiveCategoryEnum.STARTER,
                objective_type="collect",
                target_entity={"resource_type": "caps"},
                target_amount=1,
                sequence=sequence,
            ),
        )

    assigned_count = await crud.objective_crud.assign_initial(async_session, vault.id, is_boosted=True)
    assigned = await crud.objective_crud.get_multi_for_vault(async_session, vault.id)

    assert assigned_count == 0
    assert all(o.category != ObjectiveCategoryEnum.STARTER for o in assigned)


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


@pytest.mark.asyncio
async def test_completed_link_progress_not_mutated(async_session: AsyncSession) -> None:
    """Settling progress on a completed link returns it untouched (no progress rewrite)."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    objective = await crud.objective_crud.create(
        async_session,
        obj_in=ObjectiveCreate(
            challenge="Collect 10 weapons", reward="500 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT
        ),
    )

    link = await reward_service.settle_objective_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=5
    )
    await reward_service.claim_objective_reward(async_session, objective.id, vault.id)
    assert link.is_completed is True
    assert link.progress == 5

    relink = await reward_service.settle_objective_progress(
        db_session=async_session, objective_id=objective.id, vault_id=vault.id, progress=1
    )
    assert relink.progress == 5
    assert relink.is_completed is True


async def test_reset_reads_latest_progress_even_when_link_is_cached(async_session, vault):
    """A reset must re-read earned progress rather than delete a stale unfinished row."""
    from sqlalchemy import update

    from app.models.objective import Objective
    from app.models.vault_objective import VaultObjectiveProgressLink
    from app.services.progression.objectives.assignment import ObjectiveAssignmentService

    objective = Objective(challenge="Earn one", reward="50 caps", category="daily")
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, total=1)
    async_session.add_all([objective, link])
    await async_session.commit()
    await async_session.execute(
        update(VaultObjectiveProgressLink)
        .where(VaultObjectiveProgressLink.objective_id == objective.id)
        .values(progress=1)
        .execution_options(synchronize_session=False)
    )
    await async_session.commit()
    assert link.progress == 0  # Identity map is deliberately stale.
    assert await ObjectiveAssignmentService(async_session).clear_daily_objectives(vault.id) == 0
    await async_session.refresh(link)
    assert link.progress == 1
    assert not link.is_completed
