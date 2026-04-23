"""Additional tests for RewardService — uncovered paths."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.storage import Storage
from app.schemas.common import GenderEnum, RarityEnum
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_grant_item_weapon_success(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=100)
    async_session.add(storage)
    await async_session.commit()

    result = await reward_service.grant_item(
        async_session,
        vault.id,
        {
            "item_type": "weapon",
            "name": "Laser Rifle",
            "rarity": "rare",
            "weapon_type": "energy",
            "weapon_subtype": "rifle",
            "stat": "perception",
            "damage_min": 5,
            "damage_max": 15,
        },
    )

    assert result["reward_type"] == RewardType.ITEM
    assert result["item_type"] == "weapon"
    assert result["name"] == "Laser Rifle"
    assert "item_id" in result


@pytest.mark.asyncio
async def test_grant_item_outfit_success(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=100)
    async_session.add(storage)
    await async_session.commit()

    result = await reward_service.grant_item(
        async_session,
        vault.id,
        {
            "item_type": "outfit",
            "name": "Combat Armor",
            "rarity": "rare",
            "outfit_type": "power_armor",
            "gender": "male",
        },
    )

    assert result["reward_type"] == RewardType.ITEM
    assert result["item_type"] == "outfit"
    assert result["name"] == "Combat Armor"


@pytest.mark.asyncio
async def test_grant_item_unknown_type_raises(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=100)
    async_session.add(storage)
    await async_session.commit()

    with pytest.raises(ValueError, match="Unknown item_type"):
        await reward_service.grant_item(
            async_session,
            vault.id,
            {
                "item_type": "armor",
                "name": "Mystery Item",
            },
        )


@pytest.mark.asyncio
async def test_grant_item_no_storage_raises(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    with pytest.raises(ValueError, match="No storage found"):
        await reward_service.grant_item(
            async_session,
            vault.id,
            {
                "item_type": "weapon",
                "name": "Test Weapon",
            },
        )


@pytest.mark.asyncio
async def test_grant_item_storage_full_raises(async_session: AsyncSession) -> None:
    from app.models.weapon import Weapon

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=1)
    async_session.add(storage)
    await async_session.commit()
    await async_session.refresh(storage)

    weapon = Weapon(
        name="Filler",
        rarity="common",
        weapon_type="melee",
        weapon_subtype="blunt",
        stat="strength",
        damage_min=1,
        damage_max=3,
        storage_id=storage.id,
    )
    async_session.add(weapon)
    await async_session.commit()

    with pytest.raises(ValueError, match="Storage full"):
        await reward_service.grant_item(
            async_session,
            vault.id,
            {
                "item_type": "weapon",
                "name": "Test Weapon",
            },
        )


@pytest.mark.asyncio
async def test_grant_dweller_success(async_session: AsyncSession) -> None:
    """Test granting a dweller reward."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    result = await reward_service.grant_dweller(
        async_session,
        vault.id,
        {
            "first_name": "James",
            "last_name": "Paladin",
            "rarity": "rare",
            "level": 3,
            "gender": "male",
        },
    )

    assert result["reward_type"] == RewardType.DWELLER
    assert "dweller_id" in result
    assert "James" in result["name"]


@pytest.mark.asyncio
async def test_grant_dweller_invalid_rarity_defaults_common(async_session: AsyncSession) -> None:
    """Test granting dweller with invalid rarity defaults to common."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    result = await reward_service.grant_dweller(
        async_session,
        vault.id,
        {
            "first_name": "Test",
            "rarity": "mythical",
        },
    )

    assert result["reward_type"] == RewardType.DWELLER


@pytest.mark.asyncio
async def test_grant_dweller_missing_fields(async_session: AsyncSession) -> None:
    """Test granting dweller with minimal data."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    result = await reward_service.grant_dweller(async_session, vault.id, {"name": "Fallback"})

    assert result["reward_type"] == RewardType.DWELLER
    assert "Fallback" in result["name"]


