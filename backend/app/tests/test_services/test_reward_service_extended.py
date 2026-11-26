from contextlib import nullcontext
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import GenderEnum, ItemTypeEnum, JunkTypeEnum, ObjectiveCategoryEnum, RarityEnum, RewardType
from app.crud.objective import objective_crud
from app.models.dweller import Dweller
from app.models.item import Item
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.pet import Pet
from app.models.quest import Quest
from app.models.quest_reward import QuestReward
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.weapon import Weapon
from app.schemas.dweller import DwellerCreate
from app.schemas.objective import ObjectiveCreate
from app.schemas.quest import infer_item_type
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services import catalog_service as data_loader
from app.services.reward_service import reward_service
from app.services.rewards import items, lunchbox, settlement
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.dwellers import level_progress, rarity_level_bounds
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException
from app.utils.junk_assets import get_junk_image_url
from app.utils.static_data import game_data_store


async def _vault(async_session: AsyncSession) -> Vault:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


async def _vault_with_storage(async_session: AsyncSession, max_space: int = 100) -> Vault:
    vault = await _vault(async_session)
    async_session.add(Storage(vault_id=vault.id, max_space=max_space))
    await async_session.commit()
    return vault


async def _dweller(async_session: AsyncSession, vault: Vault, **overrides) -> Dweller:
    stats = {"strength": 5, "perception": 5, "endurance": 5, "charisma": 5, "intelligence": 5, "agility": 5, "luck": 5}
    body = {"first_name": "Med", "last_name": "Test", "gender": GenderEnum.FEMALE, "rarity": RarityEnum.COMMON}
    vitals = {"level": 1, "experience": 0, "max_health": 100, "health": 100, "radiation": 0, "happiness": 50}
    data = body | vitals | stats | {"vault_id": vault.id} | overrides
    return await crud.dweller.create(async_session, obj_in=DwellerCreate(**data))


async def _grant_dweller(async_session: AsyncSession, vault: Vault, **data) -> Dweller | None:
    result = await reward_service.grant_dweller(async_session, vault.id, data)
    return await async_session.get(Dweller, UUID(result["dweller_id"]))


async def _quest(async_session: AsyncSession, quest_rewards: list = (), **fields) -> Quest:
    base = {"title": "Test Quest", "short_description": "Test", "long_description": "Test quest", "quest_type": "side"}
    quest = Quest(**(base | {"requirements": "None", "rewards": "caps"} | fields))
    async_session.add(quest)
    await async_session.commit()
    rows = [QuestReward(quest_id=quest.id, reward_type=t, reward_data=d, reward_chance=c) for t, d, c in quest_rewards]
    async_session.add_all(rows)
    await async_session.commit()
    await async_session.refresh(quest, ["quest_rewards"])
    return quest


async def _storage_with_filler(async_session: AsyncSession, vault: Vault) -> Storage:
    storage = Storage(vault_id=vault.id, max_space=1)
    async_session.add(storage)
    await async_session.commit()
    async_session.add(
        Item(name="Stimpak", item_type=ItemTypeEnum.CONSUMABLE, rarity=RarityEnum.COMMON, storage_id=storage.id)
    )
    await async_session.commit()
    return storage


@pytest.mark.parametrize(
    ("item_type", "name"),
    [("consumable", "Nuka-Cola Quantum"), ("lunchbox", "Lunchbox")],
)
async def test_grant_item_supported_generic_type_creates_item(
    async_session: AsyncSession, item_type: str, name: str
) -> None:
    vault = await _vault_with_storage(async_session)
    result = await reward_service.grant_item(async_session, vault.id, {"item_type": item_type, "name": name})
    item = await async_session.get(Item, UUID(result["item_id"]))
    assert (result["item_type"], result["name"], result["amount"]) == (item_type, name, 1)
    assert item is not None
    assert (item.name, item.item_type) == (name, item_type)


