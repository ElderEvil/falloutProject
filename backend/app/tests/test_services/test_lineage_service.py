"""Tests for the LineageService (family relations & generation computation)."""

import pytest
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.services.family.lineage_service import lineage_service


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
