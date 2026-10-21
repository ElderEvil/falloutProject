"""Additional tests for RewardService — uncovered paths."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import ItemTypeEnum
from app.crud.user_profile import profile_crud
from app.models.dweller import Dweller
from app.models.item import Item
from app.models.outfit import Outfit
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.storage import Storage
from app.models.vault import Vault
from app.schemas.common import GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.reward_service import reward_service
from app.services.rewards import items, lunchbox, settlement
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.dwellers import level_progress, rarity_level_bounds
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("item_type", "name"),
    [("consumable", "Nuka-Cola Quantum"), ("lunchbox", "Lunchbox")],
)
async def test_grant_item_supported_generic_type_creates_item(
    async_session: AsyncSession, item_type: str, name: str
) -> None:
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
            "item_type": item_type,
            "name": name,
        },
    )
    item = await async_session.get(Item, UUID(result["item_id"]))

    assert result["item_type"] == item_type
    assert result["name"] == name
    assert result["amount"] == 1
    assert item is not None
    assert item.name == name
    assert item.item_type == item_type


@pytest.mark.asyncio
async def test_grant_item_pet_creates_pet_row(async_session: AsyncSession) -> None:
    """A pet reward mints a dedicated Pet row (not an inert generic Item), with art resolved."""
    from app.models.pet import Pet

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=100))
    await async_session.commit()

    result = await reward_service.grant_item(
        async_session, vault.id, {"item_type": "pet", "name": "CX404", "rarity": "legendary"}
    )

    assert result["item_type"] == "pet"
    assert result["name"] == "CX404"
    pet = await async_session.get(Pet, UUID(result["item_id"]))
    assert pet is not None
    assert pet.name == "CX404"
    assert pet.rarity == RarityEnum.LEGENDARY
    assert pet.image_url == "/static/pet_images/FOS CX404.png"
    assert (await async_session.execute(select(Item))).scalars().all() == []


@pytest.mark.asyncio
async def test_grant_item_infers_pet_from_name(async_session: AsyncSession) -> None:
    """A recognized pet name infers item_type='pet' and mints a Pet row without an explicit type."""
    from app.models.pet import Pet

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=100))
    await async_session.commit()

    result = await reward_service.grant_item(
        async_session, vault.id, {"item_name": "German Shepherd", "rarity": "rare"}
    )

    assert result["item_type"] == "pet"
    pet = await async_session.get(Pet, UUID(result["item_id"]))
    assert pet is not None
    assert pet.name == "German Shepherd"
    assert pet.rarity == RarityEnum.RARE
    assert pet.image_url == "/static/pet_images/FOS German Shepherd.png"
    assert (await async_session.execute(select(Item))).scalars().all() == []


def test_infer_item_type_recognizes_mapped_pet_names() -> None:
    """Pet inference keys off the mapped pet names and leaves existing categories untouched."""
    from app.schemas.quest import infer_item_type

    assert infer_item_type("German Shepherd") == "pet"
    assert infer_item_type("CX404") == "pet"
    assert infer_item_type("Dogmeat") == "junk"  # "dogmeat (fallout 4)" is the mapped key
    assert infer_item_type("Pool Cue") == "weapon"
    assert infer_item_type("Lunchbox") == "lunchbox"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("item_name", "stock_field", "reward_type"),
    [("Stimpak", "stimpack", RewardType.STIMPAK), ("RadAway", "radaway", RewardType.RADAWAY)],
)
async def test_grant_item_medication_credits_dweller_stock(
    async_session: AsyncSession, item_name: str, stock_field: str, reward_type: RewardType
) -> None:
    """ITEM-type medication must land in dweller stock, not as inert generic rows."""
    from app.schemas.dweller import DwellerCreate

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller_in = DwellerCreate(
        first_name="Med",
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
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    result = await reward_service.grant_item(async_session, vault.id, {"item_name": item_name, "quantity": 3})

    assert result["reward_type"] == reward_type
    assert result["amount"] == 3
    await async_session.refresh(dweller)
    assert getattr(dweller, stock_field) == 3
    assert (await async_session.execute(select(Item))).scalars().all() == []


@pytest.mark.asyncio
async def test_grant_item_unknown_type_raises(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    async_session.add(Storage(vault_id=vault.id, max_space=100))
    await async_session.commit()

    with pytest.raises(ValueError, match="Unsupported item_type: armor"):
        await reward_service.grant_item(async_session, vault.id, {"item_type": "armor", "name": "Mystery Item"})


@pytest.mark.asyncio
async def test_grant_item_no_storage_raises(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    with pytest.raises(ResourceNotFoundException, match="Storage"):
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

    with pytest.raises(ResourceConflictException, match="Storage full"):
        await reward_service.grant_item(
            async_session,
            vault.id,
            {
                "item_type": "weapon",
                "name": "Test Weapon",
            },
        )


@pytest.mark.asyncio
async def test_grant_item_legendary_dweller_uses_canonical_template(async_session: AsyncSession) -> None:
    """ITEM-type Legendary Dweller must materialize a canonical template, not a name-split random."""
    from app.utils.static_data import game_data_store

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )

    result = await reward_service.grant_item(
        async_session,
        vault.id,
        {"item_name": "Legendary Dweller", "quantity": 1, "rarity": "legendary"},
    )

    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))
    assert dweller is not None
    assert dweller.rarity == "legendary"
    legendary_names = {
        (template.first_name, template.last_name) for template in game_data_store.get_dwellers_by_rarity("legendary")
    }
    assert (dweller.first_name, dweller.last_name) in legendary_names


@pytest.mark.asyncio
async def test_grant_item_legendary_dweller_exhausted_pool_keeps_canonical_name(
    async_session: AsyncSession,
) -> None:
    """Exhausted legendary pool still grants a canonical name, not 'Legendary Dweller'."""
    from app.utils.static_data import game_data_store

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )

    with patch("app.services.rewards.items._pick_legendary_template_id", new=AsyncMock(return_value=None)):
        result = await reward_service.grant_item(
            async_session,
            vault.id,
            {"item_name": "Legendary Dweller", "quantity": 1, "rarity": "legendary"},
        )

    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))
    assert dweller is not None
    assert dweller.rarity == "legendary"
    legendary_names = {
        (template.first_name, template.last_name) for template in game_data_store.get_dwellers_by_rarity("legendary")
    }
    assert (dweller.first_name, dweller.last_name) in legendary_names
    assert (dweller.first_name, dweller.last_name) != ("Legendary", "Dweller")


@pytest.mark.asyncio
@pytest.mark.parametrize("rarity", [RarityEnum.RARE, RarityEnum.LEGENDARY])
async def test_grant_dweller_clamps_level_to_rarity_band(async_session: AsyncSession, rarity: RarityEnum) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    low, high = rarity_level_bounds(rarity)

    result = await reward_service.grant_dweller(
        async_session,
        vault.id,
        {"first_name": "Band", "last_name": "Test", "gender": "male", "rarity": rarity.value, "level": 1},
    )
    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))

    assert dweller is not None
    assert low <= dweller.level <= high
    max_health, experience = level_progress(dweller.level)
    assert dweller.max_health == max_health
    assert dweller.health == max_health
    assert dweller.experience == experience


@pytest.mark.asyncio
async def test_grant_legendary_dweller_keeps_in_band_level(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))

    result = await reward_service.grant_dweller(
        async_session,
        vault.id,
        {"first_name": "Veteran", "last_name": "Test", "gender": "female", "rarity": "legendary", "level": 30},
    )
    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))

    assert dweller is not None
    assert dweller.level == 30


@pytest.mark.asyncio
async def test_grant_legendary_dweller_without_level_rolls_band(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    low, high = rarity_level_bounds(RarityEnum.LEGENDARY)

    result = await reward_service.grant_dweller(
        async_session,
        vault.id,
        {"first_name": "Rolled", "last_name": "Test", "gender": "male", "rarity": "legendary"},
    )
    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))

    assert dweller is not None
    assert low <= dweller.level <= high


@pytest.mark.asyncio
async def test_grant_common_dweller_keeps_supplied_level(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))

    result = await reward_service.grant_dweller(
        async_session,
        vault.id,
        {"first_name": "Common", "last_name": "Test", "gender": "male", "rarity": "common", "level": 3},
    )
    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))

    assert dweller is not None
    assert dweller.level == 3


@pytest.mark.asyncio
async def test_prepare_template_dweller_clamps_level_override(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))

    data = await crud.dweller.prepare_template_dweller(
        async_session,
        vault.id,
        "abraham-washington",
        overrides={"level": 1},
    )
    low, high = rarity_level_bounds(RarityEnum.LEGENDARY)
    max_health, experience = level_progress(data["level"])

    assert low <= data["level"] <= high
    assert data["max_health"] == max_health
    assert data["health"] == max_health
    assert data["experience"] == experience


@pytest.mark.asyncio
async def test_grant_template_dweller_clamps_level_override(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    low, high = rarity_level_bounds(RarityEnum.LEGENDARY)

    result = await reward_service.grant_dweller(
        async_session, vault.id, {"template_id": "abraham-washington", "level": 1}
    )
    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))

    assert dweller is not None
    assert low <= dweller.level <= high


@pytest.mark.asyncio
async def test_grant_dweller_item_uses_reward_name(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))

    result = await reward_service.grant_item(
        async_session,
        vault.id,
        {"item_type": "dweller", "item_name": "Sarah Lyons", "rarity": "legendary"},
    )

    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))
    assert dweller is not None
    assert (dweller.first_name, dweller.last_name) == ("Sarah", "Lyons")


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
async def test_radaway_reward_goes_to_storage_when_vault_has_only_nonhumans(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    dweller.visual_attributes = {"race": "ghoul", "state_of_being": "sane"}
    dweller.radaway = 0
    storage = Storage(vault_id=vault.id, radaway=2)
    async_session.add_all([dweller, storage])
    await async_session.commit()

    result = await reward_service.grant_radaway(async_session, vault.id, 3)

    await async_session.refresh(storage)
    await async_session.refresh(dweller)
    assert result["amount"] == 3
    assert storage.radaway == 5
    assert dweller.radaway == 0


@pytest.mark.asyncio
async def test_grant_lunchbox(async_session: AsyncSession) -> None:
    """Granting a lunchbox reward mints one unopened Item; nothing auto-rolls."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=100)
    async_session.add(storage)
    await async_session.commit()

    result = await reward_service.grant_lunchbox(async_session, vault.id)

    assert result["reward_type"] == RewardType.ITEM
    assert result["item_type"] == "lunchbox"
    assert "dweller" not in result
    rows = (await async_session.execute(select(Item))).scalars().all()
    assert [(item.name, item.item_type) for item in rows] == [("Lunchbox", "lunchbox")]
    assert (await async_session.execute(select(Dweller))).scalars().all() == []


