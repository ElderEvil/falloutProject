from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    SPECIAL_STATS,
    AgeGroupEnum,
    GenderEnum,
    RarityEnum,
    RelationshipTypeEnum,
)
from app.core.game_config import game_config
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.relationship import Relationship
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.bio_service import bio_service
from app.services.relationship_service import RelationshipService, affinity_change, affinity_chemistry
from app.utils.exceptions import ValidationException

CONFIG = game_config.relationship
ROMANTIC, FRIEND, PARTNER, MARRIED = (
    RelationshipTypeEnum.ROMANTIC,
    RelationshipTypeEnum.FRIEND,
    RelationshipTypeEnum.PARTNER,
    RelationshipTypeEnum.MARRIED,
)
ACQUAINTANCE, RIVAL, EX = RelationshipTypeEnum.ACQUAINTANCE, RelationshipTypeEnum.RIVAL, RelationshipTypeEnum.EX


def _stub_dweller(
    *,
    room_id,
    charisma: int = 5,
    race: str = "human",
    state: str | None = None,
    level: int = 5,
    happiness: int = 60,
    gender: GenderEnum = GenderEnum.MALE,
    **stat_overrides: int,
) -> SimpleNamespace:
    stats = dict.fromkeys(SPECIAL_STATS, 5)
    stats.update(stat_overrides)
    stats["charisma"] = charisma
    visual_attributes = {"race": race}
    if state is not None:
        visual_attributes["state_of_being"] = state
    return SimpleNamespace(
        id=uuid4(),
        room_id=room_id,
        level=level,
        happiness=happiness,
        gender=gender,
        age_group=AgeGroupEnum.ADULT,
        visual_attributes=visual_attributes,
        **stats,
    )


def _stub_progress(monkeypatch, relationships, living, *, by_ids=None) -> None:
    monkeypatch.setattr(relationship_crud, "get_by_vault", AsyncMock(return_value=relationships))
    monkeypatch.setattr(crud.dweller, "get_living_quarters_dwellers", AsyncMock(return_value=living))
    monkeypatch.setattr(
        crud.dweller, "get_by_ids_in_vault", AsyncMock(return_value=by_ids if by_ids is not None else living)
    )


async def _seed(session: AsyncSession, first, second, kind=None, affinity=None) -> Relationship:
    relationship = await RelationshipService.get_or_create_relationship(session, first.id, second.id)
    if kind is not None:
        relationship.relationship_type = kind
    if affinity is not None:
        relationship.affinity = affinity
    await session.commit()
    return relationship


async def test_vault_relationship_progress_uses_living_quarters_and_charisma(monkeypatch):
    """Only a co-located pair changes affinity, using the signed race/Charisma pace."""
    room_id = uuid4()
    first = _stub_dweller(room_id=room_id, charisma=10, gender=GenderEnum.FEMALE)
    second = _stub_dweller(room_id=room_id, charisma=10)
    elsewhere = _stub_dweller(room_id=uuid4(), charisma=10)
    outside = _stub_dweller(room_id=room_id, charisma=10)
    growing = Relationship(dweller_1_id=first.id, dweller_2_id=second.id, affinity=50)
    nearly_full = Relationship(dweller_1_id=first.id, dweller_2_id=second.id, affinity=99)
    apart = Relationship(dweller_1_id=first.id, dweller_2_id=elsewhere.id, affinity=50)
    outside_link = Relationship(dweller_1_id=first.id, dweller_2_id=outside.id, affinity=50)
    full = Relationship(dweller_1_id=first.id, dweller_2_id=second.id, affinity=100)
    _stub_progress(
        monkeypatch,
        [growing, nearly_full, apart, outside_link, full],
        [first, second, elsewhere],
        by_ids=[first, second, elsewhere, outside],
    )
    progress = await RelationshipService.get_vault_relationships_with_progress(AsyncMock(), uuid4())
    expected = affinity_change(first, second)
    assert [item.bond_change_per_tick for item in progress] == [expected, 1, 0, 0, 0]
    assert progress[0].bond_change_per_tick == expected
    assert progress[0].same_race is True
    assert progress[0].average_charisma == 10
    assert all(item.can_make_partners for item in progress)
    assert all(item.bond_tick_seconds == game_config.game_loop.tick_interval for item in progress)
    assert all(item.conception_potential == "possible" for item in progress)


