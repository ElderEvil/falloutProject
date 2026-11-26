from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    SPECIAL_STATS,
    AgeGroupEnum,
    GenderEnum,
    NotificationType,
    PregnancyStatusEnum,
    RarityEnum,
    RelationshipTypeEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.game_config import game_config
from app.crud.relationship import relationship_crud
from app.models.notification import Notification
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.family.breeding_service import BreedingService, conception_potential
from app.services.family.family_scenario_service import FamilyScenarioService
from app.services.notification_service import NotificationService, notification_service
from app.tests.factory.dwellers import create_random_common_dweller
from app.tests.utils.query_counter import count_sql_statements
from app.utils.dwellers import elder_birth_threshold
from app.utils.exceptions import NoLivingSpaceError
from app.utils.time import utcnow


@pytest.mark.parametrize(
    ("first_race", "first_age", "second_gender", "expected"),
    [
        ("human", AgeGroupEnum.ADULT, GenderEnum.FEMALE, "possible"),
        (None, AgeGroupEnum.ADULT, GenderEnum.FEMALE, "possible"),
        ("ghoul", AgeGroupEnum.ADULT, GenderEnum.FEMALE, "race"),
        ("human", AgeGroupEnum.TEEN, GenderEnum.FEMALE, "age"),
        ("human", AgeGroupEnum.ADULT, GenderEnum.MALE, "gender"),
    ],
)
def test_conception_potential_matches_pair_rules(first_race, first_age, second_gender, expected):
    first = SimpleNamespace(visual_attributes={"race": first_race}, age_group=first_age, gender=GenderEnum.MALE)
    second = SimpleNamespace(visual_attributes={"race": "human"}, age_group=AgeGroupEnum.ADULT, gender=second_gender)
    assert conception_potential(first, second) == expected


async def _dweller(session, vault, first_name="Kid", last_name="Smith", gender=GenderEnum.MALE, **over):
    data = {"first_name": first_name, "last_name": last_name, "gender": gender, "rarity": RarityEnum.COMMON} | over
    return await crud.dweller.create(session, obj_in=DwellerCreate(**data, vault_id=vault.id))


async def _partner(session, first, second, room=None):
    first.partner_id = second.id
    second.partner_id = first.id
    if room is not None:
        first.room_id = second.room_id = room.id
    await session.commit()


async def _due_pregnancy(session, mother, father):
    pregnancy = await BreedingService.create_pregnancy(session, mother.id, father.id)
    pregnancy.due_at = utcnow() - timedelta(hours=1)
    await session.commit()
    return pregnancy


async def _roll_for_conception(session, vault, value=0.0):
    with patch("random.random", return_value=value):
        return await BreedingService.check_for_conception(session, vault.id)


async def _equip_pet(session: AsyncSession, dweller, name: str) -> None:
    pet = await crud.pet.create(session, {"name": name, "rarity": RarityEnum.LEGENDARY, "value": 500})
    await crud.pet.equip(db_session=session, item_id=pet.id, dweller_id=dweller.id)


@pytest_asyncio.fixture(name="living_quarters")
async def _living_quarters(async_session: AsyncSession, vault: Vault):
    data = {
        "name": "Living Quarters",
        "category": RoomTypeEnum.CAPACITY,
        "ability": SPECIALEnum.CHARISMA,
        "base_cost": 100,
        "incremental_cost": 50,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "capacity": 6,
        "size_min": 1,
        "size_max": 3,
    }
    return await crud.room.create(async_session, obj_in=RoomCreate(**data, vault_id=vault.id))


@pytest_asyncio.fixture(name="male_dweller")
async def _male_dweller(async_session: AsyncSession, vault: Vault):
    return await _dweller(async_session, vault, "John")


@pytest_asyncio.fixture(name="female_dweller")
async def _female_dweller(async_session: AsyncSession, vault: Vault):
    return await _dweller(async_session, vault, "Jane", gender=GenderEnum.FEMALE, rarity=RarityEnum.RARE)


@pytest_asyncio.fixture(name="male_dweller_2")
async def _male_dweller_2(async_session: AsyncSession, vault: Vault):
    return await _dweller(async_session, vault, "Mike", last_name="Rogers")


