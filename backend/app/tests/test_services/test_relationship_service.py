"""Tests for relationship service logic."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    SPECIAL_STATS,
    AgeGroupEnum,
    GenderEnum,
    NotificationType,
    RarityEnum,
    RelationshipTypeEnum,
)
from app.core.game_config import game_config
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.notification import Notification
from app.models.relationship import Relationship
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.relationship_service import RelationshipService, affinity_change
from app.utils.exceptions import ValidationException


def _stub_dweller(
    *,
    room_id,
    charisma: int = 5,
    race: str = "human",
    level: int = 5,
    happiness: int = 60,
    gender: GenderEnum = GenderEnum.MALE,
    **stat_overrides: int,
) -> SimpleNamespace:
    stats = dict.fromkeys(SPECIAL_STATS, 5)
    stats.update(stat_overrides)
    stats["charisma"] = charisma
    return SimpleNamespace(
        id=uuid4(),
        room_id=room_id,
        level=level,
        happiness=happiness,
        gender=gender,
        age_group=AgeGroupEnum.ADULT,
        visual_attributes={"race": race},
        **stats,
    )


@pytest.mark.asyncio
async def test_vault_relationship_progress_uses_living_quarters_and_charisma(monkeypatch: pytest.MonkeyPatch):
    """Only a co-located pair changes affinity, using the signed race/Charisma pace."""
    room_id = uuid4()
    first = _stub_dweller(room_id=room_id, charisma=10, gender=GenderEnum.FEMALE)
    second = _stub_dweller(room_id=room_id, charisma=10)
    elsewhere = _stub_dweller(room_id=uuid4(), charisma=10)
    outside_living_quarters = _stub_dweller(room_id=room_id, charisma=10)
    growing = Relationship(dweller_1_id=first.id, dweller_2_id=second.id, affinity=50)
    nearly_full = Relationship(dweller_1_id=first.id, dweller_2_id=second.id, affinity=99)
    apart = Relationship(dweller_1_id=first.id, dweller_2_id=elsewhere.id, affinity=50)
    outside = Relationship(dweller_1_id=first.id, dweller_2_id=outside_living_quarters.id, affinity=50)
    full = Relationship(dweller_1_id=first.id, dweller_2_id=second.id, affinity=100)

    monkeypatch.setattr(
        relationship_crud, "get_by_vault", AsyncMock(return_value=[growing, nearly_full, apart, outside, full])
    )
    monkeypatch.setattr(
        crud.dweller,
        "get_living_quarters_dwellers",
        AsyncMock(return_value=[first, second, elsewhere]),
    )
    monkeypatch.setattr(
        crud.dweller,
        "get_by_ids_in_vault",
        AsyncMock(return_value=[first, second, elsewhere, outside_living_quarters]),
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


@pytest.mark.asyncio
async def test_vault_relationship_progress_blocks_partner_when_committed(monkeypatch: pytest.MonkeyPatch):
    room_id = uuid4()
    committed = _stub_dweller(room_id=room_id, gender=GenderEnum.FEMALE)
    spouse = _stub_dweller(room_id=room_id, gender=GenderEnum.MALE)
    romantic_peer = _stub_dweller(room_id=room_id, gender=GenderEnum.MALE)
    free = _stub_dweller(room_id=room_id, gender=GenderEnum.FEMALE)
    free_peer = _stub_dweller(room_id=room_id, gender=GenderEnum.MALE)
    spouse_link = Relationship(
        dweller_1_id=committed.id,
        dweller_2_id=spouse.id,
        relationship_type=RelationshipTypeEnum.PARTNER,
        affinity=90,
    )
    blocked_romance = Relationship(
        dweller_1_id=committed.id,
        dweller_2_id=romantic_peer.id,
        relationship_type=RelationshipTypeEnum.ROMANTIC,
        affinity=75,
    )
    free_romance = Relationship(
        dweller_1_id=free.id,
        dweller_2_id=free_peer.id,
        relationship_type=RelationshipTypeEnum.ROMANTIC,
        affinity=75,
    )
    dwellers = [committed, spouse, romantic_peer, free, free_peer]

    monkeypatch.setattr(
        relationship_crud,
        "get_by_vault",
        AsyncMock(return_value=[spouse_link, blocked_romance, free_romance]),
    )
    monkeypatch.setattr(crud.dweller, "get_living_quarters_dwellers", AsyncMock(return_value=dwellers))
    monkeypatch.setattr(crud.dweller, "get_by_ids_in_vault", AsyncMock(return_value=dwellers))

    progress = await RelationshipService.get_vault_relationships_with_progress(AsyncMock(), uuid4())

    by_id = {item.id: item for item in progress}
    assert by_id[blocked_romance.id].can_make_partners is False
    assert by_id[free_romance.id].can_make_partners is True


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


@pytest_asyncio.fixture(name="dweller_2")
async def dweller_2_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a second dweller for relationship tests."""
    dweller_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "gender": GenderEnum.FEMALE,
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
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="dweller_3")
async def dweller_3_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a third dweller for relationship tests."""
    dweller_data = {
        "first_name": "Bob",
        "last_name": "Brown",
        "gender": GenderEnum.MALE,
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
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
async def test_get_relationship_none_exists(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test getting relationship when none exists."""
    relationship = await RelationshipService.get_relationship(
        async_session,
        dweller.id,
        dweller_2.id,
    )
    assert relationship is None


