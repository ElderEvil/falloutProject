"""Tests for quest CRUD operations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.quest import QuestCreate, QuestUpdate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_create_quest(async_session: AsyncSession) -> None:
    """Test creating a quest."""
    quest_data = QuestCreate(
        title="Test Quest",
        short_description="A test quest",
        long_description="This is a longer description of the test quest.",
        requirements="Level 10 dwellers",
        rewards="100 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    assert quest.id
    assert quest.title == "Test Quest"
    assert quest.short_description == "A test quest"
    assert quest.requirements == "Level 10 dwellers"
    assert quest.rewards == "100 caps"


@pytest.mark.asyncio
async def test_read_quest(async_session: AsyncSession) -> None:
    """Test reading a quest."""
    quest_data = QuestCreate(
        title="Read Test Quest",
        short_description="Reading test",
        long_description="Testing quest reading",
        requirements="Level 5 dwellers",
        rewards="50 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    read_quest = await crud.quest_crud.get(async_session, id=quest.id)
    assert read_quest
    assert read_quest.id == quest.id
    assert read_quest.title == quest.title


@pytest.mark.asyncio
async def test_update_quest(async_session: AsyncSession) -> None:
    """Test updating a quest."""
    quest_data = QuestCreate(
        title="Update Test Quest",
        short_description="Update test",
        long_description="Testing quest updating",
        requirements="Level 15 dwellers",
        rewards="200 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)

    update_data = QuestUpdate(title="Updated Quest Title", rewards="500 caps")
    updated_quest = await crud.quest_crud.update(async_session, id=quest.id, obj_in=update_data)

    assert updated_quest.id == quest.id
    assert updated_quest.title == "Updated Quest Title"
    assert updated_quest.rewards == "500 caps"
    # Unchanged fields should remain the same
    assert updated_quest.short_description == quest.short_description


@pytest.mark.asyncio
async def test_delete_quest(async_session: AsyncSession) -> None:
    """Test deleting a quest."""
    from app.utils.exceptions import ResourceNotFoundException

    quest_data = QuestCreate(
        title="Delete Test Quest",
        short_description="Delete test",
        long_description="Testing quest deletion",
        requirements="Level 20 dwellers",
        rewards="1000 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    quest_id = quest.id

    await crud.quest_crud.delete(async_session, id=quest_id)

    # Attempting to get a deleted quest should raise ResourceNotFoundException
    with pytest.raises(ResourceNotFoundException):
        await crud.quest_crud.get(async_session, id=quest_id)


@pytest.mark.asyncio
async def test_assign_quest_to_vault(async_session: AsyncSession) -> None:
    """Test assigning a quest to a vault."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create quest
    quest_data = QuestCreate(
        title="Vault Assignment Test",
        short_description="Test assignment",
        long_description="Testing quest assignment to vault",
        requirements="Level 5 dwellers",
        rewards="75 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)

    # Assign quest to vault
    link = await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )

    assert link.vault_id == vault.id
    assert link.quest_id == quest.id
    assert link.is_visible is True
    assert link.is_completed is False


