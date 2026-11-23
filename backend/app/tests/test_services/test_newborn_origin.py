from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from sqlmodel import select

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.core.game_config import game_config
from app.models.llm_interaction import LLMInteraction
from app.models.pregnancy import Pregnancy
from app.models.world_location import DwellerLocation
from app.schemas.dweller import DwellerCreate
from app.services.family.breeding_service import BreedingService
from app.utils.time import utcnow


async def _dweller(session, vault, first_name, gender=GenderEnum.MALE, **over):
    data = {"first_name": first_name, "last_name": "Smith", "gender": gender, "rarity": RarityEnum.COMMON} | over
    return await crud.dweller.create(session, obj_in=DwellerCreate(**data, vault_id=vault.id))


@pytest_asyncio.fixture(name="male_dweller")
async def _male_dweller(async_session, vault):
    return await _dweller(async_session, vault, "John")


@pytest_asyncio.fixture(name="female_dweller")
async def _female_dweller(async_session, vault):
    return await _dweller(async_session, vault, "Jane", gender=GenderEnum.FEMALE, rarity=RarityEnum.RARE)


async def _create_due_pregnancy(async_session, mother_id: UUID, father_id: UUID) -> Pregnancy:
    pregnancy = await BreedingService.create_pregnancy(async_session, mother_id, father_id)
    pregnancy.due_at = utcnow() - timedelta(hours=1)
    await async_session.commit()
    return pregnancy


async def test_deliver_baby_link_home_origin_failure_does_not_break_delivery(
    async_session, male_dweller, female_dweller, monkeypatch
) -> None:
    monkeypatch.setattr(game_config.breeding, "twin_chance", 0.0)
    pregnancy = await _create_due_pregnancy(async_session, female_dweller.id, male_dweller.id)

    with patch(
        "app.services.map_service.map_service.link_home_origin",
        AsyncMock(side_effect=RuntimeError("DB connection lost")),
    ):
        children = await BreedingService.deliver_baby(async_session, pregnancy.id)

    assert len(children) == 1
    assert children[0].age_group == AgeGroupEnum.CHILD
    assert (await async_session.execute(select(DwellerLocation))).scalars().all() == []
    assert (await async_session.execute(select(LLMInteraction))).scalars().all() == []
