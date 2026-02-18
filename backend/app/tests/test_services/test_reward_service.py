"""Tests for RewardService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.objective import ObjectiveCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_grant_caps_success(async_session: AsyncSession) -> None:
    """Test granting caps to vault."""
    # Create user and vault
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))

    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    initial_caps = vault.bottle_caps
    result = await reward_service.grant_caps(async_session, vault.id, 100)

    assert result["reward_type"] == RewardType.CAPS
    assert result["amount"] == 100

    # Refresh vault to check updated caps
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100


@pytest.mark.asyncio
async def test_grant_caps_zero_amount(async_session: AsyncSession) -> None:
    """Test granting zero caps."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    initial_caps = vault.bottle_caps
    result = await reward_service.grant_caps(async_session, vault.id, 0)

    assert result["amount"] == 0
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps


@pytest.mark.asyncio
async def test_process_objective_reward_caps(async_session: AsyncSession) -> None:
    """Test parsing and granting caps from objective reward string."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective with caps reward
    from app.crud.objective import objective_crud

    objective = await objective_crud.create(
        async_session, ObjectiveCreate(challenge="Test", reward="100 caps", category="achievement")
    )

    # Create progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    initial_caps = vault.bottle_caps
    result = await reward_service.process_objective_reward(async_session, vault.id, link)

    assert result is not None
    assert result["reward_type"] == RewardType.CAPS
    assert result["amount"] == 100

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100


@pytest.mark.asyncio
async def test_process_objective_reward_invalid(async_session: AsyncSession) -> None:
    """Test handling invalid reward string."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    from app.crud.objective import objective_crud

    objective = await objective_crud.create(
        async_session, ObjectiveCreate(challenge="Test", reward="invalid reward string", category="achievement")
    )

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    result = await reward_service.process_objective_reward(async_session, vault.id, link)
    assert result is None  # Should fail gracefully


@pytest.mark.asyncio
async def test_process_quest_rewards_single(async_session: AsyncSession) -> None:
    """Test processing a single quest reward."""
    # Create quest with reward
    quest = Quest(
        title="Test Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    # Add reward
    reward = QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 100}, reward_chance=1.0)
    async_session.add(reward)
    await async_session.commit()

    # Refresh quest to load rewards
    await async_session.refresh(quest)
    await async_session.refresh(quest, ["quest_rewards"])

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    initial_caps = vault.bottle_caps
    results = await reward_service.process_quest_rewards(async_session, vault.id, quest)

    assert len(results) == 1
    assert results[0]["reward_type"] == RewardType.CAPS
    assert results[0]["amount"] == 100

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100


@pytest.mark.asyncio
async def test_process_quest_rewards_with_chance_failure(async_session: AsyncSession) -> None:
    """Test reward with low chance not being granted."""
    quest = Quest(
        title="Test Quest",
        short_description="Test",
        long_description="Test quest",
        requirements="None",
        rewards="100 caps",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    # Add reward with 0% chance
    reward = QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 100}, reward_chance=0.0)
    async_session.add(reward)
    await async_session.commit()
    await async_session.refresh(quest)
    await async_session.refresh(quest, ["quest_rewards"])

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    initial_caps = vault.bottle_caps
    results = await reward_service.process_quest_rewards(async_session, vault.id, quest)

    assert len(results) == 0  # Reward not granted due to 0% chance
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps


@pytest.mark.asyncio
async def test_grant_resource_food(async_session: AsyncSession) -> None:
    """Test granting food resource."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    vault.food_max = 1000
    await async_session.commit()

    initial_food = vault.food
    result = await reward_service.grant_resource(async_session, vault.id, "food", 100)

    assert result["reward_type"] == RewardType.RESOURCE
    assert result["resource_type"] == "food"
    assert result["amount"] == 100

    await async_session.refresh(vault)
    assert vault.food == min(initial_food + 100, vault.food_max)


@pytest.mark.asyncio
async def test_grant_resource_invalid_type(async_session: AsyncSession) -> None:
    """Test granting invalid resource type raises error."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    with pytest.raises(ValueError, match="Invalid resource_type"):
        await reward_service.grant_resource(async_session, vault.id, "invalid", 100)


@pytest.mark.asyncio
async def test_parse_objective_reward_caps() -> None:
    """Test parsing caps reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("100 caps")

    assert reward_type == RewardType.CAPS
    assert reward_data["amount"] == 100


@pytest.mark.asyncio
async def test_parse_objective_reward_food() -> None:
    """Test parsing food reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("50 food")

    assert reward_type == RewardType.RESOURCE
    assert reward_data["resource_type"] == "food"
    assert reward_data["amount"] == 50


@pytest.mark.asyncio
async def test_parse_objective_reward_weapon() -> None:
    """Test parsing weapon reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("weapon:Laser Pistol")

    assert reward_type == RewardType.ITEM
    assert reward_data["item_type"] == "weapon"
    assert reward_data["name"] == "Laser Pistol"


@pytest.mark.asyncio
async def test_parse_objective_reward_dweller() -> None:
    """Test parsing dweller reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("dweller:Wanderer")

    assert reward_type == RewardType.DWELLER
    assert reward_data["first_name"] == "Wanderer"


@pytest.mark.asyncio
async def test_parse_objective_reward_invalid() -> None:
    """Test parsing invalid reward string raises error."""
    with pytest.raises(ValueError, match="Cannot parse objective reward string"):
        reward_service._parse_objective_reward("completely invalid string")
