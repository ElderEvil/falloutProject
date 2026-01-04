"""Tests for relationship service logic."""

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.config.game_balance import ROMANCE_THRESHOLD
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum, RelationshipTypeEnum
from app.schemas.dweller import DwellerCreate
from app.services.relationship_service import RelationshipService


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
        relationship,
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
        relationship,
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
        relationship,
        amount=ROMANCE_THRESHOLD,
    )

    assert updated.affinity >= ROMANCE_THRESHOLD
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
        relationship,
        amount=ROMANCE_THRESHOLD,
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
    with pytest.raises(ValueError, match="No relationship exists"):
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
        relationship,
        amount=ROMANCE_THRESHOLD,
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
async def test_make_partners_fails_not_romantic(
    async_session: AsyncSession,
    dweller: Dweller,
    dweller_2: Dweller,
):
    """Test that making partners fails if not in romantic relationship."""
    # Create relationship but don't initiate romance
    await RelationshipService.get_or_create_relationship(async_session, dweller.id, dweller_2.id)

    with pytest.raises(ValueError, match="must be in a romantic relationship"):
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
    with pytest.raises(ValueError, match="No relationship exists"):
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
        relationship,
        amount=ROMANCE_THRESHOLD,
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
        relationship,
        amount=ROMANCE_THRESHOLD,
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
        relationship,
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