async def test_affinity_queries_include_equipped_charisma(async_session, vault, dweller, dweller_2):
    from app.core.enums import RoomTypeEnum
    from app.models.pet import Pet
    from app.options.identity_modifiers import identity_modifiers_for
    from app.schemas.room import RoomCreate
    from app.services.game_loop_service import game_loop_service
    from app.services.relationship_service import effective_charisma
    from app.tests.factory.rooms import create_fake_room
    from app.utils.item_factory import build_outfit

    vault_id = vault.id
    dweller_ids = (dweller.id, dweller_2.id)
    room_data = create_fake_room()
    room_data["name"] = "Living Quarters"
    room_data["category"] = RoomTypeEnum.CAPACITY
    room = await crud.room.create(async_session, RoomCreate(**room_data, vault_id=vault_id))
    for member in (dweller, dweller_2):
        member.room_id = room.id
        async_session.add(member)
    outfit = build_outfit({"name": "Charisma Suit", "charisma": 2}, RarityEnum.COMMON)
    outfit.dweller_id = dweller_ids[0]
    async_session.add(outfit)
    async_session.add(Pet(name="Mr. Pebbles", rarity=RarityEnum.LEGENDARY, dweller_id=dweller_ids[0]))
    await async_session.commit()
    async_session.expire_all()
    living = {m.id: m for m in await crud.dweller.get_living_quarters_dwellers(async_session, vault_id)}
    equipped = living[dweller_ids[0]]
    assert equipped.__dict__.get("outfit") is not None
    assert equipped.__dict__.get("pet") is not None
    expected_charisma = equipped.charisma + identity_modifiers_for(equipped).charisma + 4
    assert effective_charisma(equipped) == expected_charisma
    by_ids = {m.id: m for m in await crud.dweller.get_by_ids_in_vault(async_session, list(dweller_ids), vault_id)}
    assert by_ids[dweller_ids[0]].__dict__.get("outfit") is not None
    assert effective_charisma(by_ids[dweller_ids[0]]) == expected_charisma
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller_ids[0], dweller_ids[1])
    progress = await RelationshipService.get_vault_relationships_with_progress(async_session, vault_id)
    item = next(row for row in progress if row.id == relationship.id)
    expected_average = int((effective_charisma(equipped) + effective_charisma(living[dweller_ids[1]])) / 2 + 0.5)
    assert item.average_charisma == expected_average
    before = relationship.affinity
    await game_loop_service._update_room_relationships(async_session, vault_id)
    await async_session.refresh(relationship)
    assert relationship.affinity == max(0, min(100, before + affinity_change(equipped, living[dweller_ids[1]])))


async def test_vault_relationship_progress_blocks_partner_when_committed(monkeypatch):
    room_id = uuid4()
    committed = _stub_dweller(room_id=room_id, gender=GenderEnum.FEMALE)
    spouse = _stub_dweller(room_id=room_id, gender=GenderEnum.MALE)
    romantic_peer = _stub_dweller(room_id=room_id, gender=GenderEnum.MALE)
    free = _stub_dweller(room_id=room_id, gender=GenderEnum.FEMALE)
    free_peer = _stub_dweller(room_id=room_id, gender=GenderEnum.MALE)
    spouse_link = Relationship(
        dweller_1_id=committed.id,
        dweller_2_id=spouse.id,
        relationship_type=PARTNER,
        affinity=90,
    )
    blocked_romance = Relationship(
        dweller_1_id=committed.id,
        dweller_2_id=romantic_peer.id,
        relationship_type=ROMANTIC,
        affinity=75,
    )
    free_romance = Relationship(
        dweller_1_id=free.id, dweller_2_id=free_peer.id, relationship_type=ROMANTIC, affinity=75
    )
    dwellers = [committed, spouse, romantic_peer, free, free_peer]
    _stub_progress(monkeypatch, [spouse_link, blocked_romance, free_romance], dwellers)
    progress = await RelationshipService.get_vault_relationships_with_progress(AsyncMock(), uuid4())
    by_id = {item.id: item for item in progress}
    assert by_id[blocked_romance.id].can_make_partners is False
    assert by_id[free_romance.id].can_make_partners is True


