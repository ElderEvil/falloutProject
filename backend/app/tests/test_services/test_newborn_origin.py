"""Tests for newborn dweller → home-vault origin link on world map."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.llm_interaction import LLMInteraction
from app.models.vault import Vault
from app.models.wasteland_location import (
    DwellerLocation,
    DwellerLocationRelationEnum,
    LocationTypeEnum,
    WastelandLocation,
)
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.services.breeding_service import BreedingService


@pytest_asyncio.fixture(name="male_dweller")
async def male_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    dweller_data = {
        "first_name": "John",
        "last_name": "Smith",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 10,
        "experience": 100,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 75,
        "strength": 6,
        "perception": 5,
        "endurance": 7,
        "charisma": 5,
        "intelligence": 4,
        "agility": 6,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="female_dweller")
async def female_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    dweller_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.RARE,
        "age_group": AgeGroupEnum.ADULT,
        "level": 8,
        "experience": 80,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 80,
        "strength": 4,
        "perception": 7,
        "endurance": 5,
        "charisma": 8,
        "intelligence": 6,
        "agility": 5,
        "luck": 7,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


async def _create_due_pregnancy(
    async_session: AsyncSession,
    mother_id,
    father_id,
):
    pregnancy = await BreedingService.create_pregnancy(async_session, mother_id, father_id)
    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()
    return pregnancy


@pytest.mark.asyncio
async def test_deliver_baby_links_child_to_home_origin(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Happy: deliver_baby → child has ORIGIN DwellerLocation link to HOME_VAULT row."""
    pregnancy = await _create_due_pregnancy(async_session, female_dweller.id, male_dweller.id)

    child = await BreedingService.deliver_baby(async_session, pregnancy.id)

    assert child is not None
    assert child.age_group == AgeGroupEnum.CHILD

    # HOME_VAULT WastelandLocation exists at (50, 50)
    home_stmt = select(WastelandLocation).where(
        WastelandLocation.type == LocationTypeEnum.HOME_VAULT,
        WastelandLocation.vault_id == female_dweller.vault_id,
    )
    home_locations = (await async_session.execute(home_stmt)).scalars().all()
    assert len(home_locations) == 1
    home = home_locations[0]
    assert home.coord_x == 50.0
    assert home.coord_y == 50.0

    # Child has ORIGIN DwellerLocation linking to the home vault row
    link_stmt = select(DwellerLocation).where(
        DwellerLocation.dweller_id == child.id,
        DwellerLocation.location_id == home.id,
        DwellerLocation.relation == DwellerLocationRelationEnum.ORIGIN,
    )
    links = (await async_session.execute(link_stmt)).scalars().all()
    assert len(links) == 1
    assert links[0].dweller_id == child.id
    assert links[0].relation == DwellerLocationRelationEnum.ORIGIN

    # No LLMInteraction rows created
    llm_rows = (await async_session.execute(select(LLMInteraction))).scalars().all()
    assert len(llm_rows) == 0


@pytest.mark.asyncio
async def test_deliver_baby_link_home_origin_failure_does_not_break_delivery(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Failure: link_home_origin raises → delivery still completes, no exception propagates."""
    pregnancy = await _create_due_pregnancy(async_session, female_dweller.id, male_dweller.id)

    with patch(
        "app.services.map_service.map_service.link_home_origin",
        AsyncMock(side_effect=RuntimeError("DB connection lost")),
    ):
        child = await BreedingService.deliver_baby(async_session, pregnancy.id)

    # Delivery still succeeded
    assert child is not None
    assert child.age_group == AgeGroupEnum.CHILD

    # No DwellerLocation rows (link_home_origin failed)
    link_rows = (await async_session.execute(select(DwellerLocation))).scalars().all()
    assert len(link_rows) == 0

    # No LLMInteraction rows created
    llm_rows = (await async_session.execute(select(LLMInteraction))).scalars().all()
    assert len(llm_rows) == 0
