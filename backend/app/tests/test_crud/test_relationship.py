"""CRUD tests for unordered relationship pair lookups."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate


async def _create_dweller(async_session: AsyncSession, vault: Vault, name: str) -> Dweller:
    return await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name=name,
            last_name="Tester",
            gender=GenderEnum.MALE,
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
        ),
    )


@pytest.mark.asyncio
async def test_get_by_pairs_matches_unordered_pairs_and_excludes_others(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    first = await _create_dweller(async_session, vault, "Ada")
    second = await _create_dweller(async_session, vault, "Burt")
    third = await _create_dweller(async_session, vault, "Cara")

    requested = await relationship_crud.create_with_defaults(async_session, first.id, second.id)
    await relationship_crud.create_with_defaults(async_session, first.id, third.id)

    found = await relationship_crud.get_by_pairs(async_session, [(second.id, first.id)])

    assert [relationship.id for relationship in found] == [requested.id]


@pytest.mark.asyncio
async def test_get_by_pairs_orders_duplicate_pairs_consistently_with_single_lookup(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    first = await _create_dweller(async_session, vault, "Dana")
    second = await _create_dweller(async_session, vault, "Eli")

    await relationship_crud.create_with_defaults(async_session, first.id, second.id)
    await relationship_crud.create_with_defaults(async_session, second.id, first.id)

    single = await relationship_crud.get_by_dweller_pair(async_session, first.id, second.id)
    batch = await relationship_crud.get_by_pairs(async_session, [(first.id, second.id)])

    assert single is not None
    assert len(batch) == 2
    assert batch[0].id == single.id