async def test_vault_relationship_progress_reports_discomfort(monkeypatch):
    room_id = uuid4()
    human = _stub_dweller(
        room_id=room_id,
        charisma=1,
        race="human",
        level=1,
        happiness=0,
        strength=10,
        perception=0,
        endurance=10,
        intelligence=0,
        agility=10,
        luck=0,
    )
    feral = _stub_dweller(
        room_id=room_id,
        charisma=1,
        race="ghoul",
        state="feral",
        level=50,
        happiness=100,
        strength=0,
        perception=10,
        endurance=0,
        intelligence=10,
        agility=0,
        luck=10,
    )
    relationship = Relationship(dweller_1_id=human.id, dweller_2_id=feral.id, affinity=5)
    _stub_progress(monkeypatch, [relationship], [human, feral])
    item = (await RelationshipService.get_vault_relationships_with_progress(AsyncMock(), uuid4()))[0]
    assert item.discomfort_severity == "strong"
    assert item.discomfort_source == "feral"
    # Feral ghouls cannot initiate social bonds, so the discomfort is reported but
    # the pair does not drift while one side is non-reasoning.
    assert item.bond_change_per_tick == 0
    assert item.can_make_partners is False


def test_affinity_change_same_race_beats_cross_race():
    room_id = uuid4()
    human = _stub_dweller(room_id=room_id)
    human_peer = _stub_dweller(room_id=room_id)
    ghoul_peer = _stub_dweller(room_id=room_id, race="ghoul")
    assert affinity_change(human, human_peer) > affinity_change(human, ghoul_peer)


def test_affinity_change_rewards_charisma():
    room_id = uuid4()
    low = _stub_dweller(room_id=room_id, charisma=1)
    low_peer = _stub_dweller(room_id=room_id, charisma=1)
    high = _stub_dweller(room_id=room_id, charisma=10)
    high_peer = _stub_dweller(room_id=room_id, charisma=10)
    assert affinity_change(high, high_peer) > affinity_change(low, low_peer)


def test_affinity_change_drifts_down_for_incompatible_mixed_pair():
    room_id = uuid4()
    first = _stub_dweller(
        room_id=room_id,
        charisma=1,
        race="human",
        level=1,
        happiness=0,
        strength=10,
        perception=0,
        endurance=10,
        intelligence=0,
        agility=10,
        luck=0,
    )
    second = _stub_dweller(
        room_id=room_id,
        charisma=1,
        race="ghoul",
        level=50,
        happiness=100,
        strength=0,
        perception=10,
        endurance=0,
        intelligence=10,
        agility=0,
        luck=10,
    )
    assert affinity_change(first, second) < 0


def test_affinity_chemistry_penalizes_discomfort():
    room_id = uuid4()
    human = _stub_dweller(room_id=room_id)
    human_peer = _stub_dweller(room_id=room_id)
    feral = _stub_dweller(room_id=room_id, race="ghoul", state="feral")
    mutant = _stub_dweller(room_id=room_id, race="super_mutant")
    behemoth = _stub_dweller(room_id=room_id, race="super_mutant", state="behemoth")
    assert affinity_chemistry(human, human_peer) > affinity_chemistry(human, mutant)
    assert affinity_chemistry(human, mutant) > affinity_chemistry(human, behemoth)
    assert affinity_chemistry(human, human_peer) > affinity_chemistry(human, feral)


def test_affinity_change_is_zero_for_non_reasoning_states():
    room_id = uuid4()
    human = _stub_dweller(room_id=room_id)
    feral = _stub_dweller(room_id=room_id, race="ghoul", state="feral")
    behemoth = _stub_dweller(room_id=room_id, race="super_mutant", state="behemoth")
    assert affinity_change(human, feral) == 0
    assert affinity_change(human, behemoth) == 0


