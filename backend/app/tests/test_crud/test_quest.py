"""Tests for quest CRUD operations."""

import os
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum
from app.schemas.quest import QuestCreate, QuestUpdate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


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
    """Test vault quests reveal only chain starters until their requirement completes."""
    from app.models.quest_requirement import QuestRequirement, RequirementType

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
    async_session.add(
        QuestRequirement(
            quest_id=quest2.id,
            requirement_type=RequirementType.QUEST_COMPLETED,
            requirement_data={"quest_id": str(quest1.id)},
        )
    )
    await async_session.commit()

    quest3_data = QuestCreate(
        title="Quest 3",
        short_description="Third quest",
        long_description="Third quest description",
        requirements="Level 15",
        rewards="150 caps",
    )
    quest3 = await crud.quest_crud.create(async_session, obj_in=quest3_data)

    # All links begin visible; the requirement keeps quest2 hidden until quest1 completes.
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest1.id, vault_id=vault.id, is_visible=True
    )
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest2.id, vault_id=vault.id, is_visible=True
    )
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest3.id, vault_id=vault.id, is_visible=True
    )

    # Get quests for vault (returns all assigned quests with computed visibility status)
    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)

    assert len(quests) == 3  # All three quests should be returned
    quest_dict = {q.title: q for q in quests}
    assert "Quest 1" in quest_dict
    assert quest_dict["Quest 1"].is_visible is True
    from app.utils.quest_duration import effective_quest_duration_minutes

    assert quest_dict["Quest 1"].duration_minutes == effective_quest_duration_minutes(quest1.duration_minutes)
    assert "Quest 2" in quest_dict
    assert quest_dict["Quest 2"].is_visible is False  # Locked but still returned for Show All
    assert quest_dict["Quest 2"].previous_quest_id == quest1.id
    assert "Quest 3" in quest_dict
    assert quest_dict["Quest 3"].is_visible is True

    quest_page_indexes = {}
    for page_index in range(3):
        page = await crud.quest_crud.get_multi_for_vault(
            db_session=async_session, skip=page_index, limit=1, vault_id=vault.id
        )
        assert len(page) == 1
        quest_page_indexes[page[0].title] = page_index
    assert quest_page_indexes["Quest 1"] != quest_page_indexes["Quest 2"]

    quest1_link = await async_session.get(crud.quest_crud.link_model, (vault.id, quest1.id))
    assert quest1_link is not None
    quest1_link.is_completed = True
    await async_session.commit()

    unlocked_quests = await crud.quest_crud.get_multi_for_vault(
        db_session=async_session, skip=0, limit=100, vault_id=vault.id
    )
    assert {quest.title: quest.is_visible for quest in unlocked_quests}["Quest 2"] is True

    quest2_page = await crud.quest_crud.get_multi_for_vault(
        db_session=async_session, skip=quest_page_indexes["Quest 2"], limit=1, vault_id=vault.id
    )
    assert quest2_page[0].title == "Quest 2"
    assert quest2_page[0].is_visible is True


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
    dweller1_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller1 = Dweller(**dweller1_data, vault_id=vault.id)
    async_session.add(dweller1)

    dweller2_data = create_fake_dweller()
    dweller2_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
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
async def test_assign_party_rejects_ineligible_dwellers(async_session: AsyncSession) -> None:
    """Quest parties reject children, explorers, and deleted dwellers without changing the current party."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.tests.factory.dwellers import create_fake_dweller

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Restricted Party Quest",
            short_description="Test restrictions",
            long_description="Test restrictions",
            requirements="1 dweller",
            rewards="100 caps",
        ),
    )
    child_data = create_fake_dweller()
    child_data.update(is_adult=False, age_group=AgeGroupEnum.CHILD)
    child = Dweller(**child_data, vault_id=vault.id)
    explorer_data = create_fake_dweller()
    explorer_data.update(
        is_adult=True,
        age_group=AgeGroupEnum.ADULT,
        status=DwellerStatusEnum.EXPLORING,
    )
    explorer = Dweller(**explorer_data, vault_id=vault.id)
    assigned_data = create_fake_dweller()
    assigned_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    assigned = Dweller(**assigned_data, vault_id=vault.id)
    deleted_data = create_fake_dweller()
    deleted_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT, is_deleted=True)
    deleted = Dweller(**deleted_data, vault_id=vault.id)
    async_session.add(child)
    async_session.add(explorer)
    async_session.add(assigned)
    async_session.add(deleted)
    await async_session.commit()

    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [assigned.id])
    with pytest.raises(ValueError, match="Child dweller"):
        await quest_party_crud.assign_party(async_session, quest.id, vault.id, [child.id])
    with pytest.raises(ValueError, match="exploring"):
        await quest_party_crud.assign_party(async_session, quest.id, vault.id, [explorer.id])
    with pytest.raises(ValueError, match="Deleted dweller"):
        await quest_party_crud.assign_party(async_session, quest.id, vault.id, [deleted.id])

    party = await quest_party_crud.get_party_for_quest(async_session, quest.id, vault.id)
    assert [member.dweller_id for member in party] == [assigned.id]


@pytest.mark.asyncio
async def test_start_quest(async_session: AsyncSession) -> None:
    """Test starting a quest (setting the timer)."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.services.quest_service import quest_service
    from app.tests.factory.dwellers import create_fake_dweller
    from app.utils.exceptions import ResourceConflictException

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
        duration_minutes=45,
    )
    quest = await crud.quest_crud.create(async_session, obj_in=quest_data)
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )
    dweller_data = create_fake_dweller()
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.started_at is not None
    from app.utils.quest_duration import effective_quest_duration_minutes

    assert link.duration_minutes == effective_quest_duration_minutes(quest.duration_minutes)
    with pytest.raises(ResourceConflictException, match="already in progress"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_quest_snapshots_local_duration_multiplier(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.services.quest_service import quest_service
    from app.tests.factory.dwellers import create_fake_dweller

    monkeypatch.setattr(settings, "QUEST_DURATION_MULTIPLIER", 0.1)
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Accelerated Quest",
            short_description="Test local duration scaling",
            long_description="A quest that snapshots the local duration multiplier.",
            requirements="1 dweller",
            rewards="100 caps",
            duration_minutes=120,
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True)
    dweller_data = create_fake_dweller()
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.duration_minutes == 12


@pytest.mark.asyncio
async def test_unstarted_quest_uses_local_duration_multiplier(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "QUEST_DURATION_MULTIPLIER", 0.2)
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Pre-start accelerated quest",
            short_description="Test displayed local duration scaling",
            long_description="An unstarted quest displays its effective local duration.",
            requirements="1 dweller",
            rewards="100 caps",
            duration_minutes=120,
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True)

    quests = await crud.quest_crud.get_multi_for_vault(db_session=async_session, skip=0, limit=100, vault_id=vault.id)

    assert quests[0].duration_minutes == 24


