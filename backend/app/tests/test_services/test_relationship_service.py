"""Tests for relationship service logic."""

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.relationship import Relationship
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum, RelationshipTypeEnum
from app.schemas.dweller import DwellerCreate
from app.services.relationship_service import RelationshipService
from app.utils.exceptions import ValidationException


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
async def test_create_or_get_relationship_creates_new(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test creating a new relationship."""
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    assert relationship is not None
    assert relationship.dweller_1_id == dweller.id
    assert relationship.dweller_2_id == dweller_2.id
    assert relationship.relationship_type == RelationshipTypeEnum.ACQUAINTANCE
    assert relationship.affinity == 0


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
async def test_get_relationship_bidirectional(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that relationship lookup works in both directions."""
    # Create relationship A -> B
    await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    # Should find it when querying B -> A
    relationship = await RelationshipService.get_relationship(
        async_session,
        dweller_2.id,
        dweller.id,
    )

    assert relationship is not None
    assert (relationship.dweller_1_id == dweller.id and relationship.dweller_2_id == dweller_2.id) or (
        relationship.dweller_1_id == dweller_2.id and relationship.dweller_2_id == dweller.id
    )


@pytest.mark.asyncio
async def test_increase_affinity(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test increasing affinity between dwellers."""
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    # Increase affinity
    updated = await RelationshipService.increase_affinity(
        async_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
        amount=10,
    )

    assert updated.affinity == 10
    assert updated.updated_at > relationship.created_at


@pytest.mark.asyncio
async def test_increase_affinity_caps_at_100(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that affinity is capped at 100."""
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    # Increase by large amount
    updated = await RelationshipService.increase_affinity(
        async_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
        amount=150,
    )

    assert updated.affinity == 100


@pytest.mark.asyncio
async def test_increase_affinity_auto_upgrades_to_friend(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that relationship auto-upgrades to friend at threshold."""
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    assert relationship.relationship_type == RelationshipTypeEnum.ACQUAINTANCE

    # Increase affinity past threshold
    updated = await RelationshipService.increase_affinity(
        async_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
        amount=game_config.relationship.romance_threshold,
    )

    assert updated.affinity >= game_config.relationship.romance_threshold
    assert updated.relationship_type == RelationshipTypeEnum.FRIEND


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
async def test_calculate_compatibility_different_rooms(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test compatibility with dwellers in different rooms."""
    # Ensure dwellers are not in the same room
    dweller.room_id = None
    dweller_2.room_id = None
    await async_session.commit()

    compatibility = await RelationshipService.calculate_compatibility(
        async_session,
        dweller,
        dweller_2,
    )

    # Should be less than 1.0 due to proximity penalty
    assert 0.0 <= compatibility < 1.0


@pytest.mark.asyncio
async def test_initiate_romance_success(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test successfully initiating romance."""
    # Create relationship and increase affinity past threshold
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    await RelationshipService.increase_affinity(
        async_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
        amount=game_config.relationship.romance_threshold,
    )

    # Now initiate romance
    romantic_rel = await RelationshipService.initiate_romance(
        async_session,
        dweller.id,
        dweller_2.id,
    )

    assert romantic_rel.relationship_type == RelationshipTypeEnum.ROMANTIC


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
async def test_make_partners_success(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test successfully making dwellers partners."""
    # Create relationship, increase affinity, initiate romance
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

    # Now make partners
    partner_rel = await RelationshipService.make_partners(
        async_session,
        dweller.id,
        dweller_2.id,
    )

    assert partner_rel.relationship_type == RelationshipTypeEnum.PARTNER

    # Verify partner_id is set on both dwellers
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)

    assert dweller.partner_id == dweller_2.id
    assert dweller_2.partner_id == dweller.id


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
async def test_break_up_clears_partner_ids(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that breaking up clears partner_id on both dwellers."""
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

    # Break up
    await RelationshipService.break_up(
        async_session,
        partner_rel.id,
    )

    # Verify partner_id is cleared
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)

    assert dweller.partner_id is None
    assert dweller_2.partner_id is None


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
async def test_break_up_applies_affinity_penalty(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that breaking up applies affinity penalty."""
    # Create romantic relationship
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    await RelationshipService.increase_affinity(
        async_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
        amount=80,
    )

    await RelationshipService.initiate_romance(
        async_session,
        dweller.id,
        dweller_2.id,
    )

    # Break up
    await RelationshipService.break_up(
        async_session,
        relationship.id,
    )

    await async_session.refresh(relationship)

    # Affinity should be reduced by 30 (80 - 30 = 50)
    assert relationship.affinity == 50


@pytest.mark.asyncio
async def test_break_up_affinity_doesnt_go_negative(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that affinity doesn't go below 0 on breakup."""
    # Create relationship with low affinity
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    # Set low affinity manually
    relationship.affinity = 10
    relationship.relationship_type = RelationshipTypeEnum.ROMANTIC
    await async_session.commit()

    # Break up
    await RelationshipService.break_up(
        async_session,
        relationship.id,
    )

    await async_session.refresh(relationship)

    # Affinity should be 0, not negative
    assert relationship.affinity == 0


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
async def test_marry_success(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test successfully marrying partners with sufficient affinity."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold
    await async_session.commit()

    married_rel = await RelationshipService.marry(async_session, partner_rel.id)

    assert married_rel.relationship_type == RelationshipTypeEnum.MARRIED
    await async_session.refresh(married_rel)
    assert married_rel.affinity == game_config.relationship.marriage_threshold

    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    assert dweller.partner_id == dweller_2.id
    assert dweller_2.partner_id == dweller.id


@pytest.mark.asyncio
async def test_marry_applies_happiness_bonus(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that marriage applies the happiness bonus to both dwellers."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold
    await async_session.commit()

    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    base_1 = dweller.happiness
    base_2 = dweller_2.happiness

    await RelationshipService.marry(async_session, partner_rel.id)

    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    expected = game_config.relationship.partner_happiness_bonus + game_config.relationship.married_happiness_bonus
    assert dweller.happiness == min(100, base_1 + expected)
    assert dweller_2.happiness == min(100, base_2 + expected)


@pytest.mark.asyncio
async def test_marry_fails_not_partner(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that marrying fails when relationship is not PARTNER."""
    relationship = await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)
    relationship.relationship_type = RelationshipTypeEnum.ROMANTIC
    relationship.affinity = game_config.relationship.marriage_threshold
    await async_session.commit()

    with pytest.raises(ValidationException, match="Only partners can marry"):
        await RelationshipService.marry(async_session, relationship.id)


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
async def test_increase_affinity_auto_marry_rolls_back_on_bonus_failure(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed marriage transition commits no partial state: the relationship
    stays PARTNER and the happiness bonus is not applied."""
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold - 1
    await async_session.commit()
    rel_id = partner_rel.id
    await async_session.refresh(dweller)
    base_1 = dweller.happiness
    await async_session.refresh(dweller_2)
    base_2 = dweller_2.happiness

    async def _boom(*args, **kwargs):
        raise RuntimeError("bonus failed")

    monkeypatch.setattr(RelationshipService, "_apply_marriage_bonus", _boom)

    with pytest.raises(RuntimeError, match="bonus failed"):
        await RelationshipService.increase_affinity(async_session, dweller.id, dweller_2.id, amount=1)

    await async_session.rollback()
    reloaded = await relationship_crud.get(async_session, rel_id)
    assert reloaded.relationship_type == RelationshipTypeEnum.PARTNER
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    assert dweller.happiness == base_1
    assert dweller_2.happiness == base_2


@pytest.mark.asyncio
async def test_increase_affinity_auto_marry_rolls_back_when_commit_fails(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed transaction commit after bonus preparation persists no partial
    state: the relationship stays PARTNER and the happiness bonus is not applied.

    The relationship type change and both dwellers' marriage bonuses are flushed
    in a single commit, so a persistence failure must roll everything back.
    """
    partner_rel = await _make_partners(async_session, dweller, dweller_2)
    partner_rel.affinity = game_config.relationship.marriage_threshold - 1
    await async_session.commit()
    rel_id = partner_rel.id
    await async_session.refresh(dweller)
    base_1 = dweller.happiness
    await async_session.refresh(dweller_2)
    base_2 = dweller_2.happiness

    original_commit = async_session.commit

    async def _boom_commit():
        raise RuntimeError("persistence failed")

    monkeypatch.setattr(async_session, "commit", _boom_commit)

    with pytest.raises(RuntimeError, match="persistence failed"):
        await RelationshipService.increase_affinity(async_session, dweller.id, dweller_2.id, amount=1)

    monkeypatch.setattr(async_session, "commit", original_commit)
    await async_session.rollback()
    reloaded = await relationship_crud.get(async_session, rel_id)
    assert reloaded.relationship_type == RelationshipTypeEnum.PARTNER
    await async_session.refresh(dweller)
    await async_session.refresh(dweller_2)
    assert dweller.happiness == base_1
    assert dweller_2.happiness == base_2


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