def test_feral_discomfort_tips_incompatible_pair_below_drift_threshold():
    room_id = uuid4()
    human = _stub_dweller(
        room_id=room_id,
        charisma=1,
        race="human",
        level=1,
        happiness=0,
        strength=10,
        perception=0,
        endurance=10,
        intelligence=0,
        agility=10,
        luck=0,
    )
    feral = _stub_dweller(
        room_id=room_id,
        charisma=1,
        race="ghoul",
        state="feral",
        level=50,
        happiness=100,
        strength=0,
        perception=10,
        endurance=0,
        intelligence=10,
        agility=0,
        luck=10,
    )
    assert affinity_chemistry(human, feral) < CONFIG.affinity_drift_threshold


DWELLER_STATS = {
    "rarity": RarityEnum.COMMON,
    "age_group": AgeGroupEnum.ADULT,
    "level": 5,
    "experience": 100,
    "max_health": 100,
    "health": 100,
    "radiation": 0,
    "happiness": 60,
    "strength": 4,
    "perception": 5,
    "endurance": 6,
    "charisma": 7,
    "intelligence": 5,
    "agility": 4,
    "luck": 6,
}


async def _create_dweller(async_session, vault, first_name, last_name, gender, **overrides) -> Dweller:
    data = {**DWELLER_STATS, **overrides, "first_name": first_name, "last_name": last_name, "gender": gender}
    return await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))


@pytest_asyncio.fixture(name="dweller_2")
async def dweller_2_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    return await _create_dweller(async_session, vault, "Jane", "Smith", GenderEnum.FEMALE)


@pytest_asyncio.fixture(name="dweller_3")
async def dweller_3_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    return await _create_dweller(async_session, vault, "Bob", "Brown", GenderEnum.MALE)


async def test_get_relationship_none_exists(async_session, dweller, dweller_2):
    assert await RelationshipService.get_relationship(async_session, dweller.id, dweller_2.id) is None


async def test_create_or_get_relationship_returns_existing(async_session, dweller, dweller_2):
    rel1 = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    # Creating again returns the same row.
    rel2 = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    assert rel1.id == rel2.id


async def test_calculate_compatibility_perfect_match(async_session, vault):
    shared_room_id = uuid4()
    stats = {
        "first_name": "John",
        "last_name": "Doe",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 10,
        "experience": 100,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 75,
        "strength": 5,
        "perception": 5,
        "endurance": 5,
        "charisma": 5,
        "intelligence": 5,
        "agility": 5,
        "luck": 5,
    }
    dweller1 = await crud.dweller.create(async_session, obj_in=DwellerCreate(**stats, vault_id=vault.id))
    dweller2 = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**{**stats, "first_name": "Jane"}, vault_id=vault.id)
    )
    for member in (dweller1, dweller2):
        member.room_id = shared_room_id
        async_session.add(member)
    await async_session.commit()
    await async_session.refresh(dweller1)
    await async_session.refresh(dweller2)
    # Identical stats in the same room.
    assert await RelationshipService.calculate_compatibility(async_session, dweller1, dweller2) == 1.0


@pytest.mark.parametrize("method", ["initiate_romance", "make_partners"])
async def test_romance_steps_fail_low_affinity(async_session, dweller, dweller_2, method):
    await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    with pytest.raises(ValueError, match="Affinity too low"):
        await getattr(RelationshipService, method)(async_session, dweller.id, dweller_2.id)


@pytest.mark.parametrize("method", ["initiate_romance", "make_partners"])
async def test_romance_steps_fail_without_relationship(async_session, dweller, dweller_2, method):
    with pytest.raises(ValueError, match="Relationship not found between dwellers"):
        await getattr(RelationshipService, method)(async_session, dweller.id, dweller_2.id)


async def test_initiate_romance_rejects_feral_ghoul(async_session, dweller, dweller_2):
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    await RelationshipService.increase_affinity(
        async_session, relationship.dweller_1_id, relationship.dweller_2_id, amount=CONFIG.romance_threshold
    )
    dweller.visual_attributes = {"race": "ghoul", "state_of_being": "feral"}
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValidationException, match="cannot take purposeful actions"):
        await RelationshipService.initiate_romance(async_session, dweller.id, dweller_2.id)


