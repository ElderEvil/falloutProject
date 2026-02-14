"""Tests for PrerequisiteService."""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.prerequisite_service import prerequisite_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_validate_level_requirement_met(async_session: AsyncSession) -> None:
    """Test level requirement when dweller meets level."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
        async_session, vault.id, {"quest_id": prereq_quest.id}
    )
    assert result is True


@pytest.mark.asyncio
async def test_validate_quest_completed_requirement_not_met(async_session: AsyncSession) -> None:
    """Test quest completed requirement when quest not done."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
        async_session, vault.id, {"quest_id": prereq_quest.id}
    )
    assert result is False


@pytest.mark.asyncio
async def test_can_start_quest_all_requirements_met(async_session: AsyncSession) -> None:
    """Test can_start_quest when all requirements are met."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
    await async_session.refresh(quest, ["quest_requirements"])

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
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
    await async_session.refresh(quest, ["quest_requirements"])

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
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

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
    await async_session.refresh(quest, ["quest_requirements"])

    missing = await prerequisite_service.get_missing_requirements(async_session, vault.id, quest)

    assert len(missing) > 0
    assert any("level" in desc.lower() for desc in missing)


@pytest.mark.asyncio
async def test_quest_start_blocked_when_requirements_not_met(
    async_client: AsyncClient, async_session: AsyncSession
) -> None:
    """Test that quest start endpoint returns 400 when requirements not met.

    This is a TDD test - it will fail until prerequisite validation is wired
    into the quest start endpoint.
    """
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Hard Quest",
        short_description="Requires high level",
        long_description="This quest requires a level 50 dweller",
        requirements="Level 50 dweller",
        rewards="1000 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type=RequirementType.LEVEL,
        requirement_data={"level": 50, "count": 1},
        is_mandatory=True,
    )
    async_session.add(req)
    await async_session.commit()

    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest.id, vault_id=vault.id)

    dweller = Dweller(first_name="Weak", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.post(
        f"/api/v1/quests/{vault.id}/{quest.id}/start",
        headers=headers,
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert "requirement" in response.text.lower() or "prerequisite" in response.text.lower()


@pytest.mark.asyncio
async def test_get_eligible_dwellers_for_quest(async_client: AsyncClient, async_session: AsyncSession) -> None:
    """Test that eligible dwellers endpoint returns only dwellers meeting quest requirements.

    This is a TDD test - it will fail until the eligible dwellers endpoint is implemented.
    """
    from app.tests.utils.user import user_authentication_headers

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    quest = Quest(
        title="Level Quest",
        short_description="Requires level 5",
        long_description="This quest requires a level 5 dweller",
        requirements="Level 5 dweller",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type=RequirementType.LEVEL,
        requirement_data={"level": 5, "count": 1},
        is_mandatory=True,
    )
    async_session.add(req)
    await async_session.commit()

    dweller_low = Dweller(first_name="Low", gender="male", rarity="common", level=1, vault_id=vault.id)
    dweller_med = Dweller(first_name="Med", gender="male", rarity="common", level=5, vault_id=vault.id)
    dweller_high = Dweller(first_name="High", gender="male", rarity="common", level=10, vault_id=vault.id)
    async_session.add(dweller_low)
    async_session.add(dweller_med)
    async_session.add(dweller_high)
    await async_session.commit()

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])

    response = await async_client.get(
        f"/api/v1/quests/{vault.id}/{quest.id}/eligible-dwellers",
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert len(data) == 2, f"Expected 2 eligible dwellers, got {len(data)}"
    dweller_ids = [d["id"] for d in data]
    assert str(dweller_med.id) in dweller_ids
    assert str(dweller_high.id) in dweller_ids
    assert str(dweller_low.id) not in dweller_ids