@pytest.mark.asyncio
async def test_grant_lunchbox_amount_mints_several(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=100))
    await async_session.commit()

    await reward_service.grant_lunchbox(async_session, vault.id, amount=3)

    rows = (await async_session.execute(select(Item))).scalars().all()
    assert [(item.name, item.item_type) for item in rows] == [("Lunchbox", "lunchbox")] * 3


def test_parse_objective_reward_lunchbox() -> None:
    assert settlement._parse_objective_reward("1 lunchbox") == (RewardType.LUNCHBOX, {"amount": 1})
    assert settlement._parse_objective_reward("2 lunchboxes") == (RewardType.LUNCHBOX, {"amount": 2})


@pytest.mark.asyncio
async def test_lunchbox_roll_is_catalog_backed(async_session: AsyncSession) -> None:
    """Every lunchbox roll is a real catalog row whose rarity matches the rolled tier."""
    from app.services import catalog_service as data_loader

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    storage = Storage(vault_id=vault.id, max_space=100)
    async_session.add(storage)
    await async_session.commit()
    await async_session.refresh(storage)

    granted_items, _ = await lunchbox._roll_lunchbox_contents(async_session, vault.id, storage.id)

    catalog = {
        str(entry["name"]).lower(): RarityEnum(entry["rarity"]).value
        for entry in data_loader.load_weapons() + data_loader.load_outfits()
    }
    assert granted_items
    for entry in granted_items:
        assert catalog[entry["name"].lower()] == entry["rarity"]


