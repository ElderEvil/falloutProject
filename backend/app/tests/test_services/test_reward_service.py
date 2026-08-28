"""Tests for RewardService."""

from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import ObjectiveCategoryEnum
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
        async_session, ObjectiveCreate(challenge="Test", reward="100 caps", category=ObjectiveCategoryEnum.ACHIEVEMENT)
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
    """Test invalid reward string raises instead of being silently swallowed."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    from app.crud.objective import objective_crud

    objective = await objective_crud.create(
        async_session,
        ObjectiveCreate(challenge="Test", reward="invalid reward string", category=ObjectiveCategoryEnum.ACHIEVEMENT),
    )

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    with pytest.raises(ValueError, match="Cannot parse objective reward string"):
        await reward_service.process_objective_reward(async_session, vault.id, link)


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
async def test_process_quest_item_reward_uses_typed_item_data(async_session: AsyncSession) -> None:
    """Quest item rewards use their stored type and template fields."""
    from app.models.outfit import Outfit
    from app.models.storage import Storage

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    async_session.add(Storage(vault_id=vault.id, max_space=10))
    quest = Quest(
        title="Typed Outfit Reward",
        short_description="Template-backed reward",
        long_description="A quest that grants the promised outfit.",
        requirements="None",
        rewards="Vault Suit",
    )
    async_session.add(quest)
    await async_session.commit()
    async_session.add(
        QuestReward(
            quest_id=quest.id,
            reward_type=RewardType.ITEM,
            reward_data={"item_name": "Vault Suit", "quantity": 1},
            item_data={
                "item_type": "outfit",
                "name": "Vault Suit",
                "rarity": "rare",
                "outfit_type": "common_outfit",
            },
        )
    )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_rewards"])

    rewards = await reward_service.process_quest_rewards(async_session, vault.id, quest)

    outfit = (await async_session.execute(select(Outfit).where(Outfit.name == "Vault Suit"))).scalar_one()
    assert rewards == [
        {"reward_type": RewardType.ITEM, "item_type": "outfit", "name": "Vault Suit", "item_id": str(outfit.id)}
    ]
    assert outfit.storage_id is not None


@pytest.mark.asyncio
async def test_process_quest_dweller_template_reward_uses_canonical_stats(async_session: AsyncSession) -> None:
    """A dweller reward materializes the named canonical template, not a random dweller."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = Quest(
        title="Template Dweller Reward",
        short_description="A known hero joins the vault.",
        long_description="Completing this quest grants Abraham Washington.",
        requirements="None",
        rewards="Abraham Washington",
    )
    async_session.add(quest)
    await async_session.commit()
    async_session.add(
        QuestReward(
            quest_id=quest.id,
            reward_type=RewardType.DWELLER,
            reward_data={"template_id": "abraham-washington"},
        )
    )
    await async_session.commit()
    await async_session.refresh(quest, ["quest_rewards"])

    rewards = await reward_service.process_quest_rewards(async_session, vault.id, quest)

    dweller_id = rewards[0]["dweller_id"]
    dweller = await async_session.get(Dweller, UUID(dweller_id))
    assert dweller is not None
    assert (dweller.first_name, dweller.last_name, dweller.rarity) == ("Abraham", "Washington", "legendary")
    assert (dweller.strength, dweller.perception, dweller.endurance) == (2, 8, 6)


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