@pytest.mark.asyncio
async def test_start_quest_stores_utc_timestamp(async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quest timers must be naive UTC, not server-local time (FE/BE clock mismatch on non-UTC hosts)."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.services.quest_service import quest_service
    from app.tests.factory.dwellers import create_fake_dweller

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="UTC Quest",
            short_description="Test UTC timer",
            long_description="Timed quest",
            requirements="1 dweller",
            rewards="100 caps",
            duration_minutes=30,
        ),
    )
    await crud.quest_crud.assign_to_vault(
        db_session=async_session, quest_id=quest.id, vault_id=vault.id, is_visible=True
    )
    dweller_data = create_fake_dweller()
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])

    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Berlin"
    time.tzset()
    try:
        link = await quest_service.start_quest(async_session, quest.id, vault.id)
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()

    assert link.started_at is not None
    assert abs((link.started_at - datetime.utcnow()).total_seconds()) < timedelta(minutes=1).total_seconds()


@pytest.mark.asyncio
async def test_start_quest_requires_an_assigned_party(async_session: AsyncSession) -> None:
    """A quest cannot run without a party to send into the wasteland."""
    from app.services.quest_service import quest_service
    from app.utils.exceptions import ValidationException

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Party Required",
            short_description="Send a team",
            long_description="A quest should not start without anyone assigned.",
            requirements="Level 1",
            rewards="10 caps",
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    with pytest.raises(ValidationException, match="Assign at least one dweller"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("quest_category", ["building", "population", "training"])
async def test_start_state_quest_is_ready_without_a_party(async_session: AsyncSession, quest_category: str) -> None:
    """State quests settle from their prerequisite state, not a dispatched party."""
    from app.services.quest_service import quest_service

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title=f"{quest_category.title()} objective",
            short_description="Reach the vault objective",
            long_description="The vault already meets this objective.",
            requirements="Existing vault progress",
            rewards="100 caps",
            quest_category=quest_category,
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    link = await quest_service.start_quest(async_session, quest.id, vault.id)

    assert link.is_reward_ready is True
    assert link.started_at is None


@pytest.mark.asyncio
async def test_start_quest_requires_a_positive_template_duration(async_session: AsyncSession) -> None:
    """Quest timers must come from a positive server-side template duration."""
    from app.services.quest_service import quest_service
    from app.utils.exceptions import ValidationException

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Untimed Quest",
            short_description="No timer",
            long_description="A quest with an invalid configured duration.",
            requirements="Level 1",
            rewards="10 caps",
            duration_minutes=0,
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    with pytest.raises(ValidationException, match="duration must be a positive value"):
        await quest_service.start_quest(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_quest_cannot_complete_before_its_duration(async_session: AsyncSession) -> None:
    """Manual completion must not bypass a running quest's timer."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.services.quest_service import quest_service
    from app.tests.factory.dwellers import create_fake_dweller
    from app.utils.exceptions import ValidationException

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="No Early Return",
            short_description="Wait for the party",
            long_description="A quest that must run before it can settle.",
            requirements="Level 1",
            rewards="10 caps",
            duration_minutes=60,
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    dweller_data = create_fake_dweller()
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])
    await quest_service.start_quest(async_session, quest.id, vault.id)

    with pytest.raises(ValidationException, match="not ready to claim"):
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_check_and_complete_quests_for_vault(async_session: AsyncSession) -> None:
    """Refreshing a vault makes its elapsed quest claimable without granting rewards."""
    from datetime import datetime, timedelta

    from app.models.quest_reward import QuestReward, RewardType
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
    async_session.add(
        QuestReward(
            quest_id=quest.id,
            reward_type=RewardType.CAPS,
            reward_data={"amount": 50},
            reward_chance=1.0,
        )
    )
    link = VaultQuestCompletionLink(
        vault_id=vault.id,
        quest_id=quest.id,
        is_visible=True,
        is_completed=False,
    )
    async_session.add(link)
    await async_session.commit()

    past_time = datetime.utcnow() - timedelta(minutes=120)
    link.started_at = past_time
    link.duration_minutes = 60
    await async_session.commit()

    completed = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)

    assert completed >= 1

    await async_session.refresh(link)
    await async_session.refresh(vault)
    assert link.is_completed is False
    assert link.is_reward_ready is True
    assert vault.bottle_caps == vault_data["bottle_caps"]


@pytest.mark.asyncio
async def test_timed_quest_completion_simulation(async_session: AsyncSession) -> None:
    """Simulate a party return followed by an atomic reward claim."""
    from datetime import datetime, timedelta

    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.models.quest_reward import QuestReward, RewardType
    from app.models.storage import Storage
    from app.models.weapon import Weapon
    from app.schemas.common import AgeGroupEnum
    from app.services.event_bus import GameEvent, event_bus
    from app.services.quest_service import quest_service
    from app.tests.factory.dwellers import create_fake_dweller

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=10))
    dweller_data = create_fake_dweller() | {"is_adult": True, "age_group": AgeGroupEnum.ADULT}
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)

    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Timed reward simulation",
            short_description="Automatic settlement",
            long_description="A party returns with caps and a weapon.",
            requirements="One adult dweller",
            rewards="50 caps and a laser pistol",
            duration_minutes=120,
        ),
    )
    async_session.add_all(
        [
            QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 50}, reward_chance=1.0),
            QuestReward(
                quest_id=quest.id,
                reward_type=RewardType.ITEM,
                reward_data={"item_type": "weapon", "name": "Laser Pistol"},
            ),
        ]
    )
    link = await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    await async_session.commit()
    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])

    link.started_at = datetime.utcnow() - timedelta(minutes=61)
    link.duration_minutes = 60
    await async_session.commit()

    assert await quest_service.check_and_complete_quests(async_session) == 1

    await async_session.refresh(link)
    assert link.is_completed is False
    assert link.is_reward_ready is True
    assert vault.bottle_caps == vault_data["bottle_caps"]
    assert dweller.status == DwellerStatusEnum.IDLE

    events = []

    async def capture_event(_event_type, _vault_id, data) -> None:
        events.append(data)

    event_bus.subscribe(GameEvent.QUEST_COMPLETED, capture_event)
    try:
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)
    finally:
        event_bus.unsubscribe(GameEvent.QUEST_COMPLETED, capture_event)

    await async_session.refresh(link)
    await async_session.refresh(vault)
    await async_session.refresh(dweller)
    weapon = (await async_session.execute(select(Weapon).where(Weapon.name == "Laser Pistol"))).scalar_one()
    assert link.is_completed is True
    assert weapon.storage_id is not None
    assert dweller.experience == dweller_data["experience"] + 1200
    assert events == [{"quest_id": str(quest.id), "quest_title": quest.title, "quest_type": quest.quest_type.value}]

    with pytest.raises(ResourceConflictException, match="Already completed"):
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)

    await async_session.refresh(vault)
    assert vault.bottle_caps == vault_data["bottle_caps"] + 50


@pytest.mark.asyncio
async def test_quest_completion_rolls_back_when_any_reward_fails(async_session: AsyncSession) -> None:
    """A quest must not settle partially when one of its rewards cannot be delivered."""
    from datetime import datetime, timedelta

    from app.models.quest_reward import QuestReward, RewardType
    from app.services.quest_service import quest_service

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Atomic reward quest",
            short_description="Reward settlement",
            long_description="Fails without available storage.",
            requirements="None",
            rewards="Caps and an item",
        ),
    )
    async_session.add_all(
        [
            QuestReward(
                quest_id=quest.id,
                reward_type=RewardType.CAPS,
                reward_data={"amount": 50},
                reward_chance=1.0,
            ),
            QuestReward(
                quest_id=quest.id,
                reward_type=RewardType.ITEM,
                reward_data={"item_type": "weapon", "name": "Laser Pistol"},
                reward_chance=1.0,
            ),
        ]
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)

    link = await async_session.get(crud.quest_crud.link_model, (vault.id, quest.id))
    assert link is not None
    link.is_reward_ready = True
    await async_session.commit()

    with pytest.raises(ResourceNotFoundException, match="Storage"):
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)

    await async_session.refresh(vault)
    await async_session.refresh(link)
    assert link.is_completed is False
    assert link.is_reward_ready is True
    assert vault.bottle_caps == vault_data["bottle_caps"]


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
    await crud.quest_crud.create(async_session, obj_in=quest1_data)

    quest2_data = QuestCreate(
        title="Auto Quest 2",
        short_description="Second auto quest",
        long_description="Second auto quest description",
        requirements="Level 2",
        rewards="20 caps",
    )
    await crud.quest_crud.create(async_session, obj_in=quest2_data)

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
    from app.services.quest_service import quest_service
    from app.tests.factory.dwellers import create_fake_dweller
    from app.utils.exceptions import ResourceConflictException

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

    dwellers = []
    for _ in range(3):
        dweller_data = create_fake_dweller()
        dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
        dwellers.append(Dweller(**dweller_data, vault_id=vault.id))
    dweller1, dweller2, dweller3 = dwellers
    async_session.add_all(dwellers)
    await async_session.commit()

    party1 = await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller1.id, dweller2.id])
    assert len(party1) == 2
    assert party1[0].dweller_id == dweller1.id

    party2 = await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller3.id])
    assert len(party2) == 1
    assert party2[0].dweller_id == dweller3.id

    await quest_service.start_quest(async_session, quest.id, vault.id)

    with pytest.raises(ResourceConflictException, match="already in progress"):
        await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller1.id])


@pytest.mark.asyncio
@pytest.mark.parametrize("link_state", [{"is_reward_ready": True}, {"is_completed": True}])
async def test_assign_party_rejects_reward_ready_or_completed_quest(
    async_session: AsyncSession, link_state: dict[str, bool]
) -> None:
    """Reward-ready and completed quests cannot acquire a party."""
    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller
    from app.models.vault_quest import VaultQuestCompletionLink
    from app.tests.factory.dwellers import create_fake_dweller

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Finished Objective",
            short_description="No party allowed",
            long_description="State objective guard",
            requirements="None",
            rewards="None",
        ),
    )
    dweller_data = create_fake_dweller()
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add_all([dweller, VaultQuestCompletionLink(vault_id=vault.id, quest_id=quest.id, **link_state)])
    await async_session.commit()

    with pytest.raises(ResourceConflictException, match="already in progress"):
        await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])


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
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()

    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])

    party = await quest_party_crud.get_party_for_quest(async_session, quest.id, vault.id)

    assert len(party) == 1
    assert hasattr(party[0], "id")
    assert str(party[0].dweller_id) == str(dweller.id)