@pytest.mark.asyncio
async def test_grant_item_outfit_uses_catalog_stats(async_session: AsyncSession) -> None:
    """Objective/quest gear resolves through the catalog instead of a zero-SPECIAL default row."""
    from app.services import catalog_service as data_loader

    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=100))
    await async_session.commit()

    await reward_service.grant_item(
        async_session, vault.id, {"item_type": "outfit", "name": "Mechanic jumpsuit", "rarity": "common"}
    )

    outfit = (await async_session.execute(select(Outfit))).scalars().first()
    catalog_entry = next(o for o in data_loader.load_outfits() if o["name"] == "Mechanic jumpsuit")
    assert outfit is not None
    assert outfit.name == "Mechanic jumpsuit"
    assert outfit.outfit_type.value == catalog_entry["outfit_type"]
    assert outfit.strength == catalog_entry.get("strength", 0)


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


def test_parse_starter_resident_reward_returns_profile() -> None:
    """Named starter rewards carry their curated name, bio, and appearance."""
    reward_type, reward_data = settlement._parse_objective_reward("dweller:Juno Pike")

    assert reward_type == RewardType.DWELLER
    assert reward_data["first_name"] == "Juno"
    assert reward_data["last_name"] == "Pike"
    assert reward_data["bio"].startswith("Followed a pre-war radio signal")
    assert reward_data["visual_attributes"]["hair_style"] == "short"