@pytest.mark.asyncio
async def test_assign_quest_twice_updates_visibility(async_session: AsyncSession) -> None:
    """Test that assigning the same quest twice updates the visibility."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create quest
    quest_data = QuestCreate(
        title="Double Assignment Test",
        short_description="Test double assignment",
        long_description="Testing quest double assignment",
        requirements="Level 10 dwellers",
        rewards="150 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)

    # First assignment (visible)
    link1 = await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )
    assert link1.is_visible is True

    # Second assignment (not visible) - should update existing link
    link2 = await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=False
    )
    assert link2.vault_id == link1.vault_id
    assert link2.quest_id == link1.quest_id
    assert link2.is_visible is False


@pytest.mark.asyncio
async def test_get_multi_for_vault(async_session: AsyncSession) -> None:
    """Test getting multiple quests for a vault (returns all with visibility status)."""
    # Create user and vault
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create multiple quests
    quest1_data = QuestCreate(
        title="Quest 1",
        short_description="First quest",
        long_description="First quest description",
        requirements="Level 5",
        rewards="50 caps",
    )
    quest1 = await crud.quest_crud.create(async_session, obj_in=quest1_data)

    quest2_data = QuestCreate(
        title="Quest 2",
        short_description="Second quest",
        long_description="Second quest description",
        requirements="Level 10",
        rewards="100 caps",
    )
    quest2 = await crud.quest_crud.create(async_session, obj_in=quest2_data)

    quest3_data = QuestCreate(
        title="Quest 3",
        short_description="Third quest",
        long_description="Third quest description",
        requirements="Level 15",
        rewards="150 caps",
    )
    quest3 = await crud.quest_crud.create(async_session, obj_in=quest3_data)

    # Assign quests: quest1 visible, quest2 not visible, quest3 visible
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest1.id, vault_id=vault.id, is_visible=True
    )
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest2.id, vault_id=vault.id, is_visible=False
    )
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest3.id, vault_id=vault.id, is_visible=True
    )

    # Get quests for vault (returns all assigned quests with their visibility status)
    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)

    assert len(quests) == 3  # All three quests should be returned
    quest_dict = {q.title: q for q in quests}
    assert "Quest 1" in quest_dict
    assert quest_dict["Quest 1"].is_visible is True
    assert "Quest 2" in quest_dict
    assert quest_dict["Quest 2"].is_visible is False  # Not visible but still returned
    assert "Quest 3" in quest_dict
    assert quest_dict["Quest 3"].is_visible is True


@pytest.mark.asyncio
async def test_get_multi_for_vault_with_requirements_and_rewards(async_session: AsyncSession) -> None:
    """Test getting quests with their requirements and rewards."""
    from app.models.quest_requirement import QuestRequirement
    from app.models.quest_reward import QuestReward, RewardType
    from app.schemas.quest import QuestRequirementJSON, QuestRewardJSON

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    quest_data = QuestCreate(
        title="Quest With Rewards",
        short_description="Test",
        long_description="Test quest",
        requirements="Level 10",
        rewards="100 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)

    req = QuestRequirement(
        quest_id=quest.id,
        requirement_type="level",
        requirement_data={"level": 10},
        is_mandatory=True,
    )
    async_session.add(req)

    reward = QuestReward(
        quest_id=quest.id,
        reward_type=RewardType.CAPS,
        reward_data={"amount": 100},
        reward_chance=1.0,
    )
    async_session.add(reward)
    await async_session.commit()

    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )

    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)

    assert len(quests) == 1
    assert quests[0].quest_requirements is not None
    assert len(quests[0].quest_requirements) == 1
    assert quests[0].quest_requirements[0].requirement_type == "level"
    assert quests[0].quest_rewards is not None
    assert len(quests[0].quest_rewards) == 1
    assert quests[0].quest_rewards[0].reward_type == "caps"


@pytest.mark.asyncio
async def test_assign_party_to_quest(async_session: AsyncSession) -> None:
    """Test assigning dwellers to a quest party."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.models.quest_party import QuestParty
    from app.tests.factory.dwellers import create_fake_dweller

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    quest_data = QuestCreate(
        title="Party Quest",
        short_description="Test party",
        long_description="Party quest",
        requirements="3 dwellers",
        rewards="300 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )

    dweller1_data = create_fake_dweller()
    dweller1 = Dweller(**dweller1_data, vault_id=vault.id)
    async_session.add(dweller1)

    dweller2_data = create_fake_dweller()
    dweller2 = Dweller(**dweller2_data, vault_id=vault.id)
    async_session.add(dweller2)
    await async_session.commit()

    party = await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller1.id, dweller2.id])

    assert len(party) == 2
    assert party[0].slot_number == 1
    assert party[1].slot_number == 2
    assert party[0].status == "assigned"
    assert party[0].dweller_id == dweller1.id
    assert party[1].dweller_id == dweller2.id