@pytest.mark.asyncio
async def test_grant_resource_water(async_session: AsyncSession) -> None:
    """Test granting water resource."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    vault.water_max = 1000
    await async_session.commit()

    initial_water = vault.water
    result = await reward_service.grant_resource(async_session, vault.id, "water", 50)

    assert result["reward_type"] == RewardType.RESOURCE
    assert result["resource_type"] == "water"
    assert result["amount"] == 50

    await async_session.refresh(vault)
    assert vault.water == min(initial_water + 50, vault.water_max)


@pytest.mark.asyncio
async def test_grant_resource_power(async_session: AsyncSession) -> None:
    """Test granting power resource."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    vault.power_max = 1000
    await async_session.commit()

    initial_power = vault.power
    result = await reward_service.grant_resource(async_session, vault.id, "power", 75)

    assert result["resource_type"] == "power"
    await async_session.refresh(vault)
    assert vault.power == min(initial_power + 75, vault.power_max)


@pytest.mark.asyncio
async def test_grant_resource_caps_at_max(async_session: AsyncSession) -> None:
    """Test that resource grant respects max cap."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    vault.food = 950
    vault.food_max = 1000
    await async_session.commit()

    await reward_service.grant_resource(async_session, vault.id, "food", 100)

    await async_session.refresh(vault)
    assert vault.food == 1000


@pytest.mark.asyncio
async def test_grant_experience_success(async_session: AsyncSession) -> None:
    """Test granting experience to dwellers."""
    from app.schemas.dweller import DwellerCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    dweller_in = DwellerCreate(
        first_name="XP",
        last_name="Test",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        level=1,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        vault_id=vault.id,
    )
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    result = await reward_service.grant_experience(async_session, [dweller.id], 100)

    assert result["reward_type"] == RewardType.EXPERIENCE
    assert result["amount"] == 100
    assert str(dweller.id) in result["dweller_ids"]


@pytest.mark.asyncio
async def test_grant_experience_level_up(async_session: AsyncSession) -> None:
    """Test granting experience that causes level up."""
    from app.schemas.dweller import DwellerCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    dweller_in = DwellerCreate(
        first_name="Level",
        last_name="Up",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        level=1,
        experience=90,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        vault_id=vault.id,
    )
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    result = await reward_service.grant_experience(async_session, [dweller.id], 100)

    assert str(dweller.id) in result["leveled_up"]


@pytest.mark.asyncio
async def test_grant_experience_invalid_dweller(async_session: AsyncSession) -> None:
    """Test granting experience to non-existent dweller is handled gracefully."""
    import uuid

    fake_id = uuid.uuid4()
    result = await reward_service.grant_experience(async_session, [fake_id], 50)

    assert result["reward_type"] == RewardType.EXPERIENCE
    assert str(fake_id) not in result["dweller_ids"]


@pytest.mark.asyncio
async def test_grant_stimpak_success(async_session: AsyncSession) -> None:
    """Test granting stimpaks to a dweller."""
    from app.schemas.dweller import DwellerCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    dweller_in = DwellerCreate(
        first_name="Stim",
        last_name="Test",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        level=1,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        vault_id=vault.id,
    )
    await crud.dweller.create(async_session, obj_in=dweller_in)

    result = await reward_service.grant_stimpak(async_session, vault.id, 5)

    assert result["reward_type"] == RewardType.STIMPAK
    assert result["amount"] == 5
    assert "dweller_id" in result


@pytest.mark.asyncio
async def test_grant_stimpak_no_dwellers(async_session: AsyncSession) -> None:
    """Test granting stimpaks when no dwellers exist."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    result = await reward_service.grant_stimpak(async_session, vault.id, 5)

    assert result["reward_type"] == RewardType.STIMPAK
    assert result["amount"] == 0
    assert "No dwellers" in result["message"]


@pytest.mark.asyncio
async def test_grant_radaway_success(async_session: AsyncSession) -> None:
    """Test granting radaways to a dweller."""
    from app.schemas.dweller import DwellerCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    dweller_in = DwellerCreate(
        first_name="Rad",
        last_name="Test",
        gender=GenderEnum.FEMALE,
        rarity=RarityEnum.COMMON,
        level=1,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        vault_id=vault.id,
    )
    await crud.dweller.create(async_session, obj_in=dweller_in)

    result = await reward_service.grant_radaway(async_session, vault.id, 3)

    assert result["reward_type"] == RewardType.RADAWAY
    assert result["amount"] == 3