@pytest.mark.asyncio
async def test_starter_resident_reward_creates_named_dweller(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    _, reward_data = settlement._parse_objective_reward("dweller:Juno Pike")

    result = await reward_service.grant_dweller(async_session, vault.id, reward_data)
    dweller = await crud.dweller.get(async_session, UUID(result["dweller_id"]))

    assert dweller.first_name == "Juno"
    assert dweller.last_name == "Pike"
    assert dweller.bio.startswith("Followed a pre-war radio signal")
    assert dweller.visual_attributes["hair_style"] == "short"


@pytest.mark.parametrize(
    ("reward_str", "expected_type", "expected_data"),
    [
        pytest.param("30 water", RewardType.RESOURCE, {"resource_type": "water", "amount": 30}, id="water"),
        pytest.param("25 power", RewardType.RESOURCE, {"resource_type": "power", "amount": 25}, id="power"),
        pytest.param("200 xp", RewardType.EXPERIENCE, {"amount": 200, "dweller_ids": []}, id="xp"),
        pytest.param("150 experience", RewardType.EXPERIENCE, {"amount": 150, "dweller_ids": []}, id="experience"),
        pytest.param(
            "weapon:rare:Hardened shotgun",
            RewardType.ITEM,
            {"item_type": "weapon", "name": "Hardened shotgun", "rarity": "rare"},
            id="rare-weapon",
        ),
        pytest.param(
            "outfit:Combat Armor",
            RewardType.ITEM,
            {"item_type": "outfit", "name": "Combat Armor", "rarity": "common"},
            id="outfit",
        ),
    ],
)
def test_parse_objective_reward(reward_str: str, expected_type: RewardType, expected_data: dict[str, object]) -> None:
    """_parse_objective_reward splits a reward string into its type and payload."""
    reward_type, reward_data = settlement._parse_objective_reward(reward_str)

    assert reward_type == expected_type
    assert reward_data == expected_data


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

    result = await settlement._process_single_reward(
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
        await settlement._process_single_reward(async_session, "fake-vault-id", "unknown_type", {})


@pytest.mark.parametrize(
    ("reward_str", "expected"),
    [
        pytest.param("weapon:Laser Pistol", {"reward_type": RewardType.ITEM, "item_type": "weapon"}, id="weapon"),
        pytest.param("outfit:Vault Suit", {"reward_type": RewardType.ITEM, "item_type": "outfit"}, id="outfit"),
        pytest.param("dweller:Wanderer", {"reward_type": RewardType.DWELLER}, id="dweller"),
    ],
)
@pytest.mark.asyncio
async def test_process_objective_reward(
    async_session: AsyncSession, reward_str: str, expected: dict[str, object]
) -> None:
    """process_objective_reward settles the objective's parsed reward for the vault."""
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
        ObjectiveCreate(challenge="Test", reward=reward_str, category=ObjectiveCategoryEnum.ACHIEVEMENT),
    )

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    result = await reward_service.process_objective_reward(async_session, vault.id, link)

    assert result is not None
    for key, value in expected.items():
        assert result[key] == value


@pytest.mark.asyncio
async def test_template_reservation_conflict_grants_fallback(async_session: AsyncSession) -> None:
    """A template already active in the vault reserves the slot: second grant falls back to common."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    template_id = "abraham-washington"
    first = await reward_service.grant_dweller(async_session, vault.id, {"template_id": template_id})
    second = await reward_service.grant_dweller(async_session, vault.id, {"template_id": template_id})

    assert first["name"] == "Abraham Washington"
    assert second["name"] != "Abraham Washington"

    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id=vault.id)
    curated = [d for d in dwellers if f"{d.first_name} {d.last_name or ''}".strip() == "Abraham Washington"]
    assert len(curated) == 1
    fallback = next(d for d in dwellers if str(d.id) == second["dweller_id"])
    assert fallback.rarity == RarityEnum.COMMON


@pytest.mark.asyncio
async def test_lunchbox_template_picks_are_distinct(async_session: AsyncSession) -> None:
    """Concurrent-eligible lunchbox openings pick distinct templates instead of a COMMON fallback."""
    from uuid import UUID

    from app.utils.static_data import game_data_store

    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=100))
    await async_session.commit()

    first_mint = await reward_service.grant_lunchbox(async_session, vault.id)
    second_mint = await reward_service.grant_lunchbox(async_session, vault.id)

    roster = {f"{t.first_name} {t.last_name or ''}".strip() for t in game_data_store.get_dwellers_by_rarity("rare")}
    with patch("app.services.rewards.lunchbox.random.choices", return_value=[RarityEnum.RARE]):
        first = await reward_service.open_lunchbox(async_session, vault.id, UUID(first_mint["item_id"]))
        second = await reward_service.open_lunchbox(async_session, vault.id, UUID(second_mint["item_id"]))

    assert first["reward_type"] == RewardType.LUNCHBOX
    assert len(first["items"]) == 3
    assert first["dweller"]["name"] in roster
    assert second["dweller"]["name"] in roster
    assert first["dweller"]["name"] != second["dweller"]["name"]
    remaining = (await async_session.execute(select(Item))).scalars().all()
    assert [item.item_type for item in remaining] == []


async def _vault_at_capacity(async_session: AsyncSession):
    """A vault holding exactly one living dweller at a cap of one."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    vault.population_max = 1
    async_session.add(vault)
    await crud.dweller.create(async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=vault.id))
    await async_session.commit()
    return vault


