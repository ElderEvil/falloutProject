"""Tests for PrerequisiteService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.dweller import dweller as dweller_crud
from app.crud.objective import objective as objective_crud
from app.crud.quest import quest as quest_crud
from app.crud.room import room as room_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.dweller import DwellerCreate
from app.schemas.objective import ObjectiveCreate
from app.schemas.quest import QuestCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.prerequisite_service import prerequisite_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_validate_level_requirement_met(async_session: AsyncSession) -> None:
    """Test level requirement when dweller meets level."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create dweller at level 10
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=10, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    result = await prerequisite_service.validate_level_requirement(async_session, vault.id, {"level": 10, "count": 1})
    assert result is True


@pytest.mark.asyncio
async def test_validate_level_requirement_not_met(async_session: AsyncSession) -> None:
    """Test level requirement when dweller below required level."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create dweller at level 5
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=5, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    result = await prerequisite_service.validate_level_requirement(async_session, vault.id, {"level": 10, "count": 1})
    assert result is False


@pytest.mark.asyncio
async def test_validate_dweller_count_requirement_met(async_session: AsyncSession) -> None:
    """Test dweller count requirement with enough dwellers."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create 5 dwellers
    for i in range(5):
        dweller = Dweller(first_name=f"Test{i}", gender="male", rarity="common", level=1, vault_id=vault.id)
        async_session.add(dweller)
    await async_session.commit()

    result = await prerequisite_service.validate_dweller_count_requirement(async_session, vault.id, {"count": 5})
    assert result is True


@pytest.mark.asyncio
async def test_validate_dweller_count_requirement_not_met(async_session: AsyncSession) -> None:
    """Test dweller count requirement with not enough dwellers."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create 2 dwellers
    for i in range(2):
        dweller = Dweller(first_name=f"Test{i}", gender="male", rarity="common", level=1, vault_id=vault.id)
        async_session.add(dweller)
    await async_session.commit()

    result = await prerequisite_service.validate_dweller_count_requirement(async_session, vault.id, {"count": 5})
    assert result is False


@pytest.mark.asyncio
async def test_validate_quest_completed_requirement_met(async_session: AsyncSession) -> None:
    """Test quest completed requirement when quest is done."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create prerequisite quest
    prereq_quest = Quest(
        title="Prerequisite Quest",
        short_description="Test",
        long_description="Test",
        requirements="None",
        rewards="None",
        quest_type="side",
    )
    async_session.add(prereq_quest)
    await async_session.commit()
    await async_session.refresh(prereq_quest)

    # Mark as completed for vault
    completion = VaultQuestCompletionLink(
        vault_id=vault.id, quest_id=prereq_quest.id, is_completed=True, is_visible=True
    )
    async_session.add(completion)
    await async_session.commit()

    result = await prerequisite_service.validate_quest_completed_requirement(
        async_session, vault.id, {"quest_id": str(prereq_quest.id)}
    )
    assert result is True


@pytest.mark.asyncio
async def test_validate_quest_completed_requirement_not_met(async_session: AsyncSession) -> None:
    """Test quest completed requirement when quest not done."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create prerequisite quest
    prereq_quest = Quest(
        title="Prerequisite Quest",
        short_description="Test",
        long_description="Test",
        requirements="None",
        rewards="None",
        quest_type="side",
    )
    async_session.add(prereq_quest)
    await async_session.commit()
    await async_session.refresh(prereq_quest)

    # Not marking as completed

    result = await prerequisite_service.validate_quest_completed_requirement(
        async_session, vault.id, {"quest_id": str(prereq_quest.id)}
    )
    assert result is False


@pytest.mark.asyncio
async def test_can_start_quest_all_requirements_met(async_session: AsyncSession) -> None:
    """Test can_start_quest when all requirements are met."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create quest with level requirement
    quest = Quest(
        title="Test Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="Level 1 dweller",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    # Add requirement
    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type=RequirementType.LEVEL,
        requirement_data={"level": 1, "count": 1},
        is_mandatory=True,
    )
    async_session.add(req)
    await async_session.commit()
    await async_session.refresh(quest)

    # Create dweller meeting requirement
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=5, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    can_start, missing = await prerequisite_service.can_start_quest(async_session, vault.id, quest)

    assert can_start is True
    assert len(missing) == 0


@pytest.mark.asyncio
async def test_can_start_quest_missing_requirements(async_session: AsyncSession) -> None:
    """Test can_start_quest when requirements are missing."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create quest with level requirement
    quest = Quest(
        title="Test Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="Level 50 dweller",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    # Add requirement
    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type=RequirementType.LEVEL,
        requirement_data={"level": 50, "count": 1},
        is_mandatory=True,
    )
    async_session.add(req)
    await async_session.commit()
    await async_session.refresh(quest)

    # Create low-level dweller
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    can_start, missing = await prerequisite_service.can_start_quest(async_session, vault.id, quest)

    assert can_start is False
    assert len(missing) > 0


@pytest.mark.asyncio
async def test_get_missing_requirements(async_session: AsyncSession) -> None:
    """Test get_missing_requirements returns human-readable descriptions."""
    user_data = create_fake_user()
    user = await async_session.get_user_service().create(async_session, UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await async_session.get_vault_service().create(
        async_session, VaultCreateWithUserID(**vault_data, user_id=user.id)
    )

    # Create quest
    quest = Quest(
        title="Test Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="Level 100 dweller",
        rewards="1000 caps",
        quest_type="main",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    # Add unmet requirement
    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type=RequirementType.LEVEL,
        requirement_data={"level": 100, "count": 1},
        is_mandatory=True,
    )
    async_session.add(req)
    await async_session.commit()
    await async_session.refresh(quest)

    missing = await prerequisite_service.get_missing_requirements(async_session, vault.id, quest)

    assert len(missing) > 0
    assert any("level" in desc.lower() for desc in missing)