@pytest.mark.asyncio
async def test_grant_radaway_no_dwellers(async_session: AsyncSession) -> None:
    """Test granting radaways when no dwellers exist."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    result = await reward_service.grant_radaway(async_session, vault.id, 3)

    assert result["reward_type"] == RewardType.RADAWAY
    assert result["amount"] == 0


@pytest.mark.asyncio
async def test_grant_lunchbox(async_session: AsyncSession) -> None:
    """Test granting a lunchbox reward."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, capacity=100, used=0)
    async_session.add(storage)
    await async_session.commit()

    result = await reward_service.grant_lunchbox(async_session, vault.id)

    assert result["reward_type"] == RewardType.LUNCHBOX
    assert "items" in result
    assert "dweller" in result
    assert len(result["items"]) >= 0


@pytest.mark.asyncio
async def test_process_quest_rewards_empty(async_session: AsyncSession) -> None:
    quest = Quest(
        title="Empty Quest",
        short_description="Test",
        long_description="No rewards",
        requirements="None",
        rewards="",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest, ["quest_rewards"])

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    results = await reward_service.process_quest_rewards(async_session, vault.id, quest)
    assert results == []


@pytest.mark.asyncio
async def test_process_quest_rewards_multiple(async_session: AsyncSession) -> None:
    """Test processing quest with multiple rewards."""
    quest = Quest(
        title="Multi Reward Quest",
        short_description="Test",
        long_description="Multiple rewards",
        requirements="None",
        rewards="caps and items",
        quest_type="main",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    reward1 = QuestReward(
        quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 200}, reward_chance=1.0
    )
    reward2 = QuestReward(
        quest_id=quest.id, reward_type=RewardType.STIMPAK, reward_data={"amount": 2}, reward_chance=1.0
    )
    async_session.add_all([reward1, reward2])
    await async_session.commit()

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    dweller_in = {
        "first_name": "Stim",
        "last_name": "User",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "level": 1,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 50,
        "strength": 5,
        "perception": 5,
        "endurance": 5,
        "charisma": 5,
        "intelligence": 5,
        "agility": 5,
        "luck": 5,
        "vault_id": vault.id,
    }
    from app.schemas.dweller import DwellerCreate

    await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_in))

    await async_session.refresh(quest, ["quest_rewards"])

    results = await reward_service.process_quest_rewards(async_session, vault.id, quest)

    assert len(results) == 2
    types = {r["reward_type"] for r in results}
    assert RewardType.CAPS in types
    assert RewardType.STIMPAK in types


@pytest.mark.asyncio
async def test_process_quest_rewards_error_handling(async_session: AsyncSession) -> None:
    """Test that quest reward processing continues after individual failures."""
    quest = Quest(
        title="Error Quest",
        short_description="Test",
        long_description="Has invalid reward",
        requirements="None",
        rewards="test",
        quest_type="side",
    )
    async_session.add(quest)
    await async_session.commit()
    await async_session.refresh(quest)

    reward = QuestReward(
        quest_id=quest.id,
        reward_type=RewardType.CAPS,
        reward_data={"amount": 50},
        reward_chance=1.0,
    )
    async_session.add(reward)
    await async_session.commit()
    await async_session.refresh(quest, ["quest_rewards"])

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    results = await reward_service.process_quest_rewards(async_session, vault.id, quest)
    assert len(results) == 1
    assert results[0]["amount"] == 50


@pytest.mark.asyncio
async def test_parse_objective_reward_water() -> None:
    """Test parsing water reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("30 water")

    assert reward_type == RewardType.RESOURCE
    assert reward_data["resource_type"] == "water"
    assert reward_data["amount"] == 30


@pytest.mark.asyncio
async def test_parse_objective_reward_power() -> None:
    """Test parsing power reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("25 power")

    assert reward_type == RewardType.RESOURCE
    assert reward_data["resource_type"] == "power"
    assert reward_data["amount"] == 25