@pytest.mark.parametrize(
    ("payload", "name", "rarity"),
    [
        ({"item_type": "pet", "name": "CX404", "rarity": "legendary"}, "CX404", RarityEnum.LEGENDARY),
        ({"item_name": "German Shepherd", "rarity": "rare"}, "German Shepherd", RarityEnum.RARE),
    ],
)
async def test_grant_item_pet_creates_pet_row(async_session: AsyncSession, payload: dict, name: str, rarity) -> None:
    vault = await _vault_with_storage(async_session)
    result = await reward_service.grant_item(async_session, vault.id, payload)
    assert (result["item_type"], result["name"]) == ("pet", name)
    pet = await async_session.get(Pet, UUID(result["item_id"]))
    assert pet is not None
    assert (pet.name, pet.rarity, pet.image_url) == (name, rarity, f"/static/pet_images/FOS {name}.png")
    assert (await async_session.execute(select(Item))).scalars().all() == []


def test_infer_item_type_recognizes_mapped_pet_names() -> None:
    assert infer_item_type("German Shepherd") == "pet"
    assert infer_item_type("CX404") == "pet"
    assert infer_item_type("Dogmeat") == "junk"  # "dogmeat (fallout 4)" is the mapped key
    assert infer_item_type("Pool Cue") == "weapon"
    assert infer_item_type("Lunchbox") == "lunchbox"


@pytest.mark.parametrize(
    ("item_name", "stock_field", "reward_type"),
    [("Stimpak", "stimpack", RewardType.STIMPAK), ("RadAway", "radaway", RewardType.RADAWAY)],
)
async def test_grant_item_medication_credits_dweller_stock(
    async_session: AsyncSession, item_name: str, stock_field: str, reward_type: RewardType
) -> None:
    # ITEM-type medication must land in dweller stock, not as inert generic rows.
    vault = await _vault(async_session)
    dweller = await _dweller(async_session, vault)
    result = await reward_service.grant_item(async_session, vault.id, {"item_name": item_name, "quantity": 3})
    assert (result["reward_type"], result["amount"]) == (reward_type, 3)
    await async_session.refresh(dweller)
    assert getattr(dweller, stock_field) == 3
    assert (await async_session.execute(select(Item))).scalars().all() == []