@pytest_asyncio.fixture(name="female_dweller_2")
async def _female_dweller_2(async_session: AsyncSession, vault: Vault):
    return await _dweller(async_session, vault, "Sarah", last_name="Rogers", gender=GenderEnum.FEMALE)


@pytest_asyncio.fixture(name="couple")
async def _couple(async_session: AsyncSession, living_quarters, male_dweller, female_dweller):
    await _partner(async_session, male_dweller, female_dweller, living_quarters)
    return male_dweller, female_dweller


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("child_mother", "Mother must be an adult"),
        ("child_father", "Father must be an adult"),
        ("male_mother", "Mother must be female"),
        ("female_father", "Father must be male"),
        ("ghoul", "Only humans can conceive"),
    ],
)
async def test_create_pregnancy_rejects_invalid_parents(
    async_session, vault, male_dweller, female_dweller, case, message
):
    mother_id, father_id = female_dweller.id, male_dweller.id
    if case == "child_mother":
        kid = await _dweller(async_session, vault, gender=GenderEnum.FEMALE, age_group=AgeGroupEnum.CHILD)
        mother_id = kid.id
    elif case == "child_father":
        kid = await _dweller(async_session, vault, age_group=AgeGroupEnum.CHILD)
        father_id = kid.id
    elif case == "male_mother":
        mother_id = male_dweller.id
    elif case == "female_father":
        father_id = female_dweller.id
    else:
        ghoul = await _dweller(
            async_session,
            vault,
            first_name="Ghoul",
            gender=GenderEnum.FEMALE,
            visual_attributes={"race": "ghoul", "faction": "vault_dweller"},
        )
        mother_id = ghoul.id
    with pytest.raises(ValueError, match=message):
        await BreedingService.create_pregnancy(async_session, mother_id, father_id)


async def test_check_for_conception_no_partners(async_session, vault, living_quarters):
    assert await _roll_for_conception(async_session, vault) == []


@pytest.mark.parametrize("assignment", ["none", "one"])
async def test_check_for_conception_requires_both_partners_in_living_quarters(
    async_session, vault, living_quarters, male_dweller, female_dweller, assignment
):
    await _partner(async_session, male_dweller, female_dweller)
    if assignment == "one":
        male_dweller.room_id = living_quarters.id
        female_dweller.room_id = None
        await async_session.commit()
    assert await _roll_for_conception(async_session, vault) == []


async def test_check_for_conception_in_living_quarters(async_session, vault, couple):
    male, female = couple
    pregnancies = await _roll_for_conception(async_session, vault)
    assert len(pregnancies) == 1
    assert (pregnancies[0].mother_id, pregnancies[0].father_id) == (female.id, male.id)


async def test_check_for_conception_batches_partner_and_affinity_lookups(
    async_session, vault, living_quarters, male_dweller, female_dweller, male_dweller_2, female_dweller_2
):
    await _partner(async_session, male_dweller, female_dweller, living_quarters)
    await relationship_crud.create_with_defaults(
        async_session,
        male_dweller.id,
        female_dweller.id,
        relationship_type=RelationshipTypeEnum.ACQUAINTANCE,
        affinity=0,
    )
    with patch("random.random", return_value=1.0):
        with count_sql_statements(async_session) as one_couple:
            assert await BreedingService.check_for_conception(async_session, vault.id) == []
        await _partner(async_session, male_dweller_2, female_dweller_2, living_quarters)
        await relationship_crud.create_with_defaults(
            async_session,
            male_dweller_2.id,
            female_dweller_2.id,
            relationship_type=RelationshipTypeEnum.ACQUAINTANCE,
            affinity=0,
        )
        with count_sql_statements(async_session) as two_couples:
            assert await BreedingService.check_for_conception(async_session, vault.id) == []
    assert two_couples.value <= one_couple.value


async def test_check_for_conception_same_sex_couple_never_conceives(
    async_session, vault, living_quarters, male_dweller, male_dweller_2
):
    await _partner(async_session, male_dweller, male_dweller_2, living_quarters)
    await relationship_crud.create_with_defaults(
        async_session,
        male_dweller.id,
        male_dweller_2.id,
        relationship_type=RelationshipTypeEnum.MARRIED,
        affinity=100,
    )
    assert await _roll_for_conception(async_session, vault) == []