@pytest.mark.asyncio
async def test_parse_objective_reward_xp() -> None:
    """Test parsing XP reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("200 xp")

    assert reward_type == RewardType.EXPERIENCE
    assert reward_data["amount"] == 200


@pytest.mark.asyncio
async def test_parse_objective_reward_experience() -> None:
    """Test parsing 'experience' reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("150 experience")

    assert reward_type == RewardType.EXPERIENCE
    assert reward_data["amount"] == 150


@pytest.mark.asyncio
async def test_parse_objective_reward_outfit() -> None:
    """Test parsing outfit reward string."""
    reward_type, reward_data = reward_service._parse_objective_reward("outfit:Combat Armor")

    assert reward_type == RewardType.ITEM
    assert reward_data["item_type"] == "outfit"
    assert reward_data["name"] == "Combat Armor"


@pytest.mark.asyncio
async def test_process_single_reward_experience(async_session: AsyncSession) -> None:
    """Test _process_single_reward routes experience correctly."""
    from app.schemas.dweller import DwellerCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    dweller_in = DwellerCreate(
        first_name="XP",
        last_name="Target",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        level=1,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        vault_id=vault.id,
    )
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    result = await reward_service._process_single_reward(
        async_session,
        vault.id,
        RewardType.EXPERIENCE,
        {"dweller_ids": [str(dweller.id)], "amount": 50},
    )

    assert result["reward_type"] == RewardType.EXPERIENCE


@pytest.mark.asyncio
async def test_process_single_reward_unknown_type_raises(async_session: AsyncSession) -> None:
    """Test _process_single_reward raises on unknown type."""
    with pytest.raises(ValueError, match="Unknown reward type"):
        await reward_service._process_single_reward(async_session, "fake-vault-id", "unknown_type", {})


@pytest.mark.asyncio
async def test_process_objective_reward_weapon(async_session: AsyncSession) -> None:
    from app.crud.objective import objective_crud
    from app.models.vault_objective import VaultObjectiveProgressLink
    from app.schemas.common import ObjectiveCategoryEnum
    from app.schemas.objective import ObjectiveCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=100)
    async_session.add(storage)
    await async_session.commit()

    objective = await objective_crud.create(
        async_session,
        ObjectiveCreate(challenge="Test", reward="weapon:Laser Pistol", category=ObjectiveCategoryEnum.ACHIEVEMENT),
    )

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    result = await reward_service.process_objective_reward(async_session, vault.id, link)

    assert result is not None
    assert result["reward_type"] == RewardType.ITEM
    assert result["item_type"] == "weapon"


@pytest.mark.asyncio
async def test_process_objective_reward_outfit(async_session: AsyncSession) -> None:
    from app.crud.objective import objective_crud
    from app.models.vault_objective import VaultObjectiveProgressLink
    from app.schemas.common import ObjectiveCategoryEnum
    from app.schemas.objective import ObjectiveCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=100)
    async_session.add(storage)
    await async_session.commit()

    objective = await objective_crud.create(
        async_session,
        ObjectiveCreate(challenge="Test", reward="outfit:Vault Suit", category=ObjectiveCategoryEnum.ACHIEVEMENT),
    )

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    result = await reward_service.process_objective_reward(async_session, vault.id, link)
    assert result is None


@pytest.mark.asyncio
async def test_process_objective_reward_dweller(async_session: AsyncSession) -> None:
    """Test processing objective reward for dweller."""
    from app.crud.objective import objective_crud
    from app.models.vault_objective import VaultObjectiveProgressLink
    from app.schemas.common import ObjectiveCategoryEnum
    from app.schemas.objective import ObjectiveCreate

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    objective = await objective_crud.create(
        async_session,
        ObjectiveCreate(challenge="Test", reward="dweller:Wanderer", category=ObjectiveCategoryEnum.ACHIEVEMENT),
    )

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    result = await reward_service.process_objective_reward(async_session, vault.id, link)

    assert result is not None
    assert result["reward_type"] == RewardType.DWELLER