async def test_break_up_marks_as_ex(async_session, dweller, dweller_2):
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    await RelationshipService.increase_affinity(
        async_session, relationship.dweller_1_id, relationship.dweller_2_id, amount=CONFIG.romance_threshold
    )
    await RelationshipService.initiate_romance(async_session, dweller.id, dweller_2.id)
    partner_rel = await RelationshipService.make_partners(async_session, dweller.id, dweller_2.id)
    old_affinity = partner_rel.affinity
    await RelationshipService.break_up(async_session, partner_rel.id)
    await async_session.refresh(partner_rel)
    assert partner_rel.relationship_type == EX
    # Affinity should be reduced by 30
    assert partner_rel.affinity == max(0, old_affinity - 30)


async def test_break_up_fails_relationship_not_found(async_session):
    with pytest.raises(ValueError, match="Relationship not found"):
        await RelationshipService.break_up(async_session, uuid4())


async def _make_partners(async_session: AsyncSession, dweller_1: Dweller, dweller_2: Dweller) -> Relationship:
    """Create a PARTNER relationship between two dwellers at the romance threshold."""
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller_1.id, dweller_2.id)
    await RelationshipService.increase_affinity(
        async_session, relationship.dweller_1_id, relationship.dweller_2_id, amount=CONFIG.romance_threshold
    )
    await RelationshipService.initiate_romance(async_session, dweller_1.id, dweller_2.id)
    return await RelationshipService.make_partners(async_session, dweller_1.id, dweller_2.id)


async def _married(async_session: AsyncSession, dweller: Dweller, dweller_2: Dweller) -> Relationship:
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = CONFIG.marriage_threshold
    await async_session.commit()
    await RelationshipService.marry(async_session, partner_rel.id)
    return partner_rel


@pytest.mark.parametrize(
    ("feral", "affinity", "match"),
    [
        (True, CONFIG.marriage_threshold, "cannot take purposeful actions"),
        (False, CONFIG.marriage_threshold - 1, "Affinity too low"),
    ],
    ids=["feral_ghoul", "low_affinity"],
)
async def test_marry_rejects_ineligible_partner(async_session, dweller, dweller_2, feral, affinity, match):
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = affinity
    async_session.add(partner_rel)
    if feral:
        dweller.visual_attributes = {"race": "ghoul", "state_of_being": "feral"}
        async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValidationException, match=match):
        await RelationshipService.marry(async_session, partner_rel.id)


async def test_marry_fails_relationship_not_found(async_session):
    with pytest.raises(ValidationException, match="Relationship not found"):
        await RelationshipService.marry(async_session, uuid4())


@pytest.mark.parametrize(
    ("kind", "affinity", "expected_type", "expected_affinity"),
    [
        (PARTNER, CONFIG.marriage_threshold - 1, MARRIED, CONFIG.marriage_threshold),
        (RIVAL, CONFIG.rival_recovery_threshold - 1, ACQUAINTANCE, CONFIG.rival_recovery_threshold),
    ],
    ids=["auto_marry", "rival_recovers"],
)
async def test_increase_affinity_promotes_at_threshold(
    async_session, dweller, dweller_2, kind, affinity, expected_type, expected_affinity
):
    await _seed(async_session, dweller, dweller_2, kind, affinity)
    updated = await RelationshipService.increase_affinity(async_session, dweller.id, dweller_2.id, amount=1)
    await async_session.refresh(updated)
    assert updated.relationship_type == expected_type
    assert updated.affinity == expected_affinity


DECREASE_CASES = [
    (ROMANTIC, CONFIG.romantic_demotion_threshold + 1, 2, FRIEND, CONFIG.romantic_demotion_threshold - 1),
    (FRIEND, CONFIG.friend_demotion_threshold, 1, ACQUAINTANCE, CONFIG.friend_demotion_threshold - 1),
    (PARTNER, 50, 10, PARTNER, 40),
    (MARRIED, 5, 10, MARRIED, 0),
    (PARTNER, 1, 10, PARTNER, 0),
]