@pytest.mark.parametrize(
    ("deliver", "expire_cooldown", "expected"), [(False, False, 0), (True, False, 0), (True, True, 1)]
)
async def test_check_for_conception_respects_mother_state(
    async_session, vault, couple, deliver, expire_cooldown, expected
):
    male, female = couple
    pregnancy = await BreedingService.create_pregnancy(async_session, female.id, male.id)
    if deliver:
        pregnancy.due_at = utcnow() - timedelta(hours=1)
        await async_session.commit()
        await BreedingService.deliver_baby(async_session, pregnancy.id)
    if expire_cooldown:
        pregnancy.updated_at = utcnow() - timedelta(hours=game_config.breeding.birth_cooldown_hours + 1)
        await async_session.commit()
    pregnancies = await _roll_for_conception(async_session, vault)
    assert len(pregnancies) == expected
    if expected:
        assert pregnancies[0].mother_id == female.id


@pytest.mark.parametrize(("population_max", "expected"), [(1, 0), (2, 0), (3, 1)])
async def test_check_for_conception_respects_population_capacity(
    async_session, vault, couple, population_max, expected
):
    male, female = couple
    vault.population_max = population_max
    async_session.add(vault)
    await async_session.commit()
    pregnancies = await _roll_for_conception(async_session, vault)
    assert len(pregnancies) == expected
    if expected:
        assert (pregnancies[0].mother_id, pregnancies[0].father_id) == (female.id, male.id)


async def test_check_for_conception_reserves_for_committed_pregnancies(
    async_session, vault, living_quarters, male_dweller, female_dweller, male_dweller_2, female_dweller_2
):
    await _partner(async_session, male_dweller, female_dweller, living_quarters)
    await BreedingService.create_pregnancy(async_session, female_dweller_2.id, male_dweller_2.id)
    vault.population_max = 5
    async_session.add(vault)
    await async_session.commit()
    assert await _roll_for_conception(async_session, vault) == []


async def test_check_for_conception_single_slot_limits_pairs(
    async_session, vault, living_quarters, male_dweller, female_dweller, male_dweller_2, female_dweller_2
):
    await _partner(async_session, male_dweller, female_dweller, living_quarters)
    await _partner(async_session, male_dweller_2, female_dweller_2, living_quarters)
    vault.population_max = 5
    async_session.add(vault)
    await async_session.commit()
    assert len(await _roll_for_conception(async_session, vault)) == 1


async def test_deliver_baby_not_due_fails(async_session, male_dweller, female_dweller):
    pregnancy = await BreedingService.create_pregnancy(async_session, female_dweller.id, male_dweller.id)
    with pytest.raises(ValueError, match="not due yet"):
        await BreedingService.deliver_baby(async_session, pregnancy.id)


async def test_deliver_baby_random_gender(async_session, couple, monkeypatch):
    male, female = couple
    monkeypatch.setattr(game_config.breeding, "twin_chance", 0.0)
    pregnancy = await _due_pregnancy(async_session, female, male)
    child = (await BreedingService.deliver_baby(async_session, pregnancy.id))[0]
    assert child.gender in [GenderEnum.MALE, GenderEnum.FEMALE]


@pytest.mark.parametrize(("twin", "triplet", "count"), [(1.0, 0.0, 2), (0.0, None, 1), (1.0, 1.0, 3), (0.0, 1.0, 1)])
async def test_deliver_baby_litter_size(async_session, couple, monkeypatch, twin, triplet, count):
    male, female = couple
    monkeypatch.setattr(game_config.breeding, "twin_chance", twin)
    if triplet is not None:
        monkeypatch.setattr(game_config.breeding, "triplet_chance", triplet)
    pregnancy = await _due_pregnancy(async_session, female, male)
    with patch.object(NotificationService, "_deliver", new_callable=AsyncMock) as deliver:
        children = await BreedingService.deliver_baby(async_session, pregnancy.id)
        await notification_service.deliver_deferred_notifications(async_session)
    assert len(children) == count
    assert len({child.id for child in children}) == count
    for child in children:
        assert (child.parent_1_id, child.parent_2_id) == (female.id, male.id)
        assert child.age_group == AgeGroupEnum.CHILD
        assert child.bio is not None
    siblings = await crud.dweller.get_all_in_vault(async_session, female.vault_id)
    assert {child.id for child in children} <= {dweller.id for dweller in siblings}
    assert deliver.await_count == count
    for parent in (female, male):
        refreshed = await crud.dweller.get(async_session, parent.id)
        family = [
            entry
            for entry in refreshed.bio_entries
            if entry["source"] == "family" and entry["ref"]["child_id"] in {str(c.id) for c in children}
        ]
        assert len(family) == count


