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
    """Test getting multiple quests for a vault (only visible, not completed)."""
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

    # Get quests for vault (should only return visible, not completed)
    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)

    assert len(quests) == 2  # Only quest1 and quest3 should be returned
    quest_titles = {q.title for q in quests}
    assert "Quest 1" in quest_titles
    assert "Quest 3" in quest_titles
    assert "Quest 2" not in quest_titles  # Not visible