async def test_grant_item_unknown_type_raises(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    with pytest.raises(ValueError, match="Unsupported item_type: armor"):
        await reward_service.grant_item(async_session, vault.id, {"item_type": "armor", "name": "Mystery Item"})


async def test_grant_item_no_storage_raises(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    with pytest.raises(ResourceNotFoundException, match="Storage"):
        await reward_service.grant_item(async_session, vault.id, {"item_type": "weapon", "name": "Test Weapon"})


async def test_grant_item_storage_full_raises(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    storage = Storage(vault_id=vault.id, max_space=1)
    async_session.add(storage)
    await async_session.commit()
    await async_session.refresh(storage)
    weapon = {"name": "Filler", "rarity": "common", "weapon_type": "melee", "weapon_subtype": "blunt"}
    async_session.add(Weapon(**weapon, stat="strength", damage_min=1, damage_max=3, storage_id=storage.id))
    await async_session.commit()
    with pytest.raises(ResourceConflictException, match="Storage full"):
        await reward_service.grant_item(async_session, vault.id, {"item_type": "weapon", "name": "Test Weapon"})


@pytest.mark.parametrize("exhausted_pool", [False, True])
async def test_grant_item_legendary_dweller_uses_canonical_template(
    async_session: AsyncSession, exhausted_pool: bool
) -> None:
    # ITEM-type Legendary Dweller must materialize a canonical template, not a name-split random.
    vault = await _vault(async_session)
    pool = patch("app.services.rewards.items._pick_legendary_template_id", new=AsyncMock(return_value=None))
    with pool if exhausted_pool else nullcontext():
        result = await reward_service.grant_item(
            async_session, vault.id, {"item_name": "Legendary Dweller", "quantity": 1, "rarity": "legendary"}
        )
    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))
    assert dweller is not None
    assert dweller.rarity == "legendary"
    legendary_names = {
        (template.first_name, template.last_name) for template in game_data_store.get_dwellers_by_rarity("legendary")
    }
    assert (dweller.first_name, dweller.last_name) in legendary_names
    if exhausted_pool:
        assert (dweller.first_name, dweller.last_name) != ("Legendary", "Dweller")


@pytest.mark.parametrize("rarity", [RarityEnum.RARE, RarityEnum.LEGENDARY])
async def test_grant_dweller_clamps_level_to_rarity_band(async_session: AsyncSession, rarity: RarityEnum) -> None:
    vault = await _vault(async_session)
    low, high = rarity_level_bounds(rarity)
    dweller = await _grant_dweller(
        async_session, vault, first_name="Band", last_name="Test", rarity=rarity.value, level=1
    )
    assert dweller is not None
    assert low <= dweller.level <= high
    max_health, experience = level_progress(dweller.level)
    assert (dweller.max_health, dweller.health, dweller.experience) == (max_health, max_health, experience)


@pytest.mark.parametrize(("rarity", "level"), [("legendary", 30), ("common", 3)])
async def test_grant_dweller_keeps_supplied_level(async_session: AsyncSession, rarity: str, level: int) -> None:
    vault = await _vault(async_session)
    dweller = await _grant_dweller(async_session, vault, first_name="Veteran", rarity=rarity, level=level)
    assert dweller is not None
    assert dweller.level == level


async def test_grant_legendary_dweller_without_level_rolls_band(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    low, high = rarity_level_bounds(RarityEnum.LEGENDARY)
    dweller = await _grant_dweller(async_session, vault, first_name="Rolled", rarity="legendary")
    assert dweller is not None
    assert low <= dweller.level <= high


async def test_prepare_template_dweller_clamps_level_override(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    data = await crud.dweller.prepare_template_dweller(
        async_session, vault.id, "abraham-washington", overrides={"level": 1}
    )
    low, high = rarity_level_bounds(RarityEnum.LEGENDARY)
    max_health, experience = level_progress(data["level"])
    assert low <= data["level"] <= high
    assert (data["max_health"], data["health"], data["experience"]) == (max_health, max_health, experience)


async def test_prepare_template_dweller_unknown_id_raises_404(async_session: AsyncSession) -> None:
    # An unknown template id raises the 404 guard, not a TypeError from the constructor.
    vault = await _vault(async_session)
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await crud.dweller.prepare_template_dweller(async_session, vault.id, "no-such-template")
    assert "no-such-template" in str(excinfo.value)


async def test_grant_dweller_unknown_template_raises_404(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    with pytest.raises(ResourceNotFoundException) as excinfo:
        await reward_service.grant_dweller(async_session, vault.id, {"template_id": "no-such-template"})
    assert "no-such-template" in str(excinfo.value)


async def test_grant_template_dweller_clamps_level_override(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    low, high = rarity_level_bounds(RarityEnum.LEGENDARY)
    dweller = await _grant_dweller(async_session, vault, template_id="abraham-washington", level=1)
    assert dweller is not None
    assert low <= dweller.level <= high


async def test_grant_dweller_item_uses_reward_name(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    result = await reward_service.grant_item(
        async_session, vault.id, {"item_type": "dweller", "item_name": "Sarah Lyons", "rarity": "legendary"}
    )
    dweller = await async_session.get(Dweller, UUID(result["dweller_id"]))
    assert dweller is not None
    assert (dweller.first_name, dweller.last_name) == ("Sarah", "Lyons")


@pytest.mark.parametrize(("field", "amount"), [("water", 50), ("power", 75)])
async def test_grant_resource_tracks_and_caps(async_session: AsyncSession, field: str, amount: int) -> None:
    vault = await _vault(async_session)
    setattr(vault, f"{field}_max", 1000)
    await async_session.commit()
    initial = getattr(vault, field)
    result = await reward_service.grant_resource(async_session, vault.id, field, amount)
    assert (result["reward_type"], result["resource_type"], result["amount"]) == (RewardType.RESOURCE, field, amount)
    await async_session.refresh(vault)
    assert getattr(vault, field) == min(initial + amount, getattr(vault, f"{field}_max"))


async def test_grant_resource_caps_at_max(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    vault.food, vault.food_max = 950, 1000
    await async_session.commit()
    await reward_service.grant_resource(async_session, vault.id, "food", 100)
    await async_session.refresh(vault)
    assert vault.food == 1000


async def test_grant_resource_invalid_type(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    with pytest.raises(ValueError, match="Invalid resource_type"):
        await reward_service.grant_resource(async_session, vault.id, "invalid", 100)


async def test_grant_caps_zero_amount(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    initial_caps = vault.bottle_caps
    result = await reward_service.grant_caps(async_session, vault.id, 0)
    assert result["amount"] == 0
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps


async def test_grant_experience_level_up(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    dweller = await _dweller(async_session, vault, first_name="Level", last_name="Up", experience=182)
    result = await reward_service.grant_experience(async_session, [dweller.id], 100)
    assert str(dweller.id) in result["leveled_up"]
    await async_session.refresh(dweller)
    assert (dweller.level, dweller.experience) == (2, 282)


async def test_grant_stimpak_no_dwellers(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    result = await reward_service.grant_stimpak(async_session, vault.id, 5)
    assert (result["reward_type"], result["amount"]) == (RewardType.STIMPAK, 0)
    assert "No dwellers" in result["message"]


async def test_grant_radaway_success(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    await _dweller(async_session, vault, first_name="Rad")
    result = await reward_service.grant_radaway(async_session, vault.id, 3)
    assert (result["reward_type"], result["amount"]) == (RewardType.RADAWAY, 3)


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
    assert (storage.radaway, dweller.radaway) == (5, 0)


@pytest.mark.parametrize("amount", [1, 3])
async def test_grant_lunchbox_mints_items(async_session: AsyncSession, amount: int) -> None:
    vault = await _vault_with_storage(async_session)
    result = await reward_service.grant_lunchbox(async_session, vault.id, amount=amount)
    assert (result["reward_type"], result["item_type"]) == (RewardType.ITEM, "lunchbox")
    assert "dweller" not in result
    rows = (await async_session.execute(select(Item))).scalars().all()
    assert [(item.name, item.item_type) for item in rows] == [("Lunchbox", "lunchbox")] * amount
    assert (await async_session.execute(select(Dweller))).scalars().all() == []


async def test_lunchbox_roll_is_catalog_backed(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    storage = (await async_session.execute(select(Storage))).scalars().one()
    granted_items, _ = await lunchbox._roll_lunchbox_contents(async_session, vault.id, storage.id)
    catalog = {
        str(entry["name"]).lower(): RarityEnum(entry["rarity"]).value
        for entry in data_loader.load_weapons() + data_loader.load_outfits()
    }
    assert granted_items
    for entry in granted_items:
        assert catalog[entry["name"].lower()] == entry["rarity"]


async def test_grant_item_outfit_uses_catalog_stats(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    await reward_service.grant_item(
        async_session, vault.id, {"item_type": "outfit", "name": "Mechanic jumpsuit", "rarity": "common"}
    )
    outfit = (await async_session.execute(select(Outfit))).scalars().first()
    catalog_entry = next(o for o in data_loader.load_outfits() if o["name"] == "Mechanic jumpsuit")
    assert outfit is not None
    assert (outfit.name, outfit.outfit_type.value) == ("Mechanic jumpsuit", catalog_entry["outfit_type"])
    assert outfit.strength == catalog_entry.get("strength", 0)


async def test_process_quest_rewards_with_chance_failure(async_session: AsyncSession) -> None:
    quest = await _quest(async_session, [(RewardType.CAPS, {"amount": 100}, 0.0)])
    vault = await _vault(async_session)
    initial_caps = vault.bottle_caps
    results = await reward_service.process_quest_rewards(async_session, vault.id, quest)
    assert len(results) == 0  # Reward not granted due to 0% chance
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps


async def test_process_quest_dweller_template_reward_uses_canonical_stats(async_session: AsyncSession) -> None:
    quest = await _quest(
        async_session,
        [(RewardType.DWELLER, {"template_id": "abraham-washington"}, 1.0)],
        title="Template Dweller Reward",
        short_description="A known hero joins the vault.",
        long_description="Completing this quest grants Abraham Washington.",
        rewards="Abraham Washington",
    )
    vault = await _vault(async_session)
    rewards = await reward_service.process_quest_rewards(async_session, vault.id, quest)
    dweller = await async_session.get(Dweller, UUID(rewards[0]["dweller_id"]))
    assert dweller is not None
    assert (dweller.first_name, dweller.last_name, dweller.rarity) == ("Abraham", "Washington", "legendary")
    assert (dweller.strength, dweller.perception, dweller.endurance) == (2, 8, 6)


async def test_process_quest_rewards_empty(async_session: AsyncSession) -> None:
    quest = await _quest(async_session, title="Empty Quest", long_description="No rewards", rewards="")
    vault = await _vault(async_session)
    assert await reward_service.process_quest_rewards(async_session, vault.id, quest) == []


async def test_process_quest_rewards_multiple(async_session: AsyncSession) -> None:
    quest = await _quest(
        async_session,
        [(RewardType.CAPS, {"amount": 200}, 1.0), (RewardType.STIMPAK, {"amount": 2}, 1.0)],
        title="Multi Reward Quest",
        long_description="Multiple rewards",
        rewards="caps and items",
        quest_type="main",
    )
    vault = await _vault(async_session)
    await _dweller(async_session, vault, first_name="Stim", last_name="User", gender=GenderEnum.MALE)
    results = await reward_service.process_quest_rewards(async_session, vault.id, quest)
    assert len(results) == 2
    types = {r["reward_type"] for r in results}
    assert RewardType.CAPS in types
    assert RewardType.STIMPAK in types


@pytest.mark.parametrize(
    ("reward_str", "expected_type", "expected_data"),
    [
        pytest.param("30 water", RewardType.RESOURCE, {"resource_type": "water", "amount": 30}, id="water"),
        pytest.param("25 power", RewardType.RESOURCE, {"resource_type": "power", "amount": 25}, id="power"),
        pytest.param("200 xp", RewardType.EXPERIENCE, {"amount": 200, "dweller_ids": []}, id="xp"),
        pytest.param("150 experience", RewardType.EXPERIENCE, {"amount": 150, "dweller_ids": []}, id="experience"),
        pytest.param("1 lunchbox", RewardType.LUNCHBOX, {"amount": 1}, id="lunchbox"),
        pytest.param("2 lunchboxes", RewardType.LUNCHBOX, {"amount": 2}, id="lunchboxes"),
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
        pytest.param(
            "1 pet carrier",
            RewardType.ITEM,
            {"item_type": "pet_carrier", "name": "Pet Carrier", "rarity": "common", "amount": 1},
            id="pet-carrier",
        ),
    ],
)
def test_parse_objective_reward(reward_str: str, expected_type: RewardType, expected_data: dict[str, object]) -> None:
    reward_type, reward_data = settlement._parse_objective_reward(reward_str)
    assert (reward_type, reward_data) == (expected_type, expected_data)


def test_parse_starter_resident_reward_returns_profile() -> None:
    reward_type, reward_data = settlement._parse_objective_reward("dweller:Juno Pike")
    assert reward_type == RewardType.DWELLER
    assert (reward_data["first_name"], reward_data["last_name"]) == ("Juno", "Pike")
    assert reward_data["bio"].startswith("Followed a pre-war radio signal")
    assert reward_data["visual_attributes"]["hair_style"] == "short"


async def test_starter_resident_reward_creates_named_dweller(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    _, reward_data = settlement._parse_objective_reward("dweller:Juno Pike")
    result = await reward_service.grant_dweller(async_session, vault.id, reward_data)
    dweller = await crud.dweller.get(async_session, UUID(result["dweller_id"]))
    assert (dweller.first_name, dweller.last_name) == ("Juno", "Pike")
    assert dweller.bio.startswith("Followed a pre-war radio signal")
    assert dweller.visual_attributes["hair_style"] == "short"


async def test_process_single_reward_experience(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    dweller = await _dweller(async_session, vault, first_name="XP", last_name="Target", gender=GenderEnum.MALE)
    result = await settlement._process_single_reward(
        async_session, vault.id, RewardType.EXPERIENCE, {"dweller_ids": [str(dweller.id)], "amount": 50}
    )
    assert result["reward_type"] == RewardType.EXPERIENCE


async def test_process_single_reward_unknown_type_raises(async_session: AsyncSession) -> None:
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
async def test_process_objective_reward(
    async_session: AsyncSession, reward_str: str, expected: dict[str, object]
) -> None:
    vault = await _vault_with_storage(async_session)
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


async def test_template_reservation_conflict_grants_fallback(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
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


async def test_lunchbox_template_picks_are_distinct(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    first_mint = await reward_service.grant_lunchbox(async_session, vault.id)
    second_mint = await reward_service.grant_lunchbox(async_session, vault.id)
    roster = {f"{t.first_name} {t.last_name or ''}".strip() for t in game_data_store.get_dwellers_by_rarity("rare")}
    with patch("app.services.rewards.lunchbox.random.choices", return_value=[RarityEnum.RARE]):
        first = await reward_service.open_lunchbox(async_session, vault.id, UUID(first_mint["item_id"]))
        second = await reward_service.open_lunchbox(async_session, vault.id, UUID(second_mint["item_id"]))
    assert (first["reward_type"], len(first["items"])) == (RewardType.LUNCHBOX, 3)
    assert first["dweller"]["name"] in roster
    assert second["dweller"]["name"] in roster
    assert first["dweller"]["name"] != second["dweller"]["name"]
    remaining = (await async_session.execute(select(Item))).scalars().all()
    assert [item.item_type for item in remaining] == []


async def _vault_at_capacity(async_session: AsyncSession) -> Vault:
    vault = await _vault(async_session)
    vault.population_max = 1
    async_session.add(vault)
    await crud.dweller.create(async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=vault.id))
    await async_session.commit()
    return vault


async def test_dweller_reward_at_capacity_is_refused(async_session: AsyncSession) -> None:
    vault = await _vault_at_capacity(async_session)
    with pytest.raises(ResourceConflictException, match="population capacity"):
        await settlement._process_single_reward(
            async_session, vault.id, RewardType.DWELLER, {"first_name": "Newcomer", "rarity": "common"}
        )
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 1


async def test_item_to_dweller_reward_at_capacity_is_refused(async_session: AsyncSession) -> None:
    vault = await _vault_at_capacity(async_session)
    with pytest.raises(ResourceConflictException, match="population capacity"):
        await reward_service.grant_item(
            async_session, vault.id, {"item_type": "dweller", "item_name": "Sarah Lyons", "rarity": "legendary"}
        )
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 1


async def test_lunchbox_dweller_at_capacity_is_refused_and_box_kept(async_session: AsyncSession) -> None:
    vault = await _vault_at_capacity(async_session)
    vault_id = vault.id  # Read before the rollback expires the instance.
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
    storage_id = uuid4()
    junk = items._build_junk(
        "Desk Fan",
        "rare",
        {"junk_type": JunkTypeEnum.CIRCUITRY, "value": 42, "description": "A dusty fan", "image_url": "/custom.png"},
        storage_id,
    )
    assert isinstance(junk, Junk)
    assert (junk.name, junk.junk_type, junk.value, junk.description, junk.image_url, junk.storage_id) == (
        "Desk fan",  # Catalog casing; the authored type, value, prose and art still win.
        JunkTypeEnum.CIRCUITRY,
        42,
        "A dusty fan",
        "/custom.png",
        storage_id,
    )


def test_reward_junk_falls_back_to_valuables_and_name_keyed_art() -> None:
    junk = items._build_junk("Mystery trinket", "common", {}, uuid4())
    assert junk.name == "Mystery trinket"
    assert junk.junk_type is JunkTypeEnum.VALUABLES
    assert junk.description == "Mystery trinket"
    assert junk.value is None
    assert junk.image_url == get_junk_image_url("Mystery trinket")


async def test_grant_item_nuka_cola_succeeds_with_full_storage(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    storage = await _storage_with_filler(async_session, vault)
    result = await reward_service.grant_item(
        async_session, vault.id, {"item_type": "consumable", "name": "Nuka-Cola Quantum"}
    )
    await async_session.commit()
    assert (result["item_type"], result["item_id"] is not None) == ("consumable", True)
    stored = await crud.storage.count_storage_items(async_session, storage.id)
    assert stored == 1  # only the counted filler; the bottles are space-free


async def test_grant_item_full_storage_still_rejects_counted_items(async_session: AsyncSession) -> None:
    vault = await _vault(async_session)
    await _storage_with_filler(async_session, vault)
    with pytest.raises(ResourceConflictException):
        await reward_service.grant_item(async_session, vault.id, {"item_type": "lunchbox", "name": "Lunchbox"})