# Shakespeare grants twin_chance_pct 0.75; the clamp keeps 0.5 + 0.75 from exceeding 1.0.
@pytest.mark.parametrize(
    ("base_chance", "pet_on", "roll", "count"),
    [(0.0, "mother", 0.5, 2), (0.0, "father", 0.5, 1), (0.5, "mother", 0.99, 2), (0.5, "mother", 1.05, 1)],
)
async def test_deliver_baby_twins_chance_pet_math(async_session, couple, monkeypatch, base_chance, pet_on, roll, count):
    male, female = couple
    monkeypatch.setattr(game_config.breeding, "twin_chance", base_chance)
    monkeypatch.setattr(game_config.breeding, "triplet_chance", 0.0)
    await _equip_pet(async_session, female if pet_on == "mother" else male, "Shakespeare")
    pregnancy = await _due_pregnancy(async_session, female, male)
    with patch("random.random", return_value=roll):
        children = await BreedingService.deliver_baby(async_session, pregnancy.id)
    assert len(children) == count


async def test_deliver_baby_caps_twins_to_available_population_slots(async_session, vault, couple, monkeypatch):
    male, female = couple
    monkeypatch.setattr(game_config.breeding, "twin_chance", 1.0)
    monkeypatch.setattr(game_config.breeding, "triplet_chance", 0.0)
    pregnancy = await BreedingService.create_pregnancy(async_session, female.id, male.id)
    pregnancy.due_at = utcnow() - timedelta(hours=1)
    population = await crud.vault.get_population(db_session=async_session, vault_id=vault.id)
    vault.population_max = population + 1
    async_session.add(vault)
    await async_session.commit()
    with patch("random.random", return_value=0.5):
        children = await BreedingService.deliver_baby(async_session, pregnancy.id)
    assert len(children) == 1
    refreshed = await crud.pregnancy.get(async_session, pregnancy.id)
    assert refreshed.status == PregnancyStatusEnum.DELIVERED


async def test_deliver_baby_defers_delivery_when_no_living_space(async_session, vault, couple, monkeypatch):
    male, female = couple
    monkeypatch.setattr(game_config.breeding, "twin_chance", 1.0)
    monkeypatch.setattr(game_config.breeding, "triplet_chance", 0.0)
    pregnancy = await BreedingService.create_pregnancy(async_session, female.id, male.id)
    pregnancy.due_at = utcnow() - timedelta(hours=1)
    population = await crud.vault.get_population(db_session=async_session, vault_id=vault.id)
    vault.population_max = population
    async_session.add(vault)
    await async_session.commit()
    with (
        pytest.raises(NoLivingSpaceError, match="No living space available for a newborn"),
        patch("random.random", return_value=0.5),
    ):
        await BreedingService.deliver_baby(async_session, pregnancy.id)
    newborns = [
        dweller
        for dweller in await crud.dweller.get_all_in_vault(async_session, vault.id)
        if dweller.parent_1_id == female.id and dweller.parent_2_id == male.id
    ]
    assert newborns == []
    refreshed = await crud.pregnancy.get(async_session, pregnancy.id)
    assert refreshed.status == PregnancyStatusEnum.PREGNANT
    assert refreshed.is_due