@pytest.mark.parametrize(
    ("kind", "affinity", "amount", "expected_type", "expected_affinity"),
    DECREASE_CASES,
    ids=["romantic_to_friend", "friend_to_acquaintance", "partner_kept", "married_floors", "partner_never_rival"],
)
async def test_decrease_affinity_demotes_and_floors(
    async_session, dweller, dweller_2, kind, affinity, amount, expected_type, expected_affinity
):
    await _seed(async_session, dweller, dweller_2, kind, affinity)
    updated = await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, amount)
    await async_session.refresh(updated)
    assert updated.relationship_type == expected_type
    assert updated.affinity == expected_affinity


async def test_decrease_affinity_records_rival_bios(async_session, dweller, dweller_2):
    await _seed(async_session, dweller, dweller_2, ACQUAINTANCE, 0)
    updated = await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 1)
    await async_session.refresh(updated)
    assert updated.relationship_type == RIVAL
    assert updated.affinity == -1
    first = await crud.dweller.get(async_session, dweller.id)
    second = await crud.dweller.get(async_session, dweller_2.id)
    assert any(entry["text"].startswith("Can't stand") for entry in first.bio_entries)
    assert any(entry["text"].startswith("Can't stand") for entry in second.bio_entries)


async def test_rival_bio_failure_rolls_back_relationship_and_bios(async_session, dweller, dweller_2, monkeypatch):
    relationship = await _seed(async_session, dweller, dweller_2, ACQUAINTANCE, 0)
    relationship_id = relationship.id
    first_id, second_id = dweller.id, dweller_2.id
    original = bio_service.add_entry
    calls = {"n": 0}

    def flaky_add_entry(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("bio write failed")
        original(*args, **kwargs)

    monkeypatch.setattr(bio_service, "add_entry", flaky_add_entry)
    with pytest.raises(RuntimeError, match="bio write failed"):
        await RelationshipService.decrease_affinity(async_session, first_id, second_id, 1)
    await async_session.rollback()
    reloaded = await relationship_crud.get(async_session, relationship_id)
    assert reloaded.relationship_type == ACQUAINTANCE
    assert reloaded.affinity == 0
    first = await crud.dweller.get(async_session, first_id)
    second = await crud.dweller.get(async_session, second_id)
    assert not any(entry["text"].startswith("Can't stand") for entry in first.bio_entries)
    assert not any(entry["text"].startswith("Can't stand") for entry in second.bio_entries)


async def test_decrease_affinity_rejects_non_positive_amount(async_session, dweller, dweller_2):
    await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    with pytest.raises(ValueError, match="must be positive"):
        await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 0)