@pytest.mark.asyncio
async def test_dweller_reward_at_capacity_is_refused(async_session: AsyncSession) -> None:
    """A quest/objective dweller reward is refused at the cap, leaving the vault unchanged."""
    vault = await _vault_at_capacity(async_session)

    with pytest.raises(ResourceConflictException, match="population capacity"):
        await settlement._process_single_reward(
            async_session, vault.id, RewardType.DWELLER, {"first_name": "Newcomer", "rarity": "common"}
        )

    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 1


@pytest.mark.asyncio
async def test_item_to_dweller_reward_at_capacity_is_refused(async_session: AsyncSession) -> None:
    """A dweller item reward is refused at the cap."""
    vault = await _vault_at_capacity(async_session)

    with pytest.raises(ResourceConflictException, match="population capacity"):
        await reward_service.grant_item(
            async_session, vault.id, {"item_type": "dweller", "item_name": "Sarah Lyons", "rarity": "legendary"}
        )

    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 1


@pytest.mark.asyncio
async def test_lunchbox_dweller_at_capacity_is_refused_and_box_kept(async_session: AsyncSession) -> None:
    """Opening a lunchbox at the cap is refused and the box survives the rollback."""
    vault = await _vault_at_capacity(async_session)
    vault_id = vault.id
    async_session.add(Storage(vault_id=vault_id, max_space=100))
    await async_session.commit()
    minted = await reward_service.grant_lunchbox(async_session, vault_id)

    with pytest.raises(ResourceConflictException, match="population capacity"):
        await reward_service.open_lunchbox(async_session, vault_id, UUID(minted["item_id"]))

    await async_session.rollback()
    assert await crud.dweller.count_living_in_vault(async_session, vault_id) == 1
    remaining = (await async_session.execute(select(Item))).scalars().all()
    assert [item.item_type for item in remaining] == ["lunchbox"]