async def test_deliver_baby_rolls_back_partial_delivery(async_session, vault, couple, monkeypatch):
    male, female = couple
    monkeypatch.setattr(game_config.breeding, "twin_chance", 1.0)
    monkeypatch.setattr(game_config.breeding, "triplet_chance", 0.0)
    pregnancy = await _due_pregnancy(async_session, female, male)
    vault_id, mother_id, father_id, pregnancy_id = vault.id, female.id, male.id, pregnancy.id
    original_create_newborn = BreedingService._create_newborn
    calls = 0

    async def flaky_create_newborn(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("boom")
        return await original_create_newborn(*args, **kwargs)

    monkeypatch.setattr(BreedingService, "_create_newborn", staticmethod(flaky_create_newborn))
    with pytest.raises(RuntimeError, match="boom"), patch("random.random", return_value=0.5):
        await BreedingService.deliver_baby(async_session, pregnancy_id)
    newborns = [
        dweller
        for dweller in await crud.dweller.get_all_in_vault(async_session, vault_id)
        if dweller.parent_1_id == mother_id and dweller.parent_2_id == father_id
    ]
    assert newborns == []
    refreshed = await crud.pregnancy.get(async_session, pregnancy_id)
    assert refreshed.status != PregnancyStatusEnum.DELIVERED


async def test_age_children_progress_through_teen_to_adult(async_session, vault):
    growth = game_config.breeding.child_growth_duration_hours
    child = await _dweller(
        async_session,
        vault,
        "Baby",
        last_name="Test",
        age_group=AgeGroupEnum.CHILD,
        birth_date=utcnow() - timedelta(hours=growth // 2 + 1),
        strength=3,
        charisma=3,
    )
    aged = await BreedingService.age_children(async_session, vault.id)
    assert len(aged) == 1
    assert aged[0].id == child.id
    await async_session.refresh(child)
    assert (child.age_group, child.strength) == (AgeGroupEnum.TEEN, 3)
    assert child.charisma == 3
    child.birth_date = utcnow() - timedelta(hours=growth + 1)
    await async_session.commit()
    aged = await BreedingService.age_children(async_session, vault.id)
    assert len(aged) == 1
    await async_session.refresh(child)
    assert child.age_group == AgeGroupEnum.ADULT
    # Stats are restored only when the teen becomes an adult (3 / 0.5 = 6).
    assert (child.strength, child.charisma) == (6, 6)


async def test_age_children_promotes_only_old_adults_to_elders(async_session, vault):
    stats = dict.fromkeys(SPECIAL_STATS, 3)
    old = await _dweller(
        async_session,
        vault,
        "Old",
        last_name="Timer",
        birth_date=elder_birth_threshold(utcnow()) - timedelta(days=1),
        **stats,
    )
    young = await _dweller(
        async_session, vault, "Young", last_name="Timer", birth_date=utcnow() - timedelta(days=365 * 25), **stats
    )
    aged = await BreedingService.age_children(async_session, vault.id)
    assert [dweller.id for dweller in aged] == [old.id]
    await async_session.refresh(old)
    await async_session.refresh(young)
    assert (old.age_group, young.age_group) == (AgeGroupEnum.ELDER, AgeGroupEnum.ADULT)


async def test_age_children_leaves_ageless_adults_as_adults(async_session, vault):
    # Fallout rule: ghouls, super mutants and synths never senesce into elders.
    ancient_birth = elder_birth_threshold(utcnow()) - timedelta(days=365 * 10)
    for race, faction in [
        ("ghoul", "vault_dweller"),
        ("super_mutant", "super_mutant_tribe"),
        ("synth", "the_institute"),
    ]:
        await _dweller(
            async_session,
            vault,
            race.title().replace("_", ""),
            last_name="Ageless",
            birth_date=ancient_birth,
            visual_attributes={"race": race, "faction": faction},
            **dict.fromkeys(SPECIAL_STATS, 3),
        )
    assert await BreedingService.age_children(async_session, vault.id) == []
    for dweller in await crud.dweller.get_all_in_vault(async_session, vault.id):
        assert dweller.age_group == AgeGroupEnum.ADULT


async def test_deliver_baby_records_family_entries(async_session, couple, monkeypatch):
    male, female = couple
    monkeypatch.setattr(game_config.breeding, "twin_chance", 0.0)
    pregnancy = await _due_pregnancy(async_session, female, male)
    child = (await BreedingService.deliver_baby(async_session, pregnancy.id))[0]
    assert [entry["source"] for entry in child.bio_entries] == ["template"]
    assert child.bio_entries[0]["text"] == child.bio
    for parent in (female, male):
        refreshed = await crud.dweller.get(async_session, parent.id)
        family = [entry for entry in refreshed.bio_entries if entry["source"] == "family"]
        assert len(family) == 1
        assert child.first_name in family[0]["text"]
        assert family[0]["ref"]["child_id"] == str(child.id)


def test_breeding_config_values():
    assert 0.0 <= game_config.breeding.conception_chance_per_tick <= 1.0
    assert game_config.breeding.pregnancy_duration_hours > 0
    assert game_config.breeding.child_growth_duration_hours == 60


async def test_storage_workers_are_not_living_quarters_partners(
    async_session, vault, living_quarters, male_dweller, female_dweller
):
    living_quarters.name = "Storage Room"
    living_quarters.ability = SPECIALEnum.ENDURANCE
    await _partner(async_session, male_dweller, female_dweller, living_quarters)
    assert await _roll_for_conception(async_session, vault) == []
    assert await FamilyScenarioService.find_living_quarters(async_session, vault.id) is None


async def test_auto_family_scenario_selects_living_quarters(
    async_session, vault, living_quarters, male_dweller, female_dweller
):
    scenario = await FamilyScenarioService.setup(async_session, vault.id, count=1)
    assert len(scenario.couples) == 1
    assert {scenario.couples[0].dweller_1.id, scenario.couples[0].dweller_2.id} == {male_dweller.id, female_dweller.id}
    assert male_dweller.room_id == female_dweller.room_id == living_quarters.id


@pytest.mark.parametrize(
    ("category", "ability", "valid"),
    [
        (RoomTypeEnum.CAPACITY, SPECIALEnum.ENDURANCE, False),
        (RoomTypeEnum.PRODUCTION, SPECIALEnum.CHARISMA, False),
        (RoomTypeEnum.CAPACITY, SPECIALEnum.CHARISMA, True),
    ],
)
async def test_explicit_family_room_must_be_living_quarters(
    async_session, vault, living_quarters, male_dweller, female_dweller, category, ability, valid
):
    living_quarters.category = category
    living_quarters.ability = ability
    await async_session.commit()
    kwargs = {"pairs": [(male_dweller.id, female_dweller.id)], "room_id": living_quarters.id}
    if valid:
        result = await FamilyScenarioService.setup(async_session, vault.id, **kwargs)
        assert len(result.couples) == 1
        assert male_dweller.room_id == female_dweller.room_id == living_quarters.id
    else:
        with pytest.raises(ValueError, match="Living Quarters"):
            await FamilyScenarioService.setup(async_session, vault.id, **kwargs)
        assert male_dweller.partner_id is None
        assert female_dweller.partner_id is None
        assert male_dweller.room_id is None
        assert female_dweller.room_id is None
        assert await relationship_crud.get_by_dweller(async_session, male_dweller.id) == []


@pytest.mark.parametrize(
    ("birth_count", "rooms"),
    [(2, ("Medbay", "Response Station")), (3, ("Medbay", "Response Station", "Science Lab"))],
)
async def test_multiple_births_send_one_summary_for_all_crossed_room_thresholds(
    async_session, vault, female_dweller, male_dweller, monkeypatch, birth_count, rooms
):
    while await crud.dweller.count_alive_in_vault(async_session, vault.id) < 13:
        await crud.dweller.create(
            async_session, obj_in=DwellerCreate(**create_random_common_dweller(), vault_id=vault.id)
        )
    monkeypatch.setattr(game_config.breeding, "twin_chance", 1.0)
    monkeypatch.setattr(game_config.breeding, "triplet_chance", float(birth_count == 3))
    pregnancy = await _due_pregnancy(async_session, female_dweller, male_dweller)
    children = await BreedingService.deliver_baby(async_session, pregnancy.id)
    notifications = (
        (await async_session.execute(select(Notification).where(Notification.vault_id == vault.id))).scalars().all()
    )
    births = [n for n in notifications if n.notification_type == NotificationType.BABY_BORN]
    unlocks = [n for n in notifications if n.notification_type == NotificationType.ROOM_UNLOCKED]
    assert len(children) == birth_count
    assert len(births) == birth_count
    assert len(unlocks) == 1
    for room in rooms:
        assert room in unlocks[0].message