@pytest.mark.asyncio
async def test_start_quest(async_session: AsyncSession) -> None:
    """Test starting a quest (setting the timer)."""
    from app.services.quest_service import quest_service

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    quest_data = QuestCreate(
        title="Timed Quest",
        short_description="Test timer",
        long_description="Timed quest",
        requirements="1 dweller",
        rewards="100 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )

    link = await quest_service.start_quest(async_session, quest.id, vault.id, duration_minutes=30)

    assert link.started_at is not None
    assert link.duration_minutes == 30


@pytest.mark.skip(reason="Test uses PostgreSQL-specific datetime handling")
@pytest.mark.asyncio
async def test_check_and_complete_quests(async_session: AsyncSession) -> None:
    """Test automatic quest completion after duration."""
    from datetime import datetime, timedelta, timezone
    from app.models.vault_quest import VaultQuestCompletionLink
    from app.services.quest_service import quest_service

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    quest_data = QuestCreate(
        title="Auto Complete Quest",
        short_description="Test auto",
        long_description="Auto complete",
        requirements="1 dweller",
        rewards="50 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    link = VaultQuestCompletionLink(
        vault_id=vault.id,
        quest_id=quest.id,
        is_visible=True,
        is_completed=False,
    )
    async_session.add(link)
    await async_session.commit()

    past_time = datetime.now(timezone.utc) - timedelta(minutes=120)
    link.started_at = past_time
    link.duration_minutes = 60
    await async_session.commit()

    completed = await quest_service.check_and_complete_quests(async_session)

    assert completed >= 1

    await async_session.refresh(link)
    assert link.is_completed is True


@pytest.mark.asyncio
async def test_get_multi_for_vault_auto_assigns_quests(async_session: AsyncSession) -> None:
    """Test that get_multi_for_vault auto-assigns quests when none exist for vault."""
    from app.models.quest import Quest

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    quest1_data = QuestCreate(
        title="Auto Quest 1",
        short_description="First auto quest",
        long_description="First auto quest description",
        requirements="Level 1",
        rewards="10 caps",
    )
    quest1 = await crud.quest_crud.create(async_session, obj_in=quest1_data)

    quest2_data = QuestCreate(
        title="Auto Quest 2",
        short_description="Second auto quest",
        long_description="Second auto quest description",
        requirements="Level 2",
        rewards="20 caps",
    )
    quest2 = await crud.quest_crud.create(async_session, obj_in=quest2_data)

    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)

    assert len(quests) == 2
    quest_titles = {q.title for q in quests}
    assert "Auto Quest 1" in quest_titles
    assert "Auto Quest 2" in quest_titles
    for q in quests:
        assert q.is_visible is True


@pytest.mark.asyncio
async def test_assign_party_replaces_existing(async_session: AsyncSession) -> None:
    """Test that assign_party replaces existing party members."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_dweller

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    quest_data = QuestCreate(
        title="Replace Party Quest",
        short_description="Test replace",
        long_description="Party replacement",
        requirements="2 dwellers",
        rewards="200 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )

    dweller1_data = create_fake_dweller()
    dweller1 = Dweller(**dweller1_data, vault_id=vault.id)
    async_session.add(dweller1)

    dweller2_data = create_fake_dweller()
    dweller2 = Dweller(**dweller2_data, vault_id=vault.id)
    async_session.add(dweller2)

    dweller3_data = create_fake_dweller()
    dweller3 = Dweller(**dweller3_data, vault_id=vault.id)
    async_session.add(dweller3)
    await async_session.commit()

    party1 = await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller1.id, dweller2.id])
    assert len(party1) == 2
    assert party1[0].dweller_id == dweller1.id

    party2 = await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller3.id])
    assert len(party2) == 1
    assert party2[0].dweller_id == dweller3.id


@pytest.mark.asyncio
async def test_get_party_for_quest_returns_dicts(async_session: AsyncSession) -> None:
    """Test that get_party_for_quest returns proper dictionary format."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_dweller

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    quest_data = QuestCreate(
        title="Dict Format Quest",
        short_description="Test dict",
        long_description="Dict format test",
        requirements="1 dweller",
        rewards="50 caps",
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )

    dweller_data = create_fake_dweller()
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])

    party = await quest_party_crud.get_party_for_quest(async_session, quest.id, vault.id)

    assert len(party) == 1
    assert hasattr(party[0], "id")
    assert str(party[0].dweller_id) == str(dweller.id)
