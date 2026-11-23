from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum, RelationshipTypeEnum
from app.models.relationship import Relationship
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.family.lineage_service import lineage_service


async def _make_dweller(
    async_session: AsyncSession,
    vault: Vault,
    first_name: str = "Test",
    gender: GenderEnum = GenderEnum.MALE,
    **links: UUID | None,
):
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name=first_name,
            last_name="Dweller",
            gender=gender,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            vault_id=vault.id,
        ),
    )
    for field, value in links.items():
        setattr(dweller, field, value)
    if links:
        await async_session.commit()
        await async_session.refresh(dweller)
    return dweller


async def test_lineage_siblings(async_session: AsyncSession, vault: Vault) -> None:
    parent_a = await _make_dweller(async_session, vault, "ParentA")
    parent_b = await _make_dweller(async_session, vault, "ParentB")
    sib_1 = await _make_dweller(async_session, vault, "Sib1", parent_1_id=parent_a.id, parent_2_id=parent_b.id)
    sib_2 = await _make_dweller(async_session, vault, "Sib2", parent_1_id=parent_a.id, parent_2_id=parent_b.id)

    lineage = await lineage_service.get_lineage(async_session, sib_1.id)

    assert {s.id for s in lineage.siblings} == {sib_2.id}
    assert lineage.children == []


async def test_lineage_partner_context_reports_stage_and_affinity(async_session: AsyncSession, vault: Vault) -> None:
    d1 = await _make_dweller(async_session, vault, "D1")
    d2 = await _make_dweller(async_session, vault, "D2", gender=GenderEnum.FEMALE)
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


async def test_lineage_excludes_soft_deleted_ancestors(async_session: AsyncSession, vault: Vault) -> None:
    # Soft-deleted parents are omitted from the lineage and do not count toward the generation number.
    grandparent = await _make_dweller(async_session, vault, "GrandParent")
    deleted_parent = await _make_dweller(async_session, vault, "DeletedParent", parent_1_id=grandparent.id)
    await crud.dweller.delete(db_session=async_session, id=deleted_parent.id, soft=True)
    child = await _make_dweller(async_session, vault, "Child", parent_1_id=deleted_parent.id)

    lineage = await lineage_service.get_lineage(async_session, child.id)

    # The deleted parent's own ancestor chain is not followed: the child is an orphan at generation 0.
    assert lineage.parents == []
    assert lineage.generation == 0


async def test_lineage_keeps_parent_slot_order(async_session: AsyncSession, vault: Vault):
    # parent_1 must stay first: the batched parent query has no ORDER BY.
    parent_1 = await _make_dweller(async_session, vault, "Alpha")
    parent_2 = await _make_dweller(async_session, vault, "Beta", gender=GenderEnum.FEMALE)
    child = await _make_dweller(async_session, vault, "Child", parent_1_id=parent_1.id, parent_2_id=parent_2.id)

    lineage = await lineage_service.get_lineage(async_session, child.id)

    assert [member.id for member in lineage.parents] == [parent_1.id, parent_2.id]