def test_reward_junk_uses_data_supplied_type_value_prose_and_art() -> None:
    """Migrated _build_junk forwards reward-data fields into the factory row unchanged."""
    from uuid import uuid4

    from app.core.enums import JunkTypeEnum
    from app.models.junk import Junk

    storage_id = uuid4()
    junk = items._build_junk(
        "Desk Fan",
        "rare",
        {"junk_type": JunkTypeEnum.CIRCUITRY, "value": 42, "description": "A dusty fan", "image_url": "/custom.png"},
        storage_id,
    )

    assert isinstance(junk, Junk)
    assert (junk.name, junk.junk_type, junk.value, junk.description, junk.image_url, junk.storage_id) == (
        "Desk Fan",
        JunkTypeEnum.CIRCUITRY,
        42,
        "A dusty fan",
        "/custom.png",
        storage_id,
    )


def test_reward_junk_falls_back_to_valuables_and_name_keyed_art() -> None:
    """Absent reward data keeps the exploration default: valuables, name-keyed art, rarity value."""
    from uuid import uuid4

    from app.core.enums import JunkTypeEnum
    from app.utils.junk_assets import get_junk_image_url

    junk = items._build_junk("Desk Fan", "common", {}, uuid4())

    assert junk.junk_type is JunkTypeEnum.VALUABLES
    assert junk.description == "Desk Fan"
    assert junk.value is None
    assert junk.image_url == get_junk_image_url("Desk Fan")


@pytest.mark.asyncio
async def test_grant_item_nuka_cola_succeeds_with_full_storage(async_session: AsyncSession) -> None:
    """Nuka-Cola bottles occupy no slot: they land even at zero available space."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=1)
    async_session.add(storage)
    async_session.add(
        Item(name="Stimpak", item_type=ItemTypeEnum.CONSUMABLE, rarity=RarityEnum.COMMON, storage_id=None)
    )
    await async_session.commit()
    filler = await async_session.exec(select(Item).where(Item.name == "Stimpak"))
    filler_row = filler.one()
    filler_row.storage_id = storage.id
    async_session.add(filler_row)
    await async_session.commit()

    result = await reward_service.grant_item(
        async_session,
        vault.id,
        {"item_type": "consumable", "name": "Nuka-Cola Quantum"},
    )
    await async_session.commit()

    assert result["item_type"] == "consumable"
    assert result["item_id"] is not None
    stored = await crud.storage.count_storage_items(async_session, storage.id)
    assert stored == 1  # only the counted filler; the bottles are space-free


@pytest.mark.asyncio
async def test_grant_item_full_storage_still_rejects_counted_items(async_session: AsyncSession) -> None:
    """Non-space-free rewards keep failing the capacity check in a full vault."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    storage = Storage(vault_id=vault.id, max_space=1)
    async_session.add(storage)
    async_session.add(
        Item(name="Stimpak", item_type=ItemTypeEnum.CONSUMABLE, rarity=RarityEnum.COMMON, storage_id=None)
    )
    await async_session.commit()
    filler_result = await async_session.exec(select(Item).where(Item.name == "Stimpak"))
    filler_row = filler_result.one()
    filler_row.storage_id = storage.id
    async_session.add(filler_row)
    await async_session.commit()

    with pytest.raises(ResourceConflictException):
        await reward_service.grant_item(async_session, vault.id, {"item_type": "lunchbox", "name": "Lunchbox"})
