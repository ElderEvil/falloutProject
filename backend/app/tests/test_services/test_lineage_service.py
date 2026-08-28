"""Tests for the LineageService (family relations & generation computation)."""

import pytest
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.services.lineage_service import lineage_service


async def _make_dweller(
    async_session: AsyncSession,
    vault: Vault,
    *,
    first_name: str = "Test",
    gender: GenderEnum = GenderEnum.MALE,
    parent_1_id: UUID4 | None = None,
    parent_2_id: UUID4 | None = None,
    partner_id: UUID4 | None = None,
) -> Dweller:
    """Create a dweller with explicit lineage links for testing.

    Note: ``DwellerCreate`` does not expose parent/partner links, so they are
    assigned on the persisted ORM object after creation (matching how gameplay
    sets them via the relationship/breeding services).
    """
    dweller_in = DwellerCreate(
        first_name=first_name,
        last_name="Dweller",
        gender=gender,
        rarity=RarityEnum.COMMON,
        age_group=AgeGroupEnum.ADULT,
        level=1,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=1,
        perception=1,
        endurance=1,
        charisma=1,
        intelligence=1,
        agility=1,
        luck=1,
        vault_id=vault.id,
    )
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    if parent_1_id is not None:
        dweller.parent_1_id = parent_1_id
    if parent_2_id is not None:
        dweller.parent_2_id = parent_2_id
    if partner_id is not None:
        dweller.partner_id = partner_id
    if parent_1_id is not None or parent_2_id is not None or partner_id is not None:
        await async_session.commit()
        await async_session.refresh(dweller)
    return dweller


