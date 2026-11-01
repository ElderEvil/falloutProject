"""Attention queries filter the complete living roster before pagination."""

import pytest

from app import crud
from app.core.enums import DwellerStatusEnum, RarityEnum
from app.schemas.dweller import DwellerCreate


async def make_dweller(session, vault, data, name, **overrides):
    return await crud.dweller.create(
        session,
        obj_in=DwellerCreate(
            **(
                data
                | {
                    "first_name": name,
                    "last_name": "Test",
                    "vault_id": vault.id,
                    "health": 100,
                    "max_health": 100,
                    "radiation": 0,
                    "happiness": 80,
                    "status": DwellerStatusEnum.IDLE,
                }
                | overrides
            )
        ),
    )


@pytest.mark.asyncio
async def test_low_happiness_filters_before_pagination_and_excludes_dead(async_session, vault, dweller_data):
    await make_dweller(async_session, vault, dweller_data, "Happy", happiness=50)
    low = await make_dweller(async_session, vault, dweller_data, "Low", happiness=49)
    critical = await make_dweller(async_session, vault, dweller_data, "Critical", happiness=10)
    dead = await make_dweller(async_session, vault, dweller_data, "Dead", happiness=10)
    dead.is_dead = True
    dead.status = DwellerStatusEnum.DEAD
    await async_session.commit()
    rows = await crud.dweller.get_multi_by_vault(
        async_session, vault.id, focus="low_happiness", sort_by="happiness", order="asc", skip=1, limit=1
    )
    assert [row.id for row in rows] == [low.id]
    assert critical.id != low.id


@pytest.mark.asyncio
async def test_care_uses_threshold_pet_and_radiation_ceiling_and_excludes_dead(async_session, vault, dweller_data):
    await make_dweller(async_session, vault, dweller_data, "Healthy")
    await make_dweller(async_session, vault, dweller_data, "AtThreshold", health=50)
    below = await make_dweller(async_session, vault, dweller_data, "Below", health=49)
    irradiated = await make_dweller(async_session, vault, dweller_data, "Rad", health=80, radiation=20)
    pet_owner = await make_dweller(async_session, vault, dweller_data, "Pet", health=59)
    pet = await crud.pet.create(
        async_session, {"name": "Dogmeat (Fallout 4)", "rarity": RarityEnum.LEGENDARY, "value": 500}
    )
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=pet_owner.id)
    dead = await make_dweller(async_session, vault, dweller_data, "Dead", health=0)
    dead.is_dead = True
    dead.status = DwellerStatusEnum.DEAD
    await async_session.commit()
    rows = await crud.dweller.get_multi_by_vault(async_session, vault.id, focus="needs_care")
    assert {row.id for row in rows} == {below.id, irradiated.id, pet_owner.id}


@pytest.mark.asyncio
async def test_care_health_sort_uses_effective_health_percentage(async_session, vault, dweller_data):
    low_percent = await make_dweller(async_session, vault, dweller_data, "LowPercent", health=100, max_health=500)
    mid_percent = await make_dweller(async_session, vault, dweller_data, "MidPercent", health=30, max_health=100)
    high_percent = await make_dweller(async_session, vault, dweller_data, "HighPercent", health=24, max_health=50)

    rows = await crud.dweller.get_multi_by_vault(
        async_session,
        vault.id,
        focus="needs_care",
        sort_by="health",
        order="asc",
    )

    assert [row.id for row in rows] == [low_percent.id, mid_percent.id, high_percent.id]


@pytest.mark.asyncio
async def test_care_health_sort_tie_breaks_by_dweller_id(async_session, vault, dweller_data):
    first = await make_dweller(async_session, vault, dweller_data, "TieFirst", health=40, max_health=100)
    second = await make_dweller(async_session, vault, dweller_data, "TieSecond", health=20, max_health=50)

    rows = await crud.dweller.get_multi_by_vault(
        async_session,
        vault.id,
        focus="needs_care",
        sort_by="health",
        order="asc",
    )

    assert [row.id for row in rows] == sorted([first.id, second.id], key=str)