async def test_marry_applies_bonus_once_under_repeated_attempts(async_session, dweller, dweller_2, monkeypatch):
    """A repeated marry attempt on an already-married relationship is rejected without re-applying
    the one-time happiness bonus or re-sending the notification."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = CONFIG.marriage_threshold
    await async_session.commit()
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    base_1, base_2 = dweller.happiness, dweller_2.happiness
    notify_count = {"n": 0}
    real_notify = RelationshipService._notify_marriage

    async def _counting_notify(db_session, relationship):
        notify_count["n"] += 1
        await real_notify(db_session, relationship)

    monkeypatch.setattr(RelationshipService, "_notify_marriage", _counting_notify)
    married = await RelationshipService.marry(async_session, partner_rel.id)
    assert married.relationship_type == MARRIED
    # Second attempt loses the transition and must not re-apply anything.
    with pytest.raises(ValidationException, match="Only partners can marry"):
        await RelationshipService.marry(async_session, partner_rel.id)
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    expected = CONFIG.partner_happiness_bonus + CONFIG.married_happiness_bonus
    assert dweller.happiness == min(100, base_1 + expected)
    assert dweller_2.happiness == min(100, base_2 + expected)
    assert notify_count["n"] == 1


async def test_marry_records_family_entries(async_session, dweller, dweller_2):
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = CONFIG.marriage_threshold
    await async_session.commit()
    await RelationshipService.marry(async_session, partner_rel.id)
    for partner, other in ((dweller, dweller_2), (dweller_2, dweller)):
        refreshed = await crud.dweller.get(async_session, partner.id)
        family = [entry for entry in refreshed.bio_entries if entry["source"] == "family"]
        assert len(family) == 1
        assert other.first_name in family[0]["text"]
        assert family[0]["ref"]["partner_id"] == str(other.id)


async def test_make_partners_rejects_when_dweller_already_committed(async_session, dweller, dweller_2, dweller_3):
    await _make_partners(async_session, dweller, dweller_2)
    # dweller <-> dweller_3 is ROMANTIC at the romance threshold
    rel = await _seed(async_session, dweller, dweller_3, ROMANTIC, CONFIG.romance_threshold)
    await async_session.refresh(rel)
    with pytest.raises(ValidationException, match="already"):
        await RelationshipService.make_partners(async_session, dweller.id, dweller_3.id)
    await async_session.refresh(dweller)
    await async_session.refresh(rel)
    assert dweller.partner_id == dweller_2.id
    assert rel.relationship_type == ROMANTIC


async def test_marry_rejects_when_dweller_already_committed_to_third(async_session, dweller, dweller_2, dweller_3):
    await _married(async_session, dweller, dweller_2)
    # Craft a second committed row dweller <-> dweller_3 as PARTNER
    rel = await _seed(async_session, dweller, dweller_3, PARTNER, CONFIG.marriage_threshold)
    await async_session.refresh(rel)
    with pytest.raises(ValidationException, match="already"):
        await RelationshipService.marry(async_session, rel.id)
    await async_session.refresh(rel)
    assert rel.relationship_type == PARTNER


async def test_increase_affinity_does_not_promote_already_committed_dweller(
    async_session, dweller, dweller_2, dweller_3
):
    await _make_partners(async_session, dweller, dweller_2)
    rel = await _seed(async_session, dweller, dweller_3, ROMANTIC, CONFIG.romance_threshold - 1)
    await async_session.refresh(rel)
    updated = await RelationshipService.increase_affinity(async_session, dweller.id, dweller_3.id, amount=1)
    assert updated.relationship_type == ROMANTIC
    assert updated.affinity == CONFIG.romance_threshold
    await async_session.refresh(dweller)
    assert dweller.partner_id == dweller_2.id


async def test_increase_affinity_does_not_auto_marry_already_committed_dweller(
    async_session, dweller, dweller_2, dweller_3
):
    await _make_partners(async_session, dweller, dweller_2)
    # Craft a second committed row dweller <-> dweller_3 as PARTNER
    rel = await _seed(async_session, dweller, dweller_3, PARTNER, CONFIG.marriage_threshold)
    await async_session.refresh(rel)
    first = await relationship_crud.get_by_dweller_pair(async_session, dweller.id, dweller_2.id)
    first.affinity = CONFIG.marriage_threshold - 1
    await async_session.commit()
    await async_session.refresh(first)
    updated = await RelationshipService.increase_affinity(async_session, dweller.id, dweller_2.id, amount=1)
    assert updated.relationship_type == PARTNER
    assert updated.affinity == CONFIG.marriage_threshold


async def test_break_up_commits_partner_links_and_ex_together(async_session, dweller, dweller_2, monkeypatch):
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    commits = 0
    original_commit = async_session.commit

    async def counting_commit() -> None:
        nonlocal commits
        commits += 1
        await original_commit()

    monkeypatch.setattr(async_session, "commit", counting_commit)
    await RelationshipService.break_up(async_session, partner_rel.id)
    assert commits == 1
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    await async_session.refresh(partner_rel)
    assert dweller.partner_id is None
    assert dweller_2.partner_id is None
    assert partner_rel.relationship_type == EX


async def test_break_up_failure_preserves_partner_links_and_relationship(
    async_session, db_connection, dweller, dweller_2
):
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    first_id, second_id, affinity = dweller.id, dweller_2.id, partner_rel.affinity

    def reject_relationship_write(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("UPDATE relationship "):
            raise RuntimeError("injected relationship write failure")

    event.listen(db_connection.sync_connection, "before_cursor_execute", reject_relationship_write)
    try:
        with pytest.raises(RuntimeError, match="injected relationship write failure"):
            await RelationshipService.break_up(async_session, partner_rel.id)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", reject_relationship_write)
    await async_session.rollback()
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    await async_session.refresh(partner_rel)
    assert dweller.partner_id == second_id
    assert dweller_2.partner_id == first_id
    assert partner_rel.relationship_type == PARTNER
    assert partner_rel.affinity == affinity