@pytest.mark.asyncio
async def test_lineage_orphan_generation_zero(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """An orphan has generation 0 and no relatives."""
    child = await _make_dweller(async_session, vault, first_name="Orphan")

    lineage = await lineage_service.get_lineage(async_session, child.id)

    assert lineage.dweller_id == child.id
    assert lineage.generation == 0
    assert lineage.parents == []
    assert lineage.children == []
    assert lineage.siblings == []
    assert lineage.partners == []


@pytest.mark.asyncio
async def test_lineage_parents_and_generation(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A child reports both parents and generation 1."""
    parent_a = await _make_dweller(async_session, vault, first_name="ParentA", gender=GenderEnum.MALE)
    parent_b = await _make_dweller(async_session, vault, first_name="ParentB", gender=GenderEnum.FEMALE)
    child = await _make_dweller(
        async_session,
        vault,
        first_name="Child",
        parent_1_id=parent_a.id,
        parent_2_id=parent_b.id,
    )

    lineage = await lineage_service.get_lineage(async_session, child.id)

    assert lineage.generation == 1
    assert {p.id for p in lineage.parents} == {parent_a.id, parent_b.id}
    assert lineage.children == []
    assert lineage.siblings == []
    assert lineage.partners == []


@pytest.mark.asyncio
async def test_lineage_children(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A parent reports all children linked via parent_1_id/parent_2_id."""
    parent = await _make_dweller(async_session, vault, first_name="Parent")
    child_1 = await _make_dweller(async_session, vault, first_name="Child1", parent_1_id=parent.id)
    child_2 = await _make_dweller(async_session, vault, first_name="Child2", parent_1_id=parent.id)

    lineage = await lineage_service.get_lineage(async_session, parent.id)

    assert {c.id for c in lineage.children} == {child_1.id, child_2.id}


@pytest.mark.asyncio
async def test_lineage_siblings(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """Siblings share at least one parent."""
    parent_a = await _make_dweller(async_session, vault, first_name="ParentA")
    parent_b = await _make_dweller(async_session, vault, first_name="ParentB")
    sib_1 = await _make_dweller(
        async_session,
        vault,
        first_name="Sib1",
        parent_1_id=parent_a.id,
        parent_2_id=parent_b.id,
    )
    sib_2 = await _make_dweller(
        async_session,
        vault,
        first_name="Sib2",
        parent_1_id=parent_a.id,
        parent_2_id=parent_b.id,
    )

    lineage = await lineage_service.get_lineage(async_session, sib_1.id)

    assert {s.id for s in lineage.siblings} == {sib_2.id}
    assert lineage.children == []


@pytest.mark.asyncio
async def test_lineage_partner(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A reciprocal partner_id is reported as a partner."""
    d1 = await _make_dweller(async_session, vault, first_name="D1", gender=GenderEnum.MALE)
    d2 = await _make_dweller(async_session, vault, first_name="D2", gender=GenderEnum.FEMALE)
    d1.partner_id = d2.id
    await async_session.commit()

    lineage = await lineage_service.get_lineage(async_session, d1.id)

    assert {p.id for p in lineage.partners} == {d2.id}


@pytest.mark.asyncio
async def test_lineage_partner_context_reports_stage_and_affinity(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A MARRIED partner reports relationship_type, affinity, and live state."""
    from app.models.relationship import Relationship
    from app.schemas.common import RelationshipTypeEnum

    d1 = await _make_dweller(async_session, vault, first_name="D1", gender=GenderEnum.MALE)
    d2 = await _make_dweller(async_session, vault, first_name="D2", gender=GenderEnum.FEMALE)
    d1.partner_id = d2.id
    d2.partner_id = d1.id
    async_session.add(
        Relationship(
            dweller_1_id=d1.id,
            dweller_2_id=d2.id,
            relationship_type=RelationshipTypeEnum.MARRIED,
            affinity=90,
        )
    )
    await async_session.commit()

    lineage = await lineage_service.get_lineage(async_session, d1.id)

    assert len(lineage.partners) == 1
    partner = lineage.partners[0]
    assert partner.id == d2.id
    assert partner.relationship_type == RelationshipTypeEnum.MARRIED
    assert partner.affinity == 90
    assert partner.is_dead is False
    assert partner.age_group == AgeGroupEnum.ADULT


@pytest.mark.asyncio
async def test_lineage_member_reports_dead_state(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A dead parent is reported with is_dead=True so the UI can strike it."""
    parent = await _make_dweller(async_session, vault, first_name="Deceased")
    parent.is_dead = True
    await async_session.commit()
    child = await _make_dweller(async_session, vault, first_name="Child", parent_1_id=parent.id)

    lineage = await lineage_service.get_lineage(async_session, child.id)

    assert len(lineage.parents) == 1
    assert lineage.parents[0].is_dead is True


@pytest.mark.asyncio
async def test_lineage_grandchild_generation(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """Generation walks upward through multiple parent levels."""
    grandparent = await _make_dweller(async_session, vault, first_name="GrandParent")
    parent = await _make_dweller(async_session, vault, first_name="ParentGen", parent_1_id=grandparent.id)
    child = await _make_dweller(async_session, vault, first_name="ChildGen", parent_1_id=parent.id)

    lineage = await lineage_service.get_lineage(async_session, child.id)

    assert lineage.generation == 2


@pytest.mark.asyncio
async def test_lineage_not_found_raises(
    async_session: AsyncSession,
) -> None:
    """A missing dweller raises ResourceNotFoundException."""
    from uuid import uuid4

    from app.utils.exceptions import ResourceNotFoundException

    with pytest.raises(ResourceNotFoundException, match="Unable to find the Dweller"):
        await lineage_service.get_lineage(async_session, uuid4())


@pytest.mark.asyncio
async def test_lineage_excludes_soft_deleted_ancestors(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """Soft-deleted parents are omitted from the lineage and do not count toward
    the generation number."""
    grandparent = await _make_dweller(async_session, vault, first_name="GrandParent")
    deleted_parent = await _make_dweller(async_session, vault, first_name="DeletedParent", parent_1_id=grandparent.id)
    await crud.dweller.delete(db_session=async_session, id=deleted_parent.id, soft=True)
    child = await _make_dweller(async_session, vault, first_name="Child", parent_1_id=deleted_parent.id)

    lineage = await lineage_service.get_lineage(async_session, child.id)

    # The deleted parent is omitted from the results and its own ancestor chain
    # is not followed, so the child reports generation 0 (orphan) with no parents.
    assert lineage.parents == []
    assert lineage.generation == 0


@pytest.mark.asyncio
async def test_lineage_generation_ignores_cycles(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A parent cycle must not create phantom generation levels."""
    dweller_a = await _make_dweller(async_session, vault, first_name="CycleA")
    dweller_b = await _make_dweller(async_session, vault, first_name="CycleB")
    # Set both dwellers as each other's parent to form a 2-node cycle.
    dweller_a.parent_1_id = dweller_b.id
    dweller_b.parent_1_id = dweller_a.id
    await async_session.commit()

    lineage = await lineage_service.get_lineage(async_session, dweller_a.id)

    # The other cycle member counts as one level; the cycle is not followed further.
    assert lineage.generation == 1


@pytest.mark.asyncio
async def test_lineage_generation_ignores_cross_vault_parent(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A parent from another vault does not add a generation level."""
    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreateWithUserID

    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username="other_owner", email="other@example.com", password="secret123"),
    )
    other = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(
            number=999,
            bottle_caps=0,
            happiness=50,
            power=50,
            food=50,
            water=50,
            user_id=user.id,
        ),
    )
    other_parent = await _make_dweller(async_session, other, first_name="OtherParent")
    child = await _make_dweller(async_session, vault, first_name="Child", parent_1_id=other_parent.id)

    lineage = await lineage_service.get_lineage(async_session, child.id)

    assert lineage.parents == []
    assert lineage.generation == 0