@pytest.mark.asyncio
async def test_create_or_get_relationship_returns_existing(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that create_or_get_relationship returns existing relationship."""
    # Create first relationship
    rel1 = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    # Try to create again - should return same one
    rel2 = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    assert rel1.id == rel2.id


@pytest.mark.asyncio
async def test_calculate_compatibility_perfect_match(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test compatibility calculation for identical dwellers in same room."""
    from uuid import uuid4

    # Create a shared room_id for both dwellers
    shared_room_id = uuid4()

    dweller_data = {
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

    dweller_in_1 = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller1 = await crud.dweller.create(db_session=async_session, obj_in=dweller_in_1)

    # Manually set room_id (simulating same room)
    dweller1.room_id = shared_room_id
    await async_session.commit()
    await async_session.refresh(dweller1)

    dweller_in_2 = DwellerCreate(**{**dweller_data, "first_name": "Jane"}, vault_id=vault.id)
    dweller2 = await crud.dweller.create(db_session=async_session, obj_in=dweller_in_2)

    # Manually set room_id (simulating same room)
    dweller2.room_id = shared_room_id
    await async_session.commit()
    await async_session.refresh(dweller2)

    compatibility = await RelationshipService.calculate_compatibility(
        async_session,
        dweller1,
        dweller2,
    )

    # Perfect match should be 1.0 (identical stats + same room)
    assert compatibility == 1.0


@pytest.mark.asyncio
async def test_initiate_romance_fails_low_affinity(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that romance fails with low affinity."""
    # Create relationship but don't increase affinity
    await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    # Try to initiate romance - should fail
    with pytest.raises(ValueError, match="Affinity too low"):
        await RelationshipService.initiate_romance(
            async_session,
            dweller.id,
            dweller_2.id,
        )


@pytest.mark.asyncio
async def test_initiate_romance_fails_no_relationship(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that romance fails when no relationship exists."""
    with pytest.raises(ValueError, match="Relationship not found between dwellers"):
        await RelationshipService.initiate_romance(
            async_session,
            dweller.id,
            dweller_2.id,
        )


@pytest.mark.asyncio
async def test_make_partners_fails_low_affinity(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that making partners fails if affinity is too low."""
    # Create relationship but don't increase affinity
    await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    with pytest.raises(ValueError, match="Affinity too low"):
        await RelationshipService.make_partners(
            async_session,
            dweller.id,
            dweller_2.id,
        )


@pytest.mark.asyncio
async def test_make_partners_fails_no_relationship(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that making partners fails when no relationship exists."""
    with pytest.raises(ValueError, match="Relationship not found between dwellers"):
        await RelationshipService.make_partners(
            async_session,
            dweller.id,
            dweller_2.id,
        )


@pytest.mark.asyncio
async def test_break_up_marks_as_ex(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that breaking up marks relationship as EX."""
    # Create partners
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    await RelationshipService.increase_affinity(
        async_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
        amount=game_config.relationship.romance_threshold,
    )

    await RelationshipService.initiate_romance(
        async_session,
        dweller.id,
        dweller_2.id,
    )

    partner_rel = await RelationshipService.make_partners(
        async_session,
        dweller.id,
        dweller_2.id,
    )

    old_affinity = partner_rel.affinity

    # Break up
    await RelationshipService.break_up(
        async_session,
        partner_rel.id,
    )

    # Verify relationship is marked as EX
    await async_session.refresh(partner_rel)

    assert partner_rel.relationship_type == RelationshipTypeEnum.EX
    # Affinity should be reduced by 30
    assert partner_rel.affinity == max(0, old_affinity - 30)


@pytest.mark.asyncio
async def test_break_up_fails_relationship_not_found(
    async_session: AsyncSession,
):
    """Test that breaking up fails if relationship not found."""
    from uuid import uuid4

    fake_id = uuid4()

    with pytest.raises(ValueError, match="Relationship not found"):
        await RelationshipService.break_up(
            async_session,
            fake_id,
        )


async def _make_partners(
    async_session: AsyncSession,
    dweller_1: Dweller,
    dweller_2: Dweller,
) -> Relationship:
    """Create a PARTNER relationship between two dwellers at the romance threshold."""
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller_1.id, dweller_2.id)
    await RelationshipService.increase_affinity(
        async_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
        amount=game_config.relationship.romance_threshold,
    )
    await RelationshipService.initiate_romance(async_session, dweller_1.id, dweller_2.id)
    return await RelationshipService.make_partners(async_session, dweller_1.id, dweller_2.id)


@pytest.mark.asyncio
async def test_marry_fails_low_affinity(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that marrying fails when affinity is below the marriage threshold."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold - 1
    await async_session.commit()

    with pytest.raises(ValidationException, match="Affinity too low"):
        await RelationshipService.marry(async_session, partner_rel.id)


@pytest.mark.asyncio
async def test_marry_fails_relationship_not_found(
    async_session: AsyncSession,
):
    """Test that marrying fails if relationship not found."""
    from uuid import uuid4

    with pytest.raises(ValidationException, match="Relationship not found"):
        await RelationshipService.marry(async_session, uuid4())


@pytest.mark.asyncio
async def test_increase_affinity_auto_marries_partners(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that affinity increase auto-upgrades partners to married at the threshold."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold - 1
    await async_session.commit()

    updated = await RelationshipService.increase_affinity(async_session, dweller.id, dweller_2.id, amount=1)

    assert updated.relationship_type == RelationshipTypeEnum.MARRIED
    assert updated.affinity == game_config.relationship.marriage_threshold


@pytest.mark.asyncio
async def test_decrease_affinity_demotes_romantic_to_friend(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    relationship.relationship_type = RelationshipTypeEnum.ROMANTIC
    relationship.affinity = game_config.relationship.romantic_demotion_threshold + 1
    await async_session.commit()

    updated = await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 2)

    await async_session.refresh(updated)
    assert updated.relationship_type == RelationshipTypeEnum.FRIEND
    assert updated.affinity == game_config.relationship.romantic_demotion_threshold - 1


@pytest.mark.asyncio
async def test_decrease_affinity_demotes_friend_to_acquaintance(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    relationship.relationship_type = RelationshipTypeEnum.FRIEND
    relationship.affinity = game_config.relationship.friend_demotion_threshold
    await async_session.commit()

    updated = await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 1)

    await async_session.refresh(updated)
    assert updated.relationship_type == RelationshipTypeEnum.ACQUAINTANCE


@pytest.mark.asyncio
async def test_decrease_affinity_keeps_committed_partner(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    relationship.relationship_type = RelationshipTypeEnum.PARTNER
    relationship.affinity = 50
    await async_session.commit()

    updated = await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 10)

    await async_session.refresh(updated)
    assert updated.relationship_type == RelationshipTypeEnum.PARTNER
    assert updated.affinity == 40


@pytest.mark.asyncio
async def test_decrease_affinity_floors_at_zero(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    relationship.relationship_type = RelationshipTypeEnum.MARRIED
    relationship.affinity = 5
    await async_session.commit()

    updated = await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 10)

    await async_session.refresh(updated)
    assert updated.affinity == 0
    assert updated.relationship_type == RelationshipTypeEnum.MARRIED


@pytest.mark.asyncio
async def test_decrease_affinity_notifies_demotion(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    relationship.relationship_type = RelationshipTypeEnum.ROMANTIC
    relationship.affinity = game_config.relationship.romantic_demotion_threshold
    await async_session.commit()

    await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 1)

    notifications = (
        (await async_session.execute(select(Notification).where(Notification.meta_data.is_not(None)))).scalars().all()
    )
    demotions = [row for row in notifications if row.meta_data and row.meta_data.get("event") == "relationship_demoted"]
    assert len(demotions) == 1
    assert demotions[0].notification_type == NotificationType.RELATIONSHIP_FORMED
    assert demotions[0].meta_data["to"] == RelationshipTypeEnum.FRIEND.value


@pytest.mark.asyncio
async def test_decrease_affinity_rejects_non_positive_amount(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    with pytest.raises(ValueError, match="must be positive"):
        await RelationshipService.decrease_affinity(async_session, dweller.id, dweller_2.id, 0)


@pytest.mark.asyncio
async def test_marry_applies_bonus_once_under_repeated_attempts(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    monkeypatch: pytest.MonkeyPatch,
):
    """A repeated marry attempt on an already-married relationship is rejected
    without re-applying the one-time happiness bonus or re-sending the
    notification (only the request that wins the PARTNER->MARRIED transition
    applies them)."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold
    await async_session.commit()
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    base_1 = dweller.happiness
    base_2 = dweller_2.happiness

    notify_count = {"n": 0}
    real_notify = RelationshipService._notify_marriage

    async def _counting_notify(db_session, relationship):
        notify_count["n"] += 1
        await real_notify(db_session, relationship)

    monkeypatch.setattr(RelationshipService, "_notify_marriage", _counting_notify)

    married = await RelationshipService.marry(async_session, partner_rel.id)
    assert married.relationship_type == RelationshipTypeEnum.MARRIED

    # Second attempt loses the transition and must not re-apply anything.
    with pytest.raises(ValidationException, match="Only partners can marry"):
        await RelationshipService.marry(async_session, partner_rel.id)

    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    expected = game_config.relationship.partner_happiness_bonus + game_config.relationship.married_happiness_bonus
    assert dweller.happiness == min(100, base_1 + expected)
    assert dweller_2.happiness == min(100, base_2 + expected)
    assert notify_count["n"] == 1


@pytest.mark.asyncio
async def test_marry_records_family_entries(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Marriage narrates into both partners' structured bios."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold
    await async_session.commit()

    await RelationshipService.marry(async_session, partner_rel.id)

    for partner, other in ((dweller, dweller_2), (dweller_2, dweller)):
        refreshed = await crud.dweller.get(async_session, partner.id)
        family = [entry for entry in refreshed.bio_entries if entry["source"] == "family"]
        assert len(family) == 1
        assert other.first_name in family[0]["text"]
        assert family[0]["ref"]["partner_id"] == str(other.id)


@pytest.mark.asyncio
async def test_make_partners_rejects_when_dweller_already_committed(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    dweller_3: Dweller,
):
    """make_partners raises when either dweller is already committed to a third."""
    await _make_partners(async_session, dweller, dweller_2)

    # dweller <-> dweller_3 is ROMANTIC at the romance threshold
    rel = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_3.id)
    rel.affinity = game_config.relationship.romance_threshold
    rel.relationship_type = RelationshipTypeEnum.ROMANTIC
    await async_session.commit()
    await async_session.refresh(rel)

    with pytest.raises(ValidationException, match="already"):
        await RelationshipService.make_partners(async_session, dweller.id, dweller_3.id)

    await async_session.refresh(dweller)
    await async_session.refresh(rel)
    assert dweller.partner_id == dweller_2.id
    assert rel.relationship_type == RelationshipTypeEnum.ROMANTIC


@pytest.mark.asyncio
async def test_marry_rejects_when_dweller_already_committed_to_third(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    dweller_3: Dweller,
):
    """marry rejects a PARTNER relationship when either dweller is already committed to a third."""
    # dweller MARRIED to dweller_2
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold
    await async_session.commit()
    await RelationshipService.marry(async_session, partner_rel.id)

    # Craft a second committed row dweller <-> dweller_3 as PARTNER
    rel = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_3.id)
    rel.affinity = game_config.relationship.marriage_threshold
    rel.relationship_type = RelationshipTypeEnum.PARTNER
    await async_session.commit()
    await async_session.refresh(rel)

    with pytest.raises(ValidationException, match="already"):
        await RelationshipService.marry(async_session, rel.id)

    await async_session.refresh(rel)
    assert rel.relationship_type == RelationshipTypeEnum.PARTNER


@pytest.mark.asyncio
async def test_increase_affinity_does_not_promote_already_committed_dweller(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    dweller_3: Dweller,
):
    """ROMANTIC->PARTNER promotion is skipped when either dweller is already committed."""
    await _make_partners(async_session, dweller, dweller_2)

    rel = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_3.id)
    rel.affinity = game_config.relationship.romance_threshold - 1
    rel.relationship_type = RelationshipTypeEnum.ROMANTIC
    await async_session.commit()
    await async_session.refresh(rel)

    updated = await RelationshipService.increase_affinity(async_session, dweller.id, dweller_3.id, amount=1)

    assert updated.relationship_type == RelationshipTypeEnum.ROMANTIC
    assert updated.affinity == game_config.relationship.romance_threshold
    await async_session.refresh(dweller)
    assert dweller.partner_id == dweller_2.id


@pytest.mark.asyncio
async def test_increase_affinity_does_not_auto_marry_already_committed_dweller(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    dweller_3: Dweller,
):
    """PARTNER->MARRIED auto-transition is skipped when either dweller is already committed to a third."""
    await _make_partners(async_session, dweller, dweller_2)

    # Craft a second committed row dweller <-> dweller_3 as PARTNER
    rel = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_3.id)
    rel.affinity = game_config.relationship.marriage_threshold
    rel.relationship_type = RelationshipTypeEnum.PARTNER
    await async_session.commit()
    await async_session.refresh(rel)

    first = await relationship_crud.get_by_dweller_pair(async_session, dweller.id, dweller_2.id)
    first.affinity = game_config.relationship.marriage_threshold - 1
    await async_session.commit()
    await async_session.refresh(first)

    updated = await RelationshipService.increase_affinity(async_session, dweller.id, dweller_2.id, amount=1)

    assert updated.relationship_type == RelationshipTypeEnum.PARTNER
    assert updated.affinity == game_config.relationship.marriage_threshold


@pytest.mark.asyncio
async def test_break_up_commits_partner_links_and_ex_together(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clearing partner links and marking the pair EX land in one transaction."""
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
    assert partner_rel.relationship_type == RelationshipTypeEnum.EX


@pytest.mark.asyncio
async def test_break_up_failure_preserves_partner_links_and_relationship(
    async_session: AsyncSession,
    db_connection: AsyncConnection,
    dweller: Dweller,
    dweller_2: Dweller,
) -> None:
    """A database failure writing EX cannot leave committed, cleared partner links."""
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
    assert partner_rel.relationship_type == RelationshipTypeEnum.PARTNER
    assert partner_rel.affinity == affinity
